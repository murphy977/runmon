import 'package:flutter/material.dart';

import '../state.dart';
import 'run_detail_page.dart';

const statusColor = {
  'running': Colors.greenAccent,
  'completed': Colors.blueAccent,
  'failed': Colors.redAccent,
  'stopped': Colors.orangeAccent,
  'created': Colors.grey,
};

const statusLabel = {
  'running': '运行中',
  'completed': '已完成',
  'failed': '失败',
  'stopped': '已停止',
  'created': '创建',
};

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
              ? const Center(
                  child: Text('还没有任务。\n在服务器上:mon run -- python train.py',
                      textAlign: TextAlign.center))
              : ListView.builder(
                  padding: const EdgeInsets.all(12),
                  itemCount: agent.runs.length,
                  itemBuilder: (context, i) {
                    final r = agent.runs[i];
                    final status = r['status'] as String? ?? '?';
                    final progress = r['progress'] as num?;
                    return Card(
                      margin: const EdgeInsets.only(bottom: 10),
                      child: ListTile(
                        onTap: () => Navigator.push(
                            context,
                            MaterialPageRoute(
                                builder: (_) => RunDetailPage(
                                    agentId: agentId,
                                    runId: r['id'] as String))),
                        title: Text(r['name'] as String? ?? '?',
                            maxLines: 1, overflow: TextOverflow.ellipsis),
                        subtitle: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const SizedBox(height: 4),
                            if (progress != null)
                              ClipRRect(
                                borderRadius: BorderRadius.circular(4),
                                child: LinearProgressIndicator(
                                    value: progress / 100.0,
                                    minHeight: 6,
                                    backgroundColor: Colors.white12),
                              ),
                            const SizedBox(height: 4),
                            Text(
                              [
                                if (progress != null) '${progress.round()}%',
                                if (r['last_loss'] != null)
                                  'loss ${(r['last_loss'] as num).toStringAsFixed(4)}',
                                fmtDuration((r['started_at'] as num?)?.toDouble(),
                                    (r['ended_at'] as num?)?.toDouble()),
                              ].join(' · '),
                              style: const TextStyle(
                                  fontFamily: 'monospace', fontSize: 12),
                            ),
                          ],
                        ),
                        trailing: Chip(
                          label: Text(statusLabel[status] ?? status,
                              style: const TextStyle(fontSize: 12)),
                          side: BorderSide(
                              color: statusColor[status] ?? Colors.grey),
                          backgroundColor: Colors.transparent,
                        ),
                      ),
                    );
                  },
                ),
        );
      },
    );
  }
}
