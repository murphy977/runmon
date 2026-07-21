from runmon.store import RunStore


def make_store(tmp_path):
    return RunStore(tmp_path / "t.db")


def test_create_and_get(tmp_path):
    s = make_store(tmp_path)
    r = s.create_run(name="train", command="python train.py", cwd="/w", log_path="/l.log")
    assert len(r.id) == 12 and r.status == "created" and r.started_at > 0
    got = s.get_run(r.id)
    assert got.name == "train" and got.command == "python train.py"


def test_update_and_list(tmp_path):
    s = make_store(tmp_path)
    r = s.create_run(name="a", command="c", cwd="", log_path="")
    s.update_run(r.id, status="running", pid=123)
    assert s.get_run(r.id).pid == 123
    s.create_run(name="b", command="c", cwd="", log_path="")
    names = [x.name for x in s.list_runs()]
    assert names == ["b", "a"]


def test_append_output_ring(tmp_path):
    s = make_store(tmp_path)
    r = s.create_run(name="a", command="c", cwd="", log_path="")
    s.append_output(r.id, "x" * 100, max_tail_chars=50)
    s.append_output(r.id, "END", max_tail_chars=50)
    got = s.get_run(r.id)
    assert got.output_length == 103
    assert len(got.output_tail) == 50 and got.output_tail.endswith("END")
    assert got.last_output_at is not None


def test_resolve(tmp_path):
    s = make_store(tmp_path)
    r = s.create_run(name="train-x", command="c", cwd="", log_path="")
    assert s.resolve_run(r.id).id == r.id
    assert s.resolve_run(r.id[:4]).id == r.id
    assert s.resolve_run("train-x").id == r.id
    assert s.resolve_run("nope") is None


def test_event_debounce_timestamps(tmp_path):
    s = make_store(tmp_path)
    assert s.last_event_at("r1", "gpu_hang") is None
    s.record_event("r1", "gpu_hang", 100.0)
    s.record_event("r1", "gpu_hang", 200.0)
    assert s.last_event_at("r1", "gpu_hang") == 200.0
    assert s.last_event_at("r1", "disk_full") is None
    s.record_event(None, "disk_full", 50.0)
    assert s.last_event_at(None, "disk_full") == 50.0


def test_outbox_flow(tmp_path):
    s = make_store(tmp_path)
    s.outbox_enqueue(0, '{"a":1}')
    s.outbox_enqueue(1, '{"a":1}')
    rows = s.outbox_pending(now=1000.0)
    assert len(rows) == 2 and rows[0]["attempts"] == 0
    s.outbox_retry(rows[0]["id"], attempts=1, next_retry_at=2000.0)
    assert len(s.outbox_pending(now=1500.0)) == 1      # 一条在等退避
    assert len(s.outbox_pending(now=None)) == 2        # 强制模式全取
    s.outbox_delivered(rows[1]["id"], ts=1500.0)
    assert s.outbox_remaining() == 1


def test_migration_adds_columns(tmp_path):
    import sqlite3
    # 先造一个 M1 时代的旧库(无 muted_until / payload 列)
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE runs (id TEXT PRIMARY KEY, name TEXT NOT NULL, command TEXT NOT NULL,"
                 " cwd TEXT NOT NULL DEFAULT '', pid INTEGER, status TEXT NOT NULL DEFAULT 'created',"
                 " exit_code INTEGER, started_at REAL NOT NULL, ended_at REAL, updated_at REAL NOT NULL,"
                 " last_output_at REAL, output_tail TEXT NOT NULL DEFAULT '', output_length INTEGER NOT NULL DEFAULT 0,"
                 " log_path TEXT NOT NULL DEFAULT '', progress REAL, eta_seconds INTEGER, last_loss REAL,"
                 " gpu_indices TEXT NOT NULL DEFAULT '')")
    conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, type TEXT NOT NULL, ts REAL NOT NULL)")
    conn.execute("INSERT INTO runs (id,name,command,started_at,updated_at) VALUES ('old1','n','c',1,1)")
    conn.commit()
    conn.close()
    s = RunStore(db)                       # 打开时自动迁移
    run = s.get_run("old1")
    assert run.muted_until is None
    s.update_run("old1", muted_until=999.0)
    assert s.get_run("old1").muted_until == 999.0


def test_event_payload_and_since(tmp_path):
    s = make_store(tmp_path)
    s.record_event("r1", "failed", 100.0, payload='{"title":"x"}')
    s.record_event("r1", "completed", 200.0)
    rows = s.events_since(0)
    assert len(rows) == 2
    assert rows[0]["payload"] == '{"title":"x"}' and rows[1]["payload"] is None
    assert s.events_since(rows[0]["id"])[0]["type"] == "completed"


def test_max_event_id(tmp_path):
    from runmon.store import RunStore
    store = RunStore(tmp_path / "m.db")
    assert store.max_event_id() == 0
    store.record_event(None, "test", 1.0, payload="{}")
    store.record_event(None, "test", 2.0, payload="{}")
    assert store.max_event_id() == 2
