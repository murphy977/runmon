/// App 设置:通知偏好、免打扰、终端字号。持久化到 SharedPreferences。
library;

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

const eventTypeLabels = {
  'completed': '完成',
  'failed': '失败',
  'error_pattern': '错误输出',
  'gpu_hang': 'GPU 假死',
  'log_silence': '日志静默',
  'disk_full': '磁盘告警',
  'gpu_free': 'GPU 空位(蹲卡)',
};

class Settings extends ChangeNotifier {
  bool systemNotify = true;
  bool dndEnabled = false;
  int dndStart = 23 * 60; // 分钟,默认 23:00
  int dndEnd = 8 * 60;    // 默认 08:00
  final Set<String> mutedTypes = {}; // 不推系统通知的事件类型
  double terminalFontSize = 13;
  int diskThresholdPct = 90; // 磁盘告警阈值(实际生效在服务器,改动时下发同步)

  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    systemNotify = p.getBool('set_sysNotify') ?? true;
    dndEnabled = p.getBool('set_dnd') ?? false;
    dndStart = p.getInt('set_dndStart') ?? 23 * 60;
    dndEnd = p.getInt('set_dndEnd') ?? 8 * 60;
    mutedTypes
      ..clear()
      ..addAll(p.getStringList('set_muted') ?? []);
    terminalFontSize = p.getDouble('set_termFont') ?? 13;
    diskThresholdPct = p.getInt('set_diskPct') ?? 90;
    notifyListeners();
  }

  Future<void> _save() async {
    final p = await SharedPreferences.getInstance();
    await p.setBool('set_sysNotify', systemNotify);
    await p.setBool('set_dnd', dndEnabled);
    await p.setInt('set_dndStart', dndStart);
    await p.setInt('set_dndEnd', dndEnd);
    await p.setStringList('set_muted', mutedTypes.toList());
    await p.setDouble('set_termFont', terminalFontSize);
    await p.setInt('set_diskPct', diskThresholdPct);
    notifyListeners();
  }

  bool _inDnd(int nowMinutes) {
    if (!dndEnabled || dndStart == dndEnd) return false;
    return dndStart < dndEnd
        ? (nowMinutes >= dndStart && nowMinutes < dndEnd)
        : (nowMinutes >= dndStart || nowMinutes < dndEnd); // 跨午夜
  }

  /// 该事件是否推系统通知(受总开关、类型开关、免打扰时段控制)。
  /// 免打扰=静音但保留:返回 false 时事件仍进列表,只是不弹。
  bool shouldNotify(String? type) {
    if (!systemNotify) return false;
    if (type != null && mutedTypes.contains(type)) return false;
    final now = DateTime.now();
    return !_inDnd(now.hour * 60 + now.minute);
  }

  Future<void> setSystemNotify(bool v) async { systemNotify = v; await _save(); }
  Future<void> setDnd(bool v) async { dndEnabled = v; await _save(); }
  Future<void> setDndWindow(int start, int end) async {
    dndStart = start; dndEnd = end; await _save();
  }
  Future<void> setTypeNotify(String type, bool on) async {
    on ? mutedTypes.remove(type) : mutedTypes.add(type);
    await _save();
  }
  Future<void> setTermFont(double v) async { terminalFontSize = v; await _save(); }
  Future<void> setDiskThreshold(int v) async { diskThresholdPct = v; await _save(); }
}

final appSettings = Settings();
