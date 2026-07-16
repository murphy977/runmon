import json
import sys

import pytest

from runmon.config import Config, data_dir
from runmon.notify import Notifier
from runmon.runner import RunWrapper
from runmon.store import RunStore


class MemoryChannel:
    name = "mem"

    def __init__(self):
        self.sent = []

    def send(self, ev):
        self.sent.append(ev)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNMON_DATA_DIR", str(tmp_path / "data"))
    store = RunStore(tmp_path / "t.db")
    ch = MemoryChannel()
    notifier = Notifier(store, [ch])
    return store, ch, notifier


def make_wrapper(env, code: str, **kw):
    store, ch, notifier = env
    cfg = Config(sample_interval_s=3600)      # 测试中默认不触发监控采样
    return RunWrapper([sys.executable, "-u", "-c", code],
                      store=store, config=cfg, notifier=notifier, **kw), store, ch


def test_success_run(env):
    w, store, ch = make_wrapper(env, "print('hello-world')")
    assert w.execute() == 0
    run = store.get_run(w.run.id)
    assert run.status == "completed" and run.exit_code == 0
    assert "hello-world" in run.output_tail
    assert [e.type for e in ch.sent] == ["completed"]
    # 完整日志与 env 快照落盘
    assert "hello-world" in (data_dir() / "logs" / f"{run.id}.log").read_text()
    assert json.loads((data_dir() / "logs" / f"{run.id}.env.json").read_text())


def test_failed_run_with_traceback(env):
    w, store, ch = make_wrapper(env, "raise RuntimeError('boom')")
    assert w.execute() == 1
    run = store.get_run(w.run.id)
    assert run.status == "failed" and run.exit_code == 1
    types = [e.type for e in ch.sent]
    assert "error_pattern" in types and "failed" in types


def test_progress_recorded(env):
    code = r"""
import sys
sys.stdout.write("Epoch 1/2\n")
sys.stdout.write("50%|-----| 50/100 [00:10<00:10,  5.0it/s] loss=0.5\n")
"""
    w, store, _ = make_wrapper(env, code)
    w.execute()
    run = store.get_run(w.run.id)
    assert run.progress == 50.0 and run.last_loss == 0.5


def test_monitor_disk_event(env, monkeypatch):
    store, ch, notifier = env
    import runmon.runner as runner_mod
    monkeypatch.setattr(runner_mod.sampler, "disk_usage", lambda: [("/", 99.0)])
    monkeypatch.setattr(runner_mod.sampler, "sample_gpus", lambda: [])
    cfg = Config(sample_interval_s=0)        # 立即采样
    w = RunWrapper([sys.executable, "-c", "import time; time.sleep(0.6)"],
                   store=store, config=cfg, notifier=notifier)
    w.execute()
    assert "disk_full" in [e.type for e in ch.sent]


def test_default_name_is_command(env):
    w, store, _ = make_wrapper(env, "pass")
    w.execute()
    assert "-c" in store.get_run(w.run.id).name
