from __future__ import annotations

import json
import threading
import time
import urllib.request

from .events import Event

_TIMEOUT = 10

BACKOFF_BASE = 5.0
BACKOFF_MAX = 3600.0


def _post(url: str, data: bytes, headers: dict) -> None:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        resp.read()


def _json_headers() -> dict:
    return {"Content-Type": "application/json; charset=utf-8"}


class NtfyChannel:
    name = "ntfy"

    def __init__(self, cfg: dict) -> None:
        self.server = cfg.get("server", "https://ntfy.sh").rstrip("/")
        self.topic = cfg["topic"]
        self.token = cfg.get("token", "")

    def send(self, ev: Event) -> None:
        payload = {"topic": self.topic, "title": ev.title, "message": ev.body,
                   "priority": 5 if ev.level == "critical" else 3}
        headers = _json_headers()
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        _post(self.server + "/", json.dumps(payload).encode(), headers)


class BarkChannel:
    name = "bark"

    def __init__(self, cfg: dict) -> None:
        self.server = cfg.get("server", "https://api.day.app").rstrip("/")
        self.key = cfg["key"]

    def send(self, ev: Event) -> None:
        payload = {"title": ev.title, "body": ev.body,
                   "level": "timeSensitive" if ev.level == "critical" else "active"}
        _post(f"{self.server}/{self.key}", json.dumps(payload).encode(), _json_headers())


class TelegramChannel:
    name = "telegram"

    def __init__(self, cfg: dict) -> None:
        self.bot_token = cfg["bot_token"]
        self.chat_id = str(cfg["chat_id"])

    def send(self, ev: Event) -> None:
        payload = {"chat_id": self.chat_id, "text": f"{ev.title}\n{ev.body}"}
        _post(f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
              json.dumps(payload).encode(), _json_headers())


class WebhookChannel:
    name = "webhook"

    def __init__(self, cfg: dict) -> None:
        self.url = cfg["url"]

    def send(self, ev: Event) -> None:
        payload = {"type": ev.type, "level": ev.level, "title": ev.title,
                   "body": ev.body, "run_id": ev.run_id}
        _post(self.url, json.dumps(payload).encode(), _json_headers())


CHANNEL_TYPES: dict[str, type] = {
    "ntfy": NtfyChannel,
    "bark": BarkChannel,
    "telegram": TelegramChannel,
    "webhook": WebhookChannel,
}


def make_channels(config) -> list:
    out = []
    for c in config.channels:
        cls = CHANNEL_TYPES.get(c.get("type", ""))
        if cls is None:
            continue
        try:
            out.append(cls(c))
        except KeyError:
            continue
    return out


def _event_to_json(ev: Event) -> str:
    return json.dumps({"type": ev.type, "level": ev.level, "title": ev.title,
                       "body": ev.body, "run_id": ev.run_id})


def _event_from_json(payload: str) -> Event:
    d = json.loads(payload)
    return Event(type=d["type"], level=d["level"], title=d["title"],
                 body=d["body"], run_id=d.get("run_id"))


class Notifier:
    def __init__(self, store, channels: list, clock=time.time) -> None:
        self.store = store
        self.channels = channels
        self.clock = clock
        self._wake = threading.Event()
        self._halt = threading.Event()
        self._thread: threading.Thread | None = None

    def notify(self, ev: Event) -> None:
        payload = _event_to_json(ev)
        for idx in range(len(self.channels)):
            self.store.outbox_enqueue(idx, payload)
        self._wake.set()

    def deliver_due(self, force: bool = False) -> int:
        now = self.clock()
        rows = self.store.outbox_pending(None if force else now)
        for row in rows:
            idx = row["channel_idx"]
            if idx >= len(self.channels):
                self.store.outbox_delivered(row["id"], now)  # 通道已被移除,丢弃
                continue
            try:
                self.channels[idx].send(_event_from_json(row["payload"]))
                self.store.outbox_delivered(row["id"], self.clock())
            except Exception:
                attempts = row["attempts"] + 1
                delay = min(BACKOFF_MAX, BACKOFF_BASE * (2 ** row["attempts"]))
                self.store.outbox_retry(row["id"], attempts, self.clock() + delay)
        return self.store.outbox_remaining()

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def _loop(self) -> None:
        while not self._halt.is_set():
            try:
                self.deliver_due()
            except Exception:
                pass
            self._wake.wait(timeout=2.0)
            self._wake.clear()

    def flush(self, timeout: float = 15.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.deliver_due(force=True) == 0:
                return True
            time.sleep(0.3)
        return False

    def stop(self) -> None:
        self._halt.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
