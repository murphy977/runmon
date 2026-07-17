"""mon attach:接管已在 tmux 里跑的任务(pipe-pane 抓输出,PID 树关联 GPU)。
限制:拿不到退出码(pane 前台进程消失即视为结束,按错误输出判成败)。"""
from __future__ import annotations

import os
import subprocess
import threading
import time

from . import sampler
from .config import Config, data_dir
from .events import ERROR_PATTERN, EventEngine
from .notify import Notifier, make_channels
from .progress import ProgressParser
from .store import RunStore


def _tmux(*args: str) -> str:
    return subprocess.run(["tmux", *args], capture_output=True, text=True,
                          check=True).stdout.strip()


class TmuxAttach:
    def __init__(self, target: str, name: str | None = None,
                 store: RunStore | None = None, config: Config | None = None,
                 notifier: Notifier | None = None) -> None:
        self.target = target
        self.config = config or Config.load()
        self.store = store or RunStore()
        self.notifier = notifier or Notifier(self.store, make_channels(self.config))
        self.engine = EventEngine(self.store, self.config)
        self.parser = ProgressParser()
        self.name = name or f"tmux:{target}"
        self.run = None
        self._had_error = False
        self._last_progress_write = 0.0

    def execute(self) -> int:
        info = _tmux("display", "-p", "-t", self.target,
                     "#{pane_id} #{pane_pid} #{pane_current_command}")
        pane_id, pane_pid, pane_cmd = info.split(" ", 2)
        self.pane_pid = int(pane_pid)
        self.run = self.store.create_run(
            name=self.name, command=f"tmux attach {self.target} ({pane_cmd})",
            cwd="", log_path="")
        log_path = data_dir() / "logs" / f"{self.run.id}.log"
        self.store.update_run(self.run.id, log_path=str(log_path),
                              pid=self.pane_pid, status="running")
        _tmux("pipe-pane", "-t", pane_id, "-o", f"cat >> {log_path}")
        log_path.touch()
        self.notifier.start()
        print(f"[mon] 已接管 {self.target}(pane {pane_id}),Ctrl+C 停止监控(不影响任务)")

        stop = threading.Event()
        mon = threading.Thread(target=self._monitor, args=(stop,), daemon=True)
        mon.start()
        pos = 0
        try:
            while True:
                # 读取 pipe-pane 增量
                with open(log_path, "rb") as f:
                    f.seek(pos)
                    chunk = f.read()
                    pos = f.tell()
                if chunk:
                    self._ingest(chunk.decode("utf-8", errors="replace"))
                # pane 前台进程结束(回到 shell)或 pane 消失 → 任务结束
                try:
                    cur = _tmux("display", "-p", "-t", pane_id,
                                "#{pane_current_command}")
                    if cur != pane_cmd:
                        break
                except subprocess.CalledProcessError:
                    break
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\n[mon] 停止监控(任务继续在 tmux 里跑)")
            self.store.update_run(self.run.id, status="stopped",
                                  ended_at=time.time())
            return 0
        finally:
            stop.set()
            mon.join(timeout=2)
            try:
                _tmux("pipe-pane", "-t", pane_id)  # 关闭管道
            except Exception:
                pass

        status = "failed" if self._had_error else "completed"
        self.store.update_run(self.run.id, status=status,
                              exit_code=1 if self._had_error else 0,
                              ended_at=time.time(), eta_seconds=None)
        ev = self.engine.on_exit(self.store.get_run(self.run.id),
                                 1 if self._had_error else 0)
        self.notifier.notify(ev)
        self.notifier.flush(timeout=15)
        self.notifier.stop()
        return 0

    def _ingest(self, text: str) -> None:
        try:
            self.store.append_output(self.run.id, text,
                                     self.config.ring_buffer_kb * 1024)
            if ev := self.engine.on_output(self.run, text):
                self._had_error = ev.type == ERROR_PATTERN or self._had_error
                self.notifier.notify(ev)
            if self.parser.feed(text) and time.time() - self._last_progress_write > 1.0:
                st = self.parser.state
                self.store.update_run(self.run.id, progress=st.percent,
                                      eta_seconds=st.eta_seconds, last_loss=st.loss)
                self._last_progress_write = time.time()
        except Exception:
            pass

    def _monitor(self, stop: threading.Event) -> None:
        history: list[tuple[float, float]] = []
        while not stop.wait(self.config.sample_interval_s):
            try:
                now = time.time()
                samples = sampler.sample_gpus()
                util = sampler.util_for_pids(
                    samples, sampler.process_tree(self.pane_pid))
                run = self.store.get_run(self.run.id)
                if run is None:
                    continue
                pending = []
                if util is not None:
                    history.append((now, util))
                    cutoff = now - (self.config.hang_gpu_minutes + 5) * 60
                    history[:] = [(t, u) for t, u in history if t >= cutoff]
                    if ev := self.engine.check_gpu_hang(run, history):
                        pending.append(ev)
                if ev := self.engine.check_log_silence(run):
                    pending.append(ev)
                if ev := self.engine.check_disk(sampler.disk_usage()):
                    pending.append(ev)
                for ev in pending:
                    self.notifier.notify(ev)
            except Exception:
                pass
