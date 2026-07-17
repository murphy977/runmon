"""真实的小型训练示例:numpy 两层 MLP 学习双螺旋分类。
输出兼容 RunMon 的进度解析(Epoch x/y、tqdm 行、loss=)。"""
import sys
import time

import numpy as np

rng = np.random.default_rng(42)

# 双螺旋数据
n = 2000
t = rng.uniform(0, 3 * np.pi, n)
labels = rng.integers(0, 2, n)
r = t + rng.normal(0, 0.3, n)
X = np.stack([r * np.cos(t + labels * np.pi), r * np.sin(t + labels * np.pi)], 1) / 10.0
y = labels.astype(np.float64)

# 两层 MLP
H = 64
W1 = rng.normal(0, 0.5, (2, H)); b1 = np.zeros(H)
W2 = rng.normal(0, 0.5, (H, 1)); b2 = np.zeros(1)
lr = 0.5

EPOCHS, STEPS, BATCH = 6, 100, 64

def mmss(s):
    s = int(s)
    return f"{s // 60:02d}:{s % 60:02d}"

start = time.time()
total = EPOCHS * STEPS
done = 0
for epoch in range(1, EPOCHS + 1):
    print(f"Epoch {epoch}/{EPOCHS}", flush=True)
    for step in range(STEPS):
        idx = rng.integers(0, n, BATCH)
        xb, yb = X[idx], y[idx][:, None]
        # 前向
        h = np.tanh(xb @ W1 + b1)
        logits = h @ W2 + b2
        p = 1 / (1 + np.exp(-logits))
        loss = float(-(yb * np.log(p + 1e-9) + (1 - yb) * np.log(1 - p + 1e-9)).mean())
        # 反向
        dlogits = (p - yb) / BATCH
        dW2 = h.T @ dlogits; db2 = dlogits.sum(0)
        dh = dlogits @ W2.T * (1 - h ** 2)
        dW1 = xb.T @ dh; db1 = dh.sum(0)
        W1 -= lr * dW1; b1 -= lr * db1; W2 -= lr * dW2; b2 -= lr * db2

        done += 1
        pct = int(done / total * 100)
        elapsed = time.time() - start
        remain = elapsed / done * (total - done)
        rate = done / elapsed if elapsed > 0 else 0
        bar = "█" * (pct // 5) + " " * (20 - pct // 5)
        sys.stdout.write(
            f"\r{pct}%|{bar}| {done}/{total} "
            f"[{mmss(elapsed)}<{mmss(remain)}, {rate:5.2f}it/s] loss={loss:.4f}")
        sys.stdout.flush()
        time.sleep(0.45)
    sys.stdout.write("\n")

# 最终精度
h = np.tanh(X @ W1 + b1)
acc = float((((1 / (1 + np.exp(-(h @ W2 + b2)))) > 0.5).ravel() == (y > 0.5)).mean())
print(f"Training complete. final_loss 已收敛, accuracy={acc:.4f}", flush=True)
