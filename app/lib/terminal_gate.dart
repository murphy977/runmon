/// 终端首次确认:每台服务器第一次开终端时提示安全含义,确认后记住。
library;

import 'package:flutter/material.dart';

import 'pages/terminal_page.dart';
import 'state.dart';
import 'ui.dart';

Future<void> openTerminalGuarded(BuildContext context, String agentId,
    String agentName, {String? cwd, String? command}) async {
  if (!appState.isTermConfirmed(agentId)) {
    final ok = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
              title: const Text('开启终端?'),
              content: Text(
                  '终端能在「$agentName」上执行任意命令,和 SSH 一样。\n\n'
                  '仅当你信任这台手机时启用。之后这台服务器不再询问。',
                  style: sans(size: 14, color: Rm.inkSoft, height: 1.6)),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(c, false),
                    child: const Text('取消')),
                SoftButton(
                    label: '启用终端', icon: Icons.terminal_rounded,
                    deep: Rm.ink, tint: Rm.pearTint,
                    onPressed: () => Navigator.pop(c, true)),
              ],
            ));
    if (ok != true) return;
    await appState.confirmTerm(agentId);
  }
  if (!context.mounted) return;
  Navigator.push(context, MaterialPageRoute(
      builder: (_) => TerminalPage(agentId: agentId, agentName: agentName,
          cwd: cwd, presetCommand: command)));
}
