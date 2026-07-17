import 'package:flutter/material.dart';
import 'package:xterm/xterm.dart';

import '../state.dart';
import '../settings.dart';
import '../ui.dart';

class TerminalPage extends StatefulWidget {
  final String agentId;
  final String agentName;
  final String? cwd;
  final String? presetCommand;
  const TerminalPage({super.key, required this.agentId, required this.agentName,
      this.cwd, this.presetCommand});

  @override
  State<TerminalPage> createState() => _TerminalPageState();
}

class _TerminalPageState extends State<TerminalPage> {
  final terminal = Terminal(maxLines: 5000);

  @override
  void initState() {
    super.initState();
    terminal.onOutput = (data) => appState.termInput(widget.agentId, data);
    terminal.onResize = (w, h, pw, ph) =>
        appState.termResize(widget.agentId, h, w);
    appState.openTerminal(widget.agentId, terminal.write,
        rows: terminal.viewHeight, cols: terminal.viewWidth, cwd: widget.cwd);
  }

  @override
  void dispose() {
    appState.closeTerminal(widget.agentId);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Rm.terminalBg,
      appBar: AppBar(
        backgroundColor: Rm.terminalBg,
        title: Text('${widget.agentName} · 终端',
            style: sans(size: 16, weight: FontWeight.w600, color: Rm.terminalText)),
        iconTheme: const IconThemeData(color: Rm.terminalText, size: 20),
      ),
      body: SafeArea(
        child: ListenableBuilder(
          listenable: appState,
          builder: (context, child) {
            final agent = appState.agents[widget.agentId];
            final offline = agent == null || !agent.online;
            return Column(children: [
              if (offline)
                Container(
                  width: double.infinity,
                  color: Rm.coralDeep,
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  child: Text('服务器已断开 · 返回上一页重新进入以恢复终端',
                      style: sans(size: 12.5, color: Rm.paper)),
                ),
              if (widget.presetCommand != null)
                _PresetBar(command: widget.presetCommand!,
                    onFill: () => appState.termInput(
                        widget.agentId, widget.presetCommand!)),
              Expanded(child: child!),
            ]);
          },
          child: TerminalView(
          terminal,
          textStyle: TerminalStyle(
              fontSize: appSettings.terminalFontSize, fontFamily: Rm.mono),
          theme: TerminalThemes.defaultTheme,
          autofocus: true,
        ),
        ),
      ),
    );
  }
}


class _PresetBar extends StatelessWidget {
  final String command;
  final VoidCallback onFill;
  const _PresetBar({required this.command, required this.onFill});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: const Color(0xFF1E262E),
      padding: const EdgeInsets.fromLTRB(14, 8, 8, 8),
      child: Row(children: [
        Expanded(
          child: Text(command,
              maxLines: 1, overflow: TextOverflow.ellipsis,
              style: mono(size: 12, color: Rm.terminalText)),
        ),
        TextButton(
          onPressed: onFill,
          style: TextButton.styleFrom(
              foregroundColor: Rm.pear,
              textStyle: sans(size: 13, weight: FontWeight.w600)),
          child: const Text('填入命令'),
        ),
      ]),
    );
  }
}
