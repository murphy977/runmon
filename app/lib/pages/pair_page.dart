import 'dart:io';

import 'package:flutter/material.dart';

import '../state.dart';
import 'scan_page.dart';
import '../ui.dart';

class PairPage extends StatefulWidget {
  const PairPage({super.key});

  @override
  State<PairPage> createState() => _PairPageState();
}

class _PairPageState extends State<PairPage> {
  final _payload = TextEditingController();
  final _name = TextEditingController(text: Platform.localHostname);
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
          .showSnackBar(const SnackBar(content: Text('配对成功')));
    } else {
      setState(() {
        _busy = false;
        _error = err;
      });
    }
  }

  InputDecoration _decor(String hint) => InputDecoration(
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('配对服务器')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 480),
          child: ListView(
            shrinkWrap: true,
            padding: const EdgeInsets.all(24),
            children: [
              Text('把服务器接进来',
                  style: sans(size: 22, weight: FontWeight.w700, spacing: -0.4)),
              const SizedBox(height: 10),
              Text('在服务器上运行下面的命令,把它打印的配对载荷(一行 JSON)粘贴到输入框。',
                  style: sans(size: 14, color: Rm.inkSoft, height: 1.6)),
              const SizedBox(height: 14),
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: Rm.terminalBg,
                  borderRadius: BorderRadius.circular(Rm.radiusInput),
                ),
                child: Text('mon pair --relay <你的relay地址>',
                    style: mono(size: 12.5, color: Rm.terminalText)),
              ),
              const SizedBox(height: 20),
              SectionLabel('配对载荷'),
              TextField(
                controller: _payload,
                maxLines: 3,
                style: mono(size: 12.5, color: Rm.ink, height: 1.5),
                decoration: _decor('{"u":"https://…","c":"123456","k":"…"}'),
              ),
              const SizedBox(height: 14),
              SectionLabel('这台设备的名字'),
              TextField(
                controller: _name,
                style: sans(size: 14),
                decoration: _decor('我的手机'),
              ),
              const SizedBox(height: 20),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 14),
                  child: Text(_error!,
                      style: sans(size: 13, color: Rm.coralDeep, height: 1.5)),
                ),
              Row(children: [
                PushButton(
                  label: _busy ? '配对中…' : '配对',
                  icon: Icons.link_rounded,
                  onPressed: _busy ? null : _pair,
                ),
                const SizedBox(width: 12),
                SoftButton(
                  label: '扫码', icon: Icons.qr_code_scanner_rounded,
                  deep: Rm.cyanDeep, tint: Rm.cyanTint,
                  onPressed: _busy ? null : _scan,
                ),
              ]),
            ],
          ),
        ),
      ),
    );
  }
}
