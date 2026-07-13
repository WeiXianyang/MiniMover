import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/car_state.dart';
import '../widgets/common_widgets.dart';
import '../widgets/page_shell.dart';
import 'manual_control_page.dart';

/// S03 - 地图与任务页面
/// 对齐 prototype page-prototype/map.html
/// 网格地图 + 路线线段 + 节点标记 + 小车位置
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

  /// 小车在路线上的位置比例（对齐 prototype 41% 位置）
  double get _carProgress => widget.carState.taskProgress > 0
      ? widget.carState.taskProgress
      : 0.41;

  @override
  Widget build(BuildContext context) {
    final cs = widget.carState;

    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
                Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── 页头：对齐 prototype 避障中 pill ──
              PageHeader(
                title: '地图与任务',
                subTitle: '路径进度与障碍状态',
                badgeText: cs.taskPaused
                    ? '已暂停'
                    : (cs.taskRunning ? '避障中' : '待命'),
                badgeActive: cs.taskRunning,
              ),
              const SizedBox(height: 20),
              // ── 地图区域：网格 + 路线 + 节点 + 小车 ──
              GlassCard(
                  height: 250,
                  padding: const EdgeInsets.all(0),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(10),
                    child: _MapRouteView(carProgress: _carProgress),
                  )),
              const SizedBox(height: 12),
              // ── 图例：对齐 prototype ──
              Row(
                children: [
                  _LegendDot(color: AppTheme.cyan, label: '当前路径'),
                  const SizedBox(width: 12),
                  _LegendDot(color: AppTheme.accent, label: '小车位置'),
                  const SizedBox(width: 12),
                  _LegendDot(color: AppTheme.statusRed, label: '告警点'),
                ],
              ),
              const SizedBox(height: 16),
              // ── 进度卡片 ──
              GlassCard(
                padding: const EdgeInsets.symmetric(
                    horizontal: 16, vertical: 14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    InfoRow(
                      label: '巡检进度',
                      value: '${(_carProgress * 100).round()}%',
                    ),
                    const SizedBox(height: 8),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(999),
                      child: LinearProgressIndicator(
                          value: _carProgress,
                          minHeight: 8,
                          backgroundColor: const Color(0xFF26364A),
                          color: AppTheme.accent),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      cs.taskRunning
                          ? '已到达 B2 区域，正在靠近配电柜 A。'
                          : '任务尚未开始，点击下方按钮启动巡检。',
                      style: AppTheme.bodyLabel,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),
              // ── 操作按钮：对齐 prototype 暂停 + 手动接管 ──
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
                      text: '手动接管',
                      onTap: () => _push(
                          context,
                          '手动接管',
                          ManualControlPage(
                              carState: cs, embedded: true)),
                    ),
                  ),
                ],
              ),
            ],
          ),
      ],
    );

    return _wrap(context, content);
  }

  void _push(BuildContext context, String title, Widget page) {
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => PageShell(title: title, child: page),
    ));
  }


  Widget _wrap(BuildContext context, Widget content) {
    if (widget.embedded) {
      return SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(
            AppTheme.pagePadding, 16, AppTheme.pagePadding, AppTheme.tabBarInset),
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

/// 网格地图 + 路线线段 + 节点 + 小车指示器
class _MapRouteView extends StatelessWidget {
  final double carProgress;
  const _MapRouteView({required this.carProgress});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, constraints) {
      final w = constraints.maxWidth;
      final h = constraints.maxHeight;

      // ── 路线路径定义（相对坐标，对齐 prototype）──
      // Node A → Node B (水平线段) → Node C (垂直线段)
      const ax = 60.0, ay = 82.0;   // 起点 A
      const bx = 210.0, by = 82.0;  // 途经点 B (配电柜A)
      const cx = 210.0, cy = 186.0; // 终点 C (仓储通道)
      const nodeR = 14.0;

      // ── 根据进度计算小车位置（沿 A→B→C 路线）──
      final abLen = bx - ax;           // 水平段长度
      final bcLen = cy - by;           // 垂直段长度
      final totalLen = abLen + bcLen;
      final traveled = carProgress * totalLen;

      double carX, carY;
      if (traveled <= abLen) {
        // 在水平段上
        carX = ax + traveled;
        carY = ay;
      } else {
        // 在垂直段上
        carX = bx;
        carY = by + (traveled - abLen);
      }

      return CustomPaint(
        size: Size(w, h),
        painter: _RouteGridPainter(
          ax: ax, ay: ay, bx: bx, by: by, cx: cx, cy: cy,
          carX: carX, carY: carY, carR: nodeR,
        ),
      );
    });
  }
}

class _RouteGridPainter extends CustomPainter {
  final double ax, ay, bx, by, cx, cy, carX, carY, carR;

  _RouteGridPainter({
    required this.ax, required this.ay,
    required this.bx, required this.by,
    required this.cx, required this.cy,
    required this.carX, required this.carY,
    required this.carR,
  });

  @override
  void paint(Canvas canvas, Size size) {
    // ── 网格背景（对齐 prototype .map 网格 30x30）──
    final gridPaint = Paint()
      ..color = const Color.fromRGBO(48, 211, 255, 0.08)
      ..strokeWidth = 1;
    const step = 30.0;
    for (double x = 0; x <= size.width; x += step) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), gridPaint);
    }
    for (double y = 0; y <= size.height; y += step) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    // ── 路线线段（水平 A→B + 垂直 B→C，对齐 prototype route-x / route-y）──
    final routePaint = Paint()
      ..color = AppTheme.cyan
      ..strokeWidth = 4
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(Offset(ax, ay), Offset(bx, by), routePaint); // 水平段
    canvas.drawLine(Offset(bx, by), Offset(cx, cy), routePaint); // 垂直段

    // ── 节点 A（起点，青色）──
    _drawNode(canvas, ax, ay, AppTheme.cyan, 'A');
    // ── 节点 B（配电柜A，青色）──
    _drawNode(canvas, bx, by, AppTheme.cyan, 'B');
    // ── 节点 C（告警点，红色）──
    _drawNode(canvas, cx, cy, AppTheme.statusRed, 'C');

    // ── 小车位置（橙色，带光晕）──
    final glowPaint = Paint()
      ..color = const Color.fromRGBO(255, 151, 72, 0.13)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 10);
    canvas.drawCircle(Offset(carX, carY), carR + 6, glowPaint);
    canvas.drawCircle(Offset(carX, carY), carR, Paint()..color = AppTheme.accent);
  }

  void _drawNode(Canvas canvas, double x, double y, Color color, String label) {
    final r = carR / 2;
    canvas.drawCircle(Offset(x, y), r, Paint()..color = color);
    // 标签使用 TextPainter
    final tp = TextPainter(
      text: TextSpan(
        text: label,
        style: const TextStyle(
          color: Color(0xFF08202A),
          fontSize: 9,
          fontWeight: FontWeight.w900,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, Offset(x - tp.width / 2, y - tp.height / 2));
  }

  @override
  bool shouldRepaint(covariant _RouteGridPainter oldDelegate) =>
      carX != oldDelegate.carX || carY != oldDelegate.carY;
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
        decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      ),
      const SizedBox(width: 5),
      Text(label, style: AppTheme.subtitle),
    ]);
  }
}
