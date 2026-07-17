/// RunMon App 核心状态:配对信息持久化、每台服务器一条 WSS、E2EE 解密、数据分发。
library;

import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:cryptography/cryptography.dart';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/io.dart';

import 'notifications.dart';

final _chacha = Chacha20.poly1305Aead();

Future<Map<String, dynamic>> decryptEnv(
    Map<String, dynamic> env, List<int> key) async {
  final nonce = base64Decode(base64.normalize(env['n'] as String));
  final data = base64Decode(base64.normalize(env['c'] as String));
  final box = SecretBox(data.sublist(0, data.length - 16),
      nonce: nonce, mac: Mac(data.sublist(data.length - 16)));
  final clear = await _chacha.decrypt(box, secretKey: SecretKey(key));
  return jsonDecode(utf8.decode(clear)) as Map<String, dynamic>;
}

Future<Map<String, String>> encryptEnv(Object obj, List<int> key) async {
  final box = await _chacha.encrypt(utf8.encode(jsonEncode(obj)),
      secretKey: SecretKey(key));
  return {
    'n': base64Encode(box.nonce),
    'c': base64Encode([...box.cipherText, ...box.mac.bytes]),
  };
}

List<int> keyFromB64(String s) =>
    base64Url.decode(base64.normalize(s.replaceAll('+', '-').replaceAll('/', '_')));

/// 一条配对关系(一台服务器)。
class ServerLink {
  final String relayUrl;
  final String appDeviceId;
  final String appToken;
  final String agentId;
  final String agentName;
  final String keyB64;

  ServerLink({required this.relayUrl, required this.appDeviceId,
      required this.appToken, required this.agentId,
      required this.agentName, required this.keyB64});

  Map<String, dynamic> toJson() => {
        'relayUrl': relayUrl, 'appDeviceId': appDeviceId, 'appToken': appToken,
        'agentId': agentId, 'agentName': agentName, 'keyB64': keyB64,
      };

  factory ServerLink.fromJson(Map<String, dynamic> j) => ServerLink(
      relayUrl: j['relayUrl'], appDeviceId: j['appDeviceId'],
      appToken: j['appToken'], agentId: j['agentId'],
      agentName: j['agentName'], keyB64: j['keyB64']);
}

/// 单台服务器的实时状态。
class AgentState {
  final ServerLink link;
  bool online = false;
  bool connected = false; // 与 relay 的连接状态
  Map<String, dynamic>? hb;
  List<Map<String, dynamic>> runs = [];
  final Map<String, String> tails = {};
  final List<Map<String, dynamic>> events = [];

  AgentState(this.link);

  String get name => link.agentName.isEmpty ? link.agentId : link.agentName;
}

class _Conn {
  final ServerLink link;
  final void Function() onChange;
  final void Function(String) onNotice;
  IOWebSocketChannel? _ch;
  bool _closed = false;
  double _backoff = 1;
  late final List<int> _key = keyFromB64(link.keyB64);
  final Map<String, Completer<Map<String, dynamic>>> _pending = {};
  final AgentState agent;

  _Conn(this.link, this.agent, this.onChange, this.onNotice) {
    _connect();
  }

  // 端口必须显式写:Dart 的 Uri 不认识 ws:// 的默认端口,缺省会变成 0
  String get _wsUrl {
    final u = Uri.parse(link.relayUrl);
    final secure = u.scheme == 'https';
    final port = u.hasPort ? u.port : (secure ? 443 : 80);
    return '${secure ? 'wss' : 'ws'}://${u.host}:$port/ws/app';
  }

  void _connect() {
    if (_closed) return;
    try {
      final ch = IOWebSocketChannel.connect(Uri.parse(_wsUrl), headers: {
        'Authorization': 'Bearer ${link.appToken}',
        'X-Device': link.appDeviceId,
      });
      _ch = ch;
      // 真正完成握手后才算已连接(之前过早标记,UI 会误显示"服务器离线")
      ch.ready.then((_) {
        if (_closed || _ch != ch) return;
        agent.connected = true;
        _backoff = 1;
        onChange();
      }).catchError((e) {
        debugPrint('[runmon] ws 握手失败: $e');
      });
      ch.stream.listen(_onData, onDone: () {
        debugPrint('[runmon] ws 断开 code=${ch.closeCode} reason=${ch.closeReason}');
        _scheduleReconnect();
      }, onError: (e) {
        debugPrint('[runmon] ws 错误: $e');
        _scheduleReconnect();
      });
    } catch (e) {
      debugPrint('[runmon] ws 连接异常: $e');
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_closed) return;
    agent.connected = false;
    agent.online = false;
    onChange();
    Timer(Duration(milliseconds: (_backoff * 1000).round()), _connect);
    _backoff = min(_backoff * 2, 30);
  }

  Future<void> _onData(dynamic raw) async {
    try {
      final msg = jsonDecode(raw as String) as Map<String, dynamic>;
      if (msg['agent'] != null && msg['agent'] != link.agentId) return;
      switch (msg['t'] as String?) {
        case 'presence':
          agent.online = msg['online'] == true;
        case 'snapshot':
          final data = await decryptEnv(msg['enc'], _key);
          agent.runs = (data['runs'] as List).cast<Map<String, dynamic>>();
        case 'hb':
          agent.hb = await decryptEnv(msg['enc'], _key);
        case 'tail':
          final data = await decryptEnv(msg['enc'], _key);
          agent.tails[data['run_id'] as String] = data['tail'] as String;
        case 'event':
          final data = await decryptEnv(msg['enc'], _key);
          data['received_at'] = DateTime.now().millisecondsSinceEpoch;
          agent.events.insert(0, data);
          if (agent.events.length > 100) agent.events.removeLast();
          onNotice('${data['title']}\n${data['body']}');
          showEventNotification(data['title'] as String? ?? 'RunMon',
              data['body'] as String? ?? '');
        case 'cmd_result':
          final data = await decryptEnv(msg['enc'], _key);
          _pending.remove(msg['cmd_id'])?.complete(data);
        default:
      }
      onChange();
    } catch (_) {/* 单条消息解析失败不影响连接 */}
  }

  Future<Map<String, dynamic>> sendCmd(String op, String runId,
      [Map<String, dynamic>? args]) async {
    final ch = _ch;
    if (ch == null || !agent.connected) {
      return {'ok': false, 'error': '未连接 relay'};
    }
    final cmdId = '${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(99999)}';
    final enc = await encryptEnv({'op': op, 'run_id': runId, 'args': args ?? {}}, _key);
    final completer = Completer<Map<String, dynamic>>();
    _pending[cmdId] = completer;
    ch.sink.add(jsonEncode({'t': 'cmd', 'agent': link.agentId,
        'cmd_id': cmdId, 'enc': enc}));
    return completer.future.timeout(const Duration(seconds: 15),
        onTimeout: () {
      _pending.remove(cmdId);
      return {'ok': false, 'error': '超时(服务器可能离线,指令已暂存 5 分钟)'};
    });
  }

  void close() {
    _closed = true;
    _ch?.sink.close();
  }
}

class AppState extends ChangeNotifier {
  final Map<String, AgentState> agents = {};
  final Map<String, _Conn> _conns = {};
  String? lastNotice;

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    for (final raw in prefs.getStringList('servers') ?? []) {
      _attach(ServerLink.fromJson(jsonDecode(raw)));
    }
    notifyListeners();
  }

  void _attach(ServerLink link) {
    final agent = AgentState(link);
    agents[link.agentId] = agent;
    _conns[link.agentId] = _Conn(link, agent, notifyListeners, (n) {
      lastNotice = n;
      notifyListeners();
    });
  }

  Future<void> _persist() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList('servers',
        agents.values.map((a) => jsonEncode(a.link.toJson())).toList());
  }

  /// 用配对载荷 {u, c, k} 认领并保存。返回错误信息,null 为成功。
  Future<String?> pairWithPayload(String payload, String phoneName) async {
    Map<String, dynamic> p;
    try {
      p = jsonDecode(payload.trim()) as Map<String, dynamic>;
      if (p['u'] == null || p['c'] == null || p['k'] == null) {
        return '载荷缺少字段(需要 u/c/k)';
      }
    } catch (_) {
      return '载荷不是合法 JSON,请完整复制 mon pair 的输出';
    }
    try {
      final resp = await http.post(Uri.parse('${p['u']}/api/pair/claim'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'code': p['c'], 'app_name': phoneName}));
      if (resp.statusCode == 404) return '配对码无效或已过期,请在服务器重新运行 mon pair';
      if (resp.statusCode != 200) return 'relay 返回 ${resp.statusCode}';
      final claim = jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
      final link = ServerLink(
          relayUrl: (p['u'] as String).replaceAll(RegExp(r'/+$'), ''),
          appDeviceId: claim['device_id'], appToken: claim['device_token'],
          agentId: claim['agent_id'], agentName: claim['agent_name'] ?? '',
          keyB64: p['k']);
      _attach(link);
      await _persist();
      notifyListeners();
      return null;
    } catch (e) {
      return '连接 relay 失败:$e';
    }
  }

  Future<void> removeServer(String agentId) async {
    _conns.remove(agentId)?.close();
    agents.remove(agentId);
    await _persist();
    notifyListeners();
  }

  Future<Map<String, dynamic>> sendCmd(
          String agentId, String op, String runId,
          [Map<String, dynamic>? args]) =>
      _conns[agentId]?.sendCmd(op, runId, args) ??
      Future.value({'ok': false, 'error': '连接不存在'});
}

final appState = AppState();

String fmtDuration(double? startedAt, double? endedAt) {
  if (startedAt == null) return '-';
  final end = endedAt ?? DateTime.now().millisecondsSinceEpoch / 1000;
  final s = (end - startedAt).round();
  if (s < 60) return '$s秒';
  if (s < 3600) return '${s ~/ 60}分${s % 60}秒';
  return '${s ~/ 3600}小时${s % 3600 ~/ 60}分';
}
