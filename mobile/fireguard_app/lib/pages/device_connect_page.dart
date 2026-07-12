import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/car_state.dart';
import '../widgets/common_widgets.dart';
import '../widgets/page_shell.dart';

/// S01 - 设备连接页面
class DeviceConnectPage extends StatefulWidget {
  final CarState carState;
  final bool embedded;
  final VoidCallback? onConnected;
  const DeviceConnectPage({
    super.key,
    required this.carState,
    this.embedded = false,
    this.onConnected,
  });

  @override
  State<DeviceConnectPage> createState() => _DeviceConnectPageState();
}

class _DeviceConnectPageState extends State<DeviceConnectPage> {
  final _ipCtrl = TextEditingController(text: '192.168.1.11');
  final _tcpCtrl = TextEditingController(text: '6000');
  final _videoCtrl = TextEditingController(text: '6500');
  bool _connecting = false;

  @override
  void initState() {
    super.initState();
    widget.carState.addListener(_onStateChanged);
  }

  @override
  void dispose() {
    widget.carState.removeListener(_onStateChanged);
    _ipCtrl.dispose();
    _tcpCtrl.dispose();
    _videoCtrl.dispose();
    super.dispose();
  }

  void _onStateChanged() {
    if (!mounted) return;
    setState(() {});
  }

  Future<void> _connect() async {
    setState(() => _connecting = true);
    final ok = await widget.carState.connect(
      _ipCtrl.text.trim(),
      int.tryParse(_tcpCtrl.text.trim()) ?? 6000,
    );
    if (!mounted) return;
    setState(() => _connecting = false);

    if (ok) {
      widget.onConnected?.call();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('连接失败，请检查 IP 和端口')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = widget.carState;
    final online = cs.connected;

    return _wrap(
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('S01-设备连接',
              style: AppTheme.sectionLabel.copyWith(fontSize: 14)),
          const SizedBox(height: 16),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(20),
            decoration: _frameDeco(),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('设备连接', style: AppTheme.pageTitle),
                        SizedBox(height: 4),
                        Text('OpenHarmony 控制入口',
                            style: AppTheme.subtitle),
                      ],
                    ),
                    StatusBadge(
                      text: online ? '已连接' : '未连接',
                      active: online,
                    ),
                  ],
                ),
                const SizedBox(height: 28),
                _buildInputCard('小车 IP', _ipCtrl, Icons.wifi),
                const SizedBox(height: 12),
                _buildInputCard('TCP 控制端口', _tcpCtrl,
                    Icons.settings_ethernet),
                const SizedBox(height: 12),
                _buildInputCard('视频端口', _videoCtrl, Icons.videocam),
                const SizedBox(height: 12),
                GlassCard(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 14),
                  child: Column(
                    children: [
                      InfoRow(
                          label: '设备状态',
                          value: online
                              ? 'Jetson / ROS2 / 视频服务正常'
                              : '未连接'),
                      const Divider(color: AppTheme.dividerLine, height: 20),
                      InfoRow(
                          label: '硬件版本',
                          value: cs.deviceVersion.isNotEmpty
                              ? cs.deviceVersion
                              : '—'),
                      const Divider(color: AppTheme.dividerLine, height: 20),
                      InfoRow(
                          label: '电池电压',
                          value: cs.batteryVoltage > 0
                              ? '${cs.batteryVoltage.toStringAsFixed(1)}V (${cs.batteryPercent}%)'
                              : '—'),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
                GradientButton(
                  text: online
                      ? '已连接 — 进入巡检控制台'
                      : (_connecting ? '连接中...' : '连接并进入巡检控制台'),
                  onTap: (online || _connecting) ? null : _connect,
                ),
                if (online) ...[
                  const SizedBox(height: 12),
                  GradientButton(
                    text: '断开连接',
                    secondary: true,
                    onTap: () {
                      cs.disconnect();
                    },
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInputCard(
      String label, TextEditingController ctrl, IconData icon) {
    return GlassCard(
      height: 84,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: AppTheme.bodyLabel),
          const SizedBox(height: 6),
          Row(
            children: [
              Icon(icon, color: AppTheme.textSecondary, size: 18),
              const SizedBox(width: 10),
              Expanded(
                child: TextField(
                  controller: ctrl,
                  style: AppTheme.bodyValue.copyWith(fontSize: 14),
                  decoration: const InputDecoration(
                    border: InputBorder.none,
                    isDense: true,
                    contentPadding: EdgeInsets.zero,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  BoxDecoration _frameDeco() => BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.cardBorder),
        gradient: const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF172233), Color(0xFF0F1622)],
        ),
      );

  Widget _wrap(Widget content) {
    if (widget.embedded) {
      return SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(
            AppTheme.pagePadding, 16, AppTheme.pagePadding, 8),
        child: content,
      );
    }
    return PageShell(
      child: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppTheme.pagePadding),
          child: content,
        ),
      ),
    );
  }
}
