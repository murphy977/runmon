/// 左滑删除行(iOS 风格):
/// 左滑一点 → 滑出红色「删除」;再继续左滑(或点「删除」)→ 行内容整个从左边
/// 滑出去,整行变红「确认删除?」;再点一下执行删除。
/// 右滑逐级退回;点页面其他地方也退一级;同一列表同时只展开一行。
library;

import 'package:flutter/material.dart';

import 'ui.dart';

/// 协调一个列表里的多行:开新行时收起旧行;页面级点击让所有行退一级。
class SwipeDeleteController extends ChangeNotifier {
  Object? _openKey;
  int _demoteTick = 0; // 自增信号:行收到后各自退一级

  int get demoteTick => _demoteTick;
  bool isOpen(Object key) => _openKey == key;

  void openRow(Object key) {
    _openKey = key;
    notifyListeners();
  }

  void demoteAll() {
    _demoteTick++;
    notifyListeners();
  }

  // ---- 点击空白处退一级:展开的行按下时先"认领"指针,页面级监听就不触发 ----
  bool _claimed = false;

  void claimPointer() => _claimed = true;

  /// 页面根部 Listener 的 onPointerDown 调这个:按下不在展开行上 → 全体退一级。
  void pagePointerDown() {
    if (_claimed) {
      _claimed = false;
      return;
    }
    demoteAll();
  }
}

enum _SwipeStage { closed, revealed, confirm }

class SwipeDeleteRow extends StatefulWidget {
  final Object rowKey;
  final SwipeDeleteController controller;
  final Widget child;
  final Future<void> Function() onDelete;
  final bool enabled;
  final double reveal; // 第一段滑出的红色区域宽度

  const SwipeDeleteRow({super.key, required this.rowKey,
      required this.controller, required this.child, required this.onDelete,
      this.enabled = true, this.reveal = 92});

  @override
  State<SwipeDeleteRow> createState() => _SwipeDeleteRowState();
}

class _SwipeDeleteRowState extends State<SwipeDeleteRow> {
  _SwipeStage _stage = _SwipeStage.closed;
  double _dx = 0; // 行内容水平位移:0(收起)→ -reveal(露删除)→ -宽度(整行滑出)
  double _width = 0;
  int _seenTick = 0;
  bool _deleting = false;
  bool _dragging = false;

  @override
  void initState() {
    super.initState();
    _seenTick = widget.controller.demoteTick;
    widget.controller.addListener(_onController);
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onController);
    super.dispose();
  }

  void _onController() {
    if (!mounted) return;
    final c = widget.controller;
    if (c.demoteTick != _seenTick) {
      _seenTick = c.demoteTick;
      if (_stage != _SwipeStage.closed) _demote();
      return;
    }
    // 别的行展开了 → 本行收起
    if (!c.isOpen(widget.rowKey) && _stage != _SwipeStage.closed) {
      _settle(_SwipeStage.closed);
    }
  }

  void _settle(_SwipeStage s) {
    setState(() {
      _stage = s;
      _dx = switch (s) {
        _SwipeStage.closed => 0,
        _SwipeStage.revealed => -widget.reveal,
        _SwipeStage.confirm => -_width,
      };
    });
    if (s != _SwipeStage.closed) widget.controller.openRow(widget.rowKey);
  }

  void _demote() => _settle(_stage == _SwipeStage.confirm
      ? _SwipeStage.revealed
      : _SwipeStage.closed);

  void _onDragUpdate(DragUpdateDetails d) {
    if (!widget.enabled) return;
    _dragging = true;
    setState(() => _dx = (_dx + d.delta.dx).clamp(-_width, 0.0));
  }

  void _onDragEnd(DragEndDetails d) {
    if (!widget.enabled) return;
    _dragging = false;
    final v = d.primaryVelocity ?? 0;
    // 确认态:往回划(或任意划动)退回删除态
    if (_stage == _SwipeStage.confirm) {
      _settle(_dx > -_width * 0.9 || v > 300
          ? _SwipeStage.revealed
          : _SwipeStage.confirm);
      return;
    }
    // 划过一半以上(或快速甩出)→ 整行滑出,进入确认态
    if (_dx < -_width * 0.55 || (v < -1200 && _stage == _SwipeStage.revealed)) {
      _settle(_SwipeStage.confirm);
      return;
    }
    // 露出删除的第一档
    if (_dx < -widget.reveal * 0.45 && v <= 60) {
      _settle(_SwipeStage.revealed);
      return;
    }
    _settle(_SwipeStage.closed);
  }

  Future<void> _confirmTap() async {
    if (_deleting) return;
    _deleting = true;
    try {
      await widget.onDelete();
    } finally {
      _deleting = false;
      if (mounted) _settle(_SwipeStage.closed);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.enabled) return widget.child;
    final r = BorderRadius.circular(Rm.radiusCard);
    final confirming = _stage == _SwipeStage.confirm;
    return Listener(
      // 只有展开状态的行认领指针,其余地方的按下都会让展开行退级
      onPointerDown: (_) {
        if (_stage != _SwipeStage.closed) widget.controller.claimPointer();
      },
      child: GestureDetector(
        onHorizontalDragUpdate: _onDragUpdate,
        onHorizontalDragEnd: _onDragEnd,
        child: LayoutBuilder(builder: (context, box) {
          _width = box.maxWidth;
          return ClipRRect(
            borderRadius: r,
            child: Stack(children: [
              // 底层红色:第一档右侧「删除」,整行滑出后居中「确认删除?」
              Positioned.fill(
                child: GestureDetector(
                  onTap: () => confirming
                      ? _confirmTap()
                      : _settle(_SwipeStage.confirm),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 160),
                    decoration: BoxDecoration(
                        color: confirming ? Rm.coralDeep : Rm.coral,
                        borderRadius: r),
                    alignment:
                        confirming ? Alignment.center : Alignment.centerRight,
                    padding: EdgeInsets.only(right: confirming ? 0 : 26),
                    child: Text(confirming ? '确认删除?' : '删除',
                        style: sans(size: confirming ? 15 : 14.5,
                            weight: FontWeight.w700, color: Colors.white)),
                  ),
                ),
              ),
              // 前层:行内容,跟手左移;确认态整体滑出屏幕左侧
              AnimatedContainer(
                duration: _dragging
                    ? Duration.zero // 拖动中跟手,松手后再动画归位
                    : const Duration(milliseconds: 180),
                curve: Curves.easeOut,
                transform: Matrix4.translationValues(_dx, 0, 0),
                child: _stage == _SwipeStage.revealed
                    // 展开时拦截行内容点击 → 收起,不触发原 onTap
                    ? GestureDetector(
                        behavior: HitTestBehavior.opaque,
                        onTap: _demote,
                        child: AbsorbPointer(child: widget.child),
                      )
                    : IgnorePointer(
                        ignoring: confirming, child: widget.child),
              ),
            ]),
          );
        }),
      ),
    );
  }
}
