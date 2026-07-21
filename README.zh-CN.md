<div align="center">

[![English](https://img.shields.io/badge/English-64748B?style=for-the-badge)](README.md) [![简体中文](https://img.shields.io/badge/简体中文-DC2626?style=for-the-badge)](README.zh-CN.md)

</div>

# RunMon · 长任务陪伴器

**手机实时监控服务器上的训练、爬虫、长脚本。** 还在跑吗?GPU 在干活吗?跑完了没?——挂了第一时间知道。端到端加密,自托管,零侵入。

> 跑了几个小时的训练中途报错,GPU 空闲半天没人知道;吃饭睡觉还惦记着 ssh 上去看一眼——RunMon 就是为了消灭这件事。

`v1.0.6` · Python + Flutter · MIT · 端到端加密

---

## 能做什么

- 📱 **手机看实时状态** —— 任务在不在跑、终端输出实时流、进度 / loss / ETA(从日志零埋点解析,不改一行训练代码)
- 📈 **资源曲线** —— GPU 利用率 / 显存 / CPU / 内存,实时曲线
- 🔔 **六类事件必达** —— 完成、失败、报错输出、**GPU 假死(进程活着却不干活)**、日志静默、磁盘写满;通道走 **企业微信** / Bark / ntfy / Telegram / webhook,App 被系统杀了也收得到
- 🎮 **远程操作** —— 停止、重跑、拉完整日志、跑完自动关机(租卡党省钱)
- 🎯 **蹲卡 & 预约执行** —— App 里勾选要蹲的卡、设好空闲门槛,GPU 空出来手机马上响;还能预约一条命令,等到卡自动开跑(终端党用 `mon wait` 一样蹲)
- 💻 **完整交互终端** —— 手机上开一个真终端跑任意命令,和 SSH 一样
- 🔗 **零侵入接入** —— 新任务 `mon run -- python train.py` 包一层;已在 tmux 里跑了十小时的任务 `mon attach` 直接接管
- 🔒 **端到端加密 · 自托管** —— 训练日志和命令全程密文,中转服务自己部署,数据不过任何第三方

## 快速开始

### 在手机上看任务实时画面

**1. 手机装 App** —— 到 [Releases](../../releases) 下载 `RunMon-arm64.apk`(现代安卓都是 arm64)。

**2. 服务器上:装 agent、配对、保持连接**
```bash
pip install runmon
mon pair       # 打印二维码 —— 用 App 扫(默认用公共体验中转)
mon daemon     # 保持开着;手机只有在它开着时才能看到实时数据
```

**3. 跑你的任务**(另开一个终端)
```bash
mon run -- python train.py   # 你原本的命令,前面包一层
```

打开 App,就能看到实时终端、GPU/CPU/内存曲线、进度/ETA,以及停止 / 重跑 / 拉日志 / 开终端的按钮。第一次先跑 `mon demo` 验证整条链路。已经在 tmux 里跑着的任务?用 `mon attach` 代替 `mon run`。

> **小贴士:** `mon daemon` 默认前台运行;加 `-d`(`mon daemon -d`)让它退到后台,或放 `tmux` / `nohup` 里跑,断开 SSH 也不停。
>
> **conda 用户:** `mon` 是系统级工具,不用装进每个虚拟环境 —— 用 `pipx install runmon` 装一次全局可用,切换环境不用重装。

### 只想要通知?(不用装 App)

```bash
pip install runmon
mon init --wecom-key <webhook>   # 或 --bark-key / --ntfy-topic / --telegram
mon run -- python train.py       # 完成 / 失败 / 假死 / … 时手机响
```

### 卡都被占着?蹲个空位

```bash
mon wait --gpus 2 --free-gb 30 -d          # 2 张卡各空出 30GB 显存时,手机马上响(-d 后台蹲)
mon wait --gpus 2 -- python train.py       # 等到 2 张整卡空闲,自动开跑(帮你设好 CUDA_VISIBLE_DEVICES)
```

条件需**持续满足 3 分钟**才触发(`--hold` 可调),不会被别人任务间隙的假空闲骗到。

📖 **完整命令参考(`run` · `wait` · `attach` · `daemon` · `pair` · `logs` · …):** [`agent/README.zh-CN.md`](agent/README.zh-CN.md)。

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

生产部署建议挂在 nginx 子域名后(带 WebSocket upgrade)+ certbot 证书,模板见 [`relay/deploy/`](relay/deploy/),完整分步指南见 [`relay/README.zh-CN.md`](relay/README.zh-CN.md)。

## 目录

| 目录 | 内容 |
|---|---|
| `agent/` | Python 包 `runmon`,CLI `mon` |
| `relay/` | Python 包 `runmon-relay`,FastAPI 中转 |
| `app/` | Flutter 手机 App(安卓,可复用出 iOS) |

## 安全

- 业务数据端到端加密(ChaCha20-Poly1305),密钥经配对二维码带外交换,relay 永不经手
- 远程操作分两层:白名单指令(停止/重跑/日志/关机)+ 交互终端(默认信任已配对设备,可在 agent config `enable_terminal = false` 硬禁用)
- 设备 token 独立、只存哈希,配对码一次性且限时

## License

[MIT](LICENSE)
