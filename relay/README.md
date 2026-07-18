<div align="center">

[![English](https://img.shields.io/badge/English-2563EB?style=for-the-badge)](README.md) [![简体中文](https://img.shields.io/badge/简体中文-64748B?style=for-the-badge)](README.zh-CN.md)

</div>

# RunMon Relay

**The self-hosted relay for [RunMon](https://github.com/murphy977/runmon)** — it forwards end-to-end-encrypted ciphertext between the agent on your GPU server and the mobile app.

Neither the server nor the phone needs a public IP; both dial **outbound** to the relay. The relay is the only party with a public address, and it only ever stores ciphertext — even if it's compromised, your training logs stay unreadable. It forwards a few KB of encrypted text plus heartbeats, so **1 core / 1 GB is plenty**.

> Most people don't need to self-host: `mon pair` uses a public relay by default, so you can start right away. You only need the setup below if you want your data to run entirely on your own server.

---

## First, tell the two apart: local test vs. production deployment

**Just want to try it locally** — one command is enough:

```bash
pip install runmon-relay
python -m runmon_relay --host 127.0.0.1 --port 8080
```

But like this it **only listens on localhost and only speaks plain HTTP** — your phone and other servers can't reach it. To actually serve the agent and the app you need the production setup below, because clients connect over **WSS (encrypted WebSocket)**, and the relay itself doesn't handle TLS — that's nginx's job out front.

Production deployment in one line: **relay runs on localhost:8080 (plaintext) → nginx terminates TLS on 443 + reverse-proxies the WebSocket → certbot issues the certificate → systemd keeps it alive.**

---

## Production deployment (5 steps)

### Prerequisites

- A server **with a public IP** (both the agent and the phone connect to it)
- A domain whose DNS you can edit
- `python3` (≥3.10), `nginx`, and `certbot` (`certbot` + `python3-certbot-nginx`) installed on the server

### 1. Install the relay into its own directory

Use a dedicated venv and service account, isolated from the system Python:

```bash
sudo useradd -r -s /usr/sbin/nologin runmon        # service account (recommended, least privilege)
sudo mkdir -p /opt/runmon-relay
sudo python3 -m venv /opt/runmon-relay/venv
sudo /opt/runmon-relay/venv/bin/pip install runmon-relay
sudo chown -R runmon:runmon /opt/runmon-relay
```

### 2. Keep it running with systemd

Download the ready-made unit file (it already sets `MemoryMax=300M` for small machines and auto-restarts on crash):

```bash
sudo curl -fsSL https://raw.githubusercontent.com/murphy977/runmon/main/relay/deploy/runmon-relay.service \
     -o /etc/systemd/system/runmon-relay.service
sudo systemctl daemon-reload
sudo systemctl enable --now runmon-relay
systemctl status runmon-relay        # should be active (running)
curl http://127.0.0.1:8080/health    # should return {"ok":true}
```

At this point the relay is running on `127.0.0.1:8080`, but only reachable from the machine itself.

### 3. Add a DNS A record

Point a subdomain at your server's public IP:

```
mon.example.com    A    YOUR_SERVER_IP
```

Wait for it to take effect (`dig mon.example.com` resolves to your IP) before continuing — certbot needs the domain to resolve in order to issue a certificate.

### 4. nginx reverse proxy

Download the ready-made template — **the important part is the WebSocket upgrade headers**; the agent's and phone's long-lived connections depend on them, and without them you get 404s:

```bash
sudo curl -fsSL https://raw.githubusercontent.com/murphy977/runmon/main/relay/deploy/nginx-example.conf \
     -o /etc/nginx/sites-available/runmon-relay.conf
sudo sed -i 's/mon.example.com/mon.your-domain.com/g' /etc/nginx/sites-available/runmon-relay.conf
sudo ln -s /etc/nginx/sites-available/runmon-relay.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 5. certbot issues the HTTPS certificate

```bash
sudo certbot --nginx -d mon.example.com
```

certbot automatically fills the certificate paths into your nginx config, adds the 80→443 redirect, and sets up auto-renewal.

### Verify

```bash
curl https://mon.example.com/health     # should return {"ok":true}
```

If you get `{"ok":true}`, you're set. Users then point their pairing at your address:

```bash
mon pair --relay https://mon.example.com
```

---

## Cloudflare / CDN note

If your domain sits behind Cloudflare or another CDN (orange-cloud proxy), it may strip the WebSocket upgrade request that uses a **default User-Agent**, breaking the connection. RunMon's agent already sends `User-Agent: runmon/x.y.z` to get around this; but if you write your own client or debug by hand, remember to send a non-default UA. Origin pulls should use 443 (Full/Strict SSL mode).

## Security notes

- All business data through the relay is **ChaCha20-Poly1305 ciphertext**; keys live only on the agent and the app. The relay only stores and forwards, so a compromised relay only ever sees ciphertext.
- Device tokens are stored only as hashes; pairing codes are single-use and time-limited.
- The relay should only listen on `127.0.0.1` (as above), with nginx as the single public entry point — don't expose `--host 0.0.0.0` directly to the internet.

## This package isn't the day-to-day entry point

What you use day to day on the GPU server is the agent package:

```bash
pip install runmon
```

For the full introduction, the mobile app download, and the quick start, see the **[project homepage](https://runmon.linxiexie.com)** and the **[GitHub repo](https://github.com/murphy977/runmon)**.

## License

MIT
