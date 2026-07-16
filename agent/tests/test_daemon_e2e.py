"""全链路 E2E:mon daemon ←WSS→ relay ←WSS→ app 客户端,验证加密同步与指令回路。"""
import asyncio
import contextlib
import json
import socket
import threading
import time

import httpx
import pytest
import uvicorn
from websockets.asyncio.client import connect as ws_async_connect

from runmon.config import Config
from runmon.crypto import decrypt, encrypt, generate_key, key_to_b64
from runmon.relay_client import Daemon
from runmon.store import RunStore
from runmon_relay.app import create_app


@pytest.fixture()
def server(tmp_path):
    db_path = tmp_path / "relay.db"
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    config = uvicorn.Config(create_app(db_path), host="127.0.0.1", port=port,
                            log_level="warning")
    srv = uvicorn.Server(config)
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    for _ in range(200):
        if srv.started:
            break
        time.sleep(0.05)
    assert srv.started
    yield f"http://127.0.0.1:{port}", db_path
    srv.should_exit = True
    thread.join(timeout=5)


def test_full_chain(tmp_path, monkeypatch, server):
    base, relay_db = server
    monkeypatch.setenv("RUNMON_DATA_DIR", str(tmp_path / "data"))
    store = RunStore(tmp_path / "agent.db")
    run = store.create_run(name="train-e2e-secret", command="c", cwd="", log_path="")
    store.append_output(run.id, "step 1 loss=0.5 SECRETMARKER\n", max_tail_chars=100000)

    start = httpx.post(base + "/api/pair/start", json={"device_name": "srv"}).json()
    claim = httpx.post(base + "/api/pair/claim",
                       json={"code": start["code"], "app_name": "phone"}).json()
    key = generate_key()
    cfg = Config()
    cfg.relay = {"url": base, "device_id": start["device_id"],
                 "device_token": start["device_token"], "key": key_to_b64(key)}
    daemon = Daemon(store=store, config=cfg)

    async def main():
        task = asyncio.create_task(daemon.run_forever())
        try:
            url = base.replace("http://", "ws://") + "/ws/app"
            async with ws_async_connect(url, additional_headers={
                    "Authorization": f"Bearer {claim['device_token']}",
                    "X-Device": claim["device_id"]}) as app_ws:
                got: dict = {}
                loop = asyncio.get_event_loop()
                deadline = loop.time() + 10
                while loop.time() < deadline and not ({"snapshot", "tail"} <= set(got)):
                    raw = await asyncio.wait_for(app_ws.recv(), timeout=10)
                    msg = json.loads(raw)
                    got[msg["t"]] = msg
                snap = decrypt(got["snapshot"]["enc"], key)
                assert snap["runs"][0]["name"] == "train-e2e-secret"
                tail = decrypt(got["tail"]["enc"], key)
                assert "SECRETMARKER" in tail["tail"]
                # 指令回路:mute
                await app_ws.send(json.dumps({
                    "t": "cmd", "agent": start["device_id"], "cmd_id": "c-e2e",
                    "enc": encrypt({"op": "mute", "run_id": run.id,
                                    "args": {"hours": 1}}, key)}))
                while True:
                    raw = await asyncio.wait_for(app_ws.recv(), timeout=10)
                    msg = json.loads(raw)
                    if msg.get("t") == "cmd_result" and msg.get("cmd_id") == "c-e2e":
                        assert decrypt(msg["enc"], key)["ok"] is True
                        break
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    asyncio.run(main())
    assert store.get_run(run.id).muted_until > time.time()

    # 隐私验收:relay 数据库里不允许出现任何明文业务内容
    blob = relay_db.read_bytes()
    for wal in (relay_db.with_suffix(".db-wal"),):
        if wal.exists():
            blob += wal.read_bytes()
    assert b"train-e2e-secret" not in blob
    assert b"SECRETMARKER" not in blob
