# RunMon · 长任务陪伴器

**手机实时监控服务器上的训练、爬虫、长脚本。** 还在跑吗?GPU 在干活吗?跑完了没?——挂了第一时间知道。端到端加密,自托管,零侵入。

> 跑了几个小时的训练中途报错,GPU 空闲半天没人知道;吃饭睡觉还惦记着 ssh 上去看一眼——RunMon 就是为了消灭这件事。

`v1.0.0` · Python + Flutter · MIT · 端到端加密

---

## 能做什么

- 📱 **手机看实时状态** —— 任务在不在跑、终端输出实时流、进度 / loss / ETA(从日志零埋点解析,不改一行训练代码)
- 📈 **资源曲线** —— GPU 利用率 / 显存 / CPU / 内存,实时曲线
- 🔔 **六类事件必达** —— 完成、失败、报错输出、**GPU 假死(进程活着却不干活)**、日志静默、磁盘写满;通道走 ntfy / Bark / Telegram / webhook,App 被系统杀了也收得到
- 🎮 **远程操作** —— 停止、重跑、拉完整日志、跑完自动关机(租卡党省钱)
- 💻 **完整交互终端** —— 手机上开一个真终端跑任意命令,和 SSH 一样
- 🔗 **零侵入接入** —— 新任务 `mon run -- python train.py` 包一层;已在 tmux 里跑了十小时的任务 `mon attach` 直接接管
- 🔒 **端到端加密 · 自托管** —— 训练日志和命令全程密文,中转服务自己部署,数据不过任何第三方

## 快速开始(三步)

**1. 服务器上装 agent、配对、跑任务**
```bash
pip install runmon
mon pair                    # 打印二维码;默认用公共体验中转,生产可 --relay 自建
mon run -- python train.py  # 你原本的命令,前面包一层
```

**2. 手机装 App** —— 到 [Releases](../../releases) 下载 `RunMon-arm64.apk`(现代安卓都是 arm64)

**3. App 里扫码配对** —— 扫服务器终端打印的二维码,完事。

之后 `mon daemon` 常驻保持连接,或 `mon logs -f` 在电脑上跟随任意任务(含后台重跑)。

## 架构

```
 GPU 服务器(可多台)              relay(自托管)              手机
┌────────────────┐          ┌─────────────┐          ┌──────────────┐
│ runmon agent    │─出站WSS─→ │   FastAPI   │ ←─WSS出站─│  Flutter App │
│ mon run/attach  │          │  只存密文    │          │ 面板/曲线/终端 │
│ GPU/事件引擎     │          └──────┬──────┘          └──────────────┘
│ 通知直发 ────────┼──出站─→ ntfy / Bark / Telegram ──→ 手机必达通知
└────────────────┘
```

- **全出站** —— 服务器和手机都不需要公网 IP,不要求同一局域网,relay 是唯一有公网地址的一方
- **通知直发** —— 任务事件从服务器直达通知通道,不依赖 relay;agent 单独就是完整可用的产品
- **端到端加密** —— 经 relay 的业务数据全部 ChaCha20-Poly1305 密文,密钥只在 agent 和 App 两端,relay 被入侵也只见密文

## 自托管 relay

relay 是一个轻量 FastAPI 服务,转发几 KB 级的加密文本 + 心跳,1 核 1G 绰绰有余。

```bash
pip install runmon-relay
python -m runmon_relay --host 127.0.0.1 --port 8080
```

生产部署建议挂在 nginx 子域名后(带 WebSocket upgrade)+ certbot 证书,模板见 [`relay/deploy/`](relay/deploy/)。

## 目录

| 目录 | 内容 |
|---|---|
| `agent/` | Python 包 `runmon`,CLI `mon` |
| `relay/` | Python 包 `runmon-relay`,FastAPI 中转 |
| `app/` | Flutter 手机 App(安卓,可复用出 iOS) |
| `site/` | 官网(自包含静态页) |
| `docs/` | 设计文档与实施计划 |

## 安全

- 业务数据端到端加密(ChaCha20-Poly1305),密钥经配对二维码带外交换,relay 永不经手
- 远程操作分两层:白名单指令(停止/重跑/日志/关机)+ 交互终端(默认信任已配对设备,可在 agent config `enable_terminal = false` 硬禁用)
- 设备 token 独立、只存哈希,配对码一次性且限时

## License

[MIT](LICENSE)
