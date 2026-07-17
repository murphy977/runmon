"""RunMon relay:配对 REST + WSS 存储转发。业务数据全密文,relay 只读路由字段。"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from .storage import RelayStore


class PairStartBody(BaseModel):
    device_name: str = ""


class PairClaimBody(BaseModel):
    code: str
    app_name: str = ""


class PairStatusBody(BaseModel):
    code: str
    pair_token: str


class ConnectionManager:
    def __init__(self, store: RelayStore) -> None:
        self.store = store
        self.agents: dict[str, WebSocket] = {}
        self.apps: dict[str, WebSocket] = {}

    async def _safe_send(self, ws: WebSocket, text: str) -> None:
        try:
            await ws.send_text(text)
        except Exception:
            pass

    async def forward_to_apps(self, agent_id: str, msg: dict) -> None:
        text = json.dumps(msg, ensure_ascii=False)
        for app_id in self.store.apps_for_agent(agent_id):
            if ws := self.apps.get(app_id):
                await self._safe_send(ws, text)

    async def notify_presence(self, agent_id: str, online: bool) -> None:
        await self.forward_to_apps(agent_id, {
            "t": "presence", "agent": agent_id, "online": online,
            "name": self.store.device_name(agent_id)})

    async def replay_to_app(self, ws: WebSocket, app_id: str) -> None:
        """app 连上时补发:presence + 快照 + 各 run 尾部 + 近期事件。"""
        for agent_id in self.store.agents_for_app(app_id):
            await self._safe_send(ws, json.dumps({
                "t": "presence", "agent": agent_id,
                "online": agent_id in self.agents,
                "name": self.store.device_name(agent_id)}, ensure_ascii=False))
            for raw in (self.store.snapshots_for(agent_id)
                        + self.store.tails_for(agent_id)
                        + self.store.events_for(agent_id)):
                msg = json.loads(raw)
                msg["agent"] = agent_id
                await self._safe_send(ws, json.dumps(msg, ensure_ascii=False))


def _ws_credentials(ws: WebSocket) -> tuple[str, str]:
    device = ws.headers.get("x-device", "")
    auth = ws.headers.get("authorization", "")
    token = auth[7:].strip() if auth.startswith("Bearer ") else ""
    return device, token


def create_app(db_path: Path | str) -> FastAPI:
    store = RelayStore(db_path)
    mgr = ConnectionManager(store)
    app = FastAPI(title="runmon-relay")
    app.state.store = store
    app.state.mgr = mgr

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.post("/api/pair/start")
    def pair_start(body: PairStartBody):
        return store.pair_start(body.device_name)

    @app.post("/api/pair/claim")
    def pair_claim(body: PairClaimBody):
        result = store.pair_claim(body.code, body.app_name)
        if result is None:
            raise HTTPException(status_code=404, detail="配对码无效或已过期")
        return result

    @app.post("/api/pair/status")
    def pair_status(body: PairStatusBody):
        result = store.pair_status(body.code, body.pair_token)
        if result is None:
            raise HTTPException(status_code=404, detail="not found")
        return result

    @app.websocket("/ws/agent")
    async def ws_agent(ws: WebSocket):
        device, token = _ws_credentials(ws)
        if store.auth(device, token) != "agent":
            await ws.close(code=4401)
            return
        await ws.accept()
        mgr.agents[device] = ws
        await mgr.notify_presence(device, True)
        for cmd in store.pop_cmds(device):
            await mgr._safe_send(ws, cmd)
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                t = msg.get("t")
                if t == "snapshot":
                    store.save_snapshot(device, "snapshot", raw)
                elif t == "hb":
                    store.save_snapshot(device, "hb", raw)
                elif t == "tail":
                    store.save_tail(device, str(msg.get("run", "")), raw)
                elif t == "event":
                    store.add_event(device, raw)
                elif t in ("term_output",):
                    pass  # 交互终端输出:实时转发,不落库
                elif t != "cmd_result":
                    continue
                msg["agent"] = device
                await mgr.forward_to_apps(device, msg)
        except WebSocketDisconnect:
            pass
        finally:
            if mgr.agents.get(device) is ws:
                del mgr.agents[device]
            await mgr.notify_presence(device, False)

    @app.websocket("/ws/app")
    async def ws_app(ws: WebSocket):
        device, token = _ws_credentials(ws)
        if store.auth(device, token) != "app":
            await ws.close(code=4401)
            return
        await ws.accept()
        mgr.apps[device] = ws
        await mgr.replay_to_app(ws, device)
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                t = msg.get("t")
                if t not in ("cmd", "term_open", "term_input",
                             "term_resize", "term_close"):
                    continue
                agent_id = msg.get("agent", "")
                if agent_id not in store.agents_for_app(device):
                    continue  # 只能指挥自己配对的 agent
                text = json.dumps(msg, ensure_ascii=False)
                if agent_ws := mgr.agents.get(agent_id):
                    await mgr._safe_send(agent_ws, text)
                elif t == "cmd":
                    store.queue_cmd(agent_id, text)  # 白名单指令离线暂存;终端实时消息丢弃
        except WebSocketDisconnect:
            pass
        finally:
            if mgr.apps.get(device) is ws:
                del mgr.apps[device]

    return app
