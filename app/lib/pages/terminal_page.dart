import 'package:flutter/material.dart';
import 'package:xterm/xterm.dart';

import '../state.dart';
import '../ui.dart';

class TerminalPage extends StatefulWidget {
  final String agentId;
  final String agentName;
  const TerminalPage({super.key, required this.agentId, required this.agentName});

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
        rows: terminal.viewHeight, cols: terminal.viewWidth);
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
        child: TerminalView(
          terminal,
          textStyle: const TerminalStyle(fontSize: 13, fontFamily: Rm.mono),
          theme: TerminalThemes.defaultTheme,
          autofocus: true,
        ),
      ),
    );
  }
}
