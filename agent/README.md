<div align="center">

[![English](https://img.shields.io/badge/English-2563EB?style=for-the-badge)](README.md) [![简体中文](https://img.shields.io/badge/简体中文-64748B?style=for-the-badge)](README.zh-CN.md)

</div>

# runmon

**Long-job companion** — when a training run, crawler, or long script is running on your server, your phone knows the moment it "finished, failed, or silently stalled." Zero-instrumentation, not a line of training code changed.

`runmon` is the Python CLI (`mon`) you install on the server that runs your jobs. It does two things: it **pushes notifications** to your phone when something happens, and — paired with the RunMon app — it streams a **live view** you can watch and remote-control from your phone.

## Install

```bash
pip install runmon
```

Requires Python ≥ 3.10. GPU metrics use NVIDIA NVML; on a machine without a GPU it degrades gracefully (everything else keeps working).

---

## Two ways to use it

### A · Notifications only — no app, no relay

The lightest setup: you just want your phone to buzz when a job finishes, fails, or stalls. **No RunMon app needed** — notifications arrive in the ntfy / Bark / WeCom / Telegram app you already have.

```bash
# 1. Configure a channel (pick one)
mon init --ntfy-topic my-secret-topic-2333   # ntfy: install the ntfy app, subscribe to this topic
mon init --wecom-key <webhook>               # WeCom (企业微信) group bot — most reliable in China
mon init --bark-key <key>                    # iOS Bark

# 2. Wrap your command
mon run -- python train.py
```

Done — the six event types below get pushed to your phone.

### B · Live monitoring on your phone — RunMon app + relay

The full experience: watch the **live terminal**, resource charts, progress/ETA, and **remote-control** the job from the RunMon app.

```bash
# 1. Pair with the app (one time). Prints a QR code — scan it in the app.
mon pair

# 2. Keep the connection alive. The phone sees live data ONLY while this runs.
#    Run it in tmux/nohup so it survives after you disconnect (see "mon daemon" below).
mon daemon

# 3. Run your job (in another shell)
mon run -- python train.py
```

Now open the app: live terminal, GPU/CPU/memory curves, progress/loss/ETA, and buttons to **stop / re-run / pull logs / open a terminal**.

> **First time?** Run `mon demo` instead of a real job to test the whole chain end-to-end.

---

## Command reference

| Command | What it does |
|---|---|
| `mon run -- <cmd>` | Run and monitor a command (the everyday wrapper) |
| `mon attach` | Take over a job already running in tmux — no restart |
| `mon daemon` | Keep the live connection to your phone open |
| `mon pair` | Pair with the RunMon app (prints a QR code) |
| `mon init` | Configure notification channels |
| `mon ls` | List jobs (progress / elapsed) |
| `mon status <job>` | Job details + output tail + ETA/loss |
| `mon stop <job>` | Stop a job (SIGINT → SIGTERM → SIGKILL) |
| `mon logs -f <job>` | Follow a job's output live |
| `mon demo` | Run a fake training job to test the setup |

### `mon run` — wrap and monitor

```bash
mon run -- python train.py                          # simplest — your command after the --
mon run --name exp1 --gpu 0,1 -- python train.py    # name the job + bind specific GPUs
```
Progress, ETA, and loss are parsed automatically from stdout (works with tqdm / `Epoch x/y` / `loss=…`) — no instrumentation needed. Try `mon demo` / `mon demo --fail` first to see it in action.

### `mon attach` — take over a tmux job

Already have a job running in a tmux session (maybe you started it days ago)? Take it over **without restarting**:
```bash
mon attach            # attach to the job in the current tmux pane
```
From then on it's monitored exactly like a `mon run` job — events, live view, and remote control all apply.

### `mon daemon` — keep the phone connection alive

`mon daemon` is the bridge to your phone: it syncs job state to the relay and receives your remote commands. **The live view in the app only works while the daemon is running.** (Notifications from `mon run` do *not* need it — those go out directly.)

**Keep it alive across SSH disconnects** — otherwise it dies when you close the terminal and the phone stops seeing live data:
```bash
# tmux (recommended)
tmux new -s mon
mon daemon
# press Ctrl+B then D to detach; come back later with:  tmux attach -t mon

# or nohup in the background
nohup mon daemon > ~/mon-daemon.log 2>&1 &
```

### `mon pair` — pair with the app

```bash
mon pair                                  # uses the default public relay; prints a QR code
mon pair --relay https://your-relay.com   # point at your own self-hosted relay
```
Scan the printed QR code in the RunMon app to link this server to your phone. One-time per server.

### `mon logs` — follow output

```bash
mon logs -f exp1      # tail -f style; works even for backgrounded re-runs
```

### `mon ls` / `mon status` / `mon stop` — manage jobs

```bash
mon ls                # all jobs, with progress and elapsed time
mon status exp1       # details + output tail + ETA/loss
mon stop exp1         # stop (SIGINT → SIGTERM → SIGKILL)
```

---

## What lands on your phone (six events)

| Event | Trigger (default, configurable) | Level |
|---|---|---|
| ✅ Done | exit code 0 | info |
| ❌ Failed | non-zero exit code | critical |
| ⚠️ Error output | log shows Traceback / CUDA OOM / Segfault | critical |
| 🧊 GPU stall | process alive but GPU utilization <5% for 10 min | critical |
| 🤫 Log silence | no new output for 30 min | warning |
| 💾 Disk alert | any mount point over 90% used | warning |

The same kind of event notifies at most once per 30 minutes; failed notifications retry with exponential backoff (up to 1 hour) and are persisted locally so nothing is lost.

## Notification channels

`mon init` accepts combinations and can push to several channels at once:

```bash
mon init --ntfy-topic TOPIC [--ntfy-server https://your-self-hosted-ntfy]
mon init --bark-key KEY                  # iOS Bark
mon init --wecom-key WEBHOOK_URL         # WeCom (企业微信) group bot — most reliable in China
mon init --telegram BOT_TOKEN:CHAT_ID    # Telegram bot
mon init --webhook https://your/hook     # generic webhook (Feishu / DingTalk / custom)
```

## Config

Config lives in `~/.config/runmon/config.toml`; all thresholds are adjustable:

```toml
hang_gpu_minutes = 20      # GPU-stall detection window
silence_minutes = 60       # log-silence alert
disk_threshold_pct = 85
```

## Notes

- GPU sampling relies on NVIDIA NVML; on machines without a GPU it degrades gracefully.
- For the phone app, self-hosting the relay, and the big picture, see the [project README](../README.md).
