import 'package:flutter/material.dart';
import 'theme/app_theme.dart';
import 'services/tcp_service.dart';
import 'services/car_state.dart';
import 'services/fleet_service.dart';
import 'pages/device_connect_page.dart';
import 'pages/inspection_home_page.dart';
import 'pages/alarm_detail_page.dart';
import 'pages/fleet_page.dart';

void main() {
  runApp(const FireGuardApp());
}

class FireGuardApp extends StatelessWidget {
  const FireGuardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'FireGuard 工业巡检',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      home: const MainShell(),
    );
  }
}

/// 底部 4 Tab: 设备连接 | 巡检主页 | 告警详情 | 车队编队
/// 其余页面通过按钮 push 进入（带返回箭头）
class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _currentIndex = 0;
  final _tcpService = TcpService();
  final _fleetService = FleetService();
  late final CarState _carState;

  static const _tabs = [
    ('设备连接', Icons.wifi),
    ('巡检主页', Icons.dashboard),
    ('告警详情', Icons.warning),
    ('车队编队', Icons.precision_manufacturing),
  ];

  @override
  void initState() {
    super.initState();
    _carState = CarState(tcpService: _tcpService);
    _carState.addListener(_onCarStateChanged);
  }

  void _onCarStateChanged() {
    if (!mounted) return;
    // 告警时自动切换到告警页签
    if (_carState.hasAlarm && _currentIndex != 2) {
      setState(() => _currentIndex = 2);
    }
  }

  @override
  void dispose() {
    _carState.removeListener(_onCarStateChanged);
    _carState.dispose();
    _fleetService.dispose();
    _tcpService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bgGradientTop,
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [AppTheme.bgGradientTop, AppTheme.bgGradientBottom],
          ),
        ),
        child: IndexedStack(
          index: _currentIndex,
          children: [
            DeviceConnectPage(
              embedded: true,
              carState: _carState,
              onConnected: () => setState(() => _currentIndex = 1),
            ),
            InspectionHomePage(embedded: true, carState: _carState),
            AlarmDetailPage(embedded: true, carState: _carState),
            FleetPage(embedded: true, fleetService: _fleetService),
          ],
        ),
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (i) => setState(() => _currentIndex = i),
        type: BottomNavigationBarType.fixed,
        backgroundColor: AppTheme.bgGradientTop,
        selectedItemColor: AppTheme.accent,
        unselectedItemColor: AppTheme.textSecondary,
        selectedFontSize: 11,
        unselectedFontSize: 11,
        items: _tabs
            .map((t) => BottomNavigationBarItem(
                  icon: Icon(t.$2, size: 22),
                  activeIcon: Icon(t.$2, size: 22),
                  label: t.$1,
                ))
            .toList(),
      ),
    );
  }
}
