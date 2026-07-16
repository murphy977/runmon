from __future__ import annotations

import re
import time
from dataclasses import dataclass

COMPLETED = "completed"
FAILED = "failed"
ERROR_PATTERN = "error_pattern"
GPU_HANG = "gpu_hang"
LOG_SILENCE = "log_silence"
DISK_FULL = "disk_full"

ERROR_PATTERNS = [
    re.compile(r"Traceback \(most recent call last\)"),
    re.compile(r"CUDA out of memory"),
    re.compile(r"CUDA error", re.IGNORECASE),
    re.compile(r"\bSegmentation fault\b"),
    re.compile(r"^Killed$", re.MULTILINE),
]


def format_duration(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}秒"
    if s < 3600:
        return f"{s // 60}分{s % 60}秒"
    return f"{s // 3600}小时{s % 3600 // 60}分"


@dataclass
class Event:
    type: str
    level: str
    title: str
    body: str
    run_id: str | None = None


class EventEngine:
    def __init__(self, store, config, clock=time.time) -> None:
        self.store = store
        self.config = config
        self.clock = clock

    def _debounced(self, run_id: str | None, etype: str) -> bool:
        last = self.store.last_event_at(run_id, etype)
        return last is not None and self.clock() - last < self.config.debounce_minutes * 60

    def _emit(self, run_id: str | None, etype: str, level: str, title: str, body: str) -> Event:
        self.store.record_event(run_id, etype, self.clock())
        return Event(etype, level, title, body, run_id)

    def on_exit(self, run, exit_code: int) -> Event:
        dur = format_duration(self.clock() - run.started_at)
        if exit_code == 0:
            return self._emit(run.id, COMPLETED, "info", f"✅ {run.name} 完成", f"耗时 {dur}")
        return self._emit(run.id, FAILED, "critical",
                          f"❌ {run.name} 失败 (exit {exit_code})", f"耗时 {dur}")

    def on_output(self, run, chunk: str) -> Event | None:
        for pat in ERROR_PATTERNS:
            if pat.search(chunk):
                if self._debounced(run.id, ERROR_PATTERN):
                    return None
                return self._emit(run.id, ERROR_PATTERN, "critical",
                                  f"⚠️ {run.name} 检测到错误输出", f"匹配:{pat.pattern}")
        return None

    def check_gpu_hang(self, run, samples: list[tuple[float, float]]) -> Event | None:
        now = self.clock()
        if now - run.started_at < self.config.hang_warmup_minutes * 60:
            return None
        window = self.config.hang_gpu_minutes * 60
        if not samples or now - samples[0][0] < window:
            return None
        in_window = [u for ts, u in samples if now - ts <= window]
        if not in_window or max(in_window) >= self.config.hang_gpu_threshold_pct:
            return None
        if self._debounced(run.id, GPU_HANG):
            return None
        return self._emit(run.id, GPU_HANG, "critical", f"🧊 {run.name} 疑似假死",
                          f"GPU 利用率已连续 {self.config.hang_gpu_minutes} 分钟低于 "
                          f"{self.config.hang_gpu_threshold_pct}%,进程仍存活")

    def check_log_silence(self, run) -> Event | None:
        last = run.last_output_at or run.started_at
        if self.clock() - last < self.config.silence_minutes * 60:
            return None
        if self._debounced(run.id, LOG_SILENCE):
            return None
        return self._emit(run.id, LOG_SILENCE, "warning", f"🤫 {run.name} 日志静默",
                          f"已 {self.config.silence_minutes} 分钟无新输出")

    def check_disk(self, mounts: list[tuple[str, float]]) -> Event | None:
        over = [(m, p) for m, p in mounts if p >= self.config.disk_threshold_pct]
        if not over:
            return None
        if self._debounced(None, DISK_FULL):
            return None
        mount, pct = max(over, key=lambda x: x[1])
        return self._emit(None, DISK_FULL, "warning", "💾 磁盘空间告警",
                          f"{mount} 已用 {pct:.0f}%")
