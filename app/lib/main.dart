import 'package:flutter/material.dart';

import 'pages/pair_page.dart';
import 'pages/runs_page.dart';
import 'state.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  appState.init();
  runApp(const RunMonApp());
}

class RunMonApp extends StatelessWidget {
  const RunMonApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'RunMon',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF00C853), brightness: Brightness.dark),
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFF101418),
      ),
      home: const HomePage(),
    );
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  String? _shownNotice;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: appState,
      builder: (context, _) {
        // 新事件横幅
        if (appState.lastNotice != null && appState.lastNotice != _shownNotice) {
          _shownNotice = appState.lastNotice;
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) {
              ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                  content: Text(_shownNotice!),
                  duration: const Duration(seconds: 5)));
            }
          });
        }
        final agents = appState.agents.values.toList();
        return Scaffold(
          appBar: AppBar(title: const Text('RunMon'), centerTitle: false),
          floatingActionButton: FloatingActionButton.extended(
            icon: const Icon(Icons.add_link),
            label: const Text('配对服务器'),
            onPressed: () => Navigator.push(context,
                MaterialPageRoute(builder: (_) => const PairPage())),
          ),
          body: agents.isEmpty
              ? const Center(
                  child: Padding(
                    padding: EdgeInsets.all(32),
                    child: Text(
                      '还没有服务器。\n\n在服务器上运行:\n  pip install runmon\n  mon pair --relay <你的relay地址>\n\n然后点右下角「配对服务器」粘贴配对载荷。',
                      style: TextStyle(fontFamily: 'monospace', height: 1.6),
                    ),
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(12),
                  itemCount: agents.length,
                  itemBuilder: (context, i) => _ServerCard(agent: agents[i]),
                ),
        );
      },
    );
  }
}

class _ServerCard extends StatelessWidget {
  final AgentState agent;
  const _ServerCard({required this.agent});

  @override
  Widget build(BuildContext context) {
    final hb = agent.hb;
    final running =
        agent.runs.where((r) => r['status'] == 'running').length;
    final gpus = (hb?['gpus'] as List?) ?? [];
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => Navigator.push(context,
            MaterialPageRoute(builder: (_) => RunsPage(agentId: agent.link.agentId))),
        onLongPress: () async {
          final ok = await showDialog<bool>(
              context: context,
              builder: (c) => AlertDialog(
                    title: Text('删除「${agent.name}」?'),
                    content: const Text('删除后需重新配对。服务器上的任务不受影响。'),
                    actions: [
                      TextButton(
                          onPressed: () => Navigator.pop(c, false),
                          child: const Text('取消')),
                      FilledButton(
                          onPressed: () => Navigator.pop(c, true),
                          child: const Text('删除')),
                    ],
                  ));
          if (ok == true) appState.removeServer(agent.link.agentId);
        },
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Icon(Icons.circle,
                    size: 12,
                    color: !agent.connected
                        ? Colors.grey
                        : agent.online
                            ? Colors.greenAccent
                            : Colors.redAccent),
                const SizedBox(width: 8),
                Expanded(
                    child: Text(agent.name,
                        style: Theme.of(context).textTheme.titleMedium)),
                Text(
                    !agent.connected
                        ? '连接中…'
                        : agent.online
                            ? '在线 · $running 个运行中'
                            : '服务器离线',
                    style: Theme.of(context).textTheme.bodySmall),
              ]),
              if (gpus.isNotEmpty) ...[
                const SizedBox(height: 12),
                for (final g in gpus)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(children: [
                      SizedBox(
                          width: 56,
                          child: Text('GPU${g['index']}',
                              style: const TextStyle(
                                  fontFamily: 'monospace', fontSize: 12))),
                      Expanded(
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(4),
                          child: LinearProgressIndicator(
                              value: (g['util'] as num) / 100.0,
                              minHeight: 8,
                              backgroundColor: Colors.white12),
                        ),
                      ),
                      SizedBox(
                          width: 110,
                          child: Text(
                              ' ${g['util']}% ${g['mem_used']}/${g['mem_total']}M',
                              style: const TextStyle(
                                  fontFamily: 'monospace', fontSize: 12),
                              textAlign: TextAlign.right)),
                    ]),
                  ),
              ],
              if (hb != null)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text('CPU ${hb['cpu']}% · 内存 ${hb['mem']}%',
                      style: Theme.of(context).textTheme.bodySmall),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
