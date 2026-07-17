import json
import subprocess
import sys
import time

import pytest

from runmon.crypto import decrypt, generate_key
from runmon.relay_client import SyncState, compute_sync_messages, handle_command
from runmon.store import RunStore


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNMON_DATA_DIR", str(tmp_path / "data"))
    return RunStore(tmp_path / "t.db")


KEY = generate_key()


def test_sync_first_pass_sends_snapshot_and_tail(store):
    run = store.create_run(name="train", command="c", cwd="", log_path="")
    store.append_output(run.id, "hello\n", max_tail_chars=1000)
    state = SyncState()
    msgs = compute_sync_messages(store, state, KEY)
    types = [m["t"] for m in msgs]
    assert types == ["snapshot", "tail"]
    snap = decrypt(msgs[0]["enc"], KEY)
    assert snap["runs"][0]["name"] == "train"
    tail = decrypt(msgs[1]["enc"], KEY)
    assert tail["tail"] == "hello\n" and tail["run_id"] == run.id
    # 无变化 → 不发
    assert compute_sync_messages(store, state, KEY) == []


def test_sync_detects_output_and_status_change(store):
    run = store.create_run(name="a", command="c", cwd="", log_path="")
    state = SyncState()
    compute_sync_messages(store, state, KEY)
    store.append_output(run.id, "more", max_tail_chars=1000)
    msgs = compute_sync_messages(store, state, KEY)
    assert [m["t"] for m in msgs] == ["tail"]              # 输出增长只发尾窗,不动快照
    store.update_run(run.id, status="completed", exit_code=0)
    msgs = compute_sync_messages(store, state, KEY)
    assert [m["t"] for m in msgs] == ["snapshot"]          # 状态变化才发快照


def test_sync_forwards_events(store):
    state = SyncState()
    compute_sync_messages(store, state, KEY)
    store.record_event("r1", "failed", time.time(),
                       payload='{"type":"failed","title":"x","level":"critical","body":"","run_id":"r1"}')
    msgs = compute_sync_messages(store, state, KEY)
    evs = [m for m in msgs if m["t"] == "event"]
    assert len(evs) == 1 and decrypt(evs[0]["enc"], KEY)["type"] == "failed"
    assert compute_sync_messages(store, state, KEY) == []       # 不重发


def test_handle_mute(store):
    run = store.create_run(name="a", command="c", cwd="", log_path="")
    res = handle_command(store, {"op": "mute", "run_id": run.id, "args": {"hours": 1}})
    assert res["ok"] is True
    assert store.get_run(run.id).muted_until > time.time() + 3000
    res = handle_command(store, {"op": "mute", "run_id": run.id, "args": {"hours": 0}})
    assert store.get_run(run.id).muted_until > time.time() + 10 * 365 * 86400  # 永久


def test_handle_tail(store, tmp_path):
    log = tmp_path / "x.log"
    log.write_text("\n".join(f"line{i}" for i in range(200)))
    run = store.create_run(name="a", command="c", cwd="", log_path=str(log))
    res = handle_command(store, {"op": "tail", "run_id": run.id, "args": {"lines": 5}})
    assert res["ok"] is True
    assert res["tail"].splitlines() == [f"line{i}" for i in range(195, 200)]


def test_handle_stop(store):
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                            start_new_session=True)
    run = store.create_run(name="sleepy", command="c", cwd="", log_path="")
    store.update_run(run.id, status="running", pid=proc.pid)
    res = handle_command(store, {"op": "stop", "run_id": run.id})
    assert res["ok"] is True
    assert proc.wait(timeout=15) != 0


def test_handle_unknown(store):
    assert handle_command(store, {"op": "format_disk"})["ok"] is False


def test_handle_shutdown_after(store):
    run = store.create_run(name="a", command="c", cwd="", log_path="")
    res = handle_command(store, {"op": "shutdown_after", "run_id": run.id,
                                 "args": {"enabled": True}})
    assert res["ok"] is True and store.get_run(run.id).shutdown_after == 1
    handle_command(store, {"op": "shutdown_after", "run_id": run.id,
                           "args": {"enabled": False}})
    assert store.get_run(run.id).shutdown_after == 0
