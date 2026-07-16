import 'dart:io';

import 'package:flutter/material.dart';

import '../state.dart';

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
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('✅ 配对成功')));
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
      appBar: AppBar(title: const Text('配对服务器')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text('在服务器上运行 mon pair --relay <URL>,'
              '把打印出的配对载荷(一行 JSON)粘贴到这里:'),
          const SizedBox(height: 12),
          TextField(
            controller: _payload,
            maxLines: 4,
            style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              hintText: '{"u":"https://…","c":"123456","k":"…"}',
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _name,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              labelText: '这台手机的名字(显示在服务器端)',
            ),
          ),
          const SizedBox(height: 16),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(_error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ),
          FilledButton.icon(
            onPressed: _busy ? null : _pair,
            icon: _busy
                ? const SizedBox(
                    width: 16, height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.link),
            label: const Text('配对'),
          ),
        ],
      ),
    );
  }
}
