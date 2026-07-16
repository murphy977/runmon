import 'package:flutter/material.dart';

import '../state.dart';
import 'runs_page.dart' show statusColor, statusLabel;

class RunDetailPage extends StatefulWidget {
  final String agentId;
  final String runId;
  const RunDetailPage({super.key, required this.agentId, required this.runId});

  @override
  State<RunDetailPage> createState() => _RunDetailPageState();
}

class _RunDetailPageState extends State<RunDetailPage> {
  final _scroll = ScrollController();
  bool _busy = false;

  Future<void> _cmd(String op, [Map<String, dynamic>? args,
      String? confirmText]) async {
    if (confirmText != null) {
      final ok = await showDialog<bool>(
          context: context,
          builder: (c) => AlertDialog(
                title: Text(confirmText),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(c, false),
                      child: const Text('取消')),
                  FilledButton(
                      onPressed: () => Navigator.pop(c, true),
                      child: const Text('确定')),
                ],
              ));
      if (ok != true) return;
    }
    setState(() => _busy = true);
    final res = await appState.sendCmd(widget.agentId, op, widget.runId, args);
    if (!mounted) return;
    setState(() => _busy = false);
    final ok = res['ok'] == true;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(ok ? '✅ $op 已执行' : '❌ 失败:${res['error'] ?? '未知错误'}')));
    if (ok && op == 'tail' && res['tail'] is String && mounted) {
      showDialog(
          context: context,
          builder: (c) => AlertDialog(
                title: const Text('完整日志尾部'),
                content: SizedBox(
                  width: double.maxFinite,
                  child: SingleChildScrollView(
                    child: SelectableText(res['tail'] as String,
                        style: const TextStyle(
                            fontFamily: 'monospace', fontSize: 11)),
                  ),
                ),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(c),
                      child: const Text('关闭')),
                ],
              ));
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: appState,
      builder: (context, _) {
        final agent = appState.agents[widget.agentId];
        final run = agent?.runs
            .where((r) => r['id'] == widget.runId)
            .cast<Map<String, dynamic>?>()
            .firstOrNull;
        if (agent == null || run == null) {
          return const Scaffold(body: Center(child: Text('任务不存在')));
        }
        final tail = agent.tails[widget.runId] ?? '';
        final status = run['status'] as String? ?? '?';
        final progress = run['progress'] as num?;
        final running = status == 'running';
        // 输出更新时自动滚到底
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (_scroll.hasClients) {
            _scroll.jumpTo(_scroll.position.maxScrollExtent);
          }
        });
        return Scaffold(
          appBar: AppBar(
            title: Text(run['name'] as String? ?? '',
                maxLines: 1, overflow: TextOverflow.ellipsis),
            actions: [
              Center(
                child: Padding(
                  padding: const EdgeInsets.only(right: 16),
                  child: Text(statusLabel[status] ?? status,
                      style: TextStyle(color: statusColor[status])),
                ),
              ),
            ],
          ),
          body: Column(
            children: [
              if (progress != null)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                  child: Row(children: [
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                            value: progress / 100.0,
                            minHeight: 10,
                            backgroundColor: Colors.white12),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text('${progress.round()}%',
                        style: const TextStyle(fontFamily: 'monospace')),
                  ]),
                ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                child: Row(
                  children: [
                    Text(
                      [
                        if (run['last_loss'] != null)
                          'loss ${(run['last_loss'] as num).toStringAsFixed(4)}',
                        if (running && run['eta_seconds'] != null)
                          '预计还需 ${fmtDuration(0, (run['eta_seconds'] as num).toDouble())}',
                        '耗时 ${fmtDuration((run['started_at'] as num?)?.toDouble(), (run['ended_at'] as num?)?.toDouble())}',
                        if (run['exit_code'] != null) 'exit ${run['exit_code']}',
                      ].join(' · '),
                      style: const TextStyle(
                          fontFamily: 'monospace', fontSize: 12),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: Container(
                  margin: const EdgeInsets.all(16),
                  padding: const EdgeInsets.all(12),
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: const Color(0xFF0A0E12),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.white12),
                  ),
                  child: SingleChildScrollView(
                    controller: _scroll,
                    child: SelectableText(
                      tail.isEmpty ? '(暂无输出)' : tail.replaceAll('\r', '\n'),
                      style: const TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 12,
                          height: 1.4,
                          color: Color(0xFFB9F6CA)),
                    ),
                  ),
                ),
              ),
              SafeArea(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                  child: Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      FilledButton.tonalIcon(
                        onPressed: _busy || !running
                            ? null
                            : () => _cmd('stop', null,
                                '停止「${run['name']}」?\nSIGINT→SIGTERM→SIGKILL 逐级升级。'),
                        icon: const Icon(Icons.stop_circle_outlined),
                        label: const Text('停止'),
                      ),
                      FilledButton.tonalIcon(
                        onPressed: _busy
                            ? null
                            : () => _cmd('rerun', null,
                                '按原命令原目录重跑「${run['name']}」?'),
                        icon: const Icon(Icons.replay),
                        label: const Text('重跑'),
                      ),
                      FilledButton.tonalIcon(
                        onPressed: _busy
                            ? null
                            : () => _cmd('mute', {'hours': 8}),
                        icon: const Icon(Icons.notifications_paused_outlined),
                        label: const Text('静音8h'),
                      ),
                      FilledButton.tonalIcon(
                        onPressed: _busy
                            ? null
                            : () => _cmd('tail', {'lines': 500}),
                        icon: const Icon(Icons.article_outlined),
                        label: const Text('完整日志'),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
