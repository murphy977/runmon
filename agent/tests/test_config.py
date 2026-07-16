from pathlib import Path

from runmon.config import Config, config_path, data_dir


def test_defaults():
    cfg = Config()
    assert cfg.hang_gpu_threshold_pct == 5
    assert cfg.hang_gpu_minutes == 10
    assert cfg.hang_warmup_minutes == 5
    assert cfg.silence_minutes == 30
    assert cfg.disk_threshold_pct == 90
    assert cfg.debounce_minutes == 30
    assert cfg.sample_interval_s == 5
    assert cfg.ring_buffer_kb == 512
    assert cfg.notify_include_tail == 0
    assert cfg.channels == []


def test_roundtrip(tmp_path):
    p = tmp_path / "config.toml"
    cfg = Config(silence_minutes=15)
    cfg.channels = [{"type": "ntfy", "topic": "t1"}, {"type": "webhook", "url": "http://x"}]
    cfg.save(p)
    loaded = Config.load(p)
    assert loaded.silence_minutes == 15
    assert loaded.channels == cfg.channels


def test_load_missing_returns_defaults(tmp_path):
    assert Config.load(tmp_path / "nope.toml").silence_minutes == 30


def test_env_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNMON_CONFIG", str(tmp_path / "c.toml"))
    monkeypatch.setenv("RUNMON_DATA_DIR", str(tmp_path / "data"))
    assert config_path() == tmp_path / "c.toml"
    d = data_dir()
    assert d == tmp_path / "data"
    assert (d / "logs").is_dir()
