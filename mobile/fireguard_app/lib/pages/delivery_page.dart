import 'dart:async';
import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/car_state.dart';
import '../services/nav_service.dart';
import '../services/patrol_presets.dart';
import '../widgets/common_widgets.dart';
import '../widgets/page_shell.dart';

/// S05 - 定点配送 / 巡逻管理（双模式 + 可编辑预设 + 路线预览）
class DeliveryPage extends StatefulWidget {
  final CarState carState;
  final bool embedded;
  final VoidCallback? onReturnHome;
  const DeliveryPage({
    super.key,
    required this.carState,
    this.embedded = false,
    this.onReturnHome,
  });

  @override
  State<DeliveryPage> createState() => _DeliveryPageState();
}

class _DeliveryPageState extends State<DeliveryPage> {
  final NavService _nav = NavService();
  final _nameCtrl = TextEditingController();
  final _xCtrl = TextEditingController();
  final _yCtrl = TextEditingController();

  // ── 导航栈 ──
  bool _stackReady = false;
  String _statusHint = '';

  // ── 巡逻 ──
  PatrolStatus? _patrolStatus;
  NavRoute? _currentRoute;
  bool _patrolActive = false;

  // ── 模式 A ──
  List<String> _savedRoutes = [];

  // ── 模式 B：合并后的预设点 ──
  List<PresetPoint> _presets = [];
  final List<PresetPoint> _selectedPresets = [];
  // 会话内编辑覆盖 <name, (x,y)>
  final Map<String, _CoordEdit> _edits = {};

  // ── 路线预览 ──
  NavMapMeta? _mapMeta;
  Uint8List? _mapImage;

  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    _nav.updateConfig(widget.carState.host);
    _refreshAll();
    _pollTimer = Timer.periodic(const Duration(seconds: 4), (_) => _poll());
    widget.carState.addListener(_onCar);
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _nav.dispose();
    _nameCtrl.dispose();
    _xCtrl.dispose();
    _yCtrl.dispose();
    widget.carState.removeListener(_onCar);
    super.dispose();
  }

  void _onCar() {
    if (mounted) setState(() {});
  }

  // ═══ 轮询 ═══
  Future<void> _poll() async {
    final stack = await _nav.stackStatus();
    final patrol = await _nav.patrolStatus();
    final route = await _nav.getPatrolRoute();
    if (mounted) {
      setState(() {
        _stackReady = stack.patrolReady;
        _statusHint = stack.patrolReady ? '就绪' : stack.hint;
        _patrolStatus = patrol;
        final wasActive = _patrolActive;
        _patrolActive = patrol?.patrolActive ?? false;
        // 巡逻自然结束（active→inactive）时同步 CarState
        if (wasActive && !_patrolActive) widget.carState.completeTask();
        _currentRoute = route;
      });
    }
  }

  /// 每轮刷新：加载静态配置 + 拉取车端已保存路线途经点 → 合并去重
  Future<void> _refreshAll() async {
    setState(() => _statusHint = '连接中…');

    // 并行拉取
    final results = await Future.wait([
      _nav.listSavedRoutes(),
      _nav.fetchMapMeta(),
      _nav.fetchMapImage(),
    ]);
    final routes = (results[0] as List<String>?) ?? [];
    final meta = results[1] as NavMapMeta?;
    final img = results[2] as Uint8List?;

    // 拉取每条已保存路线的途经点
    final List<PresetPoint> routePresets = [];
    for (final name in routes) {
      final detail = await _nav.getRouteDetail(name);
      if (detail != null && detail.points.isNotEmpty) {
        routePresets.addAll(pointsToPresets(detail.points, routeName: name));
      }
    }

    if (mounted) {
      setState(() {
        _savedRoutes = routes;
        _mapMeta = meta;
        _mapImage = img;
        _presets = mergePresets(PRESET_POINTS.toList(), routePresets);
      });
    }
    await _poll();
  }

  // ═══ 获取点的有效坐标（考虑会话编辑） ═══
  PresetPoint _effective(PresetPoint p) {
    final e = _edits[p.name];
    if (e == null) return p;
    return p.copyWith(name: e.name, x: e.x, y: e.y);
  }

  // ═══ 导航栈 ═══
  Future<void> _startStack() async {
    setState(() => _statusHint = '启动中 (约15s)…');
    await _nav.stackStart();
    await _poll();
  }

  // ═══ 模式 A ═══
  Future<void> _loadSavedRoute(String name) async {
    final ok = await _nav.loadRoute(name);
    if (ok) {
      await _poll();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('已加载路线: $name'), duration: const Duration(seconds: 1)),
        );
      }
    }
  }

  // ═══ 模式 B：预设点操作 ═══
  void _togglePreset(PresetPoint p) {
    final ep = _effective(p);
    setState(() {
      final idx = _selectedPresets.indexWhere((s) => s.name == ep.name);
      if (idx >= 0) {
        _selectedPresets.removeAt(idx);
      } else {
        _selectedPresets.add(ep);
      }
    });
  }

  void _clearPresets() => setState(() => _selectedPresets.clear());

  /// 长按 → 编辑弹窗
  void _editPreset(PresetPoint p) {
    // 车端路线途经点不支持编辑
    if (p.source == 'route') return;
    final e = _edits[p.name];
    _nameCtrl.text = e?.name ?? p.name;
    _xCtrl.text = (e?.x ?? p.x).toStringAsFixed(3);
    _yCtrl.text = (e?.y ?? p.y).toStringAsFixed(3);

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF162030),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        title: const Text('编辑点坐标', style: TextStyle(color: AppTheme.textPrimary, fontWeight: FontWeight.w800)),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          _buildEditField('名称', _nameCtrl),
          const SizedBox(height: 10),
          _buildEditField('X 坐标', _xCtrl, isNum: true),
          const SizedBox(height: 10),
          _buildEditField('Y 坐标', _yCtrl, isNum: true),
        ]),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消', style: TextStyle(color: AppTheme.textSecondary)),
          ),
          TextButton(
            onPressed: () {
              final nx = double.tryParse(_xCtrl.text);
              final ny = double.tryParse(_yCtrl.text);
              final nn = _nameCtrl.text.trim();
              if (nx == null || ny == null || nn.isEmpty) return;
              setState(() {
                _edits[p.name] = _CoordEdit(nn, nx, ny);
                // 同步更新已选中的
                final si = _selectedPresets.indexWhere((s) => s.name == p.name);
                if (si >= 0) {
                  _selectedPresets[si] = _selectedPresets[si].copyWith(name: nn, x: nx, y: ny);
                }
              });
              Navigator.pop(ctx);
            },
            child: const Text('保存', style: TextStyle(color: AppTheme.accent, fontWeight: FontWeight.w800)),
          ),
        ],
      ),
    );
  }

  Widget _buildEditField(String label, TextEditingController ctrl, {bool isNum = false}) {
    return TextField(
      controller: ctrl,
      style: const TextStyle(color: AppTheme.textPrimary, fontSize: 14),
      keyboardType: isNum ? const TextInputType.numberWithOptions(decimal: true) : TextInputType.text,
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
        filled: true,
        fillColor: const Color(0xFF0F1622),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: AppTheme.cardBorder)),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: AppTheme.cardBorder)),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: AppTheme.accent)),
      ),
    );
  }

  Future<void> _applyPresetRoute() async {
    if (_selectedPresets.isEmpty) return;
    final points = _selectedPresets.map((p) => NavPoint(p.x, p.y)).toList();
    final ok = await _nav.setPatrolRoute(points);
    if (ok) {
      await _poll();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('已设置 ${points.length} 个路径点'), duration: const Duration(seconds: 1)),
        );
      }
    }
  }

  // ═══ 巡逻控制 ═══
  Future<void> _startPatrol() async {
    if (_currentRoute == null || (_currentRoute?.pointCount ?? 0) < 2) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请先设置路线 (至少 2 个点)'), duration: Duration(seconds: 1)),
      );
      return;
    }
    await _nav.startPatrol();
    await _poll();
  }

  Future<void> _stopPatrol() async {
    await _nav.stopPatrol();
    widget.carState.abortTask();
    await _poll();
  }

  Future<void> _clearRoute() async {
    await _nav.clearPatrolRoute();
    widget.carState.abortTask();
    setState(() {
      _currentRoute = null;
      _selectedPresets.clear();
    });
  }

  double get _patrolProgress {
    if (_patrolStatus == null || _currentRoute == null || _currentRoute!.pointCount == 0) return 0;
    final s = _patrolStatus!.status;
    final m = RegExp(r'navigating_waypoint_(\d+)').firstMatch(s);
    if (m != null) {
      final idx = int.tryParse(m.group(1)!) ?? 0;
      return (idx / _currentRoute!.pointCount).clamp(0.0, 1.0);
    }
    if (s == 'finished') return 1.0;
    return 0.0;
  }

  @override
  Widget build(BuildContext context) {
    final content = Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      PageHeader(
        title: '定点配送',
        subTitle: _statusHint.isEmpty ? '同一地图上的应急调度' : _statusHint,
        badgeText: _patrolActive ? '巡逻中' : (_stackReady ? '就绪' : '待命'),
        badgeActive: _patrolActive || _stackReady,
      ),
      const SizedBox(height: 20),

      // ── 导航栈状态 ──
      GlassCard(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Column(children: [
          InfoRow(label: '导航栈', value: _stackReady ? '已就绪' : '未启动'),
          const Divider(color: AppTheme.dividerLine, height: 18),
          InfoRow(label: '当前路线', value: _currentRoute != null ? '${_currentRoute!.pointCount} 个点' : '无'),
          const Divider(color: AppTheme.dividerLine, height: 18),
          InfoRow(label: '巡逻状态', value: _patrolStatus?.status ?? _statusHint),
        ]),
      ),
      const SizedBox(height: 14),

      if (!_stackReady) ...[
        GradientButton(text: '启动导航栈', onTap: _startStack),
        const SizedBox(height: 14),
      ],

      // ═══ 模式 A：已保存路线 ═══
      _sectionTitle('已保存路线', '从车端加载'),
      const SizedBox(height: 8),
      if (_savedRoutes.isEmpty)
        _emptyCard('暂无已保存路线')
      else
        Wrap(spacing: 8, runSpacing: 8, children: _savedRoutes.map((name) {
          return GestureDetector(
            onTap: () => _loadSavedRoute(name),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: AppTheme.btnSecondaryBg,
                borderRadius: BorderRadius.circular(9),
                border: Border.all(color: AppTheme.cardBorder),
              ),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.route, size: 16, color: AppTheme.accent),
                const SizedBox(width: 8),
                Text(name, style: const TextStyle(color: AppTheme.textPrimary, fontWeight: FontWeight.w700, fontSize: 14)),
              ]),
            ),
          );
        }).toList()),
      const SizedBox(height: 18),

      // ═══ 模式 B：预设点网格 ═══
      _sectionTitle('预设点', '单击选择 · 长按编辑'),
      const SizedBox(height: 8),
      Wrap(spacing: 8, runSpacing: 8, children: _presets.map((p) {
        final isRoute = p.source == 'route';
        final ep = _effective(p);
        final selected = _selectedPresets.any((s) => s.name == ep.name);
        return GestureDetector(
          onTap: () => _togglePreset(p),
          onLongPress: () => _editPreset(p),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
            decoration: BoxDecoration(
              color: isRoute
                  ? const Color(0xFF1A2535)
                  : (selected ? AppTheme.accent.withAlpha(30) : AppTheme.btnSecondaryBg),
              borderRadius: BorderRadius.circular(9),
              border: Border.all(
                color: isRoute
                    ? const Color(0xFF2A3D56)
                    : (selected ? AppTheme.accent : AppTheme.cardBorder),
              ),
            ),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              if (isRoute)
                const Text('🔣', style: TextStyle(fontSize: 13))
              else
                Icon(selected ? Icons.check_circle : Icons.add_circle_outline,
                    size: 16, color: selected ? AppTheme.accent : AppTheme.textSecondary),
              const SizedBox(width: 6),
              Text(
                ep.name,
                style: TextStyle(
                  color: selected ? AppTheme.accent : AppTheme.textPrimary,
                  fontWeight: FontWeight.w700,
                  fontSize: 13,
                ),
              ),
            ]),
          ),
        );
      }).toList()),
      const SizedBox(height: 12),

      // ── 自选路线面板（含地图预览） ──
      if (_selectedPresets.isNotEmpty) ...[
        GlassCard(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              Text('自选路线 (${_selectedPresets.length} 点)', style: AppTheme.bodyLabel),
              GestureDetector(
                onTap: _clearPresets,
                child: const Text('清空', style: TextStyle(color: AppTheme.accent, fontSize: 12, fontWeight: FontWeight.w700)),
              ),
            ]),
            const SizedBox(height: 8),

            // ── 路线预览地图 ──
            if (_mapMeta != null && _selectedPresets.length >= 2) _buildRoutePreview(),

            const SizedBox(height: 8),
            Wrap(spacing: 6, runSpacing: 6, children: _selectedPresets.asMap().entries.map((e) {
              final isLast = e.key == _selectedPresets.length - 1;
              return Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: isLast ? AppTheme.cyan.withAlpha(25) : AppTheme.accent.withAlpha(20),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  Text('${e.key + 1}',
                      style: TextStyle(
                          color: isLast ? AppTheme.cyan : AppTheme.accent, fontSize: 11, fontWeight: FontWeight.w800)),
                  const SizedBox(width: 6),
                  Text(e.value.name, style: const TextStyle(color: AppTheme.textPrimary, fontSize: 12, fontWeight: FontWeight.w600)),
                  const SizedBox(width: 4),
                  GestureDetector(
                    onTap: () => setState(() => _selectedPresets.removeAt(e.key)),
                    child: const Icon(Icons.close, size: 14, color: AppTheme.textSecondary),
                  ),
                ]),
              );
            }).toList()),
          ]),
        ),
        const SizedBox(height: 10),
        GradientButton(text: '设为路线', onTap: _applyPresetRoute),
        const SizedBox(height: 10),
      ],

      // ═══ 巡逻控制 ═══
      const SizedBox(height: 6),
      Wrap(spacing: 8, runSpacing: 8, children: [
        SmallButton(
          text: _patrolActive ? '停止巡逻' : '开始巡逻',
          onTap: _patrolActive ? _stopPatrol : _startPatrol,
        ),
        SmallButton(text: '清空路线', onTap: _clearRoute),
        SmallButton(text: '刷新状态', onTap: _refreshAll),
      ]),
      const SizedBox(height: 10),

      // ── 巡逻进度 ──
      if (_patrolActive && _currentRoute != null) ...[
        const SizedBox(height: 8),
        GlassCard(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('巡逻路径', style: AppTheme.bodyLabel),
            const SizedBox(height: 8),
            Text(
              '途经 ${_currentRoute!.pointCount} 个点${_currentRoute!.loop ? ' (循环)' : ''}',
              style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16, color: AppTheme.textPrimary),
            ),
            const SizedBox(height: 14),
            ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: LinearProgressIndicator(
                value: _patrolProgress,
                minHeight: 8,
                backgroundColor: const Color(0xFF26364A),
                color: AppTheme.accent,
              ),
            ),
            const SizedBox(height: 8),
            Text('状态: ${_patrolStatus?.status ?? '—'}', style: AppTheme.bodyLabel),
          ]),
        ),
      ],
    ]);

    return _wrap(context, content);
  }

  // ═══ 路线预览组件：地图底图 + 编号圆点 + 方向箭头 ═══
  Widget _buildRoutePreview() {
    return Column(children: [
      const Divider(color: AppTheme.dividerLine, height: 20),
      Text('路线预览', style: AppTheme.bodyLabel),
      const SizedBox(height: 6),
      ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: SizedBox(
          height: 120,
          width: double.infinity,
          child: CustomPaint(
            painter: _RoutePreviewPainter(
              mapImage: _mapImage,
              mapMeta: _mapMeta!,
              points: _selectedPresets.map((p) => ui.Offset(p.x, p.y)).toList(),
            ),
            child: _mapImage != null
                ? Image.memory(_mapImage!, fit: BoxFit.cover, gaplessPlayback: true)
                : Container(color: const Color(0xFF0A111B)),
          ),
        ),
      ),
    ]);
  }

  Widget _sectionTitle(String title, String sub) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text(title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w800, color: AppTheme.textPrimary)),
        Text(sub, style: AppTheme.subtitle),
      ]),
    );
  }

  Widget _emptyCard(String text) => GlassCard(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Text(text, style: AppTheme.bodyLabel, textAlign: TextAlign.center),
      );

  Widget _wrap(BuildContext context, Widget content) {
    if (widget.embedded) {
      return SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(AppTheme.pagePadding, 16, AppTheme.pagePadding, AppTheme.tabBarInset),
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

/// 路线预览绘制器：编号圆点 + 有向箭头
class _RoutePreviewPainter extends CustomPainter {
  final Uint8List? mapImage;
  final NavMapMeta mapMeta;
  final List<ui.Offset> points; // 世界坐标

  const _RoutePreviewPainter({
    required this.mapImage,
    required this.mapMeta,
    required this.points,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (points.isEmpty || mapMeta.width == 0 || mapMeta.height == 0) return;

    // 世界坐标 → 地图像素
    List<ui.Offset> toPixel(List<ui.Offset> pts) {
      return pts.map((p) {
        final px = (p.dx - mapMeta.origin[0]) / mapMeta.resolution;
        final py = mapMeta.height - (p.dy - mapMeta.origin[1]) / mapMeta.resolution;
        return ui.Offset(px, py);
      }).toList();
    }

    // 地图像素 → 显示尺寸
    List<ui.Offset> toDisplay(List<ui.Offset> pixelPts) {
      return pixelPts.map((p) {
        return ui.Offset(
          p.dx * size.width / mapMeta.width,
          p.dy * size.height / mapMeta.height,
        );
      }).toList();
    }

    final displayPts = toDisplay(toPixel(points));
    final arrowPaint = Paint()
      ..color = AppTheme.accent
      ..strokeWidth = 2.0
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final arrowFill = Paint()
      ..color = AppTheme.accent
      ..style = PaintingStyle.fill;

    // 画连接线 + 箭头
    for (int i = 0; i < displayPts.length - 1; i++) {
      final from = displayPts[i];
      final to = displayPts[i + 1];
      canvas.drawLine(from, to, arrowPaint);

      // 三角箭头在每段中点
      _drawArrowHead(canvas, from, to, arrowFill, size: 5.0);
    }

    // 画编号圆点
    for (int i = 0; i < displayPts.length; i++) {
      final pt = displayPts[i];
      final isLast = i == displayPts.length - 1;
      final r = 10.0;

      // 圆点填充
      canvas.drawCircle(
        pt,
        r,
        Paint()..color = isLast ? AppTheme.accent : AppTheme.accent,
      );
      // 圆点边框
      canvas.drawCircle(
        pt,
        r,
        Paint()..color = Colors.white..strokeWidth = 2.0..style = PaintingStyle.stroke,
      );

      // 序号
      final tp = TextPainter(
        text: TextSpan(
          text: '${i + 1}',
          style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w800),
        ),
        textDirection: ui.TextDirection.ltr,
      );
      tp.layout();
      tp.paint(canvas, pt - ui.Offset(tp.width / 2, tp.height / 2));
    }
  }

  void _drawArrowHead(Canvas canvas, ui.Offset from, ui.Offset to, Paint fillPaint, {double size = 5.0}) {
    final dir = (to - from);
    final dist = dir.distance;
    if (dist < 1) return;
    final u = dir / dist;
    final perp = ui.Offset(-u.dy, u.dx);

    final mid = from + dir * 0.5;
    final tip = mid + u * size;
    final base = mid - u * size;
    final left = base + perp * size;
    final right = base - perp * size;

    final path = Path()
      ..moveTo(tip.dx, tip.dy)
      ..lineTo(left.dx, left.dy)
      ..lineTo(right.dx, right.dy)
      ..close();
    canvas.drawPath(path, fillPaint);
  }

  @override
  bool shouldRepaint(covariant _RoutePreviewPainter old) =>
      old.points != points || old.mapImage != mapImage;
}

class _CoordEdit {
  final String name;
  final double x;
  final double y;
  const _CoordEdit(this.name, this.x, this.y);
}
