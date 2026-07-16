"""演示脚本:模拟训练输出,用于测试与演示 RunMon。"""
from __future__ import annotations

import argparse
import sys
import time


def mmss(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"


def main() -> int:
    ap = argparse.ArgumentParser(description="RunMon 演示训练脚本")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--delay", type=float, default=0.1)
    ap.add_argument("--fail", action="store_true", help="在 60%% 进度处抛异常")
    ap.add_argument("--hang", action="store_true", help="在 50%% 进度处永久卡住")
    args = ap.parse_args()

    total = args.epochs * args.steps
    done = 0
    for epoch in range(1, args.epochs + 1):
        print(f"Epoch {epoch}/{args.epochs}", flush=True)
        for _step in range(args.steps):
            done += 1
            pct = int(done / total * 100)
            loss = 2.0 / done ** 0.5
            if args.hang and pct >= 50:
                print("\ndata loader stalled...", flush=True)
                while True:
                    time.sleep(60)
            if args.fail and pct >= 60:
                raise RuntimeError("simulated CUDA out of memory")
            bar = "█" * (pct // 5) + " " * (20 - pct // 5)
            elapsed = done * args.delay
            remain = (total - done) * args.delay
            rate = 1.0 / args.delay if args.delay > 0 else 999.0
            sys.stdout.write(
                f"\r{pct}%|{bar}| {done}/{total} "
                f"[{mmss(elapsed)}<{mmss(remain)}, {rate:5.1f}it/s] loss={loss:.4f}")
            sys.stdout.flush()
            time.sleep(args.delay)
        sys.stdout.write("\n")
    print("Training complete.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
