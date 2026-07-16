# RunMon 设计文档

- 日期:2026-07-16
- 状态:已定稿(实现前基线)
- 名称:项目 **RunMon**,PyPI 包 `runmon`,CLI 命令 `mon`(均已查重可用)

---

## 1. 产品定义

**一句话:长任务陪伴器。** 服务器上跑训练/爬虫/长脚本/Claude Code 时,手机上实时知道"还在跑吗、跑到哪了、GPU 在不在干活",跑完或出事**主动通知**,还能远程做安全范围内的处理。

### 1.1 痛点场景

- 跑了几个小时的训练中途报错,GPU 空闲半天没人知道
- 吃饭、睡觉、通勤时忍不住反复 ssh 上去看进度
- 租的按小时计费 GPU(AutoDL/RunPod)跑完没发现,白烧钱

### 1.2 目标用户

ML 工程师 / 研究生 / 爬虫与数据工程 / Claude Code 重度用户。会用命令行,大多在 tmux 里跑任务,服务器常在校园网/内网/租用实例中(无公网 IP)。

### 1.3 竞品与差异化

| 竞品 | 空白 |
|---|---|
| Haoleme(直接竞品,架构已研究) | 无 GPU 假死检测、无进度/ETA 解析、无 tmux 接管、通知靠 7 秒轮询前台服务(国产 ROM 杀后台即失效) |
| W&B / TensorBoard | 要埋点改代码;只覆盖训练;无交互 |
| Bark / ntfy | 只有通知,无面板无交互 |
| Termius | 纯手动,无推送 |

**RunMon 的差异化四板斧:GPU 假死检测、训练进度/ETA 零埋点解析、tmux 接管已在跑的任务、通知必达(可插拔通道兜底)。**

### 1.4 非目标(v1 明确不做)

- 完整远程终端(不和 Termius 竞争;只做白名单操作)
- iOS(Flutter 留了路,社区起来后再做)
- 服务器全指标监控(不做 Netdata)
- 多用户/团队功能(v1 单账号多设备)
- 国内厂商推送 SDK(通道兜底已保必达,后续可选增强)

---

## 2. 总体架构

```
 GPU服务器(可多台)                你的腾讯云                     手机
┌────────────────┐            ┌─────────────┐            ┌──────────────┐
│ mon daemon      │─出站WSS──→ │    relay    │ ←──WSS出站─│  Flutter app │
│  ├ mon run 包装 │  (唯一长连) │  (FastAPI)  │            │  面板/曲线/操作│
│  ├ tmux attach │            │  只存密文    │            └──────────────┘
│  ├ GPU/CPU采集  │            └──────┬──────┘
│  ├ 事件引擎     │                   │ 仅"服务器离线"告警
│  └ 通知直发 ────┼──出站HTTPS──→ Bark / ntfy / Telegram / 飞书 ──→ 手机必达通知
└────────────────┘     (任务事件不经 relay,直达通道)
```

**三条铁律:**

1. **全出站**:agent 和 app 都只向外发起连接,两端均不需要公网 IP / 端口转发 / 同局域网。relay 是唯一有公网地址的一方。
2. **任务事件通知由 agent 直发通道**,不经 relay:更私密(内容不过中转)、更可靠(少一跳)、且 **M1 阶段无 relay 也完整可用**。relay 只负责它独有的能力——检测 agent 掉线并发"服务器离线"告警(agent 死了没法自己报丧)。
3. **E2EE**:经 relay 的所有业务数据(任务名/命令/输出/指标)均为密文,密钥只在 agent 和 app 两端,配对二维码带外传输。relay 被入侵也只泄露元数据(设备代号/时间戳/流量大小)。

---

## 3. Agent(Python 包 `runmon`,CLI `mon`)

### 3.1 进程模型

**每台机器一个常驻 daemon + 若干任务包装进程**(优化点:Haoleme 是每个任务各自轮询云端,无常驻;RunMon 用单 daemon 持一条 WSS,指令即时下达、离线即时可判、连接数 O(1))。

- `mon daemon`:常驻。持 WSS 连 relay(20s 心跳);GPU/CPU/磁盘采样(默认 5s);事件引擎;通知直发;接收 app 指令并执行白名单操作。由首次 `mon run` 自动拉起;提供 `mon daemon --install-systemd` 生成 systemd user unit(开机自启,可选)。
- `mon run <命令>`:pty 包装目标命令(完整捕获 stdout/stderr 合流 + 退出码),通过本地 Unix socket 向 daemon 注册并流式上报输出。完整日志落盘 `~/.local/share/runmon/logs/<run_id>.log`,同步到手机的只是尾部窗口。
- daemon 不在时 `mon run` 退化为"本地记录 + 直发通知"模式,不阻塞任务本身。**任何 RunMon 组件的故障都不能影响被包装任务的运行**(硬性原则)。

### 3.2 命令面

```
mon run [--name 名字] [--gpu 0,1] -- python train.py   # 包装启动(-- 后为原命令)
mon attach <tmux会话[:窗格]>                            # 接管已在跑的 tmux 任务
mon ls / mon status <run>                               # 本地查看
mon stop <run>                                          # 本地停止(同 app 端 stop)
mon init                                                # 交互式初始化:通道配置 + 生成配对二维码
mon daemon [--install-systemd]                          # 常驻服务
```

### 3.3 任务捕获

- **pty 包装**(`mon run`):forkpty 执行,合流输出进环形缓冲(默认 512KB)+ 完整落盘;退出码精确;记录 cwd/env 快照与原始命令行(供 rerun,快照仅存本机)。
- **tmux 接管**(`mon attach`):`tmux pipe-pane` 抓输出;结束判定靠窗格前台进程消失或 `pane_dead`;**退出码尽力而为**(仅 `remain-on-exit` 时可得,文档如实说明此限制)。GPU 关联通过窗格进程树的 PID 匹配 nvml 进程列表。

### 3.4 采集

- GPU:pynvml——每卡利用率/显存/温度/功耗 + 每进程显存 → 用 PID 把 GPU 归属到任务
- 系统:psutil——CPU/内存/磁盘水位
- 输出同步节奏(借鉴 Haoleme 实测值):输出活跃时 1s 增量推,静默渐退至 10s

### 3.5 事件引擎(核心卖点)

| 事件 | 判定规则(默认值,均可在 config 覆盖) | 级别 |
|---|---|---|
| 任务完成 | 退出码 0 | 信息 |
| 任务失败 | 退出码非 0;或日志匹配 `Traceback`/`CUDA out of memory`/`RuntimeError` 等内置正则(可扩展) | 严重 |
| **GPU 假死** | 任务关联 GPU 利用率 <5% 持续 10 分钟(启动后 5 分钟豁免期,躲开数据加载/编译) | 严重 |
| 日志静默 | 30 分钟无新输出 | 警告 |
| 磁盘水位 | 任一挂载点 >90% | 警告 |
| 服务器离线 | 由 relay 判定:WSS 断开 + 30s 宽限(此事件唯一由 relay 发出) | 严重 |
| 服务器恢复 | relay 判定重连 | 信息 |

- 事件去抖:同任务同类事件默认 30 分钟内不重复
- 每个事件附带处理动作:手机上可直接 stop / rerun / mute
- 假死与静默阈值支持按任务覆盖(`mon run --hang-gpu-min 20`)

### 3.6 通知直发器

- 通道适配器:**ntfy(推荐,可自托管)、Bark、Telegram bot、飞书/钉钉/企业微信 webhook、通用 webhook**;`mon init` 引导配置,支持多通道并发
- 分级隐私:默认通知只含「任务名 + 事件 + 时长」;`notify_include_tail = N` 可选附日志尾 N 行(文档明示第三方通道可见此内容;自托管 ntfy 则无此顾虑)
- 发送失败重试(指数退避,最多 1 小时),事件本地持久化不丢

### 3.7 进度解析(零埋点,best-effort)

- 识别 tqdm 行(`\r` 刷新、`45%|████ | 450/1000 [03:20<04:05, 2.24it/s]`)→ 进度/速率/ETA 直接采用
- 识别 `[Ee]poch\s+(\d+)\s*/\s*(\d+)`、`loss[=:]\s*([\d.eE+-]+)` → 进度与 loss 序列(供 app 画曲线)
- 解析失败静默降级,不影响任何其他功能

### 3.8 本地存储与断网容忍

- SQLite(WAL):runs 表、事件队列、云同步游标
- relay 断连期间:事件照发通道(不依赖 relay)、输出照常落盘,重连后按游标补传

---

## 4. Relay(FastAPI,部署于个人腾讯云)

### 4.1 职责边界

只做四件事:**转发密文、暂存离线数据、配对绑定、判 agent 生死**。不解密、不解析、不执行业务逻辑。

**离线告警的通道配置**:agent 配对时把一份「仅限离线告警」的通道端点(如 ntfy topic URL)明文注册到 relay——这是唯一存在 relay 的通道信息,只用于发「设备〈代号〉离线/恢复」这一句元数据消息,不含任何业务内容;用户不注册则离线告警仅在 app 内展示。

### 4.2 接口面

- `WS /ws/agent`(device token 鉴权):上行 hello/heartbeat/run 增量/事件密文;下行 app 指令
- `WS /ws/app`(device token 鉴权):下行 run 列表与输出流(密文);上行 subscribe / 白名单指令
- REST:`POST /api/pair/start`(agent 领配对码)、`POST /api/pair/claim`(app 扫码认领)、`GET /health`
- 指令传递:app → relay 暂存 → 经 agent 的 WSS 即时下推(agent 掉线则指令带 TTL 5 分钟,过期作废并回告 app)

### 4.3 存储与配额(保护 2G 内存小机器)

- SQLite(WAL);输出密文每 run 上限 2MB、TTL 7 天;事件 30 天;run 元数据 90 天;超限滚动删除
- 单进程 uvicorn,内存预算 <150MB;个人规模(几台机器/几十个 run)余量充足

### 4.4 部署形态

- systemd 服务,监听 `127.0.0.1:8080`,由已有 nginx 反代(新增子域名 server block,带 WebSocket upgrade),certbot 签证书 → `wss://` 全程加密
- 现有生产服务(预约系统)零改动、零新增安全组端口
- 具体主机与域名信息不入库(开源仓库),记在私有笔记

---

## 5. App(Flutter,安卓优先)

### 5.1 页面结构

1. **服务器列表**:在线状态、GPU 占用概览条、运行中任务数
2. **任务列表**:状态徽章(运行/完成/失败/假死嫌疑/静默)
3. **任务详情**:实时终端流(等宽 + ANSI 颜色)、GPU/CPU 迷你曲线、进度条 + ETA + loss 曲线、操作按钮
4. **设置**:配对管理、通知偏好、实时模式开关

### 5.2 连接与省电策略(优化点,反 Haoleme 模式)

- **前台**:打开 app 即连 WSS,实时流式刷新
- **后台:默认不驻留、不开前台服务**——必达性已由通道兜底,不和国产 ROM 的杀后台机制搏斗,省电且体验干净
- 可选「实时模式」开关:开启后跑前台服务保持 WSS(给想要秒级 app 内通知的用户),默认关

### 5.3 白名单操作(app 无法下发任意 shell)

| 操作 | 语义 |
|---|---|
| stop | 信号升级:SIGINT → 10s → SIGTERM → 10s → SIGKILL |
| rerun | 仅限 `mon run` 启动的任务:按本机存的 cwd/env/命令快照重跑 |
| tail | 拉取日志尾 N 行(加密经 relay) |
| mute | 静音该任务告警 1h/8h/永久 |

指令为语义枚举而非字符串,agent 端实现;rerun 可在 agent config 中禁用。

### 5.4 通知去重

- agent 已配通道 → app 默认只做应用内横幅(系统通知交给通道,避免双响)
- 未配通道 → app 发系统通知
- 均可在设置覆盖

---

## 6. 安全与隐私

- **配对**:`mon init` 生成 32 字节随机密钥 + 从 relay 领一次性配对码;二维码 = `{relay_url, pair_code, key_b64}`,带外(屏幕→摄像头)传输,relay 永不经手密钥
- **加密**:业务 payload 用 ChaCha20-Poly1305(该密钥)加解密;relay 可见元数据仅:设备代号(用户自定义,可用化名)、run_id(随机)、时间戳、密文大小
- **鉴权**:agent/app 各持独立 device token;relay 对配对接口限流防爆破
- **凭据卫生**:token/密钥文件 0600;不入日志;配对码一次性且 10 分钟过期
- **通道隐私分级**:见 3.6;文档中明确告知第三方通道的可见范围

---

## 7. 里程碑与验收

### M1 — Agent 单机版(无需 relay,立即可发布造势)

`pip install runmon` → `mon init` 配通道 → `mon run -- python train.py`

验收:完成/失败/GPU 假死/日志静默/磁盘 五类事件可靠推到 ntfy + Telegram + Bark;`mon ls/status` 可用;自带 `demo_train.py`(支持 `--fail`/`--hang` 注入)全流程演示;事件引擎与进度解析器有单测(真实训练日志做 fixture)。

### M2 — Relay + App MVP(完整产品)

验收:relay 部署上云(nginx 反代 + TLS);app 扫码配对;实时终端流与 GPU 曲线;stop/rerun/tail/mute 全通;服务器离线/恢复告警;断网补传;E2EE 全链路(relay 数据库中无明文抽查验证)。

### M3 — 差异化完全体

tmux 接管、多服务器面板、tqdm/ETA/loss 曲线打磨、任务历史、跑完自动关机(租卡场景)、Claude Code 等待输入检测。

### 验证环境

真实 GPU 服务器跑 agent;腾讯云跑 relay;真机安卓装 app;假死用 `kill -STOP` 模拟,OOM 用注入脚本模拟。

---

## 8. 仓库与发布

```
runmon/
├─ agent/     # Python 包 runmon(CLI mon)—— M1
├─ relay/     # FastAPI —— M2
├─ app/       # Flutter —— M2
├─ docs/specs/
└─ README.md  # 中英双语,痛点场景开头,GIF 演示
```

- License:MIT
- 发布:agent 走 PyPI;app 走 GitHub Releases APK(F-Droid 后续)
- 造势节奏:M1 完成即发(HN「Show HN」/ V2EX / 即刻 / 小红书),用真实痛点文案;M2 发布时二次传播

## 9. 开放问题(不阻塞实现)

- iOS 版时间点(Flutter 已留路)
- 国内厂商推送作为可选增强
- relay 是否提供官方托管实例(等社区需求)
- W&B/wandb 数据源集成(观望)
