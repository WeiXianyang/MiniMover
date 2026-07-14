import 'dart:async';
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/car_state.dart';
import '../services/nav_service.dart';
import '../services/patrol_presets.dart';
import '../widgets/common_widgets.dart';
import '../widgets/page_shell.dart';

/// S05 - 定点配送（单点快速导航 + 已保存路线导航）
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
  final List<String> _logs = [];
  bool _showLogs = false;
  bool _busy = false;

  // 预设点（含静态 + 路线提取）
  List<PresetPoint> _presets = [];
  PresetPoint? _selected;

  // 已保存路线（车端 JSON）
  List<String> _savedRoutes = [];

  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _nav.updateConfig(widget.carState.host);
    _refreshAll();
    _refreshTimer = Timer.periodic(const Duration(seconds: 8), (_) => _refreshAll());
    widget.carState.addListener(_onCar);
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _nav.dispose();
    widget.carState.removeListener(_onCar);
    super.dispose();
  }

  void _onCar() { if (mounted) setState(() {}); }

  void _addLog(String msg) {
    final t = DateTime.now().toIso8601String().substring(11, 19);
    debugPrint('[Delivery] $t $msg');
    setState(() { _logs.add('[$t] $msg'); if (_logs.length > 200) _logs.removeAt(0); });
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

  Future<void> _refreshAll() async {
    final results = await Future.wait([
      _nav.listSavedRoutes(),
      _nav.fetchMapMeta(),
    ]);
    final routes = (results[0] as List<String>?) ?? [];

    // 提取已保存路线的途经点
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
        _presets = mergePresets(PRESET_POINTS.toList(), routePresets);
      });
      _addLog('刷新: ${_savedRoutes.length} 条路线, ${_presets.length} 个预设点');
    }
  }

  /// 选中预设点 → 设初始位姿 → 导航
  Future<void> _navigateToPreset(PresetPoint p) async {
    if (_busy) return;
    setState(() { _busy = true; _selected = p; });
    _addLog('=== 导航到 ${p.name} ===');
    try {
      _addLog('POST initial_pose (${p.x.toStringAsFixed(3)}, ${p.y.toStringAsFixed(3)})');
      await _nav.setInitialPose(p.x, p.y);
      _addLog('POST navigate (${p.x.toStringAsFixed(3)}, ${p.y.toStringAsFixed(3)})');
      final ok = await _nav.navigate(p.x, p.y);
      if (ok) {
        widget.carState.startTask();
        _showMsg('已导航到 ${p.name} (${p.x.toStringAsFixed(2)}, ${p.y.toStringAsFixed(2)})');
      } else {
        _showMsg('导航失败', error: true);
      }
    } catch (e) {
      _addLog('异常: $e');
      _showMsg('导航失败: $e', error: true);
    } finally {
      if (mounted) setState(() { _busy = false; _selected = null; });
    }
  }

  /// 加载已保存路线 → 取第一个点导航
  Future<void> _loadAndNavigate(String name) async {
    if (_busy) return;
    setState(() => _busy = true);
    _addLog('=== 加载路线 $name ===');
    try {
      final ok = await _nav.loadRoute(name, applyInitialPose: true);
      if (ok) {
        widget.carState.startTask();
        _showMsg('已加载路线: $name');
        _addLog('路线 $name 加载成功');
      } else {
        _showMsg('加载路线失败', error: true);
      }
    } catch (e) {
      _addLog('异常: $e');
      _showMsg('加载失败: $e', error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final content = Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      PageHeader(
        title: '定点配送',
        subTitle: _busy ? '通信中…' : '选择目标快速导航',
        badgeText: widget.carState.taskRunning ? '巡检中' : (_busy ? '通信中' : '待命'),
        badgeActive: widget.carState.taskRunning || _busy,
      ),
      if (_busy)
        const Padding(
          padding: EdgeInsets.only(top: 8),
          child: ClipRRect(
            borderRadius: BorderRadius.all(Radius.circular(999)),
            child: LinearProgressIndicator(minHeight: 3, backgroundColor: Color(0xFF26364A), color: AppTheme.accent),
          ),
        ),
      const SizedBox(height: 20),

      // ═══ 已保存路线 ═══
      _sectionTitle('已保存路线', '从车端加载'),
      const SizedBox(height: 8),
      if (_savedRoutes.isEmpty)
        _emptyCard('暂无已保存路线')
      else
        Wrap(spacing: 8, runSpacing: 8, children: _savedRoutes.map((name) {
          return GestureDetector(
            onTap: () => _loadAndNavigate(name),
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
                const SizedBox(width: 6),
                const Icon(Icons.arrow_forward, size: 14, color: AppTheme.textSecondary),
              ]),
            ),
          );
        }).toList()),
      const SizedBox(height: 18),

      // ═══ 预设点快速导航 ═══
      _sectionTitle('预设目标点', '点击直接导航'),
      const SizedBox(height: 8),
      Wrap(spacing: 8, runSpacing: 8, children: _presets.map((p) {
        final isRoute = p.source == 'route';
        final isSelected = _selected?.name == p.name;
        return GestureDetector(
          onTap: _busy ? null : () => _navigateToPreset(p),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
            decoration: BoxDecoration(
              color: isRoute
                  ? const Color(0xFF1A2535)
                  : (isSelected ? AppTheme.accent.withAlpha(30) : AppTheme.btnSecondaryBg),
              borderRadius: BorderRadius.circular(9),
              border: Border.all(
                color: isRoute ? const Color(0xFF2A3D56) : AppTheme.cardBorder,
              ),
            ),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              if (_busy && isSelected)
                const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.accent))
              else ...[
                if (isRoute)
                  const Text('🔣', style: TextStyle(fontSize: 13))
                else
                  const Icon(Icons.navigation, size: 16, color: AppTheme.accent),
              ],
              const SizedBox(width: 6),
              Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                Text(p.name, style: const TextStyle(color: AppTheme.textPrimary, fontWeight: FontWeight.w700, fontSize: 13)),
                Text('(${p.x.toStringAsFixed(2)}, ${p.y.toStringAsFixed(2)})',
                    style: const TextStyle(color: AppTheme.textSecondary, fontSize: 10)),
              ]),
            ]),
          ),
        );
      }).toList()),

      // ═══ 调试日志 ═══
      const SizedBox(height: 16),
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
            height: 120,
            child: SingleChildScrollView(
              child: SelectableText(
                _logs.reversed.take(40).join('\n'),
                style: const TextStyle(color: AppTheme.cyan, fontSize: 11, fontFamily: 'monospace', height: 1.5),
              ),
            ),
          ),
        ),
    ]);

    return _wrap(context, content);
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
