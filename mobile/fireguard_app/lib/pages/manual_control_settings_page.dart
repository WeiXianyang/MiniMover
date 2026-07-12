import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../models/control_layout.dart';

/// 手动接管布局设置页面
///
/// - 点击组件选中 → 顶部设置栏调整参数
/// - 拖拽移动 · 双指缩放 · 返回=不保存
class ManualControlSettingsPage extends StatefulWidget {
  final ControlLayout originalLayout;
  final ValueChanged<ControlLayout> onSave;

  const ManualControlSettingsPage({
    super.key,
    required this.originalLayout,
    required this.onSave,
  });

  @override
  State<ManualControlSettingsPage> createState() =>
      _ManualControlSettingsPageState();
}

class _ManualControlSettingsPageState
    extends State<ManualControlSettingsPage> {
  late ControlLayout _editLayout;
  ComponentConfig? _selected;

  @override
  void initState() {
    super.initState();
    _editLayout = widget.originalLayout.clone();
  }

  @override
  Widget build(BuildContext context) {
    final c = _selected;
    return Scaffold(
      backgroundColor: const Color(0xFF0A0F18),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0A0F18),
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: AppTheme.textPrimary),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: Text(
          c != null ? c.label : '布局设置',
          style: c != null ? AppTheme.bodyValue : AppTheme.pageTitle,
        ),
      ),
      body: Column(
        children: [
          _buildSettingsPanel(),
          Expanded(
            child: GestureDetector(
              onTap: () => setState(() => _selected = null),
              child: LayoutBuilder(
                builder: (ctx, constraints) {
                  final parent = Size(constraints.maxWidth, constraints.maxHeight);
                  return Stack(
                    children: [
                      CustomPaint(size: parent, painter: _GridPainter()),
                      ..._editLayout.all
                          .where((c) => c.visible)
                          .map((c) => _buildComponent(c, parent)),
                    ],
                  );
                },
              ),
            ),
          ),
        ],
      ),
      bottomNavigationBar: _buildBottomActions(),
    );
  }

  // ═══ 顶部设置面板 ════════════════════════
  Widget _buildSettingsPanel() {
    final c = _selected;
    if (c == null) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        child: const Row(
          children: [
            Icon(Icons.touch_app, color: AppTheme.textSecondary, size: 14),
            SizedBox(width: 8),
            Expanded(
              child: Text('点击选中 · 拖拽移动 · 滑动微调参数',
                  style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
            ),
          ],
        ),
      );
    }

    return Container(
      color: const Color(0xFF111722),
      padding: const EdgeInsets.fromLTRB(16, 6, 16, 10),
      child: Row(
        children: [
          _slider('X', c.x, (v) => setState(() => c.x = v)),
          _slider('Y', c.y, (v) => setState(() => c.y = v)),
          _slider('宽', c.width, (v) => setState(() => c.width = v)),
          _slider('高', c.height, (v) => setState(() => c.height = v)),
          _slider('α', c.opacity, (v) => setState(() => c.opacity = v)),
        ],
      ),
    );
  }

  Widget _slider(String label, double v, ValueChanged<double> cb) {
    return Expanded(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 3),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Text(label, style: const TextStyle(fontSize: 9, color: AppTheme.textSecondary)),
          SizedBox(
            height: 22,
            child: Slider(
              value: v.clamp(0.01, 1.0),
              min: 0.01, max: 1.0,
              activeColor: AppTheme.accent,
              inactiveColor: AppTheme.cardBorder,
              onChanged: cb,
            ),
          ),
        ]),
      ),
    );
  }

  // ═══ 组件（拖拽 + 双指缩放 + 点击选中）══════
  double _lastScale = 1.0;

  /// 根据组件类型计算在设置页中的显示尺寸（匹配实际页面渲染形状）
  Size _displaySize(ComponentConfig c, Size parent) {
    final w = (c.width * parent.width).clamp(20.0, parent.width);
    final h = (c.height * parent.height).clamp(20.0, parent.height);
    switch (c.type) {
      case ControlComponent.moveJoystick:
        // 圆形摇杆 → 正方形
        final s = (w < h ? w : h);
        return Size(s, s);
      case ControlComponent.viewJoystick:
        // 扁椭圆 → 保持矩形比例
        return Size(w, h);
      case ControlComponent.btnLight:
      case ControlComponent.btnMic:
      case ControlComponent.btnRecord:
      case ControlComponent.btnMap:
      case ControlComponent.btnRadar:
        // 方形按钮 → 正方形
        final s = (w < h ? w : h);
        return Size(s, s);
      case ControlComponent.radarOverlay:
        // 雷达小窗 → 正方形（宽当边长）
        final s = w.clamp(80.0, parent.width * 0.5);
        return Size(s, s);
      default:
        return Size(w, h);
    }
  }

  Widget _buildComponent(ComponentConfig c, Size parent) {
    final isSelected = _selected?.type == c.type;
    final pos = Offset(c.x * parent.width, c.y * parent.height);
    final display = _displaySize(c, parent);
    final w = display.width;
    final h = display.height;

    return Positioned(
      left: pos.dx, top: pos.dy,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () => setState(() => _selected = c),
        // 只用 onScaleUpdate，同时处理拖拽和缩放（Flutter ScaleGesture 天然支持单指拖+双指捏）
        onScaleStart: (_) => _lastScale = 1.0,
        onScaleUpdate: (d) => setState(() {
          // 拖拽（单指/双指都生效）
          c.x += d.focalPointDelta.dx / parent.width;
          c.y += d.focalPointDelta.dy / parent.height;
          c.x = c.x.clamp(0.0, (1.0 - c.width).clamp(0.0, 1.0));
          c.y = c.y.clamp(0.0, (1.0 - c.height).clamp(0.0, 1.0));
          // 双指缩放（保持比例）
          final ds = d.scale / _lastScale;
          _lastScale = d.scale;
          c.width = (c.width * ds).clamp(0.02, 1.0);
          c.height = (c.height * ds).clamp(0.02, 1.0);
        }),
        child: Opacity(
          opacity: c.opacity,
          child: Container(
            width: w, height: h,
            decoration: BoxDecoration(
              border: Border.all(
                color: isSelected ? AppTheme.accent : AppTheme.cardBorder,
                width: isSelected ? 2 : 1,
              ),
              borderRadius: BorderRadius.circular(6),
              color: isSelected ? AppTheme.accent.withAlpha(30) : AppTheme.cardFill,
            ),
            child: Center(
              child: Icon(_icon(c.type),
                  size: ((w < h ? w : h) * 0.35).clamp(8.0, 32.0),
                  color: isSelected ? AppTheme.accent : AppTheme.textSecondary),
            ),
          ),
        ),
      ),
    );
  }

  IconData _icon(ControlComponent t) {
    switch (t) {
      case ControlComponent.moveJoystick: return Icons.games;
      case ControlComponent.viewJoystick: return Icons.panorama_horizontal;
      case ControlComponent.btnLight: return Icons.lightbulb_outline;
      case ControlComponent.btnMic: return Icons.mic;
      case ControlComponent.btnRecord: return Icons.fiber_manual_record;
      case ControlComponent.btnMap: return Icons.map_outlined;
      case ControlComponent.btnEmergencyStop: return Icons.warning_amber;
      case ControlComponent.btnSpeed: return Icons.speed;
      case ControlComponent.btnBack: return Icons.arrow_back;
      case ControlComponent.topBar: return Icons.info_outline;
      case ControlComponent.btnRadar: return Icons.radar;
      case ControlComponent.radarOverlay: return Icons.track_changes;
    }
  }

  // ═══ 底部 ═══════════════════════════════
  Widget _buildBottomActions() {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        child: Row(children: [
          Expanded(
            child: GestureDetector(
              onTap: _reset,
              child: Container(
                height: 44,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: AppTheme.statusRed.withAlpha(60)),
                  color: AppTheme.statusRed.withAlpha(20),
                ),
                alignment: Alignment.center,
                child: const Text('重置默认',
                    style: TextStyle(fontWeight: FontWeight.w700, color: AppTheme.statusRed)),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            flex: 2,
            child: GestureDetector(
              onTap: () {
                widget.onSave(_editLayout);
                Navigator.of(context).pop();
              },
              child: Container(
                height: 44,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(10),
                  gradient: const LinearGradient(
                      begin: Alignment.topLeft, end: Alignment.bottomRight,
                      colors: AppTheme.btnGradient),
                ),
                alignment: Alignment.center,
                child: const Text('保存并应用',
                    style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15, color: AppTheme.textDark)),
              ),
            ),
          ),
        ]),
      ),
    );
  }

  void _reset() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF172233),
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: const BorderSide(color: AppTheme.cardBorder)),
        title: const Text('重置布局？', style: AppTheme.pageTitle),
        content: const Text('所有组件将恢复默认位置和大小。', style: AppTheme.bodyLabel),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('取消', style: AppTheme.bodyLabel),
          ),
          TextButton(
            onPressed: () {
              _editLayout.initDefaults();
              setState(() => _selected = null);
              Navigator.of(ctx).pop();
            },
            child: const Text('重置', style: TextStyle(color: AppTheme.statusRed)),
          ),
        ],
      ),
    );
  }
}

class _GridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()
      ..color = const Color.fromRGBO(255, 255, 255, 0.03)
      ..strokeWidth = 0.5;
    for (double x = 0; x <= size.width; x += 40) canvas.drawLine(Offset(x, 0), Offset(x, size.height), p);
    for (double y = 0; y <= size.height; y += 30) canvas.drawLine(Offset(0, y), Offset(size.width, y), p);
  }
  @override
  bool shouldRepaint(covariant CustomPainter o) => false;
}
