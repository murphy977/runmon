import 'package:flutter/material.dart';

import 'notifications.dart';
import 'pages/events_page.dart';
import 'pages/pair_page.dart';
import 'pages/settings_page.dart';
import 'pages/runs_page.dart';
import 'settings.dart';
import 'state.dart';
import 'ui.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  appState.init();
  appSettings.load();
  initNotifications();
  runApp(const RunMonApp());
}

class RunMonApp extends StatelessWidget {
  const RunMonApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'RunMon',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
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
          appBar: AppBar(
            title: Row(mainAxisSize: MainAxisSize.min, children: [
              const Text('RunMon'),
              const SizedBox(width: 7),
              // 品牌记号:梨黄圆点
              Container(width: 8, height: 8, margin: const EdgeInsets.only(top: 6),
                  decoration: const BoxDecoration(
                      color: Rm.pear, shape: BoxShape.circle)),
            ]),
            actions: [
              IconButton(
                tooltip: '事件',
                icon: const Icon(Icons.notifications_none_rounded),
                onPressed: () => Navigator.push(context,
                    MaterialPageRoute(builder: (_) => const EventsPage())),
              ),
              IconButton(
                tooltip: '设置',
                icon: const Icon(Icons.settings_outlined),
                onPressed: () => Navigator.push(context,
                    MaterialPageRoute(builder: (_) => const SettingsPage())),
              ),
              const SizedBox(width: 4),
            ],
          ),
          floatingActionButton: Padding(
            padding: const EdgeInsets.only(bottom: 6, right: 6),
            child: PushButton(
              label: '添加服务器',
              icon: Icons.add_link,
              onPressed: () => Navigator.push(context,
                  MaterialPageRoute(builder: (_) => const PairPage())),
            ),
          ),
          body: agents.isEmpty
              ? const _EmptyHome()
              : ListView.builder(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 96),
                  itemCount: agents.length,
                  itemBuilder: (context, i) => Padding(
                    padding: const EdgeInsets.only(bottom: 14),
                    child: _ServerCard(agent: agents[i]),
                  ),
                ),
        );
      },
    );
  }
}

class _EmptyHome extends StatelessWidget {
  const _EmptyHome();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('让训练跑它的,\n你去过你的生活。',
                  style: sans(size: 26, weight: FontWeight.w700,
                      spacing: -0.5, height: 1.3)),
              const SizedBox(height: 14),
              Text('在服务器上装好 agent,任务状态、GPU、事件通知就会出现在这里。',
                  style: sans(size: 14.5, color: Rm.inkSoft, height: 1.6)),
              const SizedBox(height: 22),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Rm.terminalBg,
                  borderRadius: BorderRadius.circular(Rm.radiusCard),
                ),
                child: Text(
                    'pip install runmon\nmon pair --relay <你的relay地址>',
                    style: mono(size: 13, color: Rm.terminalText, height: 1.7)),
              ),
              const SizedBox(height: 22),
              Text('然后点右下角「配对服务器」,粘贴配对载荷。',
                  style: sans(size: 13.5, color: Rm.inkFaint)),
            ],
          ),
        ),
      ),
    );
  }
}

class _ServerCard extends StatelessWidget {
  final AgentState agent;
  const _ServerCard({required this.agent});

  @override
  Widget build(BuildContext context) {
    final hb = agent.hb;
    final gpus = (hb?['gpus'] as List?) ?? [];
    final running = agent.runs.where((r) => r['status'] == 'running').length;
    final (dotColor, statusText, statusColor) = !agent.connected
        ? (Rm.inkFaint, '连接中…', Rm.inkFaint)
        : agent.online
            ? (Rm.mint, running > 0 ? '$running 个任务运行中' : '在线 · 空闲',
               running > 0 ? Rm.mintDeep : Rm.inkSoft)
            : (Rm.coral, '服务器离线', Rm.coralDeep);
    return RmCard(
      onTap: () => Navigator.push(context, MaterialPageRoute(
          builder: (_) => RunsPage(agentId: agent.link.agentId))),
      onLongPress: () => _confirmDelete(context),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Container(width: 9, height: 9,
                decoration: BoxDecoration(color: dotColor, shape: BoxShape.circle)),
            const SizedBox(width: 10),
            Expanded(
                child: Text(agent.name,
                    style: sans(size: 16, weight: FontWeight.w600, spacing: -0.2))),
            Text(statusText,
                style: sans(size: 12.5, weight: FontWeight.w500, color: statusColor)),
          ]),
          if (gpus.isNotEmpty) ...[
            const SizedBox(height: 16),
            for (final g in gpus)
              MeterRow(
                label: 'GPU ${g['index']}',
                fraction: ((g['util'] as num?) ?? 0) / 100.0,
                value: '${g['util']}% · ${g['mem_used']}/${g['mem_total']}M',
              ),
          ],
          if (hb != null) ...[
            SizedBox(height: gpus.isEmpty ? 14 : 4),
            Text([
              if (gpus.isNotEmpty)
                'GPU ${gpus.map((g) => '${g['util']}%').join('/')}',
              'CPU ${hb['cpu']}%',
              '内存 ${hb['mem']}%',
            ].join('   ·   '), style: mono(size: 11.5, color: Rm.inkFaint)),
          ],
        ],
      ),
    );
  }

  Future<void> _confirmDelete(BuildContext context) async {
    final ok = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
              title: Text('删除「${agent.name}」?'),
              content: const Text('删除后需重新配对,服务器上的任务不受影响。'),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(c, false),
                    child: const Text('取消')),
                SoftButton(
                    label: '删除', icon: Icons.delete_outline,
                    deep: Rm.coralDeep, tint: Rm.coralTint,
                    onPressed: () => Navigator.pop(c, true)),
              ],
            ));
    if (ok == true) appState.removeServer(agent.link.agentId);
  }
}
