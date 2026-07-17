# RunMon Relay

**[RunMon](https://github.com/murphy977/runmon) 的自托管中转服务** —— 在 GPU 服务器上的 agent 和手机 App 之间转发端到端加密的密文。

服务器和手机都不需要公网 IP,双方各自**出站**连到 relay;relay 是唯一有公网地址的一方,且只存密文 —— 被入侵也读不到你的训练日志。

## 安装运行

```bash
pip install runmon-relay
python -m runmon_relay --host 127.0.0.1 --port 8080
```

转发的是几 KB 级的加密文本 + 心跳,1 核 1G 绰绰有余。

## 生产部署

建议挂在 nginx 子域名后(需带 WebSocket upgrade)+ certbot 证书。仓库的
[`relay/deploy/`](https://github.com/murphy977/runmon/tree/main/relay/deploy)
提供了 nginx 站点模板和 systemd unit 文件。

注意:如果域名套了 Cloudflare 等 CDN,默认 UA 的 WebSocket 升级请求可能被拦,
客户端需带 `User-Agent: runmon/x.y.z`(agent 已内置)。

## 这个包不是入口

日常使用装的是 agent 那个包:

```bash
pip install runmon
```

完整介绍、手机 App 下载和快速开始见 **[项目主页](https://runmon.linxiexie.com)**
和 **[GitHub 仓库](https://github.com/murphy977/runmon)**。

## License

MIT
