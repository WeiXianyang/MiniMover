import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/tcp_service.dart';
import '../widgets/common_widgets.dart';

/// S03 - 地图与任务页面
class MapTaskPage extends StatelessWidget {
  final TcpService tcpService;
  const MapTaskPage({super.key, required this.tcpService});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [AppTheme.frameGradientTop, AppTheme.frameGradientBottom],
          ),
        ),
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppTheme.pagePadding),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 20),
                Text('S03-地图任务',
                    style: AppTheme.sectionLabel.copyWith(fontSize: 14)),
                const SizedBox(height: 16),
                Container(
                  width: AppTheme.phoneWidth - 64,
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppTheme.cardBorder),
                    gradient: const LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [Color(0xFF172233), Color(0xFF0F1622)],
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const PageHeader(
                        title: '地图与任务',
                        subTitle: '多点导航 + 避障状态',
                        badgeText: '正在前往',
                      ),
                      const SizedBox(height: 20),
                      // 地图区域
                      GlassCard(
                        height: 230,
                        padding: const EdgeInsets.all(12),
                        child: _MapView(),
                      ),
                      const SizedBox(height: 14),
                      // 图例
                      Row(
                        children: [
                          _LegendDot(color: AppTheme.accent, label: '巡检点'),
                          const SizedBox(width: 12),
                          _LegendDot(
                              color: AppTheme.statusRed, label: '动态障碍'),
                          const SizedBox(width: 12),
                          _LegendDot(
                              color: AppTheme.statusGreen, label: '当前目标'),
                        ],
                      ),
                      const SizedBox(height: 16),
                      // 路径状态
                      GlassCard(
                        padding:
                            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                        child: Column(
                          children: [
                            const InfoRow(
                                label: '当前路径完成度', value: '42%'),
                            const SizedBox(height: 8),
                            ClipRRect(
                              borderRadius: BorderRadius.circular(4),
                              child: LinearProgressIndicator(
                                value: 0.42,
                                minHeight: 6,
                                backgroundColor:
                                    AppTheme.cardBorder,
                                color: AppTheme.accent,
                              ),
                            ),
                            const Divider(
                                color: AppTheme.dividerLine, height: 22),
                            const InfoRow(
                                label: '避障状态',
                                value: '已绕过纸箱，继续巡检'),
                            const Divider(
                                color: AppTheme.dividerLine, height: 22),
                            const InfoRow(
                              label: '剩余点位',
                              value: '配电柜A / 仓储通道C / 消防栓B',
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 20),
                      // 操作按钮
                      Row(
                        children: [
                          const Expanded(child: SmallButton(text: '暂停任务')),
                          const SizedBox(width: 12),
                          const Expanded(child: SmallButton(text: '中止巡检')),
                        ],
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
}

/// 简单地图模拟
class _MapView extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        return Stack(
          children: [
            // 网格背景
            CustomPaint(
              size: Size(constraints.maxWidth, constraints.maxHeight),
              painter: _GridPainter(),
            ),
            // 路径起点
            const _MapPoint(x: 18, y: 150, color: AppTheme.accent, label: '起点'),
            // 巡检点
            const _MapPoint(
                x: 208, y: 30, color: AppTheme.statusGreen, label: '配电柜A'),
            // 临时障碍
            const _MapPoint(
                x: 120, y: 58, color: AppTheme.statusRed, label: '临时障碍'),
            // 仓储通道
            const _MapPoint(
                x: 236, y: 166, color: AppTheme.statusGreen, label: '仓储通道C'),
          ],
        );
      },
    );
  }
}

class _GridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppTheme.cardBorder
      ..strokeWidth = 0.5;
    const step = 36.0;
    for (double x = 0; x <= size.width; x += step) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (double y = 0; y <= size.height; y += step) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _MapPoint extends StatelessWidget {
  final double x;
  final double y;
  final Color color;
  final String label;

  const _MapPoint({
    required this.x,
    required this.y,
    required this.color,
    required this.label,
  });

  @override
  Widget build(BuildContext context) {
    return Positioned(
      left: x,
      top: y,
      child: Column(
        children: [
          Container(
            width: 12,
            height: 12,
            decoration: BoxDecoration(
              color: color,
              shape: BoxShape.circle,
              border: Border.all(color: AppTheme.textPrimary, width: 1.5),
            ),
          ),
          const SizedBox(height: 2),
          Text(label,
              style: AppTheme.statLabel.copyWith(fontSize: 10)),
        ],
      ),
    );
  }
}

class _LegendDot extends StatelessWidget {
  final Color color;
  final String label;

  const _LegendDot({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 4),
        Text(label, style: AppTheme.subtitle),
      ],
    );
  }
}
