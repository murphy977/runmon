import 'package:flutter_test/flutter_test.dart';
import 'package:runmon_app/main.dart';

void main() {
  testWidgets('首页空状态渲染', (tester) async {
    await tester.pumpWidget(const RunMonApp());
    expect(find.text('RunMon'), findsOneWidget);
    expect(find.text('添加服务器'), findsOneWidget);
    expect(find.textContaining('pip install runmon'), findsOneWidget);
  });
}
