import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/car_state.dart';
import '../services/nav_service.dart';
import '../widgets/common_widgets.dart';
import '../widgets/page_shell.dart';
import 'manual_control_page.dart';

/// S03 - 地图与导航（单点导航，鸿蒙路线：不依赖 patrol 节点）
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
  NavPoint? _target;
  bool _loading = true;
  bool _busy = false;
  String _statusText = '';
  final List<String> _logs = [];
  bool _showLogs = false;

  @override
  void initState() {
    super.initState();
    _nav.updateConfig(widget.carState.host);
    _initNav();
    widget.carState.addListener(_onCs);
  }

  @override
  void dispose() {
    _nav.dispose();
    widget.carState.removeListener(_onCs);
    super.dispose();
  }

  void _onCs() { if (mounted) setState(() {}); }

  void _addLog(String msg) {
    final t = DateTime.now().toIso8601String().substring(11, 19);
    final line = '[$t] $msg';
    debugPrint('[MapNav] $line');
    setState(() { _logs.add(line); if (_logs.length > 200) _logs.removeAt(0); });
  }

  void _showMsg(String msg, {bool error = false}) {
    _addLog(error ? 'ERROR: $msg' : msg);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(msg, style: const TextStyle(color: Colors.white)),
          backgroundColor: error ? Colors.red.shade800 : null,
          duration: const Duration(seconds: 2),
        ),
      );
    }
  }

  Future<void> _initNav() async {
    _addLog('加载地图 — ${widget.carState.host}:5000');
    setState(() => _statusText = '加载地图…');
    try {
      final meta = await _nav.fetchMapMeta();
      if (meta != null) {
        _addLog('地图元数据: ${meta.map} ${meta.width}x${meta.height} res=${meta.resolution}');
        setState(() { _mapMeta = meta; _statusText = '下载地图图片…'; });
        final img = await _nav.fetchMapImage();
        if (img != null) {
          setState(() => _mapImage = Uint8List.fromList(img));
          _addLog('地图图片: ${img.length} bytes');
        } else {
          _addLog('地图图片下载失败（使用网格占位）');
        }
      } else {
        _addLog('地图元数据获取失败');
      }
    } catch (e) {
      _addLog('初始化异常: $e');
    }
    setState(() { _statusText = '点击地图选择导航目标'; _loading = false; });
  }

  void _onTapMap(TapUpDetails d, double displayW, double displayH) {
    if (_mapMeta == null || _busy) return;
    final px = d.localPosition.dx * _mapMeta!.width / displayW;
    final py = d.localPosition.dy * _mapMeta!.height / displayH;
    final mx = px * _mapMeta!.resolution + _mapMeta!.origin[0];
    final my = (_mapMeta!.height - py) * _mapMeta!.resolution + _mapMeta!.origin[1];
    setState(() { _target = NavPoint(mx, my); });
    _addLog('选择目标: (${mx.toStringAsFixed(3)}, ${my.toStringAsFixed(3)}) ← 像素 (${px.toStringAsFixed(0)}, ${py.toStringAsFixed(0)})');
  }

  Future<void> _setInitialPose() async {
    if (_target == null) return;
    setState(() => _busy = true);
    _addLog('设置初始位姿 — POST /api/nav/initial_pose (${_target!.x.toStringAsFixed(3)}, ${_target!.y.toStringAsFixed(3)})');
    try {
      final ok = await _nav.setInitialPose(_target!.x, _target!.y);
      if (ok) {
        widget.carState.startTask();
        _showMsg('初始位姿已设置 (${_target!.x.toStringAsFixed(2)}, ${_target!.y.toStringAsFixed(2)})');
      } else {
        _showMsg('设置初始位姿失败', error: true);
      }
    } catch (e) {
      _addLog('异常: $e');
      _showMsg('设置失败: $e', error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _navigateToTarget() async {
    if (_target == null) return;
    setState(() => _busy = true);
    _addLog('=== 单点导航 ===');
    _addLog('POST /api/nav/navigate x=${_target!.x.toStringAsFixed(3)} y=${_target!.y.toStringAsFixed(3)}');
    try {
      final ok = await _nav.navigate(_target!.x, _target!.y);
      if (ok) {
        widget.carState.startTask();
        _showMsg('导航已下发: (${_target!.x.toStringAsFixed(2)}, ${_target!.y.toStringAsFixed(2)})');
        _addLog('导航命令已发送，小车开始移动');
      } else {
        _showMsg('导航命令发送失败', error: true);
      }
    } catch (e) {
      _addLog('异常: $e');
      _showMsg('导航失败: $e', error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _clearTarget() {
    setState(() => _target = null);
    _addLog('清除目标');
  }

  @override
  Widget build(BuildContext context) {
    final hasTarget = _target != null;
    final content = Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        PageHeader(
          title: '地图与导航',
          subTitle: _busy ? '通信中…' : _statusText,
          badgeText: hasTarget ? '目标已选' : '待选择',
          badgeActive: hasTarget,
        ),
        if (_busy)
          const Padding(
            padding: EdgeInsets.only(top: 8),
            child: ClipRRect(
              borderRadius: BorderRadius.all(Radius.circular(999)),
              child: LinearProgressIndicator(minHeight: 3, backgroundColor: Color(0xFF26364A), color: AppTheme.accent),
            ),
          ),
        const SizedBox(height: 16),
        // ── 地图 ──
        LayoutBuilder(builder: (ctx, outerCts) {
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
                        // ── 目标标记 ──
                        if (_target != null && _mapMeta != null) ...[
                          // 十字准星
                          Builder(builder: (_) {
                            final l = (_target!.x - _mapMeta!.origin[0]) / _mapMeta!.resolution;
                            final t = _mapMeta!.height - (_target!.y - _mapMeta!.origin[1]) / _mapMeta!.resolution;
                            final cx = l * displayW / _mapMeta!.width;
                            final cy = t * displayH / _mapMeta!.height;
                            return Positioned(
                              left: cx - 15, top: cy - 15,
                              child: IgnorePointer(
                                child: Container(
                                  width: 30, height: 30,
                                  decoration: const BoxDecoration(shape: BoxShape.circle, color: Color(0x40FF4444)),
                                  child: const Icon(Icons.location_on, color: Color(0xFFFF4444), size: 30),
                                ),
                              ),
                            );
                          }),
                        ],
                      ]),
                    ),
            ));
        }),
        const SizedBox(height: 12),
        // ── 目标信息卡 ──
        GlassCard(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Column(children: [
            InfoRow(
              label: '目标坐标',
              value: hasTarget ? '(${_target!.x.toStringAsFixed(2)}, ${_target!.y.toStringAsFixed(2)})' : '—',
            ),
            if (hasTarget) ...[
              const Divider(color: AppTheme.dividerLine, height: 18),
              InfoRow(label: '操作', value: _busy ? '通信中…' : '选择下方按钮'),
            ],
          ]),
        ),
        const SizedBox(height: 16),
        // ── 操作按钮 ──
        Wrap(spacing: 8, runSpacing: 8, children: [
          SmallButton(
            text: '设初始位姿',
            busy: _busy,
            onTap: (_busy || !hasTarget) ? null : _setInitialPose,
          ),
          SmallButton(
            text: '导航到此',
            busy: _busy,
            onTap: (_busy || !hasTarget) ? null : _navigateToTarget,
          ),
          SmallButton(
            text: '清除目标',
            busy: _busy,
            onTap: (_busy || !hasTarget) ? null : _clearTarget,
          ),
        ]),
        const SizedBox(height: 8),
        SmallButton(
          text: '手动接管',
          busy: _busy,
          onTap: _busy ? null : () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => ManualControlPage(carState: widget.carState, embedded: true))),
        ),

        // ── 调试日志 ──
        const SizedBox(height: 12),
        GestureDetector(
          onTap: () => setState(() => _showLogs = !_showLogs),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(_showLogs ? Icons.expand_less : Icons.expand_more, size: 16, color: AppTheme.textSecondary),
            const SizedBox(width: 4),
            Text('调试日志 (${_logs.length})', style: AppTheme.subtitle),
          ]),
        ),
        if (_showLogs)
          GlassCard(
            padding: const EdgeInsets.all(10),
            child: SizedBox(
              height: 150,
              child: SingleChildScrollView(
                child: SelectableText(
                  _logs.reversed.take(50).join('\n'),
                  style: const TextStyle(color: AppTheme.cyan, fontSize: 11, fontFamily: 'monospace', height: 1.5),
                ),
              ),
            ),
          ),
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
