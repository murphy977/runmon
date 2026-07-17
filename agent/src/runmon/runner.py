from __future__ import annotations

import json
import os
import pty
import select
import shlex
import signal
import subprocess
import sys
import termios
import threading
import time
import tty

from . import sampler
from .config import Config, data_dir
from .events import EventEngine
from .notify import Notifier, make_channels
from .progress import ProgressParser
from .store import RunStore


class RunWrapper:
    def __init__(self, command: list[str], name: str | None = None,
                 store: RunStore | None = None, config: Config | None = None,
                 notifier: Notifier | None = None, gpu_indices: str = "") -> None:
        self.command = command
        self.config = config or Config.load()
        self.store = store or RunStore()
        self.notifier = notifier or Notifier(self.store, make_channels(self.config))
        self.engine = EventEngine(self.store, self.config)
        self.parser = ProgressParser()
        self.gpu_indices = gpu_indices
        display = shlex.join([os.path.basename(command[0])] + list(command[1:]))
        self.name = name or display[:60]
        self.run = None
        self.child_pid: int | None = None
        self._gpu_history: list[tuple[float, float]] = []
        self._last_progress_write = 0.0

    def execute(self) -> int:
        log_dir = data_dir() / "logs"
        self.run = self.store.create_run(
            name=self.name, command=shlex.join(self.command), cwd=os.getcwd(),
            log_path="", gpu_indices=self.gpu_indices)
        log_path = log_dir / f"{self.run.id}.log"
        self.store.update_run(self.run.id, log_path=str(log_path))
        try:  # rerun 用的环境快照(仅存本机)
            (log_dir / f"{self.run.id}.env.json").write_text(
                json.dumps(dict(os.environ)), encoding="utf-8")
        except Exception:
            pass

        pid, master = pty.fork()
        if pid == 0:  # 子进程
            os.execvp(self.command[0], self.command)
        self.child_pid = pid
        self.store.update_run(self.run.id, pid=pid, status="running")
        self.notifier.start()  # 在 fork 之后再起线程,避免多线程 fork 风险

        stop_monitor = threading.Event()
        mon = threading.Thread(target=self._monitor, args=(stop_monitor,), daemon=True)
        mon.start()
        try:
            exit_code = self._pump(master, log_path)
        finally:
            stop_monitor.set()
            mon.join(timeout=2)

        status = "completed" if exit_code == 0 else "failed"
        st = self.parser.state
        final_progress = 100.0 if (exit_code == 0 and st.percent is not None) else st.percent
        self.store.update_run(self.run.id, status=status, exit_code=exit_code,
                              ended_at=time.time(), progress=final_progress,
                              eta_seconds=None if exit_code == 0 else st.eta_seconds,
                              last_loss=st.loss)
        try:
            ev = self.engine.on_exit(self.store.get_run(self.run.id), exit_code)
            self.notifier.notify(ev)
            self.notifier.flush(timeout=15)
            self.notifier.stop()
        except Exception:
            pass
        try:
            final = self.store.get_run(self.run.id)
            if final is not None and final.shutdown_after:
                print("\n[mon] 任务结束,按设置执行自动关机…", flush=True)
                subprocess.run(shlex.split(self.config.shutdown_command), timeout=30)
        except Exception as exc:
            print(f"[mon] 自动关机失败:{exc}", flush=True)
        return exit_code

    def _pump(self, master: int, log_path) -> int:
        stdin_fd = sys.stdin.fileno() if sys.stdin.isatty() else None
        old_attrs = None
        if stdin_fd is not None:
            try:
                old_attrs = termios.tcgetattr(stdin_fd)
                tty.setcbreak(stdin_fd)
            except termios.error:
                stdin_fd = None

        def fwd(signum, _frame):
            try:
                os.kill(self.child_pid, signum)
            except ProcessLookupError:
                pass

        old_int = signal.signal(signal.SIGINT, fwd)
        old_term = signal.signal(signal.SIGTERM, fwd)
        log = open(log_path, "ab")
        try:
            while True:
                fds = [master] + ([stdin_fd] if stdin_fd is not None else [])
                try:
                    r, _, _ = select.select(fds, [], [], 1.0)
                except InterruptedError:
                    continue
                if master in r:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    if not chunk:
                        break
                    try:
                        os.write(sys.stdout.fileno(), chunk)
                    except OSError:
                        pass
                    log.write(chunk)
                    log.flush()
                    self._ingest(chunk.decode("utf-8", errors="replace"))
                if stdin_fd is not None and stdin_fd in r:
                    data = os.read(stdin_fd, 4096)
                    if data:
                        os.write(master, data)
        finally:
            log.close()
            signal.signal(signal.SIGINT, old_int)
            signal.signal(signal.SIGTERM, old_term)
            if old_attrs is not None:
                termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_attrs)
            os.close(master)
        _, status = os.waitpid(self.child_pid, 0)
        if os.WIFEXITED(status):
            return os.WEXITSTATUS(status)
        if os.WIFSIGNALED(status):
            return 128 + os.WTERMSIG(status)
        return 1

    def _ingest(self, text: str) -> None:
        try:
            self.store.append_output(self.run.id, text,
                                     self.config.ring_buffer_kb * 1024)
            if ev := self.engine.on_output(self.run, text):
                self.notifier.notify(ev)
            if self.parser.feed(text) and time.time() - self._last_progress_write > 1.0:
                st = self.parser.state
                self.store.update_run(self.run.id, progress=st.percent,
                                      eta_seconds=st.eta_seconds, last_loss=st.loss)
                self._last_progress_write = time.time()
        except Exception:
            pass  # 监控故障不影响任务

    def _monitor(self, stop: threading.Event) -> None:
        while not stop.wait(self.config.sample_interval_s):
            try:
                now = time.time()
                samples = sampler.sample_gpus()
                if self.gpu_indices:
                    idxs = {int(i) for i in self.gpu_indices.split(",") if i.strip()}
                    util = sampler.util_for_indices(samples, idxs)
                else:
                    util = sampler.util_for_pids(
                        samples, sampler.process_tree(self.child_pid))
                run = self.store.get_run(self.run.id)
                if run is None:
                    continue
                pending = []
                if util is not None:
                    self._gpu_history.append((now, util))
                    cutoff = now - (self.config.hang_gpu_minutes + 5) * 60
                    self._gpu_history = [(t, u) for t, u in self._gpu_history if t >= cutoff]
                    if ev := self.engine.check_gpu_hang(run, self._gpu_history):
                        pending.append(ev)
                if ev := self.engine.check_log_silence(run):
                    pending.append(ev)
                if ev := self.engine.check_disk(sampler.disk_usage()):
                    pending.append(ev)
                for ev in pending:
                    self.notifier.notify(ev)
            except Exception:
                pass  # 监控故障不影响任务
