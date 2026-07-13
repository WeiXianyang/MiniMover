import 'package:flutter/material.dart';
import 'theme/app_theme.dart';
import 'services/api_service.dart';
import 'services/car_state.dart';
import 'services/fleet_service.dart';
import 'pages/device_connect_page.dart';
import 'pages/inspection_home_page.dart';
import 'pages/alarm_detail_page.dart';
import 'pages/fleet_page.dart';
import 'pages/delivery_page.dart';
import 'widgets/app_icons.dart';

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

  static final _tabs = [
    ('连接', (Color c) => AppIcons.plug(color: c)),
    ('主页', (Color c) => AppIcons.home(color: c)),
    ('告警', (Color c) => AppIcons.triangleAlert(color: c)),
    ('配送', (Color c) => AppIcons.route(color: c)),
    ('编队', (Color c) => AppIcons.car(color: c)),
  ];

  @override
  void initState() {
    super.initState();
    _cs = CarState(api: _api);
    _cs.addListener(_onCs);
  }

  void _onCs() {
    if (!mounted) return;
    if (_cs.hasAlarm && _idx != 2) setState(() => _idx = 2);
  }

  @override
  void dispose() {
    _cs.removeListener(_onCs);
    _cs.dispose();
    _fleet.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F1622),
      body: Stack(
        children: [
          // ── 页面内容区（底部留出 tabbar 空间）──
          Positioned.fill(
            child: Padding(
              padding: const EdgeInsets.only(bottom: 80),
              child: IndexedStack(
                index: _idx,
                children: [
                  DeviceConnectPage(embedded: true, carState: _cs, onConnected: () => setState(() => _idx = 1)),
                  InspectionHomePage(embedded: true, carState: _cs),
                  AlarmDetailPage(embedded: true, carState: _cs),
                  DeliveryPage(embedded: true, carState: _cs, onReturnHome: () => setState(() => _idx = 1)),
                  FleetPage(embedded: true, fleetService: _fleet, carState: _cs),
                ],
              ),
            ),
          ),
          // ── 底部导航栏 — 浮动覆盖在底部 ──
          Positioned(
            left: 16, right: 16, bottom: 14,
            child: _buildTabBar(),
          ),
        ],
      ),
    );
  }

  Widget _buildTabBar() {
    return Container(
      padding: const EdgeInsets.all(6),
      decoration: BoxDecoration(
        color: const Color.fromRGBO(10, 17, 27, 0.94),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color.fromRGBO(42, 61, 86, 0.9)),
      ),
      child: Row(
        children: List.generate(_tabs.length, (i) {
          final active = i == _idx;
          return Expanded(
            child: GestureDetector(
              onTap: () => setState(() => _idx = i),
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 4),
                decoration: BoxDecoration(
                  color: active ? AppTheme.accent.withAlpha(20) : null,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _tabs[i].$2(active ? AppTheme.accent : AppTheme.textSecondary),
                    const SizedBox(height: 2),
                    Text(
                      _tabs[i].$1,
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w800,
                        color: active ? AppTheme.accent : AppTheme.textSecondary,
                        height: 1.1,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            ),
          );
        }),
      ),
    );
  }
}
