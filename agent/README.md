# runmon

**长任务陪伴器** —— 服务器上跑训练/爬虫/长脚本时,手机第一时间知道"跑完了、挂了、还是假死了"。零侵入,不改一行训练代码。

## 快速开始

```bash
pip install runmon

# 1. 配置通知通道(推荐 ntfy:手机装 ntfy app,订阅一个自定义 topic 即可)
mon init --ntfy-topic my-secret-topic-2333

# 2. 用 mon run 包装你的命令
mon run -- python train.py

# 先试试演示任务
mon demo            # 正常完成 → 收到 ✅ 通知
mon demo --fail     # 模拟报错 → 收到 ⚠️ + ❌ 通知
```

## 你会在手机上收到什么

| 事件 | 触发条件(默认,可配) | 级别 |
|---|---|---|
| ✅ 完成 | 退出码 0 | 信息 |
| ❌ 失败 | 退出码非 0 | 严重 |
| ⚠️ 错误输出 | 日志出现 Traceback / CUDA OOM / Segfault | 严重 |
| 🧊 GPU 假死 | 进程活着但 GPU 利用率 <5% 持续 10 分钟 | 严重 |
| 🤫 日志静默 | 30 分钟无新输出 | 警告 |
| 💾 磁盘告警 | 任一挂载点使用率 >90% | 警告 |

同类事件 30 分钟内只提醒一次;通知失败自动指数退避重试(最长 1 小时),本地持久化不丢。

## 常用命令

```bash
mon run --name exp1 --gpu 0,1 -- python train.py   # 命名任务并显式关联 GPU
mon ls                                              # 任务列表(进度/耗时)
mon status exp1                                     # 详情 + 输出尾部 + ETA/loss
mon stop exp1                                       # 停止(SIGINT→SIGTERM→SIGKILL)
```

进度、ETA、loss 从 stdout 自动解析(兼容 tqdm / `Epoch x/y` / `loss=…`),无需埋点。

## 通知通道

`mon init` 支持组合配置,可同时推多个通道:

```bash
mon init --ntfy-topic TOPIC [--ntfy-server https://你的自托管ntfy]
mon init --bark-key KEY                  # iOS Bark
mon init --telegram BOT_TOKEN:CHAT_ID    # Telegram bot
mon init --webhook https://your/hook     # 通用 webhook(飞书/钉钉/自定义)
```

配置写在 `~/.config/runmon/config.toml`,阈值均可修改:

```toml
hang_gpu_minutes = 20      # 假死判定窗口
silence_minutes = 60       # 静默告警
disk_threshold_pct = 85
```

## 当前限制(Roadmap 见仓库根 README)

- `mon attach`(接管已在 tmux 里跑的任务)在 M3
- 手机 App(实时面板/远程操作)在 M2,当前通知为单向
- GPU 采集依赖 NVIDIA NVML,无 GPU 机器上自动降级(其余功能不受影响)
