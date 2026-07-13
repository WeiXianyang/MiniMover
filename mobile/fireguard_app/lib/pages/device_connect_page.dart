import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/car_state.dart';
import '../widgets/common_widgets.dart';
import '../widgets/page_shell.dart';

/// S01 - 设备连接 (api_server.py :5000)
/// 对齐 prototype page-prototype/index.html
class DeviceConnectPage extends StatefulWidget {
  final CarState carState; final bool embedded; final VoidCallback? onConnected;
  const DeviceConnectPage({super.key, required this.carState, this.embedded = false, this.onConnected});
  @override
  State<DeviceConnectPage> createState() => _DeviceConnectPageState();
}

class _DeviceConnectPageState extends State<DeviceConnectPage> {
  final _ipCtrl = TextEditingController(text: '192.168.8.188');
  final _portCtrl = TextEditingController(text: '5000');
  bool _connecting = false;

  @override
  void initState() { super.initState(); widget.carState.addListener(_onCs); }
  @override
  void dispose() { widget.carState.removeListener(_onCs); _ipCtrl.dispose(); _portCtrl.dispose(); super.dispose(); }
  void _onCs() { if (mounted) setState(() {}); }

  Future<void> _connect() async {
    setState(() => _connecting = true);
    final ok = await widget.carState.connect(_ipCtrl.text.trim(), int.tryParse(_portCtrl.text.trim()) ?? 5000);
    if (!mounted) return; setState(() => _connecting = false);
    if (ok) { widget.onConnected?.call(); } else {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('连接失败，请检查 IP 和端口')));
    }
  }

  @override
  Widget build(BuildContext c) {
    final cs = widget.carState; final on = cs.connected;
    return _wrap(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        // ── 页头：对齐 prototype "可连接" 状态 ──
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('设备连接', style: AppTheme.pageTitle), SizedBox(height: 6), Text('配置车辆控制与视频端口', style: AppTheme.subtitle)]),
          StatusBadge(text: on ? '已连接' : '可连接', active: true),
        ]), const SizedBox(height: 28),
        _input('小车 IP', _ipCtrl, Icons.wifi), const SizedBox(height: 12),
        _input('API 端口 (控制 + 视频)', _portCtrl, Icons.settings_ethernet), const SizedBox(height: 14),
        // ── 设备信息卡：对齐 prototype 3 行 ──
        GlassCard(padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14), child: Column(children: [
          InfoRow(label: '设备状态', value: on ? cs.deviceStatusDisplay : '未连接'),
          const Divider(color: AppTheme.dividerLine, height: 20),
          InfoRow(label: '最近任务', value: '07-07 上午巡检'),
          const Divider(color: AppTheme.dividerLine, height: 20),
          InfoRow(label: '上次连接', value: '09:26'),
        ])),
        const SizedBox(height: 24),
        GradientButton(text: on ? '已连接' : (_connecting ? '连接中...' : '连接并进入巡检控制台'), onTap: (on || _connecting) ? null : _connect),
        if (on) ...[const SizedBox(height: 12), GradientButton(text: '断开', secondary: true, onTap: () => cs.disconnect())],
      ]),
    ]));
  }

  Widget _input(String label, TextEditingController ctrl, IconData icon) => GlassCard(height: 72, padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10), child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
    Text(label, style: AppTheme.bodyLabel.copyWith(fontSize: 11)), const SizedBox(height: 2),
    Row(children: [Icon(icon, color: AppTheme.textSecondary, size: 16), const SizedBox(width: 8), Expanded(child: TextField(controller: ctrl, style: AppTheme.bodyValue.copyWith(fontSize: 14), keyboardType: TextInputType.number, decoration: const InputDecoration(border: InputBorder.none, isDense: true, contentPadding: EdgeInsets.zero)))]),
  ]));

  Widget _wrap(Widget w) => widget.embedded ? SingleChildScrollView(padding: const EdgeInsets.fromLTRB(AppTheme.pagePadding, 16, AppTheme.pagePadding, AppTheme.tabBarInset), child: w) : PageShell(child: SafeArea(child: SingleChildScrollView(padding: const EdgeInsets.all(AppTheme.pagePadding), child: w)));
}
