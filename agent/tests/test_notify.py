import json

import runmon.notify as notify
from runmon.config import Config
from runmon.events import Event
from runmon.store import RunStore


EV = Event(type="failed", level="critical", title="❌ train 失败", body="耗时 3分", run_id="abc")


def capture(monkeypatch):
    calls = []
    monkeypatch.setattr(notify, "_post", lambda url, data, headers: calls.append((url, data, headers)))
    return calls


def test_ntfy(monkeypatch):
    calls = capture(monkeypatch)
    notify.NtfyChannel({"topic": "mytopic"}).send(EV)
    url, data, headers = calls[0]
    payload = json.loads(data)
    assert url == "https://ntfy.sh/"
    assert payload["topic"] == "mytopic" and payload["title"] == EV.title and payload["priority"] == 5


def test_bark(monkeypatch):
    calls = capture(monkeypatch)
    notify.BarkChannel({"key": "K123"}).send(EV)
    url, data, _ = calls[0]
    assert url == "https://api.day.app/K123"
    assert json.loads(data)["title"] == EV.title


def test_telegram(monkeypatch):
    calls = capture(monkeypatch)
    notify.TelegramChannel({"bot_token": "T", "chat_id": 42}).send(EV)
    url, data, _ = calls[0]
    assert url == "https://api.telegram.org/botT/sendMessage"
    p = json.loads(data)
    assert p["chat_id"] == "42" and EV.title in p["text"]


def test_webhook(monkeypatch):
    calls = capture(monkeypatch)
    notify.WebhookChannel({"url": "http://h/x"}).send(EV)
    url, data, _ = calls[0]
    assert url == "http://h/x" and json.loads(data)["type"] == "failed"


def test_wecom_full_url(monkeypatch):
    calls = capture(monkeypatch)
    url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc-123"
    notify.WecomChannel({"key": url}).send(EV)
    got_url, data, headers = calls[0]
    assert got_url == url
    p = json.loads(data)
    assert p["msgtype"] == "text" and EV.title in p["text"]["content"] and EV.body in p["text"]["content"]


def test_wecom_bare_key_builds_url(monkeypatch):
    calls = capture(monkeypatch)
    notify.WecomChannel({"key": "abc-123"}).send(EV)
    got_url, _, _ = calls[0]
    assert got_url == "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc-123"


def test_make_channels_skips_bad():
    cfg = Config()
    cfg.channels = [{"type": "ntfy", "topic": "t"}, {"type": "nope"}, {"type": "bark"}]
    chans = notify.make_channels(cfg)
    assert len(chans) == 1 and chans[0].name == "ntfy"


class FlakyChannel:
    name = "flaky"

    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.sent = []

    def send(self, ev):
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("net down")
        self.sent.append(ev)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_notifier_delivers(tmp_path):
    store = RunStore(tmp_path / "t.db")
    ch = FlakyChannel(fail_times=0)
    n = notify.Notifier(store, [ch], clock=Clock())
    n.notify(EV)
    assert n.deliver_due() == 0
    assert ch.sent[0].title == EV.title and ch.sent[0].run_id == "abc"


def test_notifier_backoff_then_success(tmp_path):
    store = RunStore(tmp_path / "t.db")
    ch = FlakyChannel(fail_times=2)
    clock = Clock()
    n = notify.Notifier(store, [ch], clock=clock)
    n.notify(EV)
    assert n.deliver_due() == 1            # 第一次失败,退避 5s
    assert n.deliver_due() == 1            # 未到期,不尝试
    clock.now += 5.1
    assert n.deliver_due() == 1            # 第二次失败,退避 10s
    clock.now += 10.1
    assert n.deliver_due() == 0            # 第三次成功
    assert len(ch.sent) == 1


def test_flush_forces_delivery(tmp_path):
    store = RunStore(tmp_path / "t.db")
    ch = FlakyChannel(fail_times=1)
    n = notify.Notifier(store, [ch], clock=Clock())
    n.notify(EV)
    assert n.flush(timeout=5.0) is True    # force 无视退避,立刻重试成功
    assert len(ch.sent) == 1


def test_multi_channel_fanout(tmp_path):
    store = RunStore(tmp_path / "t.db")
    a, b = FlakyChannel(0), FlakyChannel(0)
    n = notify.Notifier(store, [a, b], clock=Clock())
    n.notify(EV)
    n.deliver_due()
    assert len(a.sent) == 1 and len(b.sent) == 1
