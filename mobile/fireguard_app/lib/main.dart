import 'package:flutter/material.dart';
import 'theme/app_theme.dart';
import 'services/api_service.dart';
import 'services/car_state.dart';
import 'services/fleet_service.dart';
import 'pages/device_connect_page.dart';
import 'pages/inspection_home_page.dart';
import 'pages/alarm_detail_page.dart';
import 'pages/fleet_page.dart';

void main() => runApp(const FireGuardApp());

class FireGuardApp extends StatelessWidget {
  const FireGuardApp({super.key});
  @override
  Widget build(BuildContext c) => MaterialApp(
    title: 'FireGuard 工业巡检', debugShowCheckedModeBanner: false,
    theme: AppTheme.darkTheme, home: const MainShell(),
  );
}

class MainShell extends StatefulWidget {
  const MainShell({super.key});
  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _idx = 0;
  final _api = ApiService();
  final _fleet = FleetService();
  late final CarState _cs;

  static const _tabs = [
    ('设备连接', Icons.wifi), ('巡检主页', Icons.dashboard),
    ('告警详情', Icons.warning), ('车队编队', Icons.precision_manufacturing),
  ];

  @override
  void initState() { super.initState(); _cs = CarState(api: _api); _cs.addListener(_onCs); }
  void _onCs() { if (!mounted) return; if (_cs.hasAlarm && _idx != 2) setState(() => _idx = 2); }
  @override
  void dispose() { _cs.removeListener(_onCs); _cs.dispose(); _fleet.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext c) => Scaffold(
    backgroundColor: AppTheme.bgGradientTop,
    body: Container(
      decoration: const BoxDecoration(gradient: LinearGradient(
        begin: Alignment.topCenter, end: Alignment.bottomCenter,
        colors: [AppTheme.bgGradientTop, AppTheme.bgGradientBottom],
      )),
      child: IndexedStack(index: _idx, children: [
        DeviceConnectPage(embedded: true, carState: _cs, onConnected: () => setState(() => _idx = 1)),
        InspectionHomePage(embedded: true, carState: _cs),
        AlarmDetailPage(embedded: true, carState: _cs),
        FleetPage(embedded: true, fleetService: _fleet),
      ]),
    ),
    bottomNavigationBar: BottomNavigationBar(
      currentIndex: _idx, onTap: (i) => setState(() => _idx = i),
      type: BottomNavigationBarType.fixed, backgroundColor: AppTheme.bgGradientTop,
      selectedItemColor: AppTheme.accent, unselectedItemColor: AppTheme.textSecondary,
      selectedFontSize: 11, unselectedFontSize: 11,
      items: _tabs.map((t) => BottomNavigationBarItem(icon: Icon(t.$2, size: 22), activeIcon: Icon(t.$2, size: 22), label: t.$1)).toList(),
    ),
  );
}
