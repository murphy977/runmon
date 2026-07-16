from runmon.config import Config
from runmon.events import (COMPLETED, DISK_FULL, ERROR_PATTERN, FAILED, GPU_HANG,
                           LOG_SILENCE, EventEngine, format_duration)
from runmon.store import RunStore


class FakeClock:
    def __init__(self, now=10000.0):
        self.now = now

    def __call__(self):
        return self.now


def make(tmp_path, **cfg):
    store = RunStore(tmp_path / "t.db")
    clock = FakeClock()
    engine = EventEngine(store, Config(**cfg), clock=clock)
    run = store.create_run(name="train", command="c", cwd="", log_path="")
    store.update_run(run.id, started_at=clock.now, status="running")
    return store, clock, engine, store.get_run(run.id)


def test_format_duration():
    assert format_duration(45) == "45秒"
    assert format_duration(192) == "3分12秒"
    assert format_duration(8100) == "2小时15分"


def test_on_exit(tmp_path):
    _, _, engine, run = make(tmp_path)
    ok = engine.on_exit(run, 0)
    assert ok.type == COMPLETED and ok.level == "info" and "train" in ok.title
    bad = engine.on_exit(run, 1)
    assert bad.type == FAILED and bad.level == "critical" and "exit 1" in bad.title


def test_error_pattern_debounce(tmp_path):
    _, clock, engine, run = make(tmp_path)
    ev = engine.on_output(run, "blah\nTraceback (most recent call last):\n...")
    assert ev is not None and ev.type == ERROR_PATTERN
    assert engine.on_output(run, "CUDA out of memory") is None      # 30min 内去抖
    clock.now += 31 * 60
    assert engine.on_output(run, "CUDA out of memory") is not None


def test_gpu_hang(tmp_path):
    store, clock, engine, run = make(tmp_path)
    t0 = clock.now
    # 豁免期内不报
    clock.now = t0 + 3 * 60
    samples = [(t0 + i * 5, 0.0) for i in range(36)]
    assert engine.check_gpu_hang(store.get_run(run.id), samples) is None
    # 过豁免期+窗口覆盖+全程低于阈值 → 报
    clock.now = t0 + 20 * 60
    samples = [(clock.now - 660 + i * 5, 2.0) for i in range(133)]
    ev = engine.check_gpu_hang(store.get_run(run.id), samples)
    assert ev is not None and ev.type == GPU_HANG and ev.level == "critical"
    # 去抖
    assert engine.check_gpu_hang(store.get_run(run.id), samples) is None
    # 有高利用率样本 → 不报
    store2, clock2, engine2, run2 = make(tmp_path / "b")
    clock2.now += 20 * 60
    hot = [(clock2.now - 660 + i * 5, 80.0) for i in range(133)]
    assert engine2.check_gpu_hang(store2.get_run(run2.id), hot) is None
    # 窗口未覆盖(样本历史不足 10 分钟)→ 不报
    short = [(clock2.now - 120 + i * 5, 0.0) for i in range(24)]
    assert engine2.check_gpu_hang(store2.get_run(run2.id), short) is None


def test_log_silence(tmp_path):
    store, clock, engine, run = make(tmp_path)
    store.update_run(run.id, last_output_at=clock.now)
    assert engine.check_log_silence(store.get_run(run.id)) is None
    clock.now += 31 * 60
    ev = engine.check_log_silence(store.get_run(run.id))
    assert ev is not None and ev.type == LOG_SILENCE and ev.level == "warning"
    assert engine.check_log_silence(store.get_run(run.id)) is None  # 去抖


def test_disk(tmp_path):
    _, clock, engine, _ = make(tmp_path)
    assert engine.check_disk([("/", 50.0)]) is None
    ev = engine.check_disk([("/", 95.0), ("/data", 91.0)])
    assert ev is not None and ev.type == DISK_FULL and ev.run_id is None and "95" in ev.body
    assert engine.check_disk([("/", 95.0)]) is None                 # 去抖
    clock.now += 31 * 60
    assert engine.check_disk([("/", 95.0)]) is not None


def test_mute_suppresses_alerts_not_exit(tmp_path):
    store, clock, engine, run = make(tmp_path)
    store.update_run(run.id, muted_until=clock.now + 3600, last_output_at=clock.now)
    run = store.get_run(run.id)
    # 告警类被静音
    assert engine.on_output(run, "Traceback (most recent call last):") is None
    clock.now += 31 * 60
    assert engine.check_log_silence(store.get_run(run.id)) is None
    # 完成/失败不受影响
    assert engine.on_exit(store.get_run(run.id), 1).type == FAILED


def test_emit_records_payload(tmp_path):
    import json
    store, _, engine, run = make(tmp_path)
    engine.on_exit(run, 0)
    rows = store.events_since(0)
    payload = json.loads(rows[-1]["payload"])
    assert payload["type"] == COMPLETED and "train" in payload["title"]
