"""蹲 GPU 空位:CLI `mon wait` 与 daemon 侧 App 蹲卡(gpu_watch)共用一套判定。"""
from __future__ import annotations

import json
import shlex
import time
from dataclasses import dataclass
from pathlib import Path

from .config import Config, data_dir
from .events import Event, format_duration
from .notify import Notifier, make_channels
from .sampler import GpuSample
from .store import RunStore

GPU_FREE = "gpu_free"
HEARTBEAT_S = 600  # 等待期间每 10 分钟在终端打一行心跳


@dataclass
class WaitSpec:
    count: int = 1              # 需要几张卡
    free_gb: float | None = None  # 每张卡需要的空闲显存 GB;None = 要整卡空闲
    hold_minutes: float = 3.0   # 条件需持续满足的分钟数(防止别人任务间隙的假空闲)


def card_ok(util_pct: int, used_mb: int, total_mb: int, free_gb: float | None) -> bool:
    """单张卡是否达标。free_gb=None 要求整卡空闲(容忍 Xorg 等残留占用)。"""
    if free_gb is not None:  # 共卡模式:只看空闲显存够不够
        return total_mb - used_mb >= free_gb * 1024
    return used_mb <= max(total_mb * 0.05, 1024) and util_pct <= 10


def qualified(samples: list[GpuSample], free_gb: float | None) -> list[GpuSample]:
    """返回满足条件的卡,空闲显存多的在前。"""
    good = [s for s in samples
            if card_ok(s.util_pct, s.mem_used_mb, s.mem_total_mb, free_gb)]
    good.sort(key=lambda s: s.mem_used_mb - s.mem_total_mb)
    return good


class HoldTracker:
    """跟踪条件连续满足的时长,满 hold 秒返回 True。"""

    def __init__(self, hold_seconds: float, clock=time.time) -> None:
        self.hold = hold_seconds
        self.clock = clock
        self.since: float | None = None

    def feed(self, ok: bool) -> bool:
        if not ok:
            self.since = None
            return False
        if self.since is None:
            self.since = self.clock()
        return self.clock() - self.since >= self.hold


class GpuWaiter:
    def __init__(self, spec: WaitSpec, command: list[str] | None = None,
                 name: str | None = None, store: RunStore | None = None,
                 config: Config | None = None, sample_fn=None,
                 clock=time.time, sleep=time.sleep) -> None:
        from . import sampler
        self.spec = spec
        self.command = command or []
        self.name = name
        self.config = config or Config.load()
        self.store = store or RunStore()
        self.sample_fn = sample_fn or sampler.sample_gpus
        self.clock = clock
        self.sleep = sleep

    def _fmt(self, cards: list[GpuSample]) -> str:
        return " · ".join(f"卡{s.index} 空闲{(s.mem_total_mb - s.mem_used_mb) / 1024:.0f}GB"
                          for s in cards)

    def _announce(self) -> None:
        req = (f"每张空闲显存 ≥{self.spec.free_gb:g}GB" if self.spec.free_gb is not None
               else "整卡空闲")
        hold = (f",持续满足 {self.spec.hold_minutes:g} 分钟后"
                if self.spec.hold_minutes else ",满足即")
        act = f"自动启动:{shlex.join(self.command)}" if self.command else "通知手机"
        print(f"[mon wait] 蹲 {self.spec.count} 张 GPU({req}){hold}{act}", flush=True)
        if not self.config.channels and not self.config.relay.get("device_token"):
            print("[mon wait] ⚠️ 未配置通知通道也未配对手机(mon init / mon pair),"
                  "等到后只有终端提示", flush=True)

    def execute(self) -> int:
        self._announce()
        tracker = HoldTracker(self.spec.hold_minutes * 60, clock=self.clock)
        started = self.clock()
        last_beat = started
        prev_ok: bool | None = None
        while True:
            good = qualified(self.sample_fn(), self.spec.free_gb)
            ok = len(good) >= self.spec.count
            if tracker.feed(ok):
                return self._fire(good[:self.spec.count])
            now = self.clock()
            if ok != prev_ok:  # 只在状态翻转时打印,避免刷屏
                prev_ok = ok
                if ok:
                    print(f"[mon wait] 条件满足({self._fmt(good)}),"
                          f"开始计时 {self.spec.hold_minutes:g} 分钟…", flush=True)
                else:
                    print(f"[mon wait] 条件中断(当前 {len(good)}/{self.spec.count} 张满足),"
                          "继续等待", flush=True)
            if now - last_beat >= HEARTBEAT_S:
                last_beat = now
                print(f"[mon wait] 仍在等待({len(good)}/{self.spec.count} 张满足,"
                      f"已等 {format_duration(now - started)})", flush=True)
            self.sleep(self.config.sample_interval_s)

    def _fire(self, cards: list[GpuSample]) -> int:
        desc = self._fmt(cards)
        held = (f"(已持续满足 {self.spec.hold_minutes:g} 分钟)"
                if self.spec.hold_minutes else "")
        if self.command:
            ev = Event(GPU_FREE, "info", "🚀 GPU 就绪,预约任务已启动",
                       f"{desc}\n开始执行:{shlex.join(self.command)}")
        else:  # 纯蹲卡:时效性强,按 critical 推送(抢卡要快)
            ev = Event(GPU_FREE, "critical",
                       f"🎉 GPU 空位来了:{len(cards)} 张卡就绪", f"{desc}{held}")
        self.store.record_event(None, GPU_FREE, self.clock(),
                                payload=json.dumps(ev.to_dict(), ensure_ascii=False))
        notifier = Notifier(self.store, make_channels(self.config))
        notifier.notify(ev)
        notifier.flush(timeout=15)
        notifier.stop()
        print(f"[mon wait] 🎉 等到啦:{desc}", flush=True)
        if not self.command:
            return 0
        import os
        idx = ",".join(str(s.index) for s in sorted(cards, key=lambda s: s.index))
        # PCI_BUS_ID 让 CUDA 编号与 nvidia-smi/NVML 一致,再圈定选中的卡
        os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        os.environ["CUDA_VISIBLE_DEVICES"] = idx
        print(f"[mon wait] 启动预约任务(CUDA_VISIBLE_DEVICES={idx}):"
              f"{shlex.join(self.command)}", flush=True)
        from .runner import RunWrapper
        return RunWrapper(self.command, name=self.name, store=self.store,
                          config=self.config, gpu_indices=idx).execute()


# ---------- daemon 侧蹲卡(手机 App 下发,配置落盘,随心跳评估) ----------

def watch_path() -> Path:
    return data_dir() / "gpu_watch.json"


def load_watch() -> dict | None:
    try:
        w = json.loads(watch_path().read_text(encoding="utf-8"))
        return w if w.get("cards") else None
    except Exception:
        return None


def save_watch(watch: dict) -> None:
    watch_path().write_text(json.dumps(watch, ensure_ascii=False), encoding="utf-8")


def clear_watch() -> None:
    try:
        watch_path().unlink()
    except FileNotFoundError:
        pass


def set_watch(args: dict) -> dict:
    """校验 App 下发的蹲卡配置并落盘。cards: {"卡号": 需要的空闲GB 或 null(整卡)}"""
    try:
        cards = {str(int(k)): (None if v is None else max(0.0, float(v)))
                 for k, v in (args.get("cards") or {}).items()}
    except (TypeError, ValueError):
        return {"ok": False, "error": "cards 格式错误"}
    if not cards:
        return {"ok": False, "error": "至少选择一张卡"}
    command = str(args.get("command") or "").strip()
    if command and not Config.load().enable_terminal:
        return {"ok": False,
                "error": "服务器已禁用远程执行(enable_terminal=false),只能蹲卡通知"}
    hold = args.get("hold_minutes", 3)
    save_watch({"cards": cards,
                "hold_minutes": max(0.0, float(3 if hold is None else hold)),
                "command": command,
                "name": str(args.get("name") or "").strip()[:60],
                "created_at": time.time()})
    return {"ok": True}


class GpuWatchManager:
    """daemon 持有:每次心跳喂入 GPU 采样,评估蹲卡条件,满足即通知/预约执行。"""

    def __init__(self, store: RunStore, config: Config, clock=time.time) -> None:
        self.store = store
        self.config = config
        self.clock = clock
        self._sig: str | None = None  # 当前 watch 的内容签名,变了就重置计时
        self._tracker: HoldTracker | None = None

    def poll(self, gpus: list[dict]) -> dict | None:
        """gpus 为心跳里的采样([{index,util,mem_used,mem_total},…])。
        返回给 App 展示的蹲卡状态;没有蹲卡任务时返回 None。"""
        watch = load_watch()
        if watch is None:
            self._sig = None
            return None
        sig = json.dumps(watch, sort_keys=True)
        if sig != self._sig:  # 新建/修改的蹲卡任务:重新计时
            self._sig = sig
            self._tracker = HoldTracker(
                float(watch.get("hold_minutes", 3)) * 60, clock=self.clock)
        by_idx = {int(g["index"]): g for g in gpus}
        states, all_ok = [], True
        for k, need in watch["cards"].items():
            g = by_idx.get(int(k))
            ok = g is not None and card_ok(
                int(g["util"]), int(g["mem_used"]), int(g["mem_total"]),
                None if need is None else float(need))
            states.append({"index": int(k), "ok": ok,
                           "free_mb": (g["mem_total"] - g["mem_used"]) if g else 0})
            all_ok = all_ok and ok
        fired = self._tracker.feed(all_ok)
        status = {**watch, "ok": all_ok, "since": self._tracker.since,
                  "card_states": sorted(states, key=lambda s: s["index"])}
        if fired:
            self._fire(watch, status["card_states"])
            clear_watch()
            self._sig = None
            status["fired"] = True
        return status

    def _fire(self, watch: dict, states: list[dict]) -> None:
        desc = " · ".join(f"卡{s['index']} 空闲{s['free_mb'] / 1024:.0f}GB"
                          for s in states)
        command = (watch.get("command") or "").strip()
        idx = ",".join(str(s["index"]) for s in states)
        if command:
            if not self.config.enable_terminal:  # set 时已拦,这里兜底(配置可能中途改)
                ev = Event(GPU_FREE, "critical", "🎉 蹲到卡了(预约未执行)",
                           f"{desc}\n服务器已禁用远程执行(enable_terminal=false)")
            elif self._launch(command, watch.get("name") or "", idx):
                ev = Event(GPU_FREE, "info", "🚀 GPU 就绪,预约任务已启动",
                           f"{desc}\n开始执行:{command}")
            else:
                ev = Event(GPU_FREE, "critical", "🎉 蹲到卡了(预约启动失败)",
                           f"{desc}\n命令未能启动,请上服务器手动处理")
        else:
            hold = float(watch.get("hold_minutes", 3))
            ev = Event(GPU_FREE, "critical",
                       f"🎉 蹲到卡了:选中的 {len(states)} 张全部就绪",
                       desc + (f"(已持续满足 {hold:g} 分钟)" if hold else ""))
        self.store.record_event(None, GPU_FREE, self.clock(),
                                payload=json.dumps(ev.to_dict(), ensure_ascii=False))
        notifier = Notifier(self.store, make_channels(self.config))
        notifier.notify(ev)
        notifier.flush(timeout=15)
        notifier.stop()

    def _launch(self, command: str, name: str, idx: str) -> bool:
        import os
        import subprocess
        import sys
        env = dict(os.environ)
        env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"  # 让 CUDA 编号与 nvidia-smi 一致
        env["CUDA_VISIBLE_DEVICES"] = idx
        argv = [sys.executable, "-m", "runmon", "run", "--name", name or "预约任务",
                "--gpu", idx, "--", "bash", "-lc", command]
        try:
            subprocess.Popen(argv, cwd=os.path.expanduser("~"), env=env,
                             start_new_session=True, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False
