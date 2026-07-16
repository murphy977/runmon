"""relay 存储:设备/配对/密文暂存。relay 永远只见密文与路由元数据。"""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
import threading
import time
from pathlib import Path

PAIR_TTL = 600          # 配对码有效期(秒)
CMD_TTL = 300           # 离线指令暂存(秒)
EVENT_RETENTION = 30 * 86400
TAILS_PER_AGENT = 200

_SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  name TEXT NOT NULL DEFAULT '',
  token_hash TEXT NOT NULL,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS pairings (
  agent_id TEXT NOT NULL,
  app_id TEXT NOT NULL,
  PRIMARY KEY (agent_id, app_id)
);
CREATE TABLE IF NOT EXISTS pending_pairs (
  code TEXT PRIMARY KEY,
  pair_token TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  claimed_app_id TEXT,
  claimed_app_name TEXT,
  expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots (
  agent_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  msg TEXT NOT NULL,
  updated REAL NOT NULL,
  PRIMARY KEY (agent_id, kind)
);
CREATE TABLE IF NOT EXISTS run_tails (
  agent_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  msg TEXT NOT NULL,
  updated REAL NOT NULL,
  PRIMARY KEY (agent_id, run_id)
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL,
  msg TEXT NOT NULL,
  ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS pending_cmds (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL,
  msg TEXT NOT NULL,
  created REAL NOT NULL
);
"""


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class RelayStore:
    def __init__(self, db_path: Path | str) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # ---- 设备与鉴权 ----

    def create_device(self, kind: str, name: str) -> tuple[str, str]:
        device_id = f"{kind[0]}_" + secrets.token_urlsafe(9)
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._conn.execute(
                "INSERT INTO devices (id, kind, name, token_hash, created) VALUES (?,?,?,?,?)",
                (device_id, kind, name, _hash(token), time.time()))
            self._conn.commit()
        return device_id, token

    def auth(self, device_id: str, token: str) -> str | None:
        if not device_id or not token:
            return None
        with self._lock:
            row = self._conn.execute(
                "SELECT kind, token_hash FROM devices WHERE id=?", (device_id,)).fetchone()
        if row is None or not secrets.compare_digest(row["token_hash"], _hash(token)):
            return None
        return row["kind"]

    def device_name(self, device_id: str) -> str:
        with self._lock:
            row = self._conn.execute(
                "SELECT name FROM devices WHERE id=?", (device_id,)).fetchone()
        return row["name"] if row else ""

    # ---- 配对 ----

    def pair_start(self, agent_name: str) -> dict:
        agent_id, agent_token = self.create_device("agent", agent_name)
        pair_token = secrets.token_urlsafe(16)
        with self._lock:
            while True:
                code = f"{secrets.randbelow(1000000):06d}"
                exists = self._conn.execute(
                    "SELECT 1 FROM pending_pairs WHERE code=?", (code,)).fetchone()
                if not exists:
                    break
            self._conn.execute(
                "INSERT INTO pending_pairs (code, pair_token, agent_id, expires) VALUES (?,?,?,?)",
                (code, pair_token, agent_id, time.time() + PAIR_TTL))
            self._conn.commit()
        return {"code": code, "pair_token": pair_token,
                "device_id": agent_id, "device_token": agent_token}

    def pair_claim(self, code: str, app_name: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM pending_pairs WHERE code=?", (code,)).fetchone()
            if row is None or row["expires"] < time.time() or row["claimed_app_id"]:
                return None
        app_id, app_token = self.create_device("app", app_name)
        with self._lock:
            self._conn.execute(
                "UPDATE pending_pairs SET claimed_app_id=?, claimed_app_name=? WHERE code=?",
                (app_id, app_name, code))
            self._conn.execute(
                "INSERT OR IGNORE INTO pairings (agent_id, app_id) VALUES (?,?)",
                (row["agent_id"], app_id))
            self._conn.commit()
        return {"device_id": app_id, "device_token": app_token,
                "agent_id": row["agent_id"], "agent_name": self.device_name(row["agent_id"])}

    def pair_status(self, code: str, pair_token: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM pending_pairs WHERE code=?", (code,)).fetchone()
        if row is None or not secrets.compare_digest(row["pair_token"], pair_token):
            return None
        return {"claimed": bool(row["claimed_app_id"]),
                "app_name": row["claimed_app_name"] or ""}

    def apps_for_agent(self, agent_id: str) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT app_id FROM pairings WHERE agent_id=?", (agent_id,)).fetchall()
        return [r["app_id"] for r in rows]

    def agents_for_app(self, app_id: str) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT agent_id FROM pairings WHERE app_id=?", (app_id,)).fetchall()
        return [r["agent_id"] for r in rows]

    # ---- 密文暂存(重放给新连上的 app)----

    def save_snapshot(self, agent_id: str, kind: str, msg: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO snapshots (agent_id, kind, msg, updated) VALUES (?,?,?,?)"
                " ON CONFLICT(agent_id, kind) DO UPDATE SET msg=excluded.msg, updated=excluded.updated",
                (agent_id, kind, msg, time.time()))
            self._conn.commit()

    def snapshots_for(self, agent_id: str) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT msg FROM snapshots WHERE agent_id=? ORDER BY kind", (agent_id,)).fetchall()
        return [r["msg"] for r in rows]

    def save_tail(self, agent_id: str, run_id: str, msg: str) -> None:
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO run_tails (agent_id, run_id, msg, updated) VALUES (?,?,?,?)"
                " ON CONFLICT(agent_id, run_id) DO UPDATE SET msg=excluded.msg, updated=excluded.updated",
                (agent_id, run_id, msg, now))
            self._conn.execute(
                "DELETE FROM run_tails WHERE agent_id=? AND run_id NOT IN ("
                " SELECT run_id FROM run_tails WHERE agent_id=? ORDER BY updated DESC LIMIT ?)",
                (agent_id, agent_id, TAILS_PER_AGENT))
            self._conn.commit()

    def tails_for(self, agent_id: str) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT msg FROM run_tails WHERE agent_id=? ORDER BY updated", (agent_id,)).fetchall()
        return [r["msg"] for r in rows]

    def add_event(self, agent_id: str, msg: str) -> None:
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO events (agent_id, msg, ts) VALUES (?,?,?)", (agent_id, msg, now))
            self._conn.execute(
                "DELETE FROM events WHERE ts < ?", (now - EVENT_RETENTION,))
            self._conn.commit()

    def events_for(self, agent_id: str, limit: int = 50) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT msg FROM events WHERE agent_id=? ORDER BY id DESC LIMIT ?",
                (agent_id, limit)).fetchall()
        return [r["msg"] for r in reversed(rows)]

    # ---- 离线指令 ----

    def queue_cmd(self, agent_id: str, msg: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO pending_cmds (agent_id, msg, created) VALUES (?,?,?)",
                (agent_id, msg, time.time()))
            self._conn.commit()

    def pop_cmds(self, agent_id: str) -> list[str]:
        now = time.time()
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM pending_cmds WHERE agent_id=? AND created>=? ORDER BY id",
                (agent_id, now - CMD_TTL)).fetchall()
            self._conn.execute("DELETE FROM pending_cmds WHERE agent_id=?", (agent_id,))
            self._conn.commit()
        return [r["msg"] for r in rows]
