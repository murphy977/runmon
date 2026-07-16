import os
import subprocess
import sys
import time

from runmon.sampler import GpuSample, disk_usage, process_tree, util_for_indices, util_for_pids


def gs(index, util, pids):
    return GpuSample(index=index, util_pct=util, mem_used_mb=0, mem_total_mb=0, temp_c=0, pids=pids)


def test_util_for_pids():
    samples = [gs(0, 90, {111: 4000}), gs(1, 5, {222: 100})]
    assert util_for_pids(samples, {111}) == 90
    assert util_for_pids(samples, {111, 222}) == 90
    assert util_for_pids(samples, {999}) is None
    assert util_for_pids([], {111}) is None


def test_util_for_indices():
    samples = [gs(0, 30, {}), gs(1, 70, {})]
    assert util_for_indices(samples, {1}) == 70
    assert util_for_indices(samples, {0, 1}) == 70
    assert util_for_indices(samples, {5}) is None


def test_process_tree():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        time.sleep(0.2)
        tree = process_tree(os.getpid())
        assert os.getpid() in tree and child.pid in tree
    finally:
        child.kill()
        child.wait()
    assert process_tree(99999999) == set()


def test_disk_usage_returns_mounts():
    mounts = disk_usage()
    assert mounts and all(0 <= pct <= 100 for _, pct in mounts)
