"""mon daemon:与 relay 的 WSS 长连,加密同步任务状态,接收白名单指令。"""
from __future__ import annotations

import asyncio
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

import psutil

from . import sampler
from .config import Config
from .crypto import decrypt, encrypt, key_from_b64
from .store import RunStore

TAIL_WINDOW = 8192          # 同步给手机的输出尾窗(字符)
SYNC_INTERVAL = 1.0
HEARTBEAT_INTERVAL = 10.0
PERMANENT_MUTE = 4102444800.0   # 2100-01-01,视作"永久"


def run_snapshot(store: RunStore) -> list[dict]:
    return [{"id": r.id, "name": r.name, "status": r.status, "progress": r.progress,
             "eta_seconds": r.eta_seconds, "last_loss": r.last_loss,
             "started_at": r.started_at, "ended_at": r.ended_at,
             "exit_code": r.exit_code, "muted_until": r.muted_until,
             "shutdown_after": r.shutdown_after}
            for r in store.list_runs(limit=50)]


class SyncState:
    def __init__(self) -> None:
        self.last_snapshot_json = ""
        self.tail_lengths: dict[str, int] = {}
        self.last_event_id = 0


def compute_sync_messages(store: RunStore, state: SyncState, key: bytes) -> list[dict]:
    """diff 本地 store,产出需要发给 relay 的消息(纯函数,可单测)。"""
    msgs: list[dict] = []
    snap = run_snapshot(store)
    snap_json = json.dumps(snap, sort_keys=True)
    if snap_json != state.last_snapshot_json:
        state.last_snapshot_json = snap_json
        msgs.append({"t": "snapshot", "enc": encrypt({"runs": snap}, key)})
    for r in store.list_runs(limit=50):
        if state.tail_lengths.get(r.id) != r.output_length:
            state.tail_lengths[r.id] = r.output_length
            msgs.append({"t": "tail", "run": r.id,
                         "enc": encrypt({"run_id": r.id, "tail": r.output_tail[-TAIL_WINDOW:],
                                         "len": r.output_length}, key)})
    for row in store.events_since(state.last_event_id):
        state.last_event_id = row["id"]
        if row["payload"]:
            msgs.append({"t": "event", "enc": encrypt(json.loads(row["payload"]), key)})
    return msgs


def heartbeat_payload() -> dict:
    gpus = [{"index": s.index, "util": s.util_pct, "mem_used": s.mem_used_mb,
             "mem_total": s.mem_total_mb, "temp": s.temp_c}
            for s in sampler.sample_gpus()]
    return {"gpus": gpus, "cpu": psutil.cpu_percent(interval=None),
            "mem": psutil.virtual_memory().percent,
            "disk": [{"mount": m, "used_pct": p} for m, p in sampler.disk_usage()],
            "ts": time.time()}


def _tail_file(path: str, lines: int) -> str:
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - 256 * 1024))
        data = f.read().decode("utf-8", errors="replace")
    return "\n".join(data.replace("\r", "\n").splitlines()[-lines:])


def _rerun(run) -> dict:
    env = dict(os.environ)
    try:
        env_path = Path(run.log_path).parent / f"{run.id}.env.json"
        if env_path.exists():
            env = json.loads(env_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    cmd = [sys.executable, "-m", "runmon", "run",
           "--name", f"{run.name}-rerun", "--"] + shlex.split(run.command)
    subprocess.Popen(cmd, cwd=run.cwd or None, env=env, start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL)
    return {"ok": True, "op": "rerun", "run_id": run.id}


def handle_command(store: RunStore, cmd: dict) -> dict:
    """白名单指令执行。指令是语义枚举,app 无法下发任意 shell。"""
    op = cmd.get("op")
    run_id = str(cmd.get("run_id", ""))
    args = cmd.get("args") or {}
    run = store.resolve_run(run_id) if run_id else None
    if op == "stop":
        from .cli import stop_run
        ok = stop_run(store, run_id)
        return {"ok": ok, "op": op, "run_id": run_id}
    if op == "tail":
        if run is None or not run.log_path or not os.path.exists(run.log_path):
            return {"ok": False, "op": op, "error": "log not found"}
        text = _tail_file(run.log_path, int(args.get("lines", 100)))
        return {"ok": True, "op": op, "run_id": run.id, "tail": text}
    if op == "mute":
        if run is None:
            return {"ok": False, "op": op, "error": "run not found"}
        hours = float(args.get("hours", 8))
        until = time.time() + hours * 3600 if hours > 0 else PERMANENT_MUTE
        store.update_run(run.id, muted_until=until)
        return {"ok": True, "op": op, "run_id": run.id, "muted_until": until}
    if op == "shutdown_after":
        if run is None:
            return {"ok": False, "op": op, "error": "run not found"}
        enabled = 1 if args.get("enabled") else 0
        store.update_run(run.id, shutdown_after=enabled)
        return {"ok": True, "op": op, "run_id": run.id, "shutdown_after": enabled}
    if op == "rerun":
        if run is None:
            return {"ok": False, "op": op, "error": "run not found"}
        return _rerun(run)
    return {"ok": False, "error": f"unknown op: {op}"}


class Daemon:
    def __init__(self, store: RunStore | None = None, config: Config | None = None) -> None:
        self.config = config or Config.load()
        relay = self.config.relay
        if not (relay.get("url") and relay.get("device_token") and relay.get("key")):
            raise SystemExit("relay 未配置。先运行:mon pair --relay <URL>")
        self.store = store or RunStore()
        self.key = key_from_b64(relay["key"])
        self.url = relay["url"].rstrip("/")
        self.device_id = relay["device_id"]
        self.token = relay["device_token"]

    def ws_url(self) -> str:
        u = self.url.replace("https://", "wss://").replace("http://", "ws://")
        return u + "/ws/agent"

    async def run_forever(self) -> None:
        import websockets
        backoff = 1.0
        while True:
            try:
                # proxy=None:绕过系统代理直连 relay——代理常会剥掉 WebSocket 升级头导致 404
                async with websockets.connect(
                        self.ws_url(), proxy=None,
                        additional_headers={"Authorization": f"Bearer {self.token}",
                                            "X-Device": self.device_id,
                                            "User-Agent": "runmon/0.1.0"}) as ws:
                    backoff = 1.0
                    print(f"[mon daemon] 已连接 {self.url}")
                    await asyncio.gather(self._reader(ws), self._sync_loop(ws))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"[mon daemon] 连接断开:{exc};{backoff:.0f}s 后重连")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    async def _reader(self, ws) -> None:
        async for raw in ws:
            try:
                msg = json.loads(raw)
                if msg.get("t") != "cmd":
                    continue
                cmd = decrypt(msg["enc"], self.key)
                result = await asyncio.to_thread(handle_command, self.store, cmd)
                await ws.send(json.dumps({"t": "cmd_result", "cmd_id": msg.get("cmd_id"),
                                          "enc": encrypt(result, self.key)}))
            except Exception as exc:
                print(f"[mon daemon] 指令处理失败:{exc}")

    async def _sync_loop(self, ws) -> None:
        state = SyncState()
        last_hb = 0.0
        while True:
            msgs = await asyncio.to_thread(compute_sync_messages, self.store, state, self.key)
            for m in msgs:
                await ws.send(json.dumps(m))
            if time.time() - last_hb >= HEARTBEAT_INTERVAL:
                last_hb = time.time()
                hb = await asyncio.to_thread(heartbeat_payload)
                await ws.send(json.dumps({"t": "hb", "enc": encrypt(hb, self.key)}))
            await asyncio.sleep(SYNC_INTERVAL)
