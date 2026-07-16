# RunMon M2(Relay + App)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans。M2 分两段:**M2a Python 侧**(agent 加密/配对/daemon + relay 服务,本文档主体,可完整自动化测试)与 **M2b Flutter App**(依赖 Flutter 工具链,迭代式开发,见文末)。

**Goal:** 手机 App 能通过 relay 实时看到服务器任务(列表/输出尾部/GPU 心跳),并下发白名单操作;全链路 E2EE。

**Architecture:** agent 常驻 `mon daemon` 持一条 WSS 到 relay;业务数据(任务/输出/事件/心跳)全部 ChaCha20-Poly1305 加密,relay 只读路由字段做存储转发;App 持另一条 WSS 收推送、发指令。配对一次性交换密钥(带外,relay 不经手)。

**Tech Stack:** agent 新增 `cryptography`、`websockets`;relay 独立包 `runmon-relay`(FastAPI + uvicorn,SQLite);App 用 Flutter(web_socket_channel/cryptography/mobile_scanner/flutter_local_notifications)。

## 协议(全链路契约,M2 的核心固化物)

### E2EE 信封

所有业务负载 → `{"n": b64(nonce12), "c": b64(ChaCha20Poly1305(key).encrypt(nonce, json_bytes))}`,记作 `enc{...}`。密钥 32 字节,`mon pair` 生成,经配对载荷带外传给 App,relay 永不经手。

### 配对(REST,relay)

1. agent `POST /api/pair/start {device_name}` → `{code(6位), pair_token, device_id, device_token}`(10 分钟过期)
2. agent 本地生成 e2ee key,展示配对载荷 `{"u": relay_url, "c": code, "k": key_b64}`(文本/二维码)
3. App `POST /api/pair/claim {code, app_name}` → `{device_id, device_token, agent_id, agent_name}`
4. agent 轮询 `POST /api/pair/status {code, pair_token}` → `{claimed, app_name}` 确认成对

### WSS 消息(JSON;`enc` 字段 relay 不可读,其余为路由元数据)

认证:握手头 `Authorization: Bearer <device_token>`、`X-Device: <device_id>`。

| 方向 | 消息 | 说明 |
|---|---|---|
| agent→relay | `{"t":"snapshot","enc":…}` | 任务列表快照(id/name/status/progress/eta/loss/时间/exit_code),变化时发 |
| agent→relay | `{"t":"tail","run":id,"enc":…}` | 某任务输出尾部窗口(≤8KB 全量替换式,幂等),变化时发、1s 节流 |
| agent→relay | `{"t":"event","enc":…}` | 事件(engine 产出的完整 Event) |
| agent→relay | `{"t":"hb","enc":…}` | GPU/CPU/磁盘心跳,10s |
| agent→relay | `{"t":"cmd_result","cmd_id":…,"enc":…}` | 指令执行结果 |
| relay→agent | `{"t":"cmd","cmd_id":…,"enc":…}` | enc 内 `{op, run_id, args}`;op ∈ stop/tail/mute/rerun |
| relay→app | 转发以上 agent 消息,附加 `"agent": agent_id`;另有 `{"t":"presence","agent":id,"online":bool}` | App 连上即收到:每个已配对 agent 的 presence + 最新 snapshot/hb + 各 run tail + 近 50 条 event |
| app→relay | `{"t":"cmd","agent":id,"cmd_id":…,"enc":…}` | agent 在线即转发,离线暂存 TTL 5 分钟 |

**尾部替换式设计**(关键决策):tail 消息携带当前完整尾窗而非增量——无游标/去重/补洞逻辑,重连天然自愈;代价是 App 无历史回滚(与 spec"同步手机的只是尾部窗口"一致)。

### relay 存储与配额(SQLite)

devices / pairings / pending_pairs / snapshots(agent_id+kind 主键,kind∈snapshot,hb)/ run_tails(每 agent 上限 200 行滚动)/ events(30 天)/ pending_cmds(TTL 5 分钟)。密文原样存,总量天然受限(尾窗 ≤8KB×任务数)。

## M2a 任务(Python,TDD)

1. **agent crypto.py**:`generate_key/key_to_b64/key_from_b64/encrypt/decrypt`;测试:roundtrip、篡改报错、坏 key 报错。deps 加 `cryptography>=42`。
2. **store/engine 扩展**:runs 加 `muted_until` 列、events 加 `payload` 列(PRAGMA 探测 + ALTER TABLE 迁移,兼容 M1 旧库);`record_event(..., payload=None)`、`events_since(last_id)`;Event 增 `to_dict()`,`_emit` 落 payload;engine 的 on_output/check_gpu_hang/check_log_silence 尊重 muted_until(完成/失败不受 mute 影响)。
3. **relay 包**(`relay/`,独立 pyproject `runmon-relay`):storage.py(上表 + token sha256 校验 + 保留策略)、app.py(配对 REST + `/health`);TestClient 测试配对全流程、过期、错 token。
4. **relay WS 路由**:ConnectionManager,agent/app 双端点,存储+转发+presence+离线指令暂存/回放;TestClient websocket 测试:app 先连收历史 → agent 连 presence→tail 转发→cmd 双向→agent 断线 presence offline。
5. **agent 配对与 daemon**:`mon pair --relay URL`(urllib,保存 `[relay]` 配置到 config.toml,打印配对载荷,轮询确认);`mon daemon`(asyncio+websockets:重连退避、1s 同步循环 diff store 发 snapshot/tail/event、10s 心跳、指令处理 stop/tail/mute/rerun);同步 diff 逻辑抽纯函数单测;指令处理器单测(真 store)。
6. **E2E**:pytest 起真 uvicorn(随机端口)——REST 配对 → 原生 ws 双端连接 → tail/cmd 全链路含加解密断言;再手动冒烟:本机 relay + `mon demo` + daemon。

## M2b(Flutter App,单独迭代)

工具链就绪后 scaffold `app/`:
- 页面:配对(扫码/粘贴载荷)→ 服务器列表(presence+GPU 心跳)→ 任务列表(状态徽章/进度)→ 任务详情(tail 终端视图/进度/loss/操作按钮 stop·tail·mute·rerun)
- 核心:WSS client(自动重连)、ChaCha20-Poly1305 解密(`cryptography` 包)、`mobile_scanner` 扫码、`shared_preferences` 存配置、前台本地通知
- 验收:真机/模拟器与本机 relay + demo 任务联调,全流程走通

## 验证

- M2a:`.venv/bin/pytest agent/tests relay/tests` 全绿;手动:双终端 relay+daemon,第三终端 `mon demo`,ws 抓包确认密文
- 隐私抽查:relay SQLite 中 grep 不到任务名/输出明文
