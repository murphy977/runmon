import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:open_filex/open_filex.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:path_provider/path_provider.dart';

import 'ui.dart';

/// 版本信息从你自己的官网查(国内可靠,不依赖 GitHub)。
const _versionUrl = 'https://runmon.linxiexie.com/version.json';

class UpdateInfo {
  final String version;   // 显示用,如 "1.0.4"
  final int versionCode;  // 比较用(对应 pubspec 的 +N)
  final String notes;     // 此次更新内容
  final String url;       // arm64 APK 下载地址
  UpdateInfo({required this.version, required this.versionCode,
      required this.notes, required this.url});
}

/// 查最新版:有新版返回 UpdateInfo;已是最新返回 null;网络/解析出错抛异常。
Future<UpdateInfo?> checkUpdate() async {
  final pkg = await PackageInfo.fromPlatform();
  final localCode = int.tryParse(pkg.buildNumber) ?? 0;
  final resp = await http
      .get(Uri.parse(_versionUrl), headers: {'User-Agent': 'runmon-app'})
      .timeout(const Duration(seconds: 10));
  if (resp.statusCode != 200) throw Exception('HTTP ${resp.statusCode}');
  final j = jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
  final remoteCode = (j['versionCode'] as num?)?.toInt() ?? 0;
  if (remoteCode <= localCode) return null; // 已是最新
  return UpdateInfo(
    version: j['version']?.toString() ?? '',
    versionCode: remoteCode,
    notes: j['notes']?.toString() ?? '',
    url: j['url']?.toString() ?? '',
  );
}

/// 检查并弹窗提示。silent=true 时,已是最新/出错都不打扰(用于启动自动检查)。
Future<void> checkAndPrompt(BuildContext context, {bool silent = false}) async {
  UpdateInfo? info;
  try {
    info = await checkUpdate();
  } catch (_) {
    if (!silent && context.mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('检查更新失败,请稍后再试')));
    }
    return;
  }
  if (info == null) {
    if (!silent && context.mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('已是最新版本 🎉')));
    }
    return;
  }
  if (context.mounted) {
    await showDialog(
        context: context,
        barrierDismissible: false,
        builder: (_) => _UpdateDialog(info: info!));
  }
}

class _UpdateDialog extends StatefulWidget {
  final UpdateInfo info;
  const _UpdateDialog({required this.info});
  @override
  State<_UpdateDialog> createState() => _UpdateDialogState();
}

class _UpdateDialogState extends State<_UpdateDialog> {
  bool _downloading = false;
  double _progress = 0;
  String? _error;

  Future<void> _update() async {
    setState(() {
      _downloading = true;
      _error = null;
      _progress = 0;
    });
    try {
      final dir = await getExternalStorageDirectory() ??
          await getTemporaryDirectory();
      final file = File('${dir.path}/RunMon-${widget.info.version}.apk');
      final resp =
          await http.Client().send(http.Request('GET', Uri.parse(widget.info.url)));
      final total = resp.contentLength ?? 0;
      final sink = file.openWrite();
      int received = 0;
      await for (final chunk in resp.stream) {
        sink.add(chunk);
        received += chunk.length;
        if (total > 0 && mounted) setState(() => _progress = received / total);
      }
      await sink.close();
      // 拉起系统安装界面(用户需确认安装,安卓侧载 App 无法静默安装)
      final r = await OpenFilex.open(file.path,
          type: 'application/vnd.android.package-archive');
      if (!mounted) return;
      if (r.type != ResultType.done) {
        setState(() {
          _downloading = false;
          _error = '无法拉起安装程序:${r.message}';
        });
        return;
      }
      Navigator.pop(context); // 安装界面已弹出,关掉本弹窗
    } catch (_) {
      if (mounted) {
        setState(() {
          _downloading = false;
          _error = '下载失败,请检查网络后重试';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      backgroundColor: Rm.card,
      title: Text('发现新版本 v${widget.info.version}',
          style: sans(size: 18, weight: FontWeight.w700, spacing: -0.3)),
      content: SizedBox(
        width: double.maxFinite,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Flexible(
              child: SingleChildScrollView(
                child: Text(
                    widget.info.notes.isEmpty
                        ? '本次更新带来若干改进。'
                        : widget.info.notes,
                    style: sans(size: 13.5, color: Rm.inkSoft, height: 1.6)),
              ),
            ),
            if (_downloading) ...[
              const SizedBox(height: 18),
              ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: LinearProgressIndicator(
                  value: _progress > 0 ? _progress : null,
                  minHeight: 8,
                  backgroundColor: Rm.hairline,
                  color: Rm.pearDeep,
                ),
              ),
              const SizedBox(height: 6),
              Text('下载中 ${(_progress * 100).toStringAsFixed(0)}%',
                  style: mono(size: 12, color: Rm.inkFaint)),
            ],
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: sans(size: 12.5, color: Rm.coralDeep)),
            ],
          ],
        ),
      ),
      actions: _downloading
          ? const [Padding(padding: EdgeInsets.all(8), child: Text(''))]
          : [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: Text('以后再说',
                    style: sans(size: 14, color: Rm.inkFaint)),
              ),
              FilledButton(
                style: FilledButton.styleFrom(
                    backgroundColor: Rm.pear, foregroundColor: Rm.ink),
                onPressed: _update,
                child: Text(_error == null ? '立即更新' : '重试',
                    style: sans(size: 14, weight: FontWeight.w700)),
              ),
            ],
    );
  }
}
