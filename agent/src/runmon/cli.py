from __future__ import annotations

import argparse
import os
import signal
import sys
import time

from .config import Config, config_path
from .events import format_duration
from .store import RunStore


def _strip_dashdash(cmd: list[str]) -> list[str]:
    return cmd[1:] if cmd and cmd[0] == "--" else cmd


def cmd_run(args) -> int:
    command = _strip_dashdash(args.command)
    if not command:
        print("错误:缺少要运行的命令。用法:mon run -- python train.py", file=sys.stderr)
        return 2
    from .runner import RunWrapper
    wrapper = RunWrapper(command, name=args.name, gpu_indices=args.gpu)
    return wrapper.execute()


def _duration(run) -> str:
    end = run.ended_at or time.time()
    return format_duration(end - run.started_at)


def cmd_ls(_args) -> int:
    runs = RunStore().list_runs()
    if not runs:
        print("(还没有任务。用 mon run -- <命令> 启动一个)")
        return 0
    print(f"{'ID':<10}{'NAME':<32}{'STATUS':<11}{'PROGRESS':<10}DURATION")
    for r in runs:
        prog = f"{r.progress:.0f}%" if r.progress is not None else "-"
        print(f"{r.id[:8]:<10}{r.name[:30]:<32}{r.status:<11}{prog:<10}{_duration(r)}")
    return 0


def cmd_status(args) -> int:
    store = RunStore()
    run = store.resolve_run(args.run)
    if run is None:
        print(f"找不到任务:{args.run}", file=sys.stderr)
        return 1
    print(f"id: {run.id}\nname: {run.name}\ncommand: {run.command}\ncwd: {run.cwd}")
    print(f"status: {run.status}\nexit_code: {run.exit_code}\npid: {run.pid}")
    print(f"duration: {_duration(run)}")
    if run.progress is not None:
        eta = f",预计还需 {format_duration(run.eta_seconds)}" if run.eta_seconds else ""
        print(f"progress: {run.progress:.0f}%{eta}")
    if run.last_loss is not None:
        print(f"loss: {run.last_loss}")
    print(f"log: {run.log_path}")
    tail_lines = run.output_tail.replace("\r", "\n").splitlines()[-20:]
    if tail_lines:
        print("--- 输出尾部 ---")
        print("\n".join(tail_lines))
    return 0


def stop_run(store: RunStore, ident: str, escalate_wait: float = 10.0) -> bool:
    run = store.resolve_run(ident)
    if run is None or run.status != "running" or not run.pid:
        return False
    import psutil

    def alive() -> bool:
        try:  # 僵尸(已死待 reap)视为已停止
            return psutil.Process(run.pid).status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
        if not alive():
            break
        try:
            os.killpg(run.pid, sig)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                os.kill(run.pid, sig)
            except ProcessLookupError:
                break
        deadline = time.time() + escalate_wait
        while time.time() < deadline:
            if not alive():
                break
            time.sleep(0.2)
    if alive():
        return False
    store.update_run(run.id, status="stopped", ended_at=time.time())
    return True


def cmd_stop(args) -> int:
    store = RunStore()
    if stop_run(store, args.run, escalate_wait=args.wait):
        print("已停止")
        return 0
    print(f"停止失败或任务不在运行:{args.run}", file=sys.stderr)
    return 1


def _interactive_channels() -> list[dict]:
    channels: list[dict] = []
    print("配置通知通道(直接回车跳过该项):")
    if topic := input("ntfy topic(推荐,手机装 ntfy app 订阅同名 topic): ").strip():
        server = input("ntfy 服务器 [https://ntfy.sh]: ").strip() or "https://ntfy.sh"
        channels.append({"type": "ntfy", "topic": topic, "server": server})
    if key := input("Bark 设备 key(iPhone 装 Bark 获取): ").strip():
        channels.append({"type": "bark", "key": key})
    if tg := input("Telegram <bot_token>:<chat_id>: ").strip():
        token, _, chat = tg.rpartition(":")
        if token and chat:
            channels.append({"type": "telegram", "bot_token": token, "chat_id": chat})
    if url := input("通用 webhook URL: ").strip():
        channels.append({"type": "webhook", "url": url})
    return channels


def cmd_init(args) -> int:
    from .events import Event
    from .notify import Notifier, make_channels

    cfg = Config.load()
    new: list[dict] = []
    if args.ntfy_topic:
        c = {"type": "ntfy", "topic": args.ntfy_topic}
        if args.ntfy_server:
            c["server"] = args.ntfy_server
        new.append(c)
    if args.bark_key:
        c = {"type": "bark", "key": args.bark_key}
        if args.bark_server:
            c["server"] = args.bark_server
        new.append(c)
    if args.telegram:
        token, _, chat = args.telegram.rpartition(":")
        if not token or not chat:
            print("错误:--telegram 需要 BOT_TOKEN:CHAT_ID 格式", file=sys.stderr)
            return 2
        new.append({"type": "telegram", "bot_token": token, "chat_id": chat})
    if args.webhook:
        new.append({"type": "webhook", "url": args.webhook})
    if not new and not args.reset:
        new = _interactive_channels()

    existing = [] if args.reset else [c for c in cfg.channels if c not in new]
    cfg.channels = existing + new
    cfg.save()
    print(f"已保存 {len(cfg.channels)} 个通道")
    print(f"配置文件:{config_path()}")

    if not args.no_test and cfg.channels:
        store = RunStore()
        notifier = Notifier(store, make_channels(cfg))
        notifier.notify(Event(type="test", level="info", title="👋 RunMon 测试通知",
                              body="通道配置成功,任务事件将从这里推送"))
        if notifier.flush(timeout=15):
            print("✅ 测试通知已全部送达")
        else:
            print("⚠️ 部分通道未送达(将自动重试),请检查配置", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mon", description="RunMon — 长任务陪伴器")
    sub = parser.add_subparsers(dest="cmd")

    p_run = sub.add_parser("run", help="包装并监控一个命令")
    p_run.add_argument("--name", help="任务名(默认取命令本身)")
    p_run.add_argument("--gpu", default="", help="显式关联 GPU 序号,如 0,1")
    p_run.add_argument("command", nargs=argparse.REMAINDER)
    p_run.set_defaults(func=cmd_run)

    p_ls = sub.add_parser("ls", help="列出任务")
    p_ls.set_defaults(func=cmd_ls)

    p_status = sub.add_parser("status", help="查看任务详情")
    p_status.add_argument("run", help="任务 id/前缀/名字")
    p_status.set_defaults(func=cmd_status)

    p_stop = sub.add_parser("stop", help="停止任务(SIGINT→SIGTERM→SIGKILL)")
    p_stop.add_argument("run")
    p_stop.add_argument("--wait", type=float, default=10.0, help="每级信号等待秒数")
    p_stop.set_defaults(func=cmd_stop)

    p_init = sub.add_parser("init", help="配置通知通道")
    p_init.add_argument("--ntfy-topic")
    p_init.add_argument("--ntfy-server")
    p_init.add_argument("--bark-key")
    p_init.add_argument("--bark-server")
    p_init.add_argument("--telegram", metavar="BOT_TOKEN:CHAT_ID")
    p_init.add_argument("--webhook")
    p_init.add_argument("--no-test", action="store_true")
    p_init.add_argument("--reset", action="store_true", help="清空已有通道后再写入")
    p_init.set_defaults(func=cmd_init)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    return args.func(args)
