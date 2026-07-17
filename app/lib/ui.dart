/// Hallmark · theme: Hum(quiet register) · genre: playful→elegant
/// paper #F7F5EC(oklch 97% .012 95) · ink #12171B · accents: pear/cyan/coral/mint
/// display+body: Plus Jakarta Sans · mono: JetBrains Mono · radius: card 16 / pill
/// 设计纪律:每页最多一个 push 按钮;coral 只给危险/失败;圆角无处不在;阴影单层柔和。
library;

import 'package:flutter/material.dart';

// ---------- 色板 token(OKLCH → sRGB,勿在页面里写裸色值) ----------

abstract final class Rm {
  static const paper = Color(0xFFF7F5EC);
  static const paper2 = Color(0xFFEEEBDF);
  static const paper3 = Color(0xFFE5E1D3);
  static const card = Color(0xFFFEFDFA);
  static const hairline = Color(0xFFD7D4CA);

  static const ink = Color(0xFF12171B);
  static const inkSoft = Color(0xFF50565C);
  static const inkFaint = Color(0xFF82878C);

  static const pear = Color(0xFFF6CE00);
  static const pearDeep = Color(0xFFB49600);
  static const pearTint = Color(0xFFF7F0D6);

  static const cyan = Color(0xFF009FEF);
  static const cyanDeep = Color(0xFF006DA6);
  static const cyanTint = Color(0xFFDEF0FC);

  static const coral = Color(0xFFFF3A5D);
  static const coralDeep = Color(0xFFBD1F3D);
  static const coralTint = Color(0xFFFCE9E9);

  static const mint = Color(0xFF66DA85);
  static const mintDeep = Color(0xFF287C42);
  static const mintTint = Color(0xFFDFF3E2);

  static const terminalBg = Color(0xFF151B21);
  static const terminalText = Color(0xFFE2DED0);

  static const sans = 'PlusJakartaSans';
  static const mono = 'JetBrainsMono';

  static const radiusCard = 16.0;
  static const radiusInput = 12.0;

  static List<BoxShadow> get softShadow => [
        BoxShadow(
            color: ink.withValues(alpha: 0.08),
            blurRadius: 24,
            spreadRadius: -12,
            offset: const Offset(0, 10)),
      ];
}

// ---------- 排版 ----------

TextStyle sans({double size = 14, FontWeight weight = FontWeight.w400,
        Color color = Rm.ink, double? spacing, double? height}) =>
    TextStyle(fontFamily: Rm.sans, fontSize: size, fontWeight: weight,
        color: color, letterSpacing: spacing, height: height);

TextStyle mono({double size = 12, FontWeight weight = FontWeight.w400,
        Color color = Rm.inkSoft, double? height}) =>
    TextStyle(fontFamily: Rm.mono, fontSize: size, fontWeight: weight,
        color: color, height: height,
        fontFeatures: const [FontFeature.tabularFigures()]);

// ---------- 状态语义(色彩只在这里映射一次) ----------

class StatusStyle {
  final String label;
  final Color deep;
  final Color tint;
  final Color dot;
  const StatusStyle(this.label, this.deep, this.tint, this.dot);
}

const statusStyles = {
  'running': StatusStyle('运行中', Rm.mintDeep, Rm.mintTint, Rm.mint),
  'completed': StatusStyle('已完成', Rm.cyanDeep, Rm.cyanTint, Rm.cyan),
  'failed': StatusStyle('失败', Rm.coralDeep, Rm.coralTint, Rm.coral),
  'stopped': StatusStyle('已停止', Rm.inkSoft, Rm.paper3, Rm.inkFaint),
  'created': StatusStyle('创建', Rm.inkFaint, Rm.paper2, Rm.inkFaint),
};

StatusStyle statusOf(String? s) =>
    statusStyles[s] ?? StatusStyle(s ?? '?', Rm.inkSoft, Rm.paper3, Rm.inkFaint);

Color progressColor(String? status) => switch (status) {
      'completed' => Rm.mint,
      'failed' => Rm.coral,
      _ => Rm.pear,
    };

// ---------- 主题 ----------

ThemeData buildTheme() {
  final base = ThemeData(
    useMaterial3: true,
    brightness: Brightness.light,
    fontFamily: Rm.sans,
    scaffoldBackgroundColor: Rm.paper,
    colorScheme: ColorScheme.fromSeed(
        seedColor: Rm.pear, brightness: Brightness.light)
        .copyWith(surface: Rm.paper, onSurface: Rm.ink, primary: Rm.pearDeep),
  );
  return base.copyWith(
    appBarTheme: AppBarTheme(
      backgroundColor: Rm.paper,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      centerTitle: false,
      titleTextStyle: sans(size: 19, weight: FontWeight.w700, spacing: -0.4),
      iconTheme: const IconThemeData(color: Rm.ink, size: 20),
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: Rm.ink,
      contentTextStyle: sans(size: 13.5, weight: FontWeight.w500, color: Rm.paper),
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: Rm.card,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      titleTextStyle: sans(size: 16, weight: FontWeight.w700),
      contentTextStyle: sans(size: 14, color: Rm.inkSoft, height: 1.55),
    ),
    dividerTheme: const DividerThemeData(color: Rm.hairline, thickness: 1),
  );
}

// ---------- 组件 ----------

/// 卡片:奶油纸上的暖白卡,细边 + 单层软影,16 圆角。
class RmCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;
  const RmCard({super.key, required this.child, this.onTap, this.onLongPress,
      this.padding = const EdgeInsets.all(18)});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Rm.card,
        borderRadius: BorderRadius.circular(Rm.radiusCard),
        border: Border.all(color: Rm.hairline, width: 1),
        boxShadow: Rm.softShadow,
      ),
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(Rm.radiusCard),
        child: InkWell(
          borderRadius: BorderRadius.circular(Rm.radiusCard),
          hoverColor: Rm.paper2.withValues(alpha: 0.5),
          splashColor: Rm.pearTint,
          highlightColor: Rm.paper2,
          onTap: onTap,
          onLongPress: onLongPress,
          child: Padding(padding: padding, child: child),
        ),
      ),
    );
  }
}

/// 状态胶囊:tint 底 + deep 字,mono 小写。
class StatusPill extends StatelessWidget {
  final String status;
  const StatusPill(this.status, {super.key});

  @override
  Widget build(BuildContext context) {
    final s = statusOf(status);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
          color: s.tint, borderRadius: BorderRadius.circular(999)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Container(width: 6, height: 6,
            decoration: BoxDecoration(color: s.dot, shape: BoxShape.circle)),
        const SizedBox(width: 6),
        Text(s.label, style: sans(size: 12, weight: FontWeight.w600, color: s.deep)),
      ]),
    );
  }
}

/// 圆角进度条。
class RmProgress extends StatelessWidget {
  final double? value; // 0~1
  final Color color;
  final double height;
  const RmProgress({super.key, required this.value, required this.color,
      this.height = 7});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(height / 2),
      child: LinearProgressIndicator(
        value: value,
        minHeight: height,
        backgroundColor: Rm.paper2,
        valueColor: AlwaysStoppedAnimation(color),
      ),
    );
  }
}

/// Hum push 按钮(整页唯一主行动):梨黄面 + 实色厚边,按下物理下沉。
class PushButton extends StatefulWidget {
  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  const PushButton({super.key, required this.label, this.icon, this.onPressed});

  @override
  State<PushButton> createState() => _PushButtonState();
}

class _PushButtonState extends State<PushButton> {
  bool _down = false;

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onPressed != null;
    final edge = _down ? 1.0 : 3.0;
    return Opacity(
      opacity: enabled ? 1 : 0.5,
      child: GestureDetector(
        onTapDown: enabled ? (_) => setState(() => _down = true) : null,
        onTapUp: enabled ? (_) => setState(() => _down = false) : null,
        onTapCancel: enabled ? () => setState(() => _down = false) : null,
        onTap: widget.onPressed,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 90),
          curve: Curves.easeOut,
          transform: Matrix4.translationValues(0, _down ? 2 : 0, 0),
          padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 13),
          decoration: BoxDecoration(
            color: Rm.pear,
            borderRadius: BorderRadius.circular(999),
            boxShadow: [
              BoxShadow(color: Rm.pearDeep, offset: Offset(0, edge)),
              if (!_down)
                BoxShadow(color: Rm.pearDeep.withValues(alpha: 0.25),
                    blurRadius: 10, offset: const Offset(0, 5), spreadRadius: -3),
            ],
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            if (widget.icon != null) ...[
              Icon(widget.icon, size: 17, color: Rm.ink),
              const SizedBox(width: 7),
            ],
            Text(widget.label,
                style: sans(size: 14.5, weight: FontWeight.w700)),
          ]),
        ),
      ),
    );
  }
}

/// Hum soft 按钮(次级操作):tint 底 + deep 字。
class SoftButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color deep;
  final Color tint;
  final VoidCallback? onPressed;
  const SoftButton({super.key, required this.label, required this.icon,
      this.deep = Rm.inkSoft, this.tint = Rm.paper2, this.onPressed});

  @override
  Widget build(BuildContext context) {
    return TextButton.icon(
      onPressed: onPressed,
      style: TextButton.styleFrom(
        backgroundColor: tint,
        foregroundColor: deep,
        disabledBackgroundColor: Rm.paper2.withValues(alpha: 0.5),
        disabledForegroundColor: Rm.inkFaint,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        shape: const StadiumBorder(),
        textStyle: sans(size: 13.5, weight: FontWeight.w600),
        overlayColor: deep.withValues(alpha: 0.10),
      ),
      icon: Icon(icon, size: 16),
      label: Text(label),
    );
  }
}

/// GPU/资源横条:mono 标签 + 圆角条 + tabular 数值。
class MeterRow extends StatelessWidget {
  final String label;
  final double fraction; // 0~1
  final String value;
  const MeterRow({super.key, required this.label, required this.fraction,
      required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(children: [
        SizedBox(width: 52,
            child: Text(label, style: mono(size: 11.5, color: Rm.inkFaint))),
        Expanded(child: RmProgress(value: fraction, color: Rm.pear, height: 6)),
        const SizedBox(width: 10),
        Text(value, style: mono(size: 11.5, color: Rm.inkSoft)),
      ]),
    );
  }
}

/// 页面标题下的小节标签(mono,少用)。
class SectionLabel extends StatelessWidget {
  final String text;
  const SectionLabel(this.text, {super.key});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 8, left: 2),
        child: Text(text.toUpperCase(),
            style: mono(size: 11, color: Rm.inkFaint, weight: FontWeight.w500)),
      );
}
