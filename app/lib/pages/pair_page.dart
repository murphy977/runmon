import 'dart:io';

import 'package:flutter/material.dart';

import '../state.dart';
import '../ui.dart';
import 'scan_page.dart';

/// 系统 hostname 清理成体面的默认名:MacBook-Pro-375.local → MacBook-Pro
String _defaultDeviceName() {
  var s = Platform.localHostname
      .replaceAll(RegExp(r'\.local$'), '')
      .replaceAll(RegExp(r'-\d+$'), '')
      .trim();
  return s.isEmpty ? 'phone' : s;
}

class PairPage extends StatefulWidget {
  const PairPage({super.key});

  @override
  State<PairPage> createState() => _PairPageState();
}

class _PairPageState extends State<PairPage> {
  final _payload = TextEditingController();
  final _name = TextEditingController(text: _defaultDeviceName());
  bool _busy = false;
  String? _error;

  Future<void> _scan() async {
    final result = await Navigator.push<String>(
        context, MaterialPageRoute(builder: (_) => const ScanPage()));
    if (result != null && mounted) {
      _payload.text = result;
      _pair();
    }
  }

  Future<void> _pair() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final err = await appState.pairWithPayload(_payload.text,
        _name.text.trim().isEmpty ? 'phone' : _name.text.trim());
    if (!mounted) return;
    if (err == null) {
      Navigator.pop(context);
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('已连接')));
    } else {
      setState(() {
        _busy = false;
        _error = err;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('添加服务器')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 460),
          child: ListView(
            shrinkWrap: true,
            padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
            children: [
              Text('连上一台服务器',
                  style: sans(size: 24, weight: FontWeight.w700, spacing: -0.5)),
              const SizedBox(height: 8),
              Text('在服务器上跑一句 mon pair,这台设备扫码即可连上。',
                  style: sans(size: 14, color: Rm.inkSoft, height: 1.6)),
              const SizedBox(height: 28),

              // 这台设备的名字
              const SectionLabel('这台设备'),
              TextField(
                controller: _name,
                style: sans(size: 15, weight: FontWeight.w500),
                decoration: _decor(hint: '给它起个名'),
              ),
              const SizedBox(height: 6),
              Text('配对后显示在服务器端,方便你认出是哪台。',
                  style: sans(size: 12, color: Rm.inkFaint)),
              const SizedBox(height: 28),

              // 主路径:扫码
              Center(
                child: PushButton(
                  label: _busy ? '连接中…' : '扫码配对',
                  icon: Icons.qr_code_scanner_rounded,
                  onPressed: _busy ? null : _scan,
                ),
              ),
              const SizedBox(height: 24),
              _orDivider(),
              const SizedBox(height: 24),

              // 备选:手动
              const SectionLabel('手动输入'),
              Text('服务器终端里会打印一段配对码,复制粘贴到这里:',
                  style: sans(size: 13, color: Rm.inkSoft, height: 1.5)),
              const SizedBox(height: 10),
              _terminalHint('mon pair'),
              const SizedBox(height: 12),
              TextField(
                controller: _payload,
                maxLines: 3,
                style: mono(size: 12.5, color: Rm.ink, height: 1.5),
                decoration: _decor(hint: '{"u":"…","c":"…","k":"…"}'),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!,
                    style: sans(size: 13, color: Rm.coralDeep, height: 1.5)),
              ],
              const SizedBox(height: 14),
              SoftButton(
                label: '用配对码连接',
                icon: Icons.link_rounded,
                deep: Rm.cyanDeep,
                tint: Rm.cyanTint,
                onPressed: _busy ? null : _pair,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _orDivider() => Row(children: [
        const Expanded(child: Divider(color: Rm.hairline, thickness: 1)),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14),
          child: Text('或', style: sans(size: 12.5, color: Rm.inkFaint)),
        ),
        const Expanded(child: Divider(color: Rm.hairline, thickness: 1)),
      ]);

  Widget _terminalHint(String text) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Rm.terminalBg,
          borderRadius: BorderRadius.circular(Rm.radiusInput),
        ),
        child: Text(text, style: mono(size: 12.5, color: Rm.terminalText)),
      );

  InputDecoration _decor({required String hint}) => InputDecoration(
        hintText: hint,
        hintStyle: mono(size: 12.5, color: Rm.inkFaint),
        filled: true,
        fillColor: Rm.card,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(Rm.radiusInput),
          borderSide: const BorderSide(color: Rm.hairline),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(Rm.radiusInput),
          borderSide: const BorderSide(color: Rm.pearDeep, width: 1.5),
        ),
      );
}
