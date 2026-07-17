# RunMon Relay

**[RunMon](https://github.com/murphy977/runmon) 的自托管中转服务** —— 在 GPU 服务器上的 agent 和手机 App 之间转发端到端加密的密文。

服务器和手机都不需要公网 IP,双方各自**出站**连到 relay;relay 是唯一有公网地址的一方,且只存密文 —— 被入侵也读不到你的训练日志。转发的是几 KB 级的加密文本 + 心跳,**1 核 1G 绰绰有余**。

> 大多数人不需要自建:`mon pair` 默认会用一个公共体验中转,直接就能上手。只有你想让数据完全走自己的服务器时,才需要下面这套。

---

## 先分清:本机试跑 vs 生产部署

**只想在本机跑一下看看** —— 一条命令就够:

```bash
pip install runmon-relay
python -m runmon_relay --host 127.0.0.1 --port 8080
```

但这样它**只监听本机、只有明文 HTTP**,手机和别的服务器连不进来。要真正给 agent 和手机用,必须做下面的生产部署 —— 因为客户端连的是 **WSS(加密 WebSocket)**,而 relay 自己不管 TLS,得靠前面的 nginx。

三句话概括生产部署:**relay 跑在本机 8080(明文)→ nginx 在 443 做 TLS 终止 + WebSocket 反代 → certbot 签证书 → systemd 保证它一直活着。**

---

## 生产部署(5 步)

### 前提

- 一台**有公网 IP** 的服务器(agent 和手机都往它连)
- 一个你能改 DNS 的域名
- 服务器已装 `python3`(≥3.10)、`nginx`、`certbot`(`certbot` + `python3-certbot-nginx`)

### 1. 装 relay 到独立目录

用一个专门的 venv 和服务账号,和系统 Python 隔离:

```bash
sudo useradd -r -s /usr/sbin/nologin runmon        # 服务账号(推荐,权限最小)
sudo mkdir -p /opt/runmon-relay
sudo python3 -m venv /opt/runmon-relay/venv
sudo /opt/runmon-relay/venv/bin/pip install runmon-relay
sudo chown -R runmon:runmon /opt/runmon-relay
```

### 2. 用 systemd 常驻

下载现成的单元文件(已内置 `MemoryMax=300M`,适合小内存机器,崩了自动重启):

```bash
sudo curl -fsSL https://raw.githubusercontent.com/murphy977/runmon/main/relay/deploy/runmon-relay.service \
     -o /etc/systemd/system/runmon-relay.service
sudo systemctl daemon-reload
sudo systemctl enable --now runmon-relay
systemctl status runmon-relay        # 应为 active (running)
curl http://127.0.0.1:8080/health    # 应返回 {"ok":true}
```

到这里 relay 已经在本机 `127.0.0.1:8080` 跑起来了,但还只有本机能访问。

### 3. DNS 加一条 A 记录

把一个子域名指向服务器公网 IP:

```
mon.example.com    A    你的服务器IP
```

等它生效(`dig mon.example.com` 能解析到你的 IP)再往下走 —— certbot 签证书需要域名先解析得到。

### 4. nginx 反向代理

下载现成模板,**关键是它带了 WebSocket upgrade 头** —— agent 和手机的长连全靠它,漏了会 404:

```bash
sudo curl -fsSL https://raw.githubusercontent.com/murphy977/runmon/main/relay/deploy/nginx-example.conf \
     -o /etc/nginx/sites-available/runmon-relay.conf
sudo sed -i 's/mon.example.com/mon.你的域名.com/g' /etc/nginx/sites-available/runmon-relay.conf
sudo ln -s /etc/nginx/sites-available/runmon-relay.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 5. certbot 签 HTTPS 证书

```bash
sudo certbot --nginx -d mon.example.com
```

certbot 会自动往 nginx 配置里填证书路径、加上 80→443 跳转,并设置自动续期。

### 验证

```bash
curl https://mon.example.com/health     # 应返回 {"ok":true}
```

返回 `{"ok":true}` 就成了。之后让用户配对时指定你的地址:

```bash
mon pair --relay https://mon.example.com
```

---

## Cloudflare / CDN 注意

如果你的域名套了 Cloudflare 等 CDN(橙云代理),它可能会拦掉**默认 UA** 的 WebSocket 升级请求,导致连不上。RunMon 的 agent 已内置 `User-Agent: runmon/x.y.z` 绕过这个问题;但如果你自己写别的客户端或调试,记得带上非默认 UA。回源要走 443(Full/Strict SSL 模式)。

## 安全说明

- 经 relay 的业务数据全部 **ChaCha20-Poly1305 密文**,密钥只在 agent 和 App 两端,relay 只做存储转发,被入侵也只见密文。
- 设备 token 只存哈希;配对码一次性、限时。
- relay 建议只监听 `127.0.0.1`(如上),公网入口统一由 nginx 收口,别把 `--host 0.0.0.0` 直接暴露到公网。

## 这个包不是日常入口

日常在 GPU 服务器上用的是 agent 那个包:

```bash
pip install runmon
```

完整介绍、手机 App 下载和快速开始见 **[项目主页](https://runmon.linxiexie.com)**
和 **[GitHub 仓库](https://github.com/murphy977/runmon)**。

## License

MIT
