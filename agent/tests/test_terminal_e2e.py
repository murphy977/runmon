"""交互终端全链路:App 端发 term_open + term_input,收到 pty 输出。"""
import asyncio
import json
import socket
import threading
import time

import httpx
import pytest
import uvicorn
from websockets.asyncio.client import connect as ws_connect

from runmon.config import Config
from runmon.crypto import decrypt, encrypt, generate_key, key_to_b64
from runmon.relay_client import Daemon
from runmon.store import RunStore
from runmon_relay.app import create_app


@pytest.fixture()
def server(tmp_path):
    sock = socket.socket(); sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]; sock.close()
    srv = uvicorn.Server(uvicorn.Config(create_app(tmp_path / "r.db"),
                         host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(200):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True


def _pair(base):
    start = httpx.post(base + "/api/pair/start", json={"device_name": "s"}).json()
    claim = httpx.post(base + "/api/pair/claim",
                       json={"code": start["code"], "app_name": "a"}).json()
    return start, claim


def _run_daemon(tmp_path, base, key, start):
    cfg = Config(enable_terminal=True)
    cfg.relay = {"url": base, "device_id": start["device_id"],
                 "device_token": start["device_token"], "key": key_to_b64(key)}
    return Daemon(store=RunStore(tmp_path / "a.db"), config=cfg)


def test_terminal_echo(tmp_path, server):
    base = server
    start, claim = _pair(base)
    key = generate_key()
    daemon = _run_daemon(tmp_path, base, key, start)

    async def main():
        task = asyncio.create_task(daemon.run_forever())
        try:
            url = base.replace("http://", "ws://") + "/ws/app"
            async with ws_connect(url, additional_headers={
                    "Authorization": f"Bearer {claim['device_token']}",
                    "X-Device": claim["device_id"]}) as ws:
                await asyncio.sleep(0.5)  # 等 daemon 上线
                await ws.send(json.dumps({"t": "term_open", "agent": start["device_id"],
                    "enc": encrypt({"rows": 24, "cols": 80}, key)}))
                await asyncio.sleep(0.5)
                await ws.send(json.dumps({"t": "term_input", "agent": start["device_id"],
                    "enc": encrypt({"data": "echo RUNMON_MARK_42\n"}, key)}))
                got = ""
                deadline = asyncio.get_event_loop().time() + 8
                while asyncio.get_event_loop().time() < deadline:
                    raw = await asyncio.wait_for(ws.recv(), timeout=8)
                    m = json.loads(raw)
                    if m.get("t") == "term_output":
                        got += decrypt(m["enc"], key)["data"]
                        if "RUNMON_MARK_42" in got:
                            break
                assert "RUNMON_MARK_42" in got
                await ws.send(json.dumps({"t": "term_close", "agent": start["device_id"]}))
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    asyncio.run(main())


def test_terminal_hard_disabled(tmp_path, server):
    base = server
    start, claim = _pair(base)
    key = generate_key()
    cfg = Config(enable_terminal=False)  # 服务器主人一票否决
    cfg.relay = {"url": base, "device_id": start["device_id"],
                 "device_token": start["device_token"], "key": key_to_b64(key)}
    daemon = Daemon(store=RunStore(tmp_path / "a.db"), config=cfg)

    async def main():
        task = asyncio.create_task(daemon.run_forever())
        try:
            url = base.replace("http://", "ws://") + "/ws/app"
            async with ws_connect(url, additional_headers={
                    "Authorization": f"Bearer {claim['device_token']}",
                    "X-Device": claim["device_id"]}) as ws:
                await asyncio.sleep(0.5)
                await ws.send(json.dumps({"t": "term_open", "agent": start["device_id"],
                    "enc": encrypt({}, key)}))
                deadline = asyncio.get_event_loop().time() + 8
                while asyncio.get_event_loop().time() < deadline:
                    m = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
                    if m.get("t") == "term_output":
                        assert "未启用" in decrypt(m["enc"], key)["data"]
                        break
                else:
                    raise AssertionError("未收到 term_output")
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    asyncio.run(main())
