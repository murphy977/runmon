import json

from runmon.config import Config
from runmon.gpuwait import GpuWaiter, HoldTracker, WaitSpec, qualified
from runmon.sampler import GpuSample
from runmon.store import RunStore


class FakeClock:
    def __init__(self, now=10000.0):
        self.now = now

    def __call__(self):
        return self.now


def g(index, used, total=81920, util=0):
    return GpuSample(index=index, util_pct=util, mem_used_mb=used,
                     mem_total_mb=total, temp_c=40, pids={})


def test_qualified_whole_card():
    samples = [
        g(0, 500),               # 空卡(残留 500MB 容忍)
        g(1, 500, util=50),      # 显存空但在算 → 排除
        g(2, 5000),              # 占用超 5%(4096MB)→ 排除
        g(3, 900, total=8192),   # 小卡:阈值取 max(5%, 1GB)=1024,900 可过
    ]
    good = qualified(samples, None)
    assert [s.index for s in good] == [0, 3]  # 空闲显存多的在前


def test_qualified_free_gb():
    samples = [g(0, 40000, util=95), g(1, 60000), g(2, 10000)]
    good = qualified(samples, 30.0)  # 共卡模式:只看空闲显存,忙卡也算
    assert [s.index for s in good] == [2, 0]


def test_hold_tracker():
    clock = FakeClock()
    t = HoldTracker(120, clock=clock)
    assert not t.feed(True)          # 开始计时
    clock.now += 60
    assert not t.feed(True)
    assert not t.feed(False)         # 中断复位
    clock.now += 120
    assert not t.feed(True)          # 重新计时
    clock.now += 120
    assert t.feed(True)
    assert HoldTracker(0, clock=clock).feed(True)  # hold=0 立即触发


def test_waiter_fires_after_hold(tmp_path):
    store = RunStore(tmp_path / "t.db")
    clock = FakeClock()
    free = [g(0, 500), g(1, 500)]
    seq = iter([[g(0, 70000)]])      # 第一轮不满足,之后一直满足

    def sample():
        return next(seq, free)

    def sleep(_s):
        clock.now += 60              # 每轮推进 1 分钟

    spec = WaitSpec(count=2, free_gb=None, hold_minutes=2)
    w = GpuWaiter(spec, store=store, config=Config(),
                  sample_fn=sample, clock=clock, sleep=sleep)
    assert w.execute() == 0
    payload = json.loads(store.events_since(0)[-1]["payload"])
    assert payload["type"] == "gpu_free" and payload["level"] == "critical"
    assert "2 张卡" in payload["title"] and "卡0" in payload["body"]


def test_wait_requires_gpu(monkeypatch, capsys):
    import runmon.sampler as sampler
    from runmon.cli import main
    monkeypatch.setattr(sampler, "_NVML", False)
    assert main(["wait"]) == 1
    assert "NVIDIA" in capsys.readouterr().err


# ---------- daemon 侧蹲卡(App 下发) ----------

def hbg(index, used, total=81920, util=0):
    return {"index": index, "util": util, "mem_used": used, "mem_total": total}


def test_set_watch_validation(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNMON_DATA_DIR", str(tmp_path))
    from runmon import gpuwait
    assert not gpuwait.set_watch({"cards": {}})["ok"]
    assert not gpuwait.set_watch({"cards": {"a": 1}})["ok"]
    assert gpuwait.set_watch({"cards": {"0": None, "2": 30}})["ok"]
    assert gpuwait.load_watch()["cards"] == {"0": None, "2": 30.0}


def test_set_watch_command_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNMON_DATA_DIR", str(tmp_path))
    cfg = tmp_path / "c.toml"
    cfg.write_text("enable_terminal = false\n", encoding="utf-8")
    monkeypatch.setenv("RUNMON_CONFIG", str(cfg))
    from runmon import gpuwait
    r = gpuwait.set_watch({"cards": {"0": None}, "command": "python x.py"})
    assert not r["ok"] and "enable_terminal" in r["error"]
    # 不带命令则允许
    assert gpuwait.set_watch({"cards": {"0": None}})["ok"]


def test_watch_manager_fires_once(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNMON_DATA_DIR", str(tmp_path))
    from runmon import gpuwait
    assert gpuwait.set_watch(
        {"cards": {"0": None, "2": 30}, "hold_minutes": 1})["ok"]
    store = RunStore(tmp_path / "t.db")
    clock = FakeClock()
    mgr = gpuwait.GpuWatchManager(store, Config(), clock=clock)
    # 卡2 空闲不足 30GB → 未达标
    st = mgr.poll([hbg(0, 500), hbg(2, 60000)])
    assert st is not None and not st["ok"]
    assert [s["ok"] for s in st["card_states"]] == [True, False]
    # 达标 → 开始计时,未到 hold 不触发
    st = mgr.poll([hbg(0, 500), hbg(2, 40000)])
    assert st["ok"] and "fired" not in st
    # 超过 hold → 触发 + watch 清除(一次性)
    clock.now += 120
    st = mgr.poll([hbg(0, 500), hbg(2, 40000)])
    assert st.get("fired") is True
    assert gpuwait.load_watch() is None
    payload = json.loads(store.events_since(0)[-1]["payload"])
    assert payload["type"] == "gpu_free" and "卡0" in payload["body"]
    assert mgr.poll([hbg(0, 500), hbg(2, 40000)]) is None


def test_watch_missing_card_not_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNMON_DATA_DIR", str(tmp_path))
    from runmon import gpuwait
    gpuwait.set_watch({"cards": {"5": None}, "hold_minutes": 0})
    mgr = gpuwait.GpuWatchManager(RunStore(tmp_path / "t.db"), Config(),
                                  clock=FakeClock())
    st = mgr.poll([hbg(0, 500)])  # 卡 5 不存在 → 永不达标
    assert st is not None and not st["ok"] and "fired" not in st
