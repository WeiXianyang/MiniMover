import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/tcp_service.dart';
import '../widgets/common_widgets.dart';
import 'inspection_home_page.dart';

/// S01 - 设备连接页面
class DeviceConnectPage extends StatefulWidget {
  final TcpService tcpService;
  const DeviceConnectPage({super.key, required this.tcpService});

  @override
  State<DeviceConnectPage> createState() => _DeviceConnectPageState();
}

class _DeviceConnectPageState extends State<DeviceConnectPage> {
  final _ipCtrl = TextEditingController(text: '192.168.1.11');
  final _tcpCtrl = TextEditingController(text: '6000');
  final _videoCtrl = TextEditingController(text: '6500');
  bool _connecting = false;

  @override
  void dispose() {
    _ipCtrl.dispose();
    _tcpCtrl.dispose();
    _videoCtrl.dispose();
    super.dispose();
  }

  Future<void> _connect() async {
    setState(() => _connecting = true);

    widget.tcpService.updateConfig(
      _ipCtrl.text.trim(),
      int.tryParse(_tcpCtrl.text.trim()) ?? 6000,
    );

    final ok = await widget.tcpService.connect();

    if (!mounted) return;
    setState(() => _connecting = false);

    if (ok) {
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => InspectionHomePage(tcpService: widget.tcpService),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('连接失败，请检查 IP 和端口')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              AppTheme.frameGradientTop,
              AppTheme.frameGradientBottom,
            ],
          ),
        ),
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppTheme.pagePadding),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 20),
                // 标题
                Text('S01-设备连接',
                    style: AppTheme.sectionLabel.copyWith(fontSize: 14)),
                const SizedBox(height: 16),
                // 手机 Frame 外壳
                Container(
                  width: AppTheme.phoneWidth - 64,
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppTheme.cardBorder),
                    gradient: const LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        Color(0xFF172233),
                        Color(0xFF0F1622),
                      ],
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Header
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text('设备连接',
                                  style: AppTheme.pageTitle),
                              const SizedBox(height: 4),
                              const Text('OpenHarmony 控制入口',
                                  style: AppTheme.subtitle),
                            ],
                          ),
                          const StatusBadge(text: '最近在线'),
                        ],
                      ),
                      const SizedBox(height: 28),
                      // 小车 IP
                      _buildInputCard('小车 IP', _ipCtrl, Icons.wifi),
                      const SizedBox(height: 12),
                      // TCP 端口
                      _buildInputCard('TCP 控制端口', _tcpCtrl, Icons.settings_ethernet),
                      const SizedBox(height: 12),
                      // 视频端口
                      _buildInputCard('视频端口', _videoCtrl, Icons.videocam),
                      const SizedBox(height: 12),
                      // 设备状态
                      GlassCard(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                        child: Column(
                          children: [
                            const InfoRow(
                                label: '设备状态',
                                value: 'Jetson / ROS2 / 视频服务正常'),
                            const Divider(
                                color: AppTheme.dividerLine, height: 20),
                            const InfoRow(
                                label: '最近任务', value: '07-07 上午巡检'),
                            const Divider(
                                color: AppTheme.dividerLine, height: 20),
                            const InfoRow(label: '上次连接', value: '09:26'),
                          ],
                        ),
                      ),
                      const SizedBox(height: 24),
                      // 连接按钮
                      GradientButton(
                        text: _connecting ? '连接中...' : '连接并进入巡检控制台',
                        onTap: _connecting ? null : _connect,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
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
}
