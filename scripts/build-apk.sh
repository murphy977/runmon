#!/usr/bin/env bash
# 构建全部安卓 APK:三个架构分包(arm64/armv7/x86_64)+ 一个万能版。
# 用法:./scripts/build-apk.sh
# 产物在 app/build/app/outputs/flutter-apk/ ,日常手机装 app-arm64-v8a-release.apk(~25MB)。
set -euo pipefail
cd "$(dirname "$0")/../app"

export PATH="/opt/homebrew/bin:$PATH"
export PUB_HOSTED_URL=https://pub.flutter-io.cn
export FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn
# Flutter/Gradle 走直连,避开系统代理(它会拦 dl.google.com)
unset HTTPS_PROXY HTTP_PROXY https_proxy http_proxy ALL_PROXY all_proxy

echo "==> 构建三个架构分包…"
flutter build apk --release --split-per-abi
echo "==> 构建万能版…"
flutter build apk --release

echo ""
echo "==> 完成,全部 APK:"
ls -lh build/app/outputs/flutter-apk/*.apk | awk '{print "   " $5 "  " $9}'
echo ""
echo "日常手机装:app-arm64-v8a-release.apk(现代安卓都是 arm64)"
