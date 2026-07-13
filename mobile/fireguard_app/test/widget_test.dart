import 'package:flutter_test/flutter_test.dart';
import 'package:fireguard_app/main.dart';

void main() {
  testWidgets('App launches successfully', (WidgetTester tester) async {
    await tester.pumpWidget(const FireGuardApp());
    expect(find.text('设备连接'), findsOneWidget);
    expect(find.text('巡检主页'), findsOneWidget);
    expect(find.text('告警详情'), findsOneWidget);
  });
}
