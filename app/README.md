<div align="center">

[![English](https://img.shields.io/badge/English-2563EB?style=for-the-badge)](README.md) [![简体中文](https://img.shields.io/badge/简体中文-64748B?style=for-the-badge)](README.zh-CN.md)

</div>

# RunMon App

The RunMon mobile app (Flutter, Android-first) — a live dashboard, resource charts, and a full interactive terminal for the jobs running on your servers. It pairs with a server agent by scanning a QR code, and all data is end-to-end encrypted.

For what RunMon is and how to get started, see the [project README](../README.md).

## Build

```bash
flutter pub get
flutter build apk --release --split-per-abi   # per-ABI APKs
# or build every variant at once:
../scripts/build-apk.sh
```

Pre-built APKs are attached to each [GitHub Release](../../releases) — most phones want `RunMon-arm64.apk`.
