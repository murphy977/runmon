from __future__ import annotations

import argparse
import os
import signal
import sys
import time

from . import __version__
from .config import Config, config_path
from .events import format_duration
from .store import RunStore

# 未指定 --relay 时使用的公共体验中转:零配置即可上手。
# 数据端到端加密,该中转只经手密文;认真使用建议自建 relay(见 README)。
DEFAULT_RELAY = "https://mon.linxiexie.com"


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
    if key := input("企业微信群机器人 webhook 地址(群设置里加机器人获取): ").strip():
        channels.append({"type": "wecom", "key": key})
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
    if args.wecom_key:
        new.append({"type": "wecom", "key": args.wecom_key})
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


def _relay_post(url: str, path: str, body: dict) -> dict:
    import json
    import urllib.request
    req = urllib.request.Request(url.rstrip("/") + path,
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": f"runmon/{__version__}"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def cmd_pair(args) -> int:
    import json
    import socket
    from .crypto import generate_key, key_to_b64

    url = (args.relay or DEFAULT_RELAY).rstrip("/")
    if not args.relay:
        print(f"使用公共体验中转 {url}(端到端加密,仅转发密文)。")
        print("生产环境建议自建:mon pair --relay https://你的relay地址\n")
    name = args.name or socket.gethostname()
    try:
        start = _relay_post(url, "/api/pair/start", {"device_name": name})
    except Exception as exc:
        print(f"无法连接 relay:{exc}", file=sys.stderr)
        return 1
    key_b64 = key_to_b64(generate_key())
    cfg = Config.load()
    cfg.relay = {"url": url, "device_id": start["device_id"],
                 "device_token": start["device_token"], "key": key_b64}
    cfg.save()
    payload = json.dumps({"u": url, "c": start["code"], "k": key_b64},
                         separators=(",", ":"))
    print("用手机 App 扫码,或粘贴以下配对载荷(10 分钟内有效):\n")
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(payload)
        qr.print_ascii(invert=True)
    except Exception:
        pass
    print(f"  {payload}\n")
    print(f"配对码:{start['code']}")
    if args.no_wait:
        return 0
    print("等待手机认领", end="", flush=True)
    deadline = time.time() + 600
    while time.time() < deadline:
        time.sleep(2)
        print(".", end="", flush=True)
        try:
            st = _relay_post(url, "/api/pair/status",
                             {"code": start["code"], "pair_token": start["pair_token"]})
            if st.get("claimed"):
                print(f"\n✅ 已与「{st.get('app_name') or '手机'}」配对。现在运行:mon daemon")
                print("   (加 -d 让它退到后台:mon daemon -d)")
                return 0
        except Exception:
            pass
    print("\n超时未认领,可重新运行 mon pair。")
    return 1


def cmd_daemon(args) -> int:
    if getattr(args, "detach", False):
        import subprocess
        from .config import data_dir
        log = data_dir() / "daemon.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        # 重新以自身在新会话里前台启动 daemon,脱离当前终端(关 SSH 也不停)
        with open(log, "ab") as f:
            proc = subprocess.Popen(
                [sys.executable, "-m", "runmon", "daemon"],
                stdout=f, stderr=f, stdin=subprocess.DEVNULL,
                start_new_session=True)
        print(f"[mon daemon] 已在后台运行 (pid {proc.pid})")
        print(f"  日志:{log}")
        print(f"  停止:kill {proc.pid}")
        return 0
    import asyncio
    from .relay_client import Daemon
    try:
        asyncio.run(Daemon().run_forever())
    except KeyboardInterrupt:
        pass
    return 0


def cmd_attach(args) -> int:
    import shutil
    if not shutil.which("tmux"):
        print("错误:未找到 tmux", file=sys.stderr)
        return 1
    from .attach import TmuxAttach
    try:
        return TmuxAttach(args.target, name=args.name).execute()
    except Exception as exc:
        print(f"接管失败:{exc}", file=sys.stderr)
        return 1


def cmd_logs(args) -> int:
    import time as _t
    store = RunStore()
    run = store.resolve_run(args.run) if args.run else (
        store.list_runs(limit=1)[0] if store.list_runs(limit=1) else None)
    if run is None:
        print("找不到任务(用 mon ls 看看有哪些)", file=sys.stderr)
        return 1
    if not run.log_path or not os.path.exists(run.log_path):
        print(f"任务「{run.name}」还没有日志文件", file=sys.stderr)
        return 1
    print(f"—— {run.name}({run.status})日志 ——", file=sys.stderr)
    with open(run.log_path, "rb") as f:
        if not args.all:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 200 * 1024))  # 默认只回放尾部 200KB
        sys.stdout.buffer.write(f.read())
        sys.stdout.flush()
        if not args.follow:
            return 0
        try:
            while True:
                chunk = f.read()
                if chunk:
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.flush()
                    continue
                latest = store.get_run(run.id)
                if latest and latest.status not in ("running", "created"):
                    sys.stdout.buffer.write(f.read())
                    sys.stdout.flush()
                    print(f"\n—— 任务已{latest.status} ——", file=sys.stderr)
                    break
                _t.sleep(0.5)
        except KeyboardInterrupt:
            print("\n(停止跟随,任务不受影响)", file=sys.stderr)
    return 0


def cmd_demo(args) -> int:
    demo_args = [sys.executable, "-m", "runmon.demo_train"]
    if args.fail:
        demo_args.append("--fail")
    if args.hang:
        demo_args.append("--hang")
    from .runner import RunWrapper
    return RunWrapper(demo_args, name="runmon-demo").execute()


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
    p_init.add_argument("--wecom-key", help="企业微信群机器人 webhook 地址或 key")
    p_init.add_argument("--telegram", metavar="BOT_TOKEN:CHAT_ID")
    p_init.add_argument("--webhook")
    p_init.add_argument("--no-test", action="store_true")
    p_init.add_argument("--reset", action="store_true", help="清空已有通道后再写入")
    p_init.set_defaults(func=cmd_init)

    p_pair = sub.add_parser("pair", help="与手机 App 配对(经 relay)")
    p_pair.add_argument("--relay", default=None,
                        help="relay 地址,如 https://mon.example.com;不填则用公共体验中转")
    p_pair.add_argument("--name", help="本机显示名(默认 hostname)")
    p_pair.add_argument("--no-wait", action="store_true", help="不等待手机认领")
    p_pair.set_defaults(func=cmd_pair)

    p_daemon = sub.add_parser("daemon", help="常驻守护:同步状态到 relay 并接收指令")
    p_daemon.add_argument("-d", "--detach", action="store_true",
                          help="退到后台运行,不占用终端(关 SSH 也不停)")
    p_daemon.set_defaults(func=cmd_daemon)

    p_attach = sub.add_parser("attach", help="接管已在 tmux 里跑的任务")
    p_attach.add_argument("target", help="tmux 目标,如 会话名 / 会话:窗口.窗格")
    p_attach.add_argument("--name", help="任务名(默认 tmux:<目标>)")
    p_attach.set_defaults(func=cmd_attach)

    p_logs = sub.add_parser("logs", help="查看/实时跟随任务输出(后台重跑也能看)")
    p_logs.add_argument("run", nargs="?", help="任务 id/前缀/名字(缺省取最新)")
    p_logs.add_argument("-f", "--follow", action="store_true", help="实时跟随(Ctrl+C 退出)")
    p_logs.add_argument("--all", action="store_true", help="从头输出全部(默认只尾部 200KB)")
    p_logs.set_defaults(func=cmd_logs)

    p_demo = sub.add_parser("demo", help="跑一个演示训练任务")
    p_demo.add_argument("--fail", action="store_true")
    p_demo.add_argument("--hang", action="store_true")
    p_demo.set_defaults(func=cmd_demo)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    return args.func(args)
