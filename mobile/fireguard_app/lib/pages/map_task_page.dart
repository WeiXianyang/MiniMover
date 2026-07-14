import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/car_state.dart';
import '../services/nav_service.dart';
import '../widgets/common_widgets.dart';
import '../widgets/page_shell.dart';
import 'manual_control_page.dart';

/// S03 - 地图与巡逻
/// 对接小车 /api/nav/* 导航巡逻 API
class MapTaskPage extends StatefulWidget {
  final CarState carState;
  final bool embedded;
  const MapTaskPage({super.key, required this.carState, this.embedded = false});
  @override
  State<MapTaskPage> createState() => _MapTaskPageState();
}

class _MapTaskPageState extends State<MapTaskPage> {
  final NavService _nav = NavService();
  NavMapMeta? _mapMeta;
  Uint8List? _mapImage;
  PatrolStatus? _patrolStatus;
  List<NavPoint> _routePoints = [];
  bool _stackReady = false;
  bool _loading = true;
  String _statusText = '';

  @override
  void initState() {
    super.initState();
    _nav.updateConfig(widget.carState.host);
    _initNav();
    widget.carState.addListener(_onCs);
  }

  @override
  void dispose() {
    _nav.stopPatrol();
    _nav.dispose();
    widget.carState.removeListener(_onCs);
    super.dispose();
  }

  void _onCs() { if (mounted) setState(() {}); }

  Future<void> _initNav() async {
    setState(() => _statusText = '启动导航栈…');
    final meta = await _nav.fetchMapMeta();
    if (meta != null) {
      setState(() { _mapMeta = meta; _statusText = '加载地图…'; });
      final img = await _nav.fetchMapImage();
      if (img != null) setState(() => _mapImage = Uint8List.fromList(img));
    }
    final s = await _nav.stackStatus();
    setState(() { _stackReady = s.patrolReady; _statusText = s.patrolReady ? '就绪' : s.hint; _loading = false; });
  }

  Future<void> _startStack() async {
    setState(() => _statusText = '启动中 (约15s)…');
    final ok = await _nav.stackStart();
    if (ok) { final s = await _nav.stackStatus(); setState(() { _stackReady = s.patrolReady; _statusText = s.patrolReady ? '就绪' : s.hint; }); }
  }

  Future<void> _stopStack() async {
    await _nav.stackStop();
    widget.carState.abortTask();
    setState(() { _stackReady = false; _statusText = '已关闭'; _routePoints = []; });
  }

  void _onTapMap(TapUpDetails d, double displayW, double displayH) {
    if (_mapMeta == null || !_stackReady) return;
    final px = d.localPosition.dx * _mapMeta!.width / displayW;
    final py = d.localPosition.dy * _mapMeta!.height / displayH;
    final mx = px * _mapMeta!.resolution + _mapMeta!.origin[0];
    final my = (_mapMeta!.height - py) * _mapMeta!.resolution + _mapMeta!.origin[1];
    setState(() { _routePoints = [..._routePoints, NavPoint(mx, my)]; });
  }

  Future<void> _setPoseAndRoute() async {
    if (_routePoints.isEmpty) return;
    await _nav.setInitialPose(_routePoints.first.x, _routePoints.first.y);
    await _nav.setPatrolRoute(_routePoints);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('已设置 ${_routePoints.length} 个路径点'), duration: const Duration(seconds: 1)),
    );
  }

  Future<void> _startPatrol() async {
    if (_routePoints.length < 2) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('至少需要 2 个路径点'), duration: Duration(seconds: 1)),
      );
      return;
    }
    await _setPoseAndRoute();
    await _nav.startPatrol();
    _pollStatus();
  }

  Future<void> _stopPatrol() async {
    await _nav.stopPatrol();
    widget.carState.abortTask();
    setState(() => _patrolStatus = null);
  }

  void _pollStatus() async {
    final s = await _nav.patrolStatus();
    if (mounted) {
      final wasActive = _patrolStatus?.patrolActive == true;
      setState(() => _patrolStatus = s);
      if (s?.patrolActive == true) {
        Future.delayed(const Duration(seconds: 2), _pollStatus);
      } else if (wasActive) {
        widget.carState.completeTask();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final content = Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        PageHeader(title: '地图与巡逻', subTitle: _statusText,
          badgeText: _patrolStatus?.patrolActive == true ? '巡逻中' : (_stackReady ? '就绪' : '未启动'),
          badgeActive: _stackReady),
        const SizedBox(height: 16),
        LayoutBuilder(builder: (ctx, outerCts) {
          // 根据地图元数据计算显示宽高比，默认 1:1
          final metaW = _mapMeta?.width ?? 1;
          final metaH = _mapMeta?.height ?? 1;
          final aspect = metaW > 0 && metaH > 0 ? metaW / metaH : 1.0;
          final displayW = outerCts.maxWidth;
          final displayH = (displayW / aspect).clamp(120.0, 500.0);
          return GlassCard(height: displayH, padding: const EdgeInsets.all(0),
            child: ClipRRect(borderRadius: BorderRadius.circular(10),
              child: _loading
                  ? const Center(child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.accent))
                  : GestureDetector(onTapUp: (d) => _onTapMap(d, displayW, displayH),
                      child: Stack(children: [
                        if (_mapImage != null) Positioned.fill(child: Image.memory(_mapImage!, fit: BoxFit.fill)),
                        if (_mapImage == null) Positioned.fill(child: CustomPaint(size: Size.infinite, painter: _GridPainter())),
                        ..._routePoints.asMap().entries.map((e) {
                          final i = e.key; final p = e.value;
                          if (_mapMeta == null) return const SizedBox();
                          final l = (p.x - _mapMeta!.origin[0]) / _mapMeta!.resolution;
                          final t = _mapMeta!.height - (p.y - _mapMeta!.origin[1]) / _mapMeta!.resolution;
                          return Positioned(
                            left: l * displayW / _mapMeta!.width - 10,
                            top: t * displayH / _mapMeta!.height - 15,
                            child: Column(mainAxisSize: MainAxisSize.min, children: [
                              Container(width: 20, height: 20, decoration: BoxDecoration(shape: BoxShape.circle,
                                color: i == 0 ? AppTheme.accent : AppTheme.cyan, border: Border.all(color: Colors.white, width: 2)),
                                child: Center(child: Text('${i + 1}', style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w800)))),
                              Text(i == 0 ? '起点' : '点${i + 1}', style: const TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.w700)),
                            ]),
                          );
                        }),
                      ]),
                    ),
            ));
        }),
        const SizedBox(height: 12),
        GlassCard(padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Column(children: [
            InfoRow(label: '路径点数', value: '${_routePoints.length}'),
            const Divider(color: AppTheme.dividerLine, height: 18),
            InfoRow(label: '巡逻状态', value: _patrolStatus?.status ?? _statusText),
          ])),
        const SizedBox(height: 16),
        if (!_stackReady) ...[
          GradientButton(text: '启动导航栈', onTap: _startStack),
        ] else ...[
          Wrap(spacing: 8, runSpacing: 8, children: [
            SmallButton(text: _patrolStatus?.patrolActive == true ? '停止巡逻' : '开始巡逻',
                onTap: () => _patrolStatus?.patrolActive == true ? _stopPatrol() : _startPatrol()),
            SmallButton(text: '设起点+路线', onTap: _routePoints.length >= 2 ? _setPoseAndRoute : null),
            SmallButton(text: '清除路径点', onTap: () => setState(() => _routePoints = [])),
            SmallButton(text: '关闭导航栈', onTap: _stopStack),
          ]),
        ],
        const SizedBox(height: 8),
        SmallButton(text: '手动接管', onTap: () => _push(context, '手动接管', ManualControlPage(carState: widget.carState, embedded: true))),
      ]),
    ]);
    return _wrap(context, content);
  }

  void _push(BuildContext c, String t, Widget p) {
    Navigator.of(c).push(MaterialPageRoute(builder: (_) => PageShell(title: t, child: p)));
  }

  Widget _wrap(BuildContext c, Widget w) => widget.embedded
      ? SingleChildScrollView(padding: const EdgeInsets.fromLTRB(AppTheme.pagePadding, 16, AppTheme.pagePadding, AppTheme.tabBarInset), child: w)
      : PageShell(child: SafeArea(child: SingleChildScrollView(padding: const EdgeInsets.all(AppTheme.pagePadding), child: w)));
}

class _GridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()..color = const Color(0x1430D3FF)..strokeWidth = 0.5;
    for (double x = 0; x <= size.width; x += 30) canvas.drawLine(Offset(x, 0), Offset(x, size.height), p);
    for (double y = 0; y <= size.height; y += 30) canvas.drawLine(Offset(0, y), Offset(size.width, y), p);
  }
  @override
  bool shouldRepaint(covariant CustomPainter o) => false;
}
