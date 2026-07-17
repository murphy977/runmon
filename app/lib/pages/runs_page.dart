import 'package:flutter/material.dart';

import '../state.dart';
import '../ui.dart';
import 'run_detail_page.dart';
import '../terminal_gate.dart';

class RunsPage extends StatelessWidget {
  final String agentId;
  const RunsPage({super.key, required this.agentId});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: appState,
      builder: (context, _) {
        final agent = appState.agents[agentId];
        if (agent == null) return const Scaffold(body: SizedBox());
        return Scaffold(
          appBar: AppBar(title: Text(agent.name), actions: [
            IconButton(
              tooltip: '终端',
              icon: const Icon(Icons.terminal_rounded),
              onPressed: agent.online
                  ? () => openTerminalGuarded(context, agentId, agent.name)
                  : null,
            ),
            const SizedBox(width: 8),
          ]),
          body: Column(children: [
            if (agent.hbHistory.length >= 2)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
                child: _MetricsHistoryCard(agent: agent),
              ),
            Expanded(child: _runList(agent)),
          ]),
        );
      },
    );
  }

  Widget _runList(AgentState agent) {
    return agent.runs.isEmpty
              ? Center(
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    Text('还没有任务',
                        style: sans(size: 16, weight: FontWeight.w600,
                            color: Rm.inkSoft)),
                    const SizedBox(height: 10),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 14, vertical: 10),
                      decoration: BoxDecoration(
                        color: Rm.terminalBg,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text('mon run -- python train.py',
                          style: mono(size: 12.5, color: Rm.terminalText)),
                    ),
                  ]),
                )
              : ListView.builder(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                  itemCount: agent.runs.length,
                  itemBuilder: (context, i) {
                    final r = agent.runs[i];
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: _RunCard(agentId: agentId, run: r),
                    );
                  },
                );
  }
}

/// 资源历史曲线:CPU + 内存(人人都有)+ 每张 GPU(有 N 卡才显示)。
class _MetricsHistoryCard extends StatelessWidget {
  final AgentState agent;
  const _MetricsHistoryCard({required this.agent});

  Widget _metric(String label, Color color, List<double> values, String now) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(children: [
        SizedBox(width: 52,
            child: Text(label, style: mono(size: 11.5, color: Rm.inkFaint))),
        Expanded(child: Sparkline(values: values, color: color, height: 34)),
        const SizedBox(width: 10),
        SizedBox(width: 44,
            child: Text(now, textAlign: TextAlign.right,
                style: mono(size: 12, weight: FontWeight.w600, color: Rm.ink))),
      ]),
    );
  }

  @override
  Widget build(BuildContext context) {
    final h = agent.hbHistory;
    final gpus = (agent.hb?['gpus'] as List?) ?? [];
    final cpuNow = (agent.hb?['cpu'] as num?)?.round() ?? 0;
    final memNow = (agent.hb?['mem'] as num?)?.round() ?? 0;
    return RmCard(
      padding: const EdgeInsets.fromLTRB(18, 14, 18, 6),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('资源 · 最近 ${(h.length * 10 / 60).round()} 分钟',
            style: mono(size: 11, color: Rm.inkFaint)),
        const SizedBox(height: 12),
        _metric('CPU', Rm.cyan,
            [for (final x in h) (x['cpu'] as num? ?? 0).toDouble()], '$cpuNow%'),
        _metric('内存', Rm.mint,
            [for (final x in h) (x['mem'] as num? ?? 0).toDouble()], '$memNow%'),
        for (final g in gpus)
          _metric('GPU ${g['index']}', Rm.pear, [
            for (final x in h)
              (((x['gpus'] as List?) ?? [])
                      .cast<Map<String, dynamic>>()
                      .where((y) => y['index'] == g['index'])
                      .firstOrNull?['util'] as num? ?? 0)
                  .toDouble(),
          ], '${g['util']}%'),
      ]),
    );
  }
}

class _RunCard extends StatelessWidget {
  final String agentId;
  final Map<String, dynamic> run;
  const _RunCard({required this.agentId, required this.run});

  @override
  Widget build(BuildContext context) {
    final status = run['status'] as String? ?? '?';
    final progress = run['progress'] as num?;
    final loss = run['last_loss'] as num?;
    final meta = [
      if (loss != null) 'loss ${loss.toStringAsFixed(4)}',
      fmtDuration((run['started_at'] as num?)?.toDouble(),
          (run['ended_at'] as num?)?.toDouble(),
          appState.agents[agentId]?.serverNow()),
    ].join('   ');
    return RmCard(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 16),
      onTap: () => Navigator.push(context, MaterialPageRoute(
          builder: (_) => RunDetailPage(agentId: agentId,
              runId: run['id'] as String))),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Expanded(
                child: Text(run['name'] as String? ?? '?',
                    maxLines: 1, overflow: TextOverflow.ellipsis,
                    style: sans(size: 15, weight: FontWeight.w600, spacing: -0.2))),
            const SizedBox(width: 12),
            StatusPill(status),
          ]),
          if (progress != null) ...[
            const SizedBox(height: 12),
            Row(children: [
              Expanded(
                  child: RmProgress(
                      value: progress / 100.0, color: progressColor(status))),
              const SizedBox(width: 10),
              Text('${progress.round()}%', style: mono(size: 12, color: Rm.ink)),
            ]),
          ],
          const SizedBox(height: 8),
          Text(meta, style: mono(size: 11.5, color: Rm.inkFaint)),
        ],
      ),
    );
  }
}
