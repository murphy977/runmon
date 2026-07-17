import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../ui.dart';

/// 扫配对二维码:识别到疑似载荷的 JSON 即返回。
class ScanPage extends StatefulWidget {
  const ScanPage({super.key});

  @override
  State<ScanPage> createState() => _ScanPageState();
}

class _ScanPageState extends State<ScanPage> {
  bool _done = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Rm.terminalBg,
      appBar: AppBar(
        title: const Text('扫码配对'),
        backgroundColor: Rm.terminalBg,
        titleTextStyle: sans(size: 17, weight: FontWeight.w700,
            color: Rm.terminalText),
        iconTheme: const IconThemeData(color: Rm.terminalText, size: 20),
      ),
      body: Stack(children: [
        MobileScanner(
          onDetect: (capture) {
            if (_done) return;
            for (final b in capture.barcodes) {
              final v = b.rawValue ?? '';
              if (v.contains('"u"') && v.contains('"c"') && v.contains('"k"')) {
                _done = true;
                Navigator.pop(context, v);
                return;
              }
            }
          },
        ),
        Align(
          alignment: Alignment.bottomCenter,
          child: Padding(
            padding: const EdgeInsets.all(28),
            child: Text('对准服务器终端里 mon pair 打印的二维码',
                style: sans(size: 13.5, color: Rm.terminalText)),
          ),
        ),
      ]),
    );
  }
}
