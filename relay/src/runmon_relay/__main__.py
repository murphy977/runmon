"""relay 启动入口:python -m runmon_relay --host 127.0.0.1 --port 8080 --db relay.db"""
from __future__ import annotations

import argparse

import uvicorn

from .app import create_app


def main() -> int:
    ap = argparse.ArgumentParser(prog="runmon-relay")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--db", default="relay.db")
    args = ap.parse_args()
    uvicorn.run(create_app(args.db), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
