<div align="center">

[![English](https://img.shields.io/badge/English-64748B?style=for-the-badge)](README.md) [![简体中文](https://img.shields.io/badge/简体中文-DC2626?style=for-the-badge)](README.zh-CN.md)

</div>

# runmon

**长任务陪伴器** —— 服务器上跑训练/爬虫/长脚本时,手机第一时间知道"跑完了、挂了、还是假死了"。零侵入,不改一行训练代码。

`runmon` 是装在**跑任务的服务器**上的 Python 命令行工具(`mon`)。它做两件事:出事时给手机**推通知**;以及——配上 RunMon App——把任务的**实时画面**推到手机,让你能看、能远程操作。

## 安装

```bash
pip install runmon
```

需要 Python ≥ 3.10。GPU 指标依赖 NVIDIA NVML;没有 GPU 的机器上自动降级(其余功能不受影响)。

> **conda 用户:** `mon` 是系统级工具,不用装进每个虚拟环境 —— 用 `pipx install runmon` 装一次全局可用,切换环境不用重装。

---

## 两种用法

### A · 只要通知 —— 不装 App、不用 relay

最轻的用法:你只想"任务跑完/挂了/假死时手机响一下"。**不需要 RunMon App** —— 通知直接进你手机上已有的 ntfy / Bark / 企业微信 / Telegram。

```bash
# 1. 配一个通道(选一个)
mon init --ntfy-topic my-secret-topic-2333   # ntfy:手机装 ntfy app,订阅这个 topic
mon init --wecom-key <webhook>               # 企业微信群机器人(国内最稳)
mon init --bark-key <key>                    # iOS Bark

# 2. 包一层跑任务
mon run -- python train.py
```

完事——下面的六类事件就会推到你手机。

### B · 手机看实时画面 —— RunMon App + relay

完整体验:在 RunMon App 里看**实时终端**、资源曲线、进度/ETA,还能**远程操作**任务。

```bash
# 1. 与 App 配对(只做一次)。会打印二维码,用 App 扫。
mon pair

# 2. 保持连接。手机只有在这个进程开着时才能看到实时数据。
#    建议放 tmux/nohup 里跑,断开 SSH 也不停(见下方 "mon daemon")。
mon daemon

# 3. 跑你的任务(另开一个终端)
mon run -- python train.py
```

打开 App,就能看到:实时终端、GPU/CPU/内存曲线、进度/loss/ETA,以及**停止 / 重跑 / 拉日志 / 开终端**的按钮。

> **第一次用?** 先用 `mon demo` 代替真任务,把整条链路跑通验证一下。

---

## 命令速查

| 命令 | 作用 |
|---|---|
| `mon run -- <命令>` | 包装并监控一个命令(日常主力) |
| `mon wait` | 蹲 GPU 空位:空出来手机响;带命令则等到后自动开跑(预约执行) |
| `mon attach` | 接管已经在 tmux 里跑的任务 —— 不用重启 |
| `mon daemon` | 保持与手机的实时连接 |
| `mon pair` | 与 RunMon App 配对(打印二维码) |
| `mon init` | 配置通知通道 |
| `mon ls` | 列出任务(进度 / 耗时) |
| `mon status <任务>` | 任务详情 + 输出尾部 + ETA/loss |
| `mon stop <任务>` | 停止任务(SIGINT → SIGTERM → SIGKILL) |
| `mon logs -f <任务>` | 实时跟随任务输出 |
| `mon demo` | 跑个假训练任务,测试整套是否通 |

### `mon run` —— 包装并监控

```bash
mon run -- python train.py                          # 最简单 —— 你的命令跟在 -- 后面
mon run --name exp1 --gpu 0,1 -- python train.py    # 命名任务 + 显式关联 GPU
```
进度、ETA、loss 从 stdout 自动解析(兼容 tqdm / `Epoch x/y` / `loss=…`),无需埋点。先用 `mon demo` / `mon demo --fail` 看看效果。

### `mon wait` —— 蹲卡 & 预约执行

卡都被占着?让 RunMon 帮你盯,空出来第一时间手机响;带上命令还能等到后直接开跑:

```bash
mon wait --gpus 2 --free-gb 30 -d       # 2 张卡各空出 30GB 显存 → 手机马上响(-d 后台蹲)
mon wait --gpus 2 -- python train.py    # 等到 2 张整卡空闲 → 自动开跑,帮你设好 CUDA_VISIBLE_DEVICES
```

- 不带 `--free-gb` 时要求**整卡空闲**(利用率 ≤10% 且显存占用 ≤5%);带上则只看空闲显存够不够(可与他人共卡)
- 条件需**持续满足 3 分钟**才触发(`--hold` 调整,0 为立即),别人任务间隙的假空闲骗不到它
- 预约启动的任务就是一个普通 `mon run`:实时画面、事件通知、远程操作全都有

### `mon attach` —— 接管 tmux 里的任务

已经有个任务在 tmux 会话里跑着(可能几天前就起的)?**不用重启**,直接接管:
```bash
mon attach            # 接管当前 tmux 窗格里的任务
```
之后它就和 `mon run` 起的任务一样被监控——事件、实时画面、远程操作全都有。

### `mon daemon` —— 保持与手机的连接

`mon daemon` 是通往手机的桥梁:把任务状态同步到 relay,并接收你的远程指令。**App 里的实时画面只有在 daemon 开着时才有。**(`mon run` 的通知**不**依赖它,那是直发的。)

默认它是**前台**运行、占着终端。**想让它退到后台**(关 SSH 也不停):

```bash
mon daemon -d      # 后台运行,立刻把终端还给你
                   # 会打印 pid 和日志路径;之后停止:kill <pid>
```

想自己管?也可以用 tmux 或 nohup:
```bash
tmux new -s mon; mon daemon          # Ctrl+B 再按 D 退出;tmux attach -t mon 回来
nohup mon daemon > ~/mon-daemon.log 2>&1 &
```

### `mon pair` —— 与 App 配对

```bash
mon pair                                  # 用默认公共中转;打印二维码
mon pair --relay https://你的relay地址     # 指向你自建的 relay
```
用 RunMon App 扫打印出来的二维码,就把这台服务器和你手机绑定了。每台服务器配一次即可。

### `mon logs` —— 跟随输出

```bash
mon logs -f exp1      # 类似 tail -f;后台重跑的任务也能跟
```

### `mon ls` / `mon status` / `mon stop` —— 管理任务

```bash
mon ls                # 所有任务,带进度和耗时
mon status exp1       # 详情 + 输出尾部 + ETA/loss
mon stop exp1         # 停止(SIGINT → SIGTERM → SIGKILL)
```

---

## 你会在手机上收到什么(六类事件)

| 事件 | 触发条件(默认,可配) | 级别 |
|---|---|---|
| ✅ 完成 | 退出码 0 | 信息 |
| ❌ 失败 | 退出码非 0 | 严重 |
| ⚠️ 错误输出 | 日志出现 Traceback / CUDA OOM / Segfault | 严重 |
| 🧊 GPU 假死 | 进程活着但 GPU 利用率 <5% 持续 10 分钟 | 严重 |
| 🤫 日志静默 | 30 分钟无新输出 | 警告 |
| 💾 磁盘告警 | 任一挂载点使用率 >90% | 警告 |

同类事件 30 分钟内只提醒一次;通知失败自动指数退避重试(最长 1 小时),本地持久化不丢。

## 通知通道

`mon init` 支持组合配置,可同时推多个通道:

```bash
mon init --ntfy-topic TOPIC [--ntfy-server https://你的自托管ntfy]
mon init --bark-key KEY                  # iOS Bark
mon init --wecom-key WEBHOOK_URL         # 企业微信群机器人(国内最稳)
mon init --telegram BOT_TOKEN:CHAT_ID    # Telegram bot
mon init --webhook https://your/hook     # 通用 webhook(飞书/钉钉/自定义)
```

## 配置

配置写在 `~/.config/runmon/config.toml`,阈值均可修改:

```toml
hang_gpu_minutes = 20      # 假死判定窗口
silence_minutes = 60       # 静默告警
disk_threshold_pct = 85
```

## 说明

- GPU 采集依赖 NVIDIA NVML,无 GPU 的机器上自动降级。
- 手机 App、自托管 relay、整体介绍见[仓库根 README](../README.zh-CN.md)。
