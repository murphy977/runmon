"""交互式 pty shell:供 App 远程终端使用。输出经回调实时上报,输入写回 pty。
默认关闭(config.enable_terminal),需服务器显式开启——等于开放远程 shell。"""
from __future__ import annotations

import fcntl
import os
import pty
import signal
import struct
import termios
from collections.abc import Callable


class PtyShell:
    def __init__(self, on_output: Callable[[str], None]) -> None:
        self.on_output = on_output
        self.pid: int | None = None
        self.fd: int | None = None
        self._loop = None

    def open(self, loop, rows: int = 24, cols: int = 80,
             cwd: str | None = None) -> None:
        pid, fd = pty.fork()
        if pid == 0:  # 子进程:换成登录 shell
            if cwd:
                try:
                    os.chdir(cwd)
                except OSError:
                    pass
            env = dict(os.environ)
            env["TERM"] = "xterm-256color"
            shell = env.get("SHELL", "/bin/bash")
            try:
                os.execvpe(shell, [shell, "-i"], env)
            except Exception:
                os.execvpe("/bin/sh", ["/bin/sh", "-i"], env)
            os._exit(1)
        self.pid, self.fd, self._loop = pid, fd, loop
        self.resize(rows, cols)
        loop.add_reader(fd, self._on_readable)

    def _on_readable(self) -> None:
        try:
            data = os.read(self.fd, 65536)
        except OSError:
            self.close()
            return
        if not data:
            self.close()
            return
        self.on_output(data.decode("utf-8", errors="replace"))

    def write(self, data: str) -> None:
        if self.fd is not None:
            try:
                os.write(self.fd, data.encode())
            except OSError:
                self.close()

    def resize(self, rows: int, cols: int) -> None:
        if self.fd is not None:
            try:
                fcntl.ioctl(self.fd, termios.TIOCSWINSZ,
                            struct.pack("HHHH", rows, cols, 0, 0))
            except OSError:
                pass

    @property
    def alive(self) -> bool:
        return self.fd is not None

    def close(self) -> None:
        if self.fd is not None:
            try:
                self._loop.remove_reader(self.fd)
            except Exception:
                pass
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None
        if self.pid is not None:
            try:
                os.kill(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(self.pid, os.WNOHANG)
            except ChildProcessError:
                pass
            self.pid = None
