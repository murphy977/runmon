import 'package:flutter/material.dart';

import '../state.dart';
import '../ui.dart';
import 'run_detail_page.dart';

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
          appBar: AppBar(title: Text(agent.name)),
          body: agent.runs.isEmpty
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
                ),
        );
      },
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
          (run['ended_at'] as num?)?.toDouble()),
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
