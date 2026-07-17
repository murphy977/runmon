from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import tomli_w


def config_path() -> Path:
    if p := os.environ.get("RUNMON_CONFIG"):
        return Path(p)
    base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "runmon" / "config.toml"


def data_dir() -> Path:
    if p := os.environ.get("RUNMON_DATA_DIR"):
        d = Path(p)
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
        d = base / "runmon"
    (d / "logs").mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class Config:
    hang_gpu_threshold_pct: int = 5
    hang_gpu_minutes: int = 10
    hang_warmup_minutes: int = 5
    silence_minutes: int = 30
    disk_threshold_pct: int = 90
    debounce_minutes: int = 30
    sample_interval_s: int = 5
    ring_buffer_kb: int = 512
    notify_include_tail: int = 0
    shutdown_command: str = "sudo -n shutdown -h +1"
    enable_terminal: bool = True  # 默认信任已配对 App;设 false 可硬禁用远程终端
    channels: list[dict] = field(default_factory=list)
    relay: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        p = path or config_path()
        if not p.exists():
            return cls()
        data = tomllib.loads(p.read_text(encoding="utf-8"))
        channels = data.pop("channel", [])
        relay = data.pop("relay", {})
        known = {f for f in cls.__dataclass_fields__ if f not in ("channels", "relay")}
        cfg = cls(**{k: v for k, v in data.items() if k in known})
        cfg.channels = list(channels)
        cfg.relay = dict(relay)
        return cfg

    def save(self, path: Path | None = None) -> None:
        p = path or config_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        channels = data.pop("channels")
        relay = data.pop("relay")
        if relay:  # TOML 要求标量在前、表在后
            data["relay"] = relay
        data["channel"] = channels
        p.write_text(tomli_w.dumps(data), encoding="utf-8")
        p.chmod(0o600)
