from __future__ import annotations

from dataclasses import dataclass

import psutil

try:
    import pynvml
    pynvml.nvmlInit()
    _NVML = True
except Exception:
    _NVML = False


@dataclass
class GpuSample:
    index: int
    util_pct: int
    mem_used_mb: int
    mem_total_mb: int
    temp_c: int
    pids: dict[int, int]


def gpu_available() -> bool:
    return _NVML


def sample_gpus() -> list[GpuSample]:
    if not _NVML:
        return []
    out: list[GpuSample] = []
    try:
        for i in range(pynvml.nvmlDeviceGetCount()):
            h = pynvml.nvmlDeviceGetHandleByIndex(i)
            util = pynvml.nvmlDeviceGetUtilizationRates(h).gpu
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
            pids: dict[int, int] = {}
            for fn in (pynvml.nvmlDeviceGetComputeRunningProcesses,
                       pynvml.nvmlDeviceGetGraphicsRunningProcesses):
                try:
                    for p in fn(h):
                        pids[p.pid] = (p.usedGpuMemory or 0) // (1024 * 1024)
                except Exception:
                    pass
            out.append(GpuSample(i, util, mem.used // (1024 * 1024),
                                 mem.total // (1024 * 1024), temp, pids))
    except Exception:
        return out
    return out


def util_for_pids(samples: list[GpuSample], pids: set[int]) -> float | None:
    hosts = [s for s in samples if pids & set(s.pids)]
    if not hosts:
        return None
    return float(max(s.util_pct for s in hosts))


def util_for_indices(samples: list[GpuSample], indices: set[int]) -> float | None:
    hosts = [s for s in samples if s.index in indices]
    if not hosts:
        return None
    return float(max(s.util_pct for s in hosts))


def process_tree(root_pid: int) -> set[int]:
    try:
        p = psutil.Process(root_pid)
        return {root_pid} | {c.pid for c in p.children(recursive=True)}
    except psutil.NoSuchProcess:
        return set()


def disk_usage() -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    for part in psutil.disk_partitions(all=False):
        try:
            out.append((part.mountpoint, psutil.disk_usage(part.mountpoint).percent))
        except OSError:
            continue
    return out
