# RunMon

**长任务陪伴器 / Long-job companion** —— 手机实时掌握服务器上的训练、爬虫、长脚本:还在跑吗?跑到哪了?GPU 在干活吗?跑完/挂了/假死,第一时间推送到手机。

> 跑了几个小时的训练中途报错,GPU 空闲半天没人知道;吃饭睡觉还惦记着 ssh 上去看一眼——RunMon 就是为了消灭这件事。

## 架构

```
 GPU服务器(可多台)                 relay(自托管)                  手机
┌────────────────┐            ┌─────────────┐            ┌──────────────┐
│ runmon agent    │─出站WSS──→ │   FastAPI   │ ←──WSS出站─│  Flutter app │
│  mon run/attach │            │  只存密文    │            │  面板/曲线/操作│
│  GPU/事件引擎    │            └──────┬──────┘            └──────────────┘
│  通知直发 ───────┼──出站──→ ntfy / Bark / Telegram ──→ 手机必达通知
└────────────────┘
```

- **全出站**:服务器和手机都不需要公网 IP,不要求同一局域网
- **通知直发**:任务事件从服务器直达通知通道,不依赖 relay —— agent 单独就是完整可用的产品
- **端到端加密**:经 relay 的业务数据全部密文,密钥只在你手里

## Roadmap

- [x] **M1 — Agent 单机版**(`agent/`):`mon run` 包装、五类事件(完成/失败/GPU 假死/日志静默/磁盘)、ntfy/Bark/Telegram/webhook 推送、进度/ETA/loss 零埋点解析、`mon ls/status/stop/init/demo`
- [x] **M2a — Relay + agent 联网**(`relay/`):E2EE 全链路(ChaCha20-Poly1305,relay 只存密文)、`mon pair` 配对、`mon daemon` 实时同步(快照/输出尾窗/事件/GPU 心跳)、白名单指令(stop/rerun/tail/mute)、离线指令暂存
- [x] **M2b — 安卓 App**(`app/`,Flutter):配对、服务器列表(在线状态/GPU 条)、任务列表、任务详情(实时终端流/进度/loss/操作按钮)
- [ ] **M2 收尾**:真机联调打磨、二维码扫码配对、事件系统通知、relay 部署上云
- [ ] **M3 — 完全体**:tmux 接管已在跑的任务、多服务器面板、跑完自动关机、Claude Code 等待输入检测

本地联调:`./scripts/dev-stack.sh`(起 relay + 配对 + daemon,手机同 WiFi 粘贴配对载荷即可)。

## 快速开始

见 [agent/README.md](agent/README.md)。TL;DR:

```bash
pip install runmon
mon init --ntfy-topic my-secret-topic
mon run -- python train.py
```

## 文档

- [设计文档(spec)](docs/specs/2026-07-16-runmon-design.md)
- [M1 实施计划](docs/plans/2026-07-16-m1-agent.md)

## License

MIT
