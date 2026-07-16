from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .config import data_dir

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  command TEXT NOT NULL,
  cwd TEXT NOT NULL DEFAULT '',
  pid INTEGER,
  status TEXT NOT NULL DEFAULT 'created',
  exit_code INTEGER,
  started_at REAL NOT NULL,
  ended_at REAL,
  updated_at REAL NOT NULL,
  last_output_at REAL,
  output_tail TEXT NOT NULL DEFAULT '',
  output_length INTEGER NOT NULL DEFAULT 0,
  log_path TEXT NOT NULL DEFAULT '',
  progress REAL,
  eta_seconds INTEGER,
  last_loss REAL,
  gpu_indices TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT,
  type TEXT NOT NULL,
  ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel_idx INTEGER NOT NULL,
  payload TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  next_retry_at REAL NOT NULL DEFAULT 0,
  delivered_at REAL
);
"""

_RUN_COLUMNS = (
    "id", "name", "command", "cwd", "pid", "status", "exit_code", "started_at",
    "ended_at", "updated_at", "last_output_at", "output_tail", "output_length",
    "log_path", "progress", "eta_seconds", "last_loss", "gpu_indices",
)


@dataclass
class RunRecord:
    id: str
    name: str
    command: str
    cwd: str
    pid: int | None
    status: str
    exit_code: int | None
    started_at: float
    ended_at: float | None
    updated_at: float
    last_output_at: float | None
    output_tail: str
    output_length: int
    log_path: str
    progress: float | None
    eta_seconds: int | None
    last_loss: float | None
    gpu_indices: str


class RunStore:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else data_dir() / "runmon.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def _row_to_run(self, row: sqlite3.Row) -> RunRecord:
        return RunRecord(**{k: row[k] for k in _RUN_COLUMNS})

    def create_run(self, name: str, command: str, cwd: str, log_path: str,
                   gpu_indices: str = "") -> RunRecord:
        run_id = uuid.uuid4().hex[:12]
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO runs (id,name,command,cwd,status,started_at,updated_at,log_path,gpu_indices)"
                " VALUES (?,?,?,?,'created',?,?,?,?)",
                (run_id, name, command, cwd, now, now, log_path, gpu_indices))
            self._conn.commit()
        return self.get_run(run_id)

    def update_run(self, run_id: str, **fields) -> None:
        allowed = set(_RUN_COLUMNS) - {"id"}
        cols = {k: v for k, v in fields.items() if k in allowed}
        cols["updated_at"] = time.time()
        sets = ", ".join(f"{k}=?" for k in cols)
        with self._lock:
            self._conn.execute(f"UPDATE runs SET {sets} WHERE id=?", (*cols.values(), run_id))
            self._conn.commit()

    def append_output(self, run_id: str, text: str, max_tail_chars: int) -> None:
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT output_tail, output_length FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                return
            tail = (row["output_tail"] + text)[-max_tail_chars:]
            self._conn.execute(
                "UPDATE runs SET output_tail=?, output_length=?, last_output_at=?, updated_at=? WHERE id=?",
                (tail, row["output_length"] + len(text), now, now, run_id))
            self._conn.commit()

    def get_run(self, run_id: str) -> RunRecord | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return self._row_to_run(row) if row else None

    def resolve_run(self, ident: str) -> RunRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM runs WHERE id=? OR id LIKE ? OR name=?"
                " ORDER BY started_at DESC LIMIT 1",
                (ident, ident + "%", ident)).fetchone()
        return self._row_to_run(row) if row else None

    def list_runs(self, limit: int = 50) -> list[RunRecord]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._row_to_run(r) for r in rows]

    def record_event(self, run_id: str | None, etype: str, ts: float) -> None:
        with self._lock:
            self._conn.execute("INSERT INTO events (run_id, type, ts) VALUES (?,?,?)",
                               (run_id, etype, ts))
            self._conn.commit()

    def last_event_at(self, run_id: str | None, etype: str) -> float | None:
        if run_id is None:
            sql = "SELECT MAX(ts) AS m FROM events WHERE run_id IS NULL AND type=?"
            args: tuple = (etype,)
        else:
            sql = "SELECT MAX(ts) AS m FROM events WHERE run_id=? AND type=?"
            args = (run_id, etype)
        with self._lock:
            row = self._conn.execute(sql, args).fetchone()
        return row["m"]

    def outbox_enqueue(self, channel_idx: int, payload: str) -> None:
        with self._lock:
            self._conn.execute("INSERT INTO outbox (channel_idx, payload) VALUES (?,?)",
                               (channel_idx, payload))
            self._conn.commit()

    def outbox_pending(self, now: float | None) -> list[sqlite3.Row]:
        with self._lock:
            if now is None:
                return self._conn.execute(
                    "SELECT * FROM outbox WHERE delivered_at IS NULL ORDER BY id").fetchall()
            return self._conn.execute(
                "SELECT * FROM outbox WHERE delivered_at IS NULL AND next_retry_at<=? ORDER BY id",
                (now,)).fetchall()

    def outbox_retry(self, item_id: int, attempts: int, next_retry_at: float) -> None:
        with self._lock:
            self._conn.execute("UPDATE outbox SET attempts=?, next_retry_at=? WHERE id=?",
                               (attempts, next_retry_at, item_id))
            self._conn.commit()

    def outbox_delivered(self, item_id: int, ts: float) -> None:
        with self._lock:
            self._conn.execute("UPDATE outbox SET delivered_at=? WHERE id=?", (ts, item_id))
            self._conn.commit()

    def outbox_remaining(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS c FROM outbox WHERE delivered_at IS NULL").fetchone()
        return row["c"]
