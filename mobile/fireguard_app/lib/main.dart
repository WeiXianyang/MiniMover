import 'package:flutter/material.dart';
import 'theme/app_theme.dart';
import 'services/tcp_service.dart';
import 'pages/device_connect_page.dart';
import 'pages/inspection_home_page.dart';
import 'pages/map_task_page.dart';
import 'pages/alarm_detail_page.dart';
import 'pages/delivery_page.dart';
import 'pages/manual_control_page.dart';
import 'pages/report_page.dart';

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
      home: const DemoTabShell(),
    );
  }
}

/// Demo 模式 — 底部 Tab 自由切换所有页面
class DemoTabShell extends StatefulWidget {
  const DemoTabShell({super.key});

  @override
  State<DemoTabShell> createState() => _DemoTabShellState();
}

class _DemoTabShellState extends State<DemoTabShell> {
  int _currentIndex = 0;
  final _tcpService = TcpService();

  static const _pages = <_TabInfo>[
    _TabInfo('设备连接', Icons.wifi, 0),
    _TabInfo('巡检主页', Icons.dashboard, 1),
    _TabInfo('地图任务', Icons.map, 2),
    _TabInfo('告警详情', Icons.warning, 3),
    _TabInfo('定点配送', Icons.local_shipping, 4),
    _TabInfo('手动接管', Icons.gamepad, 5),
    _TabInfo('巡检报告', Icons.assessment, 6),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: [
          DeviceConnectPage(tcpService: _tcpService),
          InspectionHomePage(tcpService: _tcpService),
          MapTaskPage(tcpService: _tcpService),
          AlarmDetailPage(tcpService: _tcpService),
          DeliveryPage(tcpService: _tcpService),
          ManualControlPage(tcpService: _tcpService),
          ReportPage(tcpService: _tcpService),
        ],
      ),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          border: Border(
            top: BorderSide(color: AppTheme.cardBorder, width: 1),
          ),
        ),
        child: BottomNavigationBar(
          currentIndex: _currentIndex,
          onTap: (i) => setState(() => _currentIndex = i),
          type: BottomNavigationBarType.fixed,
          backgroundColor: AppTheme.bgGradientTop,
          selectedItemColor: AppTheme.accent,
          unselectedItemColor: AppTheme.textSecondary,
          selectedFontSize: 10,
          unselectedFontSize: 10,
          items: _pages
              .map((p) => BottomNavigationBarItem(
                    icon: Icon(p.icon, size: 20),
                    activeIcon: Icon(p.icon, size: 20),
                    label: p.label,
                  ))
              .toList(),
        ),
      ),
    );
  }
}

class _TabInfo {
  final String label;
  final IconData icon;
  final int index;
  const _TabInfo(this.label, this.icon, this.index);
}
