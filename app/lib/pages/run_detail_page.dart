import 'package:flutter/material.dart';

import '../state.dart';
import '../ui.dart';
import '../terminal_gate.dart';

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

  Future<void> _cmd(String op,
      [Map<String, dynamic>? args, String? confirmText]) async {
    if (confirmText != null) {
      final ok = await showDialog<bool>(
          context: context,
          builder: (c) => AlertDialog(
                title: Text(confirmText),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(c, false),
                      child: const Text('取消')),
                  SoftButton(
                      label: '确定', icon: Icons.check,
                      deep: Rm.ink, tint: Rm.pearTint,
                      onPressed: () => Navigator.pop(c, true)),
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
        content: Text(ok ? '已执行' : '失败:${res['error'] ?? '未知错误'}')));
    if (ok && op == 'tail' && res['tail'] is String && mounted) {
      showDialog(
          context: context,
          builder: (c) => Dialog(
                backgroundColor: Rm.terminalBg,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16)),
                child: Container(
                  constraints:
                      const BoxConstraints(maxWidth: 720, maxHeight: 560),
                  padding: const EdgeInsets.all(18),
                  child: Column(children: [
                    Row(children: [
                      Text('日志尾部',
                          style: mono(size: 12, color: Rm.inkFaint)),
                      const Spacer(),
                      IconButton(
                          onPressed: () => Navigator.pop(c),
                          icon: const Icon(Icons.close,
                              size: 18, color: Rm.inkFaint)),
                    ]),
                    Expanded(
                      child: SingleChildScrollView(
                        child: SelectableText(res['tail'] as String,
                            style: mono(size: 11.5, color: Rm.terminalText,
                                height: 1.55)),
                      ),
                    ),
                  ]),
                ),
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
        final shutdownAfter = run['shutdown_after'] == 1;
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
              Padding(
                padding: const EdgeInsets.only(right: 16),
                child: Center(child: StatusPill(status)),
              ),
            ],
          ),
          body: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 数据带:进度 + 关键指标(mono)
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 6, 20, 0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (progress != null) ...[
                      Row(children: [
                        Expanded(
                            child: RmProgress(
                                value: progress / 100.0,
                                color: progressColor(status),
                                height: 9)),
                        const SizedBox(width: 12),
                        Text('${progress.round()}%',
                            style: mono(size: 14, weight: FontWeight.w600,
                                color: Rm.ink)),
                      ]),
                      const SizedBox(height: 12),
                    ],
                    Wrap(spacing: 22, runSpacing: 8, children: [
                      if (run['last_loss'] != null)
                        _Stat('LOSS',
                            (run['last_loss'] as num).toStringAsFixed(4)),
                      if (running && run['eta_seconds'] != null)
                        _Stat('预计还需', fmtDuration(0,
                            (run['eta_seconds'] as num).toDouble())),
                      _Stat('耗时', fmtDuration(
                          (run['started_at'] as num?)?.toDouble(),
                          (run['ended_at'] as num?)?.toDouble())),
                      if (run['exit_code'] != null)
                        _Stat('EXIT', '${run['exit_code']}'),
                    ]),
                  ],
                ),
              ),
              // 终端:整页唯一的深色面
              Expanded(
                child: Container(
                  margin: const EdgeInsets.fromLTRB(20, 16, 20, 0),
                  padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: Rm.terminalBg,
                    borderRadius: BorderRadius.circular(Rm.radiusCard),
                  ),
                  child: SingleChildScrollView(
                    controller: _scroll,
                    child: SelectableText(
                      tail.isEmpty ? '(暂无输出)' : tail.replaceAll('\r', '\n'),
                      style: mono(size: 12, color: Rm.terminalText, height: 1.55),
                    ),
                  ),
                ),
              ),
              SafeArea(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 14, 20, 16),
                  child: Wrap(spacing: 10, runSpacing: 10, children: [
                    SoftButton(
                      label: '停止', icon: Icons.stop_rounded,
                      deep: Rm.coralDeep, tint: Rm.coralTint,
                      onPressed: _busy || !running
                          ? null
                          : () => _cmd('stop', null,
                              '停止「${run['name']}」?'),
                    ),
                    SoftButton(
                      label: '重跑', icon: Icons.replay_rounded,
                      deep: Rm.pearDeep, tint: Rm.pearTint,
                      onPressed: _busy
                          ? null
                          : () => _cmd('rerun', null,
                              '按原命令原目录重跑「${run['name']}」?'),
                    ),
                    SoftButton(
                      label: shutdownAfter ? '跑完关机 ✓' : '跑完关机',
                      icon: Icons.power_settings_new_rounded,
                      deep: shutdownAfter ? Rm.coralDeep : Rm.inkSoft,
                      tint: shutdownAfter ? Rm.coralTint : Rm.paper2,
                      onPressed: _busy || !running
                          ? null
                          : () => _cmd('shutdown_after',
                              {'enabled': !shutdownAfter},
                              shutdownAfter
                                  ? null
                                  : '任务跑完后自动关机?\n服务器需允许免密 sudo shutdown。'),
                    ),
                    SoftButton(
                      label: '终端', icon: Icons.terminal_rounded,
                      deep: Rm.ink, tint: Rm.pearTint,
                      onPressed: !agent.online
                          ? null
                          : () => openTerminalGuarded(
                              context, widget.agentId, agent.name,
                              cwd: run['cwd'] as String?,
                              command: run['command'] as String?),
                    ),
                    SoftButton(
                      label: '完整日志', icon: Icons.article_outlined,
                      deep: Rm.cyanDeep, tint: Rm.cyanTint,
                      onPressed: _busy ? null : () => _cmd('tail', {'lines': 500}),
                    ),
                  ]),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _Stat extends StatelessWidget {
  final String label;
  final String value;
  const _Stat(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(label, style: mono(size: 10.5, color: Rm.inkFaint)),
      const SizedBox(height: 3),
      Text(value,
          style: mono(size: 14, weight: FontWeight.w600, color: Rm.ink)),
    ]);
  }
}
