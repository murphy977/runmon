<div align="center">

[![English](https://img.shields.io/badge/English-2563EB?style=for-the-badge)](README.md) [![简体中文](https://img.shields.io/badge/简体中文-64748B?style=for-the-badge)](README.zh-CN.md)

</div>

# runmon

**Long-job companion** — when a training run, crawler, or long script is running on your server, your phone knows the moment it "finished, failed, or silently stalled." Zero-instrumentation, not a line of training code changed.

## Quick start

```bash
pip install runmon

# 1. Configure a notification channel (ntfy is easiest: install the ntfy app and subscribe to a custom topic)
mon init --ntfy-topic my-secret-topic-2333

# 2. Wrap your command with mon run
mon run -- python train.py

# Try the demo first
mon demo            # completes normally → you get a ✅ notification
mon demo --fail     # simulates an error → you get ⚠️ + ❌ notifications
```

## What lands on your phone

| Event | Trigger (default, configurable) | Level |
|---|---|---|
| ✅ Done | exit code 0 | info |
| ❌ Failed | non-zero exit code | critical |
| ⚠️ Error output | log shows Traceback / CUDA OOM / Segfault | critical |
| 🧊 GPU stall | process alive but GPU utilization <5% for 10 min | critical |
| 🤫 Log silence | no new output for 30 min | warning |
| 💾 Disk alert | any mount point over 90% used | warning |

The same kind of event notifies at most once per 30 minutes; failed notifications retry with exponential backoff (up to 1 hour) and are persisted locally so nothing is lost.

## Common commands

```bash
mon run --name exp1 --gpu 0,1 -- python train.py   # name a job and bind specific GPUs
mon ls                                              # job list (progress / elapsed)
mon status exp1                                     # details + output tail + ETA/loss
mon stop exp1                                       # stop (SIGINT→SIGTERM→SIGKILL)
```

Progress, ETA, and loss are parsed automatically from stdout (works with tqdm / `Epoch x/y` / `loss=…`) — no instrumentation needed.

## Notification channels

`mon init` accepts combinations and can push to several channels at once:

```bash
mon init --ntfy-topic TOPIC [--ntfy-server https://your-self-hosted-ntfy]
mon init --bark-key KEY                  # iOS Bark
mon init --wecom-key WEBHOOK_URL         # WeCom (企业微信) group bot — most reliable for China
mon init --telegram BOT_TOKEN:CHAT_ID    # Telegram bot
mon init --webhook https://your/hook     # generic webhook (Feishu / DingTalk / custom)
```

Config lives in `~/.config/runmon/config.toml`; all thresholds are adjustable:

```toml
hang_gpu_minutes = 20      # GPU-stall detection window
silence_minutes = 60       # log-silence alert
disk_threshold_pct = 85
```

## Notes

- GPU sampling relies on NVIDIA NVML; on machines without a GPU it degrades gracefully (everything else keeps working).
- The mobile app (live dashboard / remote control / interactive terminal) and `mon attach` (take over a job already running in tmux) are shipped — see the [project README](../README.md) for the full picture.
