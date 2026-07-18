<div align="center">

[![English](https://img.shields.io/badge/English-64748B?style=for-the-badge)](README.md) [![简体中文](https://img.shields.io/badge/简体中文-DC2626?style=for-the-badge)](README.zh-CN.md)

</div>

# RunMon App

RunMon 手机 App(Flutter,安卓优先)—— 服务器上任务的实时面板、资源曲线,还有一个完整的交互终端。扫码与服务器 agent 配对,全程数据端到端加密。

RunMon 是什么、怎么上手,见[仓库根 README](../README.zh-CN.md)。

## 构建

```bash
flutter pub get
flutter build apk --release --split-per-abi   # 按架构分包
# 或一次构建全部版本:
../scripts/build-apk.sh
```

预编译好的 APK 挂在每个 [GitHub Release](../../releases) 里 —— 多数手机装 `RunMon-arm64.apk`。
