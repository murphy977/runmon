/// 蹲卡提醒配置弹层:勾选要蹲的 GPU、每张卡设空闲门槛,可选预约命令。
library;

import 'package:flutter/material.dart';

import '../state.dart';
import '../ui.dart';

/// 每张卡的本地编辑状态。
class _CardCfg {
  bool selected = false;
  bool wholeCard = true; // true=整卡空闲;false=空闲显存 ≥ freeGb
  double freeGb;
  _CardCfg({this.freeGb = 10});
}

Future<void> showGpuWatchSheet(BuildContext context, String agentId) {
  return showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Rm.paper,
    shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(22))),
    builder: (_) => _GpuWatchSheet(agentId: agentId),
  );
}

class _GpuWatchSheet extends StatefulWidget {
  final String agentId;
  const _GpuWatchSheet({required this.agentId});

  @override
  State<_GpuWatchSheet> createState() => _GpuWatchSheetState();
}

class _GpuWatchSheetState extends State<_GpuWatchSheet> {
  final Map<int, _CardCfg> _cfg = {};
  double _hold = 3;
  final _cmdCtrl = TextEditingController();
  final _nameCtrl = TextEditingController();
  bool _sending = false;
  bool _hasWatch = false;

  AgentState? get _agent => appState.agents[widget.agentId];
  List<Map<String, dynamic>> get _gpus =>
      ((_agent?.hb?['gpus'] as List?) ?? []).cast<Map<String, dynamic>>();

  @override
  void initState() {
    super.initState();
    // 已有蹲卡任务:回填,方便改条件
    final watch = _agent?.hb?['gpu_watch'] as Map<String, dynamic>?;
    _hasWatch = watch != null;
    final cards = (watch?['cards'] as Map<String, dynamic>?) ?? {};
    for (final g in _gpus) {
      final idx = (g['index'] as num).toInt();
      final totalGb = ((g['mem_total'] as num?) ?? 0) / 1024;
      final c = _CardCfg(freeGb: (totalGb / 2).clamp(1, 999).roundToDouble());
      if (cards.containsKey('$idx')) {
        c.selected = true;
        final need = cards['$idx'];
        if (need != null) {
          c.wholeCard = false;
          c.freeGb = (need as num).toDouble();
        }
      }
      _cfg[idx] = c;
    }
    if (watch != null) {
      _hold = ((watch['hold_minutes'] as num?) ?? 3).toDouble();
      _cmdCtrl.text = watch['command'] as String? ?? '';
      _nameCtrl.text = watch['name'] as String? ?? '';
    }
  }

  @override
  void dispose() {
    _cmdCtrl.dispose();
    _nameCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final cards = <String, dynamic>{};
    _cfg.forEach((idx, c) {
      if (c.selected) cards['$idx'] = c.wholeCard ? null : c.freeGb;
    });
    if (cards.isEmpty) {
      _toast('先勾选至少一张卡');
      return;
    }
    setState(() => _sending = true);
    final r = await appState.sendCmd(widget.agentId, 'gpu_watch_set', '', {
      'cards': cards,
      'hold_minutes': _hold,
      'command': _cmdCtrl.text.trim(),
      'name': _nameCtrl.text.trim(),
    });
    if (!mounted) return;
    setState(() => _sending = false);
    if (r['ok'] == true) {
      final msg = _cmdCtrl.text.trim().isEmpty
          ? '蹲卡已开启,等到就通知你 🎉'
          : '蹲卡 + 预约已开启,等到自动开跑 🚀';
      // 先拿 messenger 再 pop:pop 之后 context 已销毁,不能再向上查找
      final messenger = ScaffoldMessenger.maybeOf(context);
      Navigator.pop(context);
      messenger?.showSnackBar(SnackBar(content: Text(msg)));
    } else {
      _toast('开启失败:${r['error'] ?? '未知错误'}');
    }
  }

  Future<void> _cancel() async {
    setState(() => _sending = true);
    final r =
        await appState.sendCmd(widget.agentId, 'gpu_watch_cancel', '', {});
    if (!mounted) return;
    setState(() => _sending = false);
    if (r['ok'] == true) {
      final messenger = ScaffoldMessenger.maybeOf(context);
      Navigator.pop(context);
      messenger?.showSnackBar(const SnackBar(content: Text('已取消蹲卡')));
    } else {
      _toast('取消失败:${r['error'] ?? '未知错误'}');
    }
  }

  void _toast(String msg) {
    final messenger = ScaffoldMessenger.maybeOf(context);
    messenger?.showSnackBar(SnackBar(content: Text(msg)));
  }

  InputDecoration _inputDeco(String hint) => InputDecoration(
        hintText: hint,
        hintStyle: mono(size: 12.5, color: Rm.inkFaint),
        filled: true,
        fillColor: Rm.card,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(Rm.radiusInput),
            borderSide: const BorderSide(color: Rm.hairline)),
        focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(Rm.radiusInput),
            borderSide: const BorderSide(color: Rm.pearDeep, width: 1.4)),
      );

  Widget _holdChip(double minutes, String label) {
    final on = _hold == minutes;
    return ChoiceChip(
      label: Text(label),
      selected: on,
      onSelected: (_) => setState(() => _hold = minutes),
      labelStyle: sans(
          size: 12.5,
          weight: FontWeight.w600,
          color: on ? Rm.pearDeep : Rm.inkSoft),
      selectedColor: Rm.pearTint,
      backgroundColor: Rm.card,
      side: BorderSide(color: on ? Rm.pearDeep : Rm.hairline),
      showCheckmark: false,
      shape: const StadiumBorder(),
    );
  }

  Widget _gpuRow(Map<String, dynamic> g) {
    final idx = (g['index'] as num).toInt();
    final c = _cfg[idx]!;
    final totalMb = ((g['mem_total'] as num?) ?? 0).toDouble();
    final freeMb = totalMb - ((g['mem_used'] as num?) ?? 0).toDouble();
    final totalGb = totalMb / 1024;
    return RmCard(
      padding: const EdgeInsets.fromLTRB(6, 2, 14, 2),
      onTap: () => setState(() => c.selected = !c.selected),
      child: Column(children: [
        Row(children: [
          Checkbox(
            value: c.selected,
            activeColor: Rm.pearDeep,
            onChanged: (v) => setState(() => c.selected = v ?? false),
          ),
          Text('GPU $idx',
              style: sans(size: 14, weight: FontWeight.w700, spacing: -0.2)),
          const SizedBox(width: 10),
          Text('${g['util']}%',
              style: mono(size: 11.5, color: Rm.inkFaint)),
          const Spacer(),
          Text(
              '空闲 ${(freeMb / 1024).toStringAsFixed(0)} / '
              '${totalGb.toStringAsFixed(0)}GB',
              style: mono(size: 11.5, color: Rm.inkSoft)),
        ]),
        if (c.selected)
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 0, 0, 10),
            child: Row(children: [
              _modeChip(c, true, '整卡空闲'),
              const SizedBox(width: 8),
              _modeChip(c, false, '空闲 ≥ ${c.freeGb.round()}GB'),
              if (!c.wholeCard)
                Expanded(
                  child: Slider(
                    value: c.freeGb.clamp(1, totalGb.floorToDouble()),
                    min: 1,
                    max: totalGb.floorToDouble().clamp(1, 9999),
                    divisions: totalGb.floor() > 1 ? totalGb.floor() - 1 : 1,
                    activeColor: Rm.pearDeep,
                    inactiveColor: Rm.paper3,
                    onChanged: (v) =>
                        setState(() => c.freeGb = v.roundToDouble()),
                  ),
                )
              else
                const Spacer(),
            ]),
          ),
      ]),
    );
  }

  Widget _modeChip(_CardCfg c, bool whole, String label) {
    final on = c.wholeCard == whole;
    return GestureDetector(
      onTap: () => setState(() => c.wholeCard = whole),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 6),
        decoration: BoxDecoration(
          color: on ? Rm.pearTint : Rm.paper2,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: on ? Rm.pearDeep : Rm.hairline),
        ),
        child: Text(label,
            style: sans(
                size: 12,
                weight: FontWeight.w600,
                color: on ? Rm.pearDeep : Rm.inkSoft)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.of(context).viewInsets.bottom;
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(bottom: bottomInset),
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Text('蹲卡提醒',
                  style: sans(size: 18, weight: FontWeight.w700, spacing: -0.3)),
              const Spacer(),
              if (_hasWatch)
                SoftButton(
                    label: '取消蹲卡',
                    icon: Icons.close_rounded,
                    deep: Rm.coralDeep,
                    tint: Rm.coralTint,
                    onPressed: _sending ? null : _cancel),
            ]),
            const SizedBox(height: 6),
            Text('勾选的卡全部空出来时,手机马上收到通知;也可以填一条命令,到点自动开跑。',
                style: sans(size: 12.5, color: Rm.inkSoft, height: 1.5)),
            const SizedBox(height: 16),
            const SectionLabel('选择要蹲的卡'),
            for (final g in _gpus)
              Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: _gpuRow(g)),
            const SizedBox(height: 10),
            const SectionLabel('需持续满足(防假空闲)'),
            Wrap(spacing: 8, children: [
              _holdChip(0, '立即'),
              _holdChip(1, '1 分钟'),
              _holdChip(3, '3 分钟'),
              _holdChip(10, '10 分钟'),
            ]),
            const SizedBox(height: 18),
            const SectionLabel('预约执行(可选)'),
            TextField(
                controller: _cmdCtrl,
                style: mono(size: 13, color: Rm.ink),
                decoration:
                    _inputDeco('cd ~/proj && python train.py(留空则只通知)')),
            const SizedBox(height: 8),
            TextField(
                controller: _nameCtrl,
                style: sans(size: 13.5),
                decoration: _inputDeco('任务名(可选)')),
            const SizedBox(height: 8),
            Text('满足条件时在服务器上用 bash 执行(家目录起步),自动设好 '
                'CUDA_VISIBLE_DEVICES,跑起来就是一个可监控的普通任务。',
                style: sans(size: 11.5, color: Rm.inkFaint, height: 1.5)),
            const SizedBox(height: 18),
            Center(
                child: PushButton(
                    label: _hasWatch ? '更新蹲卡' : '开始蹲卡',
                    icon: Icons.hourglass_top_rounded,
                    onPressed: _sending ? null : _submit)),
          ]),
        ),
      ),
    );
  }
}

/// 服务器页顶部的"蹲卡中"横幅:实时达标状态 + 点击进入编辑。
class GpuWatchBanner extends StatelessWidget {
  final String agentId;
  const GpuWatchBanner({super.key, required this.agentId});

  @override
  Widget build(BuildContext context) {
    final agent = appState.agents[agentId];
    final watch = agent?.hb?['gpu_watch'] as Map<String, dynamic>?;
    if (agent == null || watch == null || watch['fired'] == true) {
      return const SizedBox.shrink();
    }
    final cards = (watch['cards'] as Map<String, dynamic>?) ?? {};
    final states =
        ((watch['card_states'] as List?) ?? []).cast<Map<String, dynamic>>();
    final okCount = states.where((s) => s['ok'] == true).length;
    final holdMin = ((watch['hold_minutes'] as num?) ?? 3).toDouble();
    final since = (watch['since'] as num?)?.toDouble();
    final desc = cards.entries
        .map((e) =>
            '卡${e.key}${e.value == null ? ' 整卡' : ' ≥${(e.value as num).round()}GB'}')
        .join(' · ');
    String status;
    if (watch['ok'] == true && since != null) {
      final held = (agent.serverNow() - since).clamp(0, double.infinity);
      status = holdMin > 0
          ? '全部达标,持续 ${fmtDuration(0, held.toDouble())} / ${holdMin.round()} 分钟'
          : '全部达标,即将触发';
    } else {
      status = '$okCount/${states.length} 张达标,等待中';
    }
    final command = watch['command'] as String? ?? '';
    return RmCard(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      onTap: () => showGpuWatchSheet(context, agentId),
      child: Row(children: [
        const Icon(Icons.hourglass_top_rounded, size: 18, color: Rm.pearDeep),
        const SizedBox(width: 10),
        Expanded(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('蹲卡中 · $desc',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: sans(size: 13, weight: FontWeight.w600)),
            const SizedBox(height: 3),
            Text(command.isEmpty ? status : '$status · 预约:$command',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: mono(size: 11, color: Rm.inkSoft)),
          ]),
        ),
        const SizedBox(width: 6),
        Icon(Icons.chevron_right_rounded, size: 18, color: Rm.inkFaint),
      ]),
    );
  }
}
