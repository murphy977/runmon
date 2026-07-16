import json
import socket
import threading
import time

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from websockets.sync.client import connect as ws_sync_connect

from runmon_relay.app import create_app


# ---------- REST(TestClient 即可) ----------

@pytest.fixture()
def client(tmp_path):
    return TestClient(create_app(tmp_path / "relay.db"))


def test_health(client):
    assert client.get("/health").json() == {"ok": True}


def test_pair_flow(client):
    start = client.post("/api/pair/start", json={"device_name": "gpu-server"}).json()
    assert len(start["code"]) == 6
    claim = client.post("/api/pair/claim",
                        json={"code": start["code"], "app_name": "pixel"}).json()
    assert claim["agent_id"] == start["device_id"] and claim["agent_name"] == "gpu-server"
    status = client.post("/api/pair/status",
                         json={"code": start["code"], "pair_token": start["pair_token"]}).json()
    assert status == {"claimed": True, "app_name": "pixel"}


def test_pair_bad_code(client):
    assert client.post("/api/pair/claim", json={"code": "000000"}).status_code == 404
    start = client.post("/api/pair/start", json={"device_name": "x"}).json()
    client.post("/api/pair/claim", json={"code": start["code"], "app_name": "a"})
    again = client.post("/api/pair/claim", json={"code": start["code"], "app_name": "b"})
    assert again.status_code == 404  # 同一码不能被认领两次


# ---------- WS(真 uvicorn:TestClient 的多 socket 会话跨事件循环,会死锁) ----------

@pytest.fixture()
def server(tmp_path):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    config = uvicorn.Config(create_app(tmp_path / "relay.db"),
                            host="127.0.0.1", port=port, log_level="warning")
    srv = uvicorn.Server(config)
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    for _ in range(200):
        if srv.started:
            break
        time.sleep(0.05)
    assert srv.started, "uvicorn 未能启动"
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    thread.join(timeout=5)


def pair(base):
    start = httpx.post(base + "/api/pair/start", json={"device_name": "gpu-server"}).json()
    claim = httpx.post(base + "/api/pair/claim",
                       json={"code": start["code"], "app_name": "pixel"}).json()
    return start, claim


def ws(base, path, device_id, token):
    url = base.replace("http://", "ws://") + path
    return ws_sync_connect(url, additional_headers={
        "Authorization": f"Bearer {token}", "X-Device": device_id}, open_timeout=5)


def recv(sock):
    return json.loads(sock.recv(timeout=5))


def test_ws_rejects_bad_token(server):
    start, _ = pair(server)
    with pytest.raises(Exception):
        with ws(server, "/ws/agent", start["device_id"], "wrong") as w:
            w.recv(timeout=2)


def test_forwarding_and_presence(server):
    start, claim = pair(server)
    with ws(server, "/ws/app", claim["device_id"], claim["device_token"]) as app_ws:
        first = recv(app_ws)
        assert first == {"t": "presence", "agent": start["device_id"],
                         "online": False, "name": "gpu-server"}
        with ws(server, "/ws/agent", start["device_id"], start["device_token"]) as agent_ws:
            on = recv(app_ws)
            assert on["t"] == "presence" and on["online"] is True
            # agent → app 转发,附加 agent 字段
            agent_ws.send(json.dumps({"t": "tail", "run": "r1", "enc": {"n": "x", "c": "y"}}))
            fwd = recv(app_ws)
            assert fwd["t"] == "tail" and fwd["agent"] == start["device_id"]
            # app → agent 指令
            app_ws.send(json.dumps({"t": "cmd", "agent": start["device_id"],
                                    "cmd_id": "c1", "enc": {"n": "a", "c": "b"}}))
            cmd = recv(agent_ws)
            assert cmd["cmd_id"] == "c1"
            # 结果回传
            agent_ws.send(json.dumps({"t": "cmd_result", "cmd_id": "c1",
                                      "enc": {"n": "p", "c": "q"}}))
            res = recv(app_ws)
            assert res["t"] == "cmd_result" and res["cmd_id"] == "c1"
        off = recv(app_ws)
        assert off["t"] == "presence" and off["online"] is False


def test_offline_cmd_queued_and_flushed(server):
    start, claim = pair(server)
    with ws(server, "/ws/app", claim["device_id"], claim["device_token"]) as app_ws:
        recv(app_ws)  # presence offline
        app_ws.send(json.dumps({"t": "cmd", "agent": start["device_id"],
                                "cmd_id": "c9", "enc": {"n": "a", "c": "b"}}))
        time.sleep(0.3)  # 让服务端处理入队
        with ws(server, "/ws/agent", start["device_id"], start["device_token"]) as agent_ws:
            cmd = recv(agent_ws)
            assert cmd["cmd_id"] == "c9"


def test_replay_on_app_connect(server):
    start, claim = pair(server)
    with ws(server, "/ws/agent", start["device_id"], start["device_token"]) as agent_ws:
        agent_ws.send(json.dumps({"t": "snapshot", "enc": {"n": "1", "c": "s"}}))
        agent_ws.send(json.dumps({"t": "hb", "enc": {"n": "2", "c": "h"}}))
        agent_ws.send(json.dumps({"t": "tail", "run": "r1", "enc": {"n": "3", "c": "t"}}))
        agent_ws.send(json.dumps({"t": "event", "enc": {"n": "4", "c": "e"}}))
        time.sleep(0.3)  # 待服务端落库
        with ws(server, "/ws/app", claim["device_id"], claim["device_token"]) as app_ws:
            msgs = [recv(app_ws) for _ in range(5)]
            types = [m["t"] for m in msgs]
            assert types[0] == "presence" and msgs[0]["online"] is True
            assert sorted(types[1:]) == ["event", "hb", "snapshot", "tail"]
            assert all(m.get("agent") == start["device_id"] for m in msgs[1:])
