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

echo "==> 重命名…"
D=build/app/outputs/flutter-apk
cp "$D/app-arm64-v8a-release.apk"   "$D/RunMon-arm64.apk"   # 现代手机,装这个
cp "$D/app-armeabi-v7a-release.apk" "$D/RunMon-arm32.apk"   # 老 32 位手机
cp "$D/app-x86_64-release.apk"      "$D/RunMon-x86.apk"     # 电脑模拟器
cp "$D/app-release.apk"             "$D/RunMon.apk"         # 通用版(装任何机器)

echo ""
echo "==> 完成,可以发出去的 APK:"
ls -lh "$D"/RunMon.apk "$D"/RunMon-arm64.apk "$D"/RunMon-arm32.apk "$D"/RunMon-x86.apk \
  | awk '{print "   " $5 "  " $9}'
echo ""
echo "日常手机装:RunMon-arm64.apk(现代安卓都是 arm64)"
