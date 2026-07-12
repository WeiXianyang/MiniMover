import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/car_state.dart';
import '../widgets/common_widgets.dart';
import '../widgets/page_shell.dart';

/// S03 - 地图与任务页面
class MapTaskPage extends StatefulWidget {
  final CarState carState;
  final bool embedded;
  const MapTaskPage({
    super.key,
    required this.carState,
    this.embedded = false,
  });

  @override
  State<MapTaskPage> createState() => _MapTaskPageState();
}

class _MapTaskPageState extends State<MapTaskPage> {
  @override
  void initState() {
    super.initState();
    widget.carState.addListener(_onChanged);
  }

  @override
  void dispose() {
    widget.carState.removeListener(_onChanged);
    super.dispose();
  }

  void _onChanged() {
    if (mounted) setState(() {});
  }

  /// 模拟任务进度（实际应接入小车定位）
  void _simulateProgress() {
    widget.carState.advanceProgress(0.15);
  }

  @override
  Widget build(BuildContext context) {
    final cs = widget.carState;

    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('S03-地图任务',
            style: AppTheme.sectionLabel.copyWith(fontSize: 14)),
        const SizedBox(height: 16),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(20),
          decoration: _frameDeco(),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              PageHeader(
                title: '地图与任务',
                subTitle: '多点导航 + 避障状态',
                badgeText: cs.taskPaused
                    ? '已暂停'
                    : (cs.taskRunning ? '正在前往' : '待命'),
                badgeActive: cs.taskRunning,
              ),
              const SizedBox(height: 20),
              GlassCard(
                  height: 230,
                  padding: const EdgeInsets.all(12),
                  child: _MapView()),
              const SizedBox(height: 14),
              Row(
                children: [
                  _LegendDot(color: AppTheme.accent, label: '巡检点'),
                  const SizedBox(width: 12),
                  _LegendDot(color: AppTheme.statusRed, label: '动态障碍'),
                  const SizedBox(width: 12),
                  _LegendDot(
                      color: AppTheme.statusGreen, label: '当前目标'),
                ],
              ),
              const SizedBox(height: 16),
              GlassCard(
                padding: const EdgeInsets.symmetric(
                    horizontal: 16, vertical: 14),
                child: Column(
                  children: [
                    InfoRow(
                      label: '当前路径完成度',
                      value: '${(cs.taskProgress * 100).round()}%',
                    ),
                    const SizedBox(height: 8),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                          value: cs.taskProgress,
                          minHeight: 6,
                          backgroundColor: AppTheme.cardBorder,
                          color: AppTheme.accent),
                    ),
                    const Divider(
                        color: AppTheme.dividerLine, height: 22),
                    InfoRow(
                      label: '避障状态',
                      value: cs.taskRunning
                          ? '已绕过纸箱，继续巡检'
                          : '待命中',
                    ),
                    const Divider(
                        color: AppTheme.dividerLine, height: 22),
                    InfoRow(
                        label: '剩余点位',
                        value: '配电柜A / 仓储通道C / 消防栓B'),
                  ],
                ),
              ),
              const SizedBox(height: 20),
              Row(
                children: [
                  Expanded(
                    child: SmallButton(
                      text: cs.taskPaused ? '恢复任务' : '暂停任务',
                      onTap: () {
                        if (cs.taskPaused) {
                          cs.resumeTask();
                        } else {
                          cs.pauseTask();
                        }
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: SmallButton(
                      text: '中止巡检',
                      onTap: () => _abortConfirm(context, cs),
                    ),
                  ),
                ],
              ),
              if (cs.taskRunning && !cs.taskPaused) ...[
                const SizedBox(height: 14),
                GradientButton(
                  text: '模拟推进进度 (+15%)',
                  secondary: true,
                  onTap: _simulateProgress,
                ),
              ],
            ],
          ),
        ),
      ],
    );

    return _wrap(context, content);
  }

  void _abortConfirm(BuildContext context, CarState cs) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF172233),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppTheme.cardBorder),
        ),
        title: const Text('中止巡检', style: AppTheme.pageTitle),
        content: const Text('确定要中止当前巡检任务吗？小车将停止并返回待命状态。',
            style: AppTheme.bodyLabel),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('取消', style: AppTheme.bodyLabel),
          ),
          TextButton(
            onPressed: () {
              cs.abortTask();
              Navigator.of(ctx).pop();
            },
            child: const Text('中止',
                style: TextStyle(color: AppTheme.statusRed)),
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

  Widget _wrap(BuildContext context, Widget content) {
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

class _MapView extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, constraints) {
      return Stack(children: [
        CustomPaint(
            size: Size(constraints.maxWidth, constraints.maxHeight),
            painter: _GridPainter()),
        const _MapPoint(
            x: 18, y: 150, color: AppTheme.accent, label: '起点'),
        const _MapPoint(
            x: 208,
            y: 30,
            color: AppTheme.statusGreen,
            label: '配电柜A'),
        const _MapPoint(
            x: 120,
            y: 58,
            color: AppTheme.statusRed,
            label: '临时障碍'),
        const _MapPoint(
            x: 236,
            y: 166,
            color: AppTheme.statusGreen,
            label: '仓储通道C'),
      ]);
    });
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
  final double x, y;
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
      child: Column(children: [
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
        Text(label, style: AppTheme.statLabel.copyWith(fontSize: 10)),
      ]),
    );
  }
}

class _LegendDot extends StatelessWidget {
  final Color color;
  final String label;
  const _LegendDot({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Container(
          width: 8,
          height: 8,
          decoration:
              BoxDecoration(color: color, shape: BoxShape.circle)),
      const SizedBox(width: 4),
      Text(label, style: AppTheme.subtitle),
    ]);
  }
}
