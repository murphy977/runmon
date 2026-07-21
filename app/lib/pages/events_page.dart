import 'package:flutter/material.dart';

import '../state.dart';
import '../swipe_delete.dart';
import '../ui.dart';

const _levelColor = {
  'critical': (Rm.coralDeep, Rm.coral),
  'warning': (Rm.pearDeep, Rm.pear),
  'info': (Rm.mintDeep, Rm.mint),
};

class EventsPage extends StatefulWidget {
  const EventsPage({super.key});

  @override
  State<EventsPage> createState() => _EventsPageState();
}

class _EventsPageState extends State<EventsPage> {
  final _swipeCtrl = SwipeDeleteController();

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: appState,
      builder: (context, _) {
        final items = <(String, String, Map<String, dynamic>)>[];
        for (final a in appState.agents.values) {
          for (final e in a.events) {
            items.add((a.link.agentId, a.name, e));
          }
        }
        items.sort((x, y) => ((y.$3['received_at'] as num?) ?? 0)
            .compareTo((x.$3['received_at'] as num?) ?? 0));
        return Scaffold(
          appBar: AppBar(title: const Text('事件')),
          body: items.isEmpty
              ? Center(
                  child: Text('还没有事件。\n任务完成、失败、假死时会出现在这里。',
                      textAlign: TextAlign.center,
                      style: sans(size: 14, color: Rm.inkFaint, height: 1.7)))
              : Listener(
                  behavior: HitTestBehavior.translucent,
                  onPointerDown: (_) => _swipeCtrl.pagePointerDown(),
                  child: ListView.builder(
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                    itemCount: items.length,
                    itemBuilder: (context, i) {
                      final (agentId, agentName, e) = items[i];
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: SwipeDeleteRow(
                          rowKey: identityHashCode(e),
                          controller: _swipeCtrl,
                          onDelete: () async =>
                              appState.removeEvent(agentId, e),
                          child: _EventCard(agentName: agentName, e: e),
                        ),
                      );
                    },
                  ),
                ),
        );
      },
    );
  }
}

class _EventCard extends StatelessWidget {
  final String agentName;
  final Map<String, dynamic> e;
  const _EventCard({required this.agentName, required this.e});

  @override
  Widget build(BuildContext context) {
    final (deep, dot) = _levelColor[e['level']] ?? (Rm.inkSoft, Rm.inkFaint);
    final ts = (e['received_at'] as num?)?.toInt();
    final when = ts == null
        ? ''
        : TimeOfDay.fromDateTime(DateTime.fromMillisecondsSinceEpoch(ts))
            .format(context);
    return RmCard(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 5),
            child: Container(width: 8, height: 8,
                decoration: BoxDecoration(color: dot, shape: BoxShape.circle)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(e['title'] as String? ?? '',
                    style: sans(size: 14, weight: FontWeight.w600, color: deep)),
                if ((e['body'] as String?)?.isNotEmpty == true)
                  Padding(
                    padding: const EdgeInsets.only(top: 3),
                    child: Text(e['body'] as String,
                        style: sans(size: 13, color: Rm.inkSoft, height: 1.5)),
                  ),
                const SizedBox(height: 6),
                Text('$agentName · $when',
                    style: mono(size: 11, color: Rm.inkFaint)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
