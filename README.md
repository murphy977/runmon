<div align="center">

[![English](https://img.shields.io/badge/English-2563EB?style=for-the-badge)](README.md) [![简体中文](https://img.shields.io/badge/简体中文-64748B?style=for-the-badge)](README.zh-CN.md)

</div>

# RunMon · Long-job Companion

**Monitor the training runs, crawlers, and long scripts on your server — live, from your phone.** Still running? Is the GPU actually working? Finished yet? — know the instant something breaks. End-to-end encrypted, self-hosted, zero-instrumentation.

> A training run errors out halfway through and the GPU sits idle for hours with nobody noticing; you keep meaning to SSH in and check — at dinner, in bed. RunMon exists to kill that feeling.

`v1.0.2` · Python + Flutter · MIT · end-to-end encrypted

---

## What it does

- 📱 **Live status on your phone** — whether a job is running, live terminal output, progress / loss / ETA (parsed from your logs with zero instrumentation — not one line of training code changes)
- 📈 **Resource curves** — GPU utilization / VRAM / CPU / memory, as live charts
- 🔔 **Six event types, guaranteed delivery** — done, failed, error output, **GPU stall (process alive but doing no work)**, log silence, disk full; delivered over **WeCom (企业微信)** / Bark / ntfy / Telegram / webhook — you still get them even if the OS kills the app
- 🎮 **Remote control** — stop, re-run, pull full logs, auto-shutdown on finish (saves money on rented GPUs)
- 💻 **Full interactive terminal** — open a real terminal on your phone and run any command, just like SSH
- 🔗 **Zero-instrumentation** — wrap a new job with `mon run -- python train.py`; take over a job that's already been running in tmux for ten hours with `mon attach`
- 🔒 **End-to-end encrypted · self-hosted** — training logs and commands are ciphertext end to end, the relay is your own, data never passes through any third party

## Quick start

### Watch a job live on your phone

**1. Install the app** — grab `RunMon-arm64.apk` from [Releases](../../releases) (modern Android is all arm64).

**2. On the server — install, pair, keep the connection alive**
```bash
pip install runmon
mon pair       # prints a QR code — scan it in the app (uses a public relay by default)
mon daemon     # keep this running; the phone sees live data only while it's up
```

**3. Run your job** (in another shell)
```bash
mon run -- python train.py   # your original command, just wrapped
```

Open the app and you'll see the live terminal, GPU/CPU/memory curves, progress/ETA, and buttons to stop / re-run / pull logs / open a terminal. Run `mon demo` first to test the whole chain. Already have a job in tmux? Use `mon attach` instead of `mon run`.

> **Tip:** run `mon daemon` inside `tmux` (or with `nohup`) so it survives closing your SSH session.

### Just want notifications? (no app needed)

```bash
pip install runmon
mon init --wecom-key <webhook>   # or --bark-key / --ntfy-topic / --telegram
mon run -- python train.py       # phone buzzes on done / fail / stall / …
```

📖 **Full command reference (`run` · `attach` · `daemon` · `pair` · `logs` · …):** [`agent/README.md`](agent/README.md).

## Architecture

```
 GPU server(s)                     relay (self-hosted)          phone
┌────────────────┐          ┌─────────────┐          ┌──────────────┐
│ runmon agent    │──out WSS→ │   FastAPI   │ ←out WSS─│  Flutter App │
│ mon run/attach  │          │ ciphertext  │          │ panel/charts │
│ GPU/event engine│          │    only     │          │  /terminal   │
│ notify direct ──┼──out────→ ntfy / Bark / Telegram ──→ guaranteed push
└────────────────┘
```

- **All outbound** — neither the server nor the phone needs a public IP or the same LAN; the relay is the only party with a public address
- **Direct notifications** — job events go straight from the server to the notification channel, not through the relay; the agent on its own is already a complete, usable product
- **End-to-end encryption** — all business data through the relay is ChaCha20-Poly1305 ciphertext; keys live only on the agent and the app, so a compromised relay only ever sees ciphertext

## Self-hosting the relay

The relay is a lightweight FastAPI service that forwards a few KB of encrypted text plus heartbeats — 1 core / 1 GB is plenty.

```bash
pip install runmon-relay
python -m runmon_relay --host 127.0.0.1 --port 8080
```

For production, put it behind an nginx subdomain (with WebSocket upgrade) + a certbot certificate. Templates are in [`relay/deploy/`](relay/deploy/); full step-by-step guide in [`relay/README.md`](relay/README.md).

## Layout

| Directory | Contents |
|---|---|
| `agent/` | Python package `runmon`, CLI `mon` |
| `relay/` | Python package `runmon-relay`, FastAPI relay |
| `app/` | Flutter mobile app (Android, reusable for iOS) |

## Security

- Business data is end-to-end encrypted (ChaCha20-Poly1305); keys are exchanged out-of-band via the pairing QR code and never touch the relay
- Remote control has two layers: whitelisted commands (stop / re-run / logs / shutdown) + an interactive terminal (trusts paired devices by default, can be hard-disabled with `enable_terminal = false` in the agent config)
- Device tokens are independent and stored only as hashes; pairing codes are single-use and time-limited

## License

[MIT](LICENSE)
