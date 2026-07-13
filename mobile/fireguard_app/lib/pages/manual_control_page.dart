import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/app_theme.dart';
import '../services/car_state.dart';
import '../models/control_layout.dart';
import 'manual_control_settings_page.dart';
import '../widgets/mjpeg_stream.dart';

/// S06 - 手动接管（横屏游戏风格）
/// 所有组件位置/大小/透明度由 ControlLayout 驱动，可进入设置页拖拽调整
class ManualControlPage extends StatefulWidget {
  final CarState carState;
  final bool embedded;
  const ManualControlPage({
    super.key,
    required this.carState,
    this.embedded = false,
  });

  @override
  State<ManualControlPage> createState() => _ManualControlPageState();
}

class _ManualControlPageState extends State<ManualControlPage> {
  final ControlLayout _layout = ControlLayout();

  // 摇杆状态
  Offset _moveJoystick = Offset.zero;
  double _viewJoystickX = 0;
  // 开关
  bool _lightOn = false;
  bool _micOn = false;
  bool _recording = false;
  bool _emergencyStopped = false;
  bool _radarOn = false;
  double _speed = 0.5;
  int _fps = 0;
  Timer? _fpsTimer;

  @override
  void initState() {
    super.initState();
    _lockLandscape();
    _fpsTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() => _fps = 28 + (DateTime.now().millisecond % 5));
    });
  }

  @override
  void dispose() {
    _fpsTimer?.cancel();
    _restoreOrientation();
    super.dispose();
  }

  void _lockLandscape() {
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
  }

  void _restoreOrientation() {
    SystemChrome.setPreferredOrientations(DeviceOrientation.values);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  }

  void _openSettings() async {
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ManualControlSettingsPage(
          originalLayout: _layout,
          onSave: (edited) => setState(() => _layout.copyFrom(edited)),
        ),
      ),
    );
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
  }

  DateTime _lastSend = DateTime.now();
  final _throttle = const Duration(milliseconds: 200);

  // ── 摇杆回调（HTTP 方向指令） ──────────
  void _onMoveUpdate(Offset local, Size size) {
    final dx = (local.dx / (size.width / 2) - 1).clamp(-1.0, 1.0);
    final dy = (local.dy / (size.height / 2) - 1).clamp(-1.0, 1.0);
    setState(() => _moveJoystick = Offset(dx, dy));
    if (_emergencyStopped) return;
    final now = DateTime.now();
    if (now.difference(_lastSend) < _throttle) return;
    _lastSend = now;
    widget.carState.setSpeed((dy.abs() > dx.abs() ? dy.abs() : dx.abs() * _speed * 100).round().clamp(10, 100));
    if (dy.abs() > dx.abs()) { if (dy < -0.3) widget.carState.moveForward(); else if (dy > 0.3) widget.carState.moveBackward(); else widget.carState.stop(); }
    else { if (dx < -0.3) widget.carState.moveLeft(); else if (dx > 0.3) widget.carState.moveRight(); else widget.carState.stop(); }
  }
  void _onMoveEnd() {
    setState(() => _moveJoystick = Offset.zero);
    if (!_emergencyStopped) widget.carState.stop();
  }
  void _onViewUpdate(Offset local, Size size) {
    final dx = (local.dx / (size.width / 2) - 1).clamp(-1.0, 1.0);
    setState(() => _viewJoystickX = dx);
    if (_emergencyStopped) return;
    final now = DateTime.now();
    if (now.difference(_lastSend) < _throttle) return;
    _lastSend = now;
    if (dx > 0.3) widget.carState.moveRight(); else if (dx < -0.3) widget.carState.moveLeft(); else widget.carState.stop();
  }
  void _onViewEnd() { setState(() => _viewJoystickX = 0); if (!_emergencyStopped) widget.carState.stop(); }
  void _emergencyStop() { setState(() => _emergencyStopped = !_emergencyStopped); widget.carState.emergencyStop(); }

  // ═══════════════════════════════════════════
  // 雷达小窗
  // ═══════════════════════════════════════════
  Widget _buildRadarOverlay(Size parent) {
    final cfg = _layout.radarOverlay;
    final sz = cfg.toSize(parent);
    final pos = cfg.toOffset(parent);
    // 用小窗宽度做方形边长
    final side = sz.width.clamp(80.0, parent.width * 0.5);

    return Positioned(
      left: pos.dx,
      top: pos.dy,
      child: Opacity(
        opacity: cfg.opacity,
        child: GestureDetector(
          onTap: () => setState(() => _radarOn = false),
          child: Container(
            width: side,
            height: side,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: const Color.fromRGBO(0, 0, 0, 0.55),
              border: Border.all(
                  color: AppTheme.statusGreen.withAlpha(100), width: 1.5),
              boxShadow: [
                BoxShadow(
                    color: AppTheme.statusGreen.withAlpha(60),
                    blurRadius: 12),
              ],
            ),
            child: ClipOval(
              child: CustomPaint(painter: _RadarPainter()),
            ),
          ),
        ),
      ),
    );
  }

  void _cycleSpeed() {
    setState(() {
      final speeds = [0.25, 0.50, 0.75, 1.0];
      final idx = speeds.indexOf(_speed);
      _speed = speeds[(idx + 1) % speeds.length];
    });
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: true,
      onPopInvokedWithResult: (didPop, _) {
        if (didPop) _restoreOrientation();
      },
      child: Scaffold(
        backgroundColor: Colors.black,
        body: LayoutBuilder(
          builder: (ctx, constraints) {
            final parent = Size(constraints.maxWidth, constraints.maxHeight);
            return Stack(
              children: [
                _buildVideoBackground(parent),
                Container(color: const Color.fromRGBO(0, 0, 0, 0.35)),
                // 顶部栏
                if (_layout.topBar.visible)
                  _pos(_layout.topBar, parent, _buildTopBar()),
                // 左摇杆
                if (_layout.moveJoystick.visible)
                  _pos(_layout.moveJoystick, parent,
                      _buildMoveJoystick(parent)),
                // 右摇杆
                if (_layout.viewJoystick.visible)
                  _pos(_layout.viewJoystick, parent,
                      _buildViewJoystick(parent)),
                // 侧边按钮
                Positioned.fill(child: _buildSideButtons(parent)),
                // 底部控制
                Positioned.fill(child: _buildBottomBar(parent)),
                // 雷达小窗
                if (_radarOn) _buildRadarOverlay(parent),
              ],
            );
          },
        ),
      ),
    );
  }

  // ── Component positioning helper ────────
  Widget _pos(ComponentConfig c, Size parent, Widget w) {
    final size = c.toSize(parent);
    final offset = c.toOffset(parent);
    return Positioned(
      left: offset.dx,
      top: offset.dy,
      width: size.width,
      height: size.height,
      child: Opacity(opacity: c.opacity, child: w),
    );
  }

  // ═══════════════════════════════════════════
  // 视频背景
  // ═══════════════════════════════════════════
  Widget _buildVideoBackground(Size size) {
    final connected = widget.carState.connected;
    return Positioned.fill(
      child: connected
          ? MjpegStream(
              host: widget.carState.host,
              port: widget.carState.port,
              width: size.width,
              height: size.height,
              placeholder: (ctx) => _buildVideoFallback(size),
              errorBuilder: (ctx) => _buildVideoFallback(size),
            )
          : _buildVideoFallback(size),
    );
  }

  Widget _buildVideoFallback(Size size) {
    return CustomPaint(
      size: size,
      painter: _RoadPainter(),
      child: const Center(
        child: Icon(Icons.videocam,
            color: Color.fromRGBO(255, 255, 255, 0.06), size: 80),
      ),
    );
  }

  // ═══════════════════════════════════════════
  // 顶部信息栏
  // ═══════════════════════════════════════════
  Widget _buildTopBar() {
    return SafeArea(
      bottom: false,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            _topBadge(Row(mainAxisSize: MainAxisSize.min, children: [
              Container(
                  width: 6,
                  height: 6,
                  decoration: const BoxDecoration(
                      color: AppTheme.statusGreen, shape: BoxShape.circle)),
              const SizedBox(width: 6),
              const Text('接管中',
                  style: TextStyle(
                      fontWeight: FontWeight.w700,
                      fontSize: 12,
                      color: AppTheme.statusGreen)),
              const SizedBox(width: 10),
              Text('|  ${widget.carState.batteryPercent}%',
                  style: const TextStyle(
                      fontWeight: FontWeight.w400,
                      fontSize: 11,
                      color: AppTheme.textSecondary)),
              const Text(' 🔋', style: TextStyle(fontSize: 12)),
            ])),
            Row(mainAxisSize: MainAxisSize.min, children: [
              // 设置按钮
              GestureDetector(
                onTap: _openSettings,
                child: Container(
                  padding: const EdgeInsets.all(4),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: AppTheme.cardFill.withAlpha(150),
                    border:
                        Border.all(color: AppTheme.cardBorder),
                  ),
                  child: const Icon(Icons.settings, size: 14, color: AppTheme.textSecondary),
                ),
              ),
              const SizedBox(width: 8),
              _topBadge(Row(mainAxisSize: MainAxisSize.min, children: [
                Text('$_fps FPS',
                    style: const TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 12,
                        color: AppTheme.statusGreen)),
                const SizedBox(width: 8),
                const Text('|',
                    style: TextStyle(
                        color: AppTheme.textSecondary, fontSize: 11)),
                const SizedBox(width: 8),
                const Text('●●●●○',
                    style: TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 12,
                        color: AppTheme.textPrimary)),
              ])),
            ]),
          ],
        ),
      ),
    );
  }

  Widget _topBadge(Widget child) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: const Color.fromRGBO(0, 0, 0, 0.5),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color.fromRGBO(255, 255, 255, 0.08)),
      ),
      child: child,
    );
  }

  // ═══════════════════════════════════════════
  // 左摇杆
  // ═══════════════════════════════════════════
  Widget _buildMoveJoystick(Size parent) {
    final cfg = _layout.moveJoystick;
    final sz = cfg.toSize(parent);
    final radius = sz.width / 2;
    final knobR = radius * 0.42;
    final labelOffset = radius * 0.75;

    return GestureDetector(
      onPanUpdate: (d) =>
          _onMoveUpdate(d.localPosition, Size(sz.width, sz.height)),
      onPanEnd: (_) => _onMoveEnd(),
      onPanCancel: _onMoveEnd,
      child: Stack(
        alignment: Alignment.center,
        children: [
          Container(
            width: sz.width,
            height: sz.height,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: const Color.fromRGBO(0, 0, 0, 0.45),
              border: Border.all(
                  color: const Color.fromRGBO(255, 255, 255, 0.15), width: 2),
            ),
          ),
          // 十字线
          ...[-radius / 3, 0, radius / 3].map((y) => Positioned(
                top: (radius + y - 0.5),
                left: radius / 4,
                right: radius / 4,
                child: Container(
                    height: 1,
                    color: const Color.fromRGBO(255, 255, 255, 0.06)),
              )),
          ...[-radius / 3, 0, radius / 3].map((x) => Positioned(
                left: (radius + x - 0.5),
                top: radius / 4,
                bottom: radius / 4,
                child: Container(
                    width: 1,
                    color: const Color.fromRGBO(255, 255, 255, 0.06)),
              )),
          // 标签
          _joyLabel('前', radius, labelOffset - radius, Alignment.topCenter),
          _joyLabel('后', radius, radius + labelOffset, Alignment.bottomCenter),
          _joyLabel('左', -labelOffset + radius, radius, Alignment.centerLeft),
          _joyLabel(
              '右', labelOffset + radius, radius, Alignment.centerRight),
          // 旋钮
          Transform.translate(
            offset: Offset(_moveJoystick.dx * (radius - knobR - 4),
                _moveJoystick.dy * (radius - knobR - 4)),
            child: Container(
              width: knobR * 2,
              height: knobR * 2,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: const LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: AppTheme.btnGradient,
                ),
                boxShadow: [
                  BoxShadow(
                      color: AppTheme.accent.withAlpha(100),
                      blurRadius: radius * 0.2,
                      spreadRadius: 2),
                ],
              ),
              child: Center(
                child: Container(
                  width: knobR * 0.85,
                  height: knobR * 0.85,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: const Color.fromRGBO(255, 255, 255, 0.15),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _joyLabel(String text, double left, double top, Alignment align) {
    return Positioned(
      left: align == Alignment.centerLeft
          ? 12
          : (align == Alignment.centerRight ? null : null),
      right: align == Alignment.centerRight ? 12 : null,
      top: align == Alignment.topCenter
          ? 14
          : (align == Alignment.bottomCenter ? null : null),
      bottom: align == Alignment.bottomCenter ? 14 : null,
      child: Text(text,
          style: const TextStyle(
              fontSize: 9,
              color: Color.fromRGBO(255, 255, 255, 0.2),
              fontWeight: FontWeight.w700)),
    );
  }

  // ═══════════════════════════════════════════
  // 右摇杆
  // ═══════════════════════════════════════════
  Widget _buildViewJoystick(Size parent) {
    final cfg = _layout.viewJoystick;
    final sz = cfg.toSize(parent);
    final knobR = sz.height * 0.35;

    return GestureDetector(
      onPanUpdate: (d) =>
          _onViewUpdate(d.localPosition, Size(sz.width, sz.height)),
      onPanEnd: (_) => _onViewEnd(),
      onPanCancel: _onViewEnd,
      child: Stack(
        alignment: Alignment.center,
        children: [
          Container(
            width: sz.width,
            height: sz.height,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(sz.height / 2),
              color: const Color.fromRGBO(0, 0, 0, 0.45),
              border: Border.all(
                  color: const Color.fromRGBO(255, 255, 255, 0.15), width: 2),
            ),
          ),
          Container(
              width: sz.width * 0.85,
              height: 1,
              color: const Color.fromRGBO(255, 255, 255, 0.06)),
          const Positioned(
            left: 4,
            child: Text('◀',
                style: TextStyle(
                    fontSize: 9,
                    color: Color.fromRGBO(255, 255, 255, 0.2))),
          ),
          const Positioned(
            right: 4,
            child: Text('▶',
                style: TextStyle(
                    fontSize: 9,
                    color: Color.fromRGBO(255, 255, 255, 0.2))),
          ),
          Transform.translate(
            offset: Offset(_viewJoystickX * (sz.width / 2 - knobR - 4), 0),
            child: Container(
              width: knobR * 2,
              height: knobR * 2,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: const LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: AppTheme.btnGradient,
                ),
                boxShadow: [
                  BoxShadow(
                      color: AppTheme.accent.withAlpha(100),
                      blurRadius: 10,
                      spreadRadius: 2),
                ],
              ),
              child: Center(
                child: Container(
                  width: knobR * 0.8,
                  height: knobR * 0.8,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: const Color.fromRGBO(255, 255, 255, 0.15),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════
  // 侧边按钮
  // ═══════════════════════════════════════════
  Widget _buildSideButtons(Size parent) {
    return Stack(
      children: [
        _sideBtnItem(_layout.btnLight, parent, Icons.lightbulb_outline,
            _lightOn ? AppTheme.accent : AppTheme.textPrimary, () {
          setState(() => _lightOn = !_lightOn);
          // 灯带（API 暂不支持，仅本地切换）
        }),
        _sideBtnItem(_layout.btnMic, parent, Icons.mic,
            _micOn ? AppTheme.statusGreen : AppTheme.textPrimary, () {
          setState(() => _micOn = !_micOn);
        }),
        _sideBtnItem(
            _layout.btnRecord,
            parent,
            Icons.fiber_manual_record,
            _recording ? AppTheme.statusRed : AppTheme.textPrimary, () {
          setState(() => _recording = !_recording);
        }),
        _sideBtnItem(_layout.btnMap, parent, Icons.map_outlined,
            AppTheme.textPrimary, () {}),
        _sideBtnItem(_layout.btnRadar, parent, Icons.radar,
            _radarOn ? AppTheme.statusGreen : AppTheme.textPrimary, () {
          setState(() => _radarOn = !_radarOn);
        }),
      ],
    );
  }

  Widget _sideBtnItem(ComponentConfig cfg, Size parent, IconData icon,
      Color color, VoidCallback onTap) {
    final sz = cfg.toSize(parent);
    final offset = cfg.toOffset(parent);
    if (!cfg.visible) return const SizedBox.shrink();

    return Positioned(
      left: offset.dx,
      top: offset.dy,
      child: Opacity(
        opacity: cfg.opacity,
        child: GestureDetector(
          onTap: onTap,
          child: Container(
            width: sz.width,
            height: sz.height,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(sz.width * 0.28),
              color: const Color.fromRGBO(0, 0, 0, 0.4),
              border:
                  Border.all(color: const Color.fromRGBO(255, 255, 255, 0.10)),
            ),
            child: Center(
              child: Icon(icon, color: color, size: sz.shortestSide * 0.4),
            ),
          ),
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════
  // 底部控制
  // ═══════════════════════════════════════════
  Widget _buildBottomBar(Size parent) {
    return Stack(
      children: [
        // 返回
        if (_layout.btnBack.visible)
          _bottomBtn(_layout.btnBack, parent, Icons.arrow_back, '返回', () {
            Navigator.of(context).pop();
          }),
        // 急停
        if (_layout.btnEmergencyStop.visible)
          _bottomBtnLarge(
              _layout.btnEmergencyStop, parent, _emergencyStopped ? '已急停' : '⚠ 急停',
              _emergencyStopped ? AppTheme.statusGreen : AppTheme.statusRed, () {
            _emergencyStop();
          }),
        // 速度
        if (_layout.btnSpeed.visible)
          _bottomBtn(_layout.btnSpeed, parent, Icons.speed,
              '${(_speed * 100).round()}%', _cycleSpeed,
              accent: true),
      ],
    );
  }

  Widget _bottomBtn(ComponentConfig cfg, Size parent, IconData icon,
      String label, VoidCallback onTap,
      {bool accent = false}) {
    final sz = cfg.toSize(parent);
    final offset = cfg.toOffset(parent);

    return Positioned(
      left: offset.dx,
      top: offset.dy,
      width: sz.width,
      height: sz.height,
      child: Opacity(
        opacity: cfg.opacity,
        child: GestureDetector(
          onTap: onTap,
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(sz.width * 0.25),
              color: const Color.fromRGBO(0, 0, 0, 0.45),
              border:
                  Border.all(color: const Color.fromRGBO(255, 255, 255, 0.08)),
            ),
            alignment: Alignment.center,
            child: FittedBox(
              fit: BoxFit.scaleDown,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(icon,
                      size: sz.height * 0.45,
                      color: accent ? AppTheme.accent : AppTheme.textSecondary),
                  const SizedBox(width: 4),
                  Text(label,
                      style: TextStyle(
                          fontWeight: FontWeight.w700,
                          fontSize: sz.height * 0.35,
                          color:
                              accent ? AppTheme.accent : AppTheme.textSecondary)),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _bottomBtnLarge(ComponentConfig cfg, Size parent, String label,
      Color color, VoidCallback onTap) {
    final sz = cfg.toSize(parent);
    final offset = cfg.toOffset(parent);

    return Positioned(
      left: offset.dx,
      top: offset.dy,
      width: sz.width,
      height: sz.height,
      child: Opacity(
        opacity: cfg.opacity,
        child: GestureDetector(
          onTap: onTap,
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(sz.height / 2),
              color: color.withAlpha(30),
              border: Border.all(color: color, width: 2),
              boxShadow: [BoxShadow(color: color.withAlpha(120), blurRadius: 16)],
            ),
            alignment: Alignment.center,
            child: Text(label,
                style: TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 16,
                    color: color)),
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 雷达绘制
// ═══════════════════════════════════════════
class _RadarPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 2;

    // 同心圆
    for (int i = 1; i <= 4; i++) {
      final r = radius * i / 4;
      canvas.drawCircle(
        center,
        r,
        Paint()
          ..color = AppTheme.statusGreen.withAlpha(20)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 0.5,
      );
    }

    // 十字线
    canvas.drawLine(
        Offset(center.dx - radius, center.dy),
        Offset(center.dx + radius, center.dy),
        Paint()
          ..color = AppTheme.statusGreen.withAlpha(20)
          ..strokeWidth = 0.5);
    canvas.drawLine(
        Offset(center.dx, center.dy - radius),
        Offset(center.dx, center.dy + radius),
        Paint()
          ..color = AppTheme.statusGreen.withAlpha(20)
          ..strokeWidth = 0.5);

    // 模拟障碍点
    final points = [
      Offset(0.4, 0.2),
      Offset(-0.35, 0.45),
      Offset(0.5, -0.15),
      Offset(-0.2, -0.5),
      Offset(0.6, 0.35),
    ];
    for (final p in points) {
      final px = center.dx + p.dx * radius;
      final py = center.dy + p.dy * radius;
      canvas.drawCircle(
        Offset(px, py),
        3,
        Paint()..color = AppTheme.statusGreen.withAlpha(160),
      );
    }

    // 圆心
    canvas.drawCircle(
        center, 4, Paint()..color = AppTheme.statusGreen.withAlpha(220));
    canvas.drawCircle(center, 2, Paint()..color = AppTheme.statusGreen);

    // 标签
    final tp = TextPainter(
      text: const TextSpan(
        text: 'LiDAR',
        style: TextStyle(
            color: AppTheme.statusGreen,
            fontSize: 9,
            fontWeight: FontWeight.w700),
      ),
      textDirection: TextDirection.ltr,
    );
    tp.layout();
    tp.paint(canvas, Offset(center.dx - tp.width / 2, center.dy + 8));
  }

  @override
  bool shouldRepaint(covariant CustomPainter o) => false;
}

// ═══════════════════════════════════════════
// 道路背景绘制
// ═══════════════════════════════════════════
class _RoadPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final groundPaint = Paint()..color = const Color(0xFF151D28);
    canvas.drawRect(
        Rect.fromLTWH(0, size.height * 0.5, size.width, size.height * 0.5),
        groundPaint);

    const vpX = 438.0;
    const vpY = 160.0;
    final linePaint = Paint()
      ..color = const Color.fromRGBO(255, 140, 66, 0.08)
      ..strokeWidth = 1;
    final totalLines = 9;
    for (int i = 0; i < totalLines; i++) {
      final t = (i / (totalLines - 1));
      final startX = size.width * t;
      final endX = (vpX + (startX - vpX) * 2.5).clamp(0.0, size.width);
      canvas.drawLine(
          Offset(startX, vpY * 1.6), Offset(endX, size.height), linePaint);
    }

    final dashPaint = Paint()
      ..color = const Color.fromRGBO(255, 255, 255, 0.04)
      ..strokeWidth = 1.5;
    for (double x = 0; x < size.width; x += 55) {
      canvas.drawLine(
          Offset(x, size.height * 0.78),
          Offset((x + 30).clamp(0, size.width), size.height * 0.78),
          dashPaint);
      canvas.drawLine(
          Offset(x, size.height * 0.92),
          Offset((x + 30).clamp(0, size.width), size.height * 0.92),
          dashPaint);
    }

    final edgePaint = Paint()
      ..color = const Color.fromRGBO(255, 255, 255, 0.06)
      ..strokeWidth = 2;
    canvas.drawLine(Offset(0, size.height * 0.65),
        Offset(size.width, size.height * 0.65), edgePaint);

    final obsRect = RRect.fromRectAndRadius(
        Rect.fromLTWH(size.width * 0.68, size.height * 0.72, 60, 40),
        const Radius.circular(4));
    canvas.drawRRect(obsRect,
        Paint()..color = const Color.fromRGBO(255, 255, 255, 0.05));
    canvas.drawRRect(
        obsRect,
        Paint()
          ..color = const Color.fromRGBO(255, 255, 255, 0.08)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
