/// 系统级通知:事件到达时弹通知栏(Android/macOS)。
library;

import 'package:flutter_local_notifications/flutter_local_notifications.dart';

final _fln = FlutterLocalNotificationsPlugin();
bool _ready = false;

Future<void> initNotifications() async {
  try {
    const android = AndroidInitializationSettings('@mipmap/ic_launcher');
    const darwin = DarwinInitializationSettings();
    await _fln.initialize(const InitializationSettings(
        android: android, macOS: darwin, iOS: darwin));
    await _fln
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.requestNotificationsPermission();
    _ready = true;
  } catch (_) {/* 通知不可用不影响主功能 */}
}

Future<void> showEventNotification(String title, String body) async {
  if (!_ready) return;
  try {
    const details = NotificationDetails(
      android: AndroidNotificationDetails('events', '任务事件',
          channelDescription: '服务器任务事件(完成/失败/假死等)',
          importance: Importance.high, priority: Priority.high),
      macOS: DarwinNotificationDetails(),
      iOS: DarwinNotificationDetails(),
    );
    await _fln.show(DateTime.now().millisecondsSinceEpoch % 0x7FFFFFFF ~/ 1000,
        title, body, details);
  } catch (_) {}
}
