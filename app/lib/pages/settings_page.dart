import 'package:flutter/material.dart';

import '../settings.dart';
import '../ui.dart';

class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key});

  String _fmt(int m) =>
      '${(m ~/ 60).toString().padLeft(2, '0')}:${(m % 60).toString().padLeft(2, '0')}';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('设置')),
      body: ListenableBuilder(
        listenable: appSettings,
        builder: (context, _) => ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const _SectionLabel('通知'),
            Container(
              padding: const EdgeInsets.all(14),
              margin: const EdgeInsets.only(bottom: 8),
              decoration: BoxDecoration(
                  color: Rm.cyanTint,
                  borderRadius: BorderRadius.circular(Rm.radiusInput)),
              child: Text(
                  '手机锁屏或后台久了,App 内通知可能收不到。想万无一失,在服务器上跑 '
                  'mon init 配置 ntfy / Bark / Telegram,由服务器直接推送,不依赖 App 在线。',
                  style: sans(size: 12.5, color: Rm.cyanDeep, height: 1.55)),
            ),
            RmCard(
              padding: const EdgeInsets.symmetric(horizontal: 6),
              child: Column(children: [
                SwitchListTile(
                  title: Text('系统通知', style: sans(size: 15)),
                  subtitle: Text('关闭后只在 App 内看事件',
                      style: sans(size: 12.5, color: Rm.inkFaint)),
                  value: appSettings.systemNotify,
                  activeThumbColor: Rm.pearDeep,
                  onChanged: appSettings.setSystemNotify,
                ),
              ]),
            ),
            const SizedBox(height: 8),
            RmCard(
              padding: const EdgeInsets.symmetric(horizontal: 6),
              child: Column(children: [
                SwitchListTile(
                  title: Text('免打扰时段', style: sans(size: 15)),
                  subtitle: Text('时段内事件静音但仍进列表,早上能补看',
                      style: sans(size: 12.5, color: Rm.inkFaint)),
                  value: appSettings.dndEnabled,
                  activeThumbColor: Rm.pearDeep,
                  onChanged: appSettings.setDnd,
                ),
                if (appSettings.dndEnabled)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                    child: Row(children: [
                      _TimeChip(label: '从', value: _fmt(appSettings.dndStart),
                          onTap: () => _pick(context, true)),
                      const SizedBox(width: 12),
                      _TimeChip(label: '到', value: _fmt(appSettings.dndEnd),
                          onTap: () => _pick(context, false)),
                    ]),
                  ),
              ]),
            ),
            const SizedBox(height: 16),
            const _SectionLabel('哪些事件推通知'),
            RmCard(
              padding: const EdgeInsets.symmetric(horizontal: 6),
              child: Column(children: [
                for (final e in eventTypeLabels.entries)
                  SwitchListTile(
                    dense: true,
                    title: Text(e.value, style: sans(size: 14.5)),
                    value: !appSettings.mutedTypes.contains(e.key),
                    activeThumbColor: Rm.pearDeep,
                    onChanged: (v) => appSettings.setTypeNotify(e.key, v),
                  ),
              ]),
            ),
            const SizedBox(height: 16),
            const _SectionLabel('终端'),
            RmCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                Text('字号 ${appSettings.terminalFontSize.round()}',
                    style: sans(size: 14.5)),
                Slider(
                  value: appSettings.terminalFontSize,
                  min: 10, max: 20, divisions: 10,
                  activeColor: Rm.pearDeep,
                  label: '${appSettings.terminalFontSize.round()}',
                  onChanged: appSettings.setTermFont,
                ),
              ]),
            ),
            const SizedBox(height: 24),
            Center(
              child: Text('RunMon · 长任务陪伴器',
                  style: mono(size: 11.5, color: Rm.inkFaint)),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _pick(BuildContext context, bool isStart) async {
    final cur = isStart ? appSettings.dndStart : appSettings.dndEnd;
    final t = await showTimePicker(
        context: context,
        initialTime: TimeOfDay(hour: cur ~/ 60, minute: cur % 60));
    if (t == null) return;
    final m = t.hour * 60 + t.minute;
    appSettings.setDndWindow(
        isStart ? m : appSettings.dndStart, isStart ? appSettings.dndEnd : m);
  }
}

class _SectionLabel extends StatelessWidget {
  final String text;
  const _SectionLabel(this.text);
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.only(bottom: 8, left: 4),
      child: Text(text.toUpperCase(),
          style: mono(size: 11, color: Rm.inkFaint)));
}

class _TimeChip extends StatelessWidget {
  final String label, value;
  final VoidCallback onTap;
  const _TimeChip({required this.label, required this.value, required this.onTap});
  @override
  Widget build(BuildContext context) => Expanded(
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(10),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
                color: Rm.paper2, borderRadius: BorderRadius.circular(10)),
            child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
              Text(label, style: sans(size: 13, color: Rm.inkFaint)),
              Text(value, style: mono(size: 15, weight: FontWeight.w600)),
            ]),
          ),
        ),
      );
}
