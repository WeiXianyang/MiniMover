import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../theme/app_theme.dart';
import '../services/car_state.dart';
import '../services/nav_service.dart';
import '../models/control_layout.dart';
import 'manual_control_settings_page.dart';
import '../widgets/mjpeg_stream.dart';
import '../widgets/app_icons.dart';

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
  ControlLayout _layout = ControlLayout();
  static const _layoutKey = 'fireguard.manualLayout';

  // 摇杆状态
  Offset _moveJoystick = Offset.zero;
  double _viewJoystickX = 0;
  // 开关
  bool _emergencyStopped = false;
  // BGM 播放
  bool _bgmPlaying = false;
  // 人脸识别
  bool _faceRecognizing = false;
  String _faceResult = '';
  // 地图弹窗
  final NavService _navService = NavService();
  bool _showMapOverlay = false;
  Uint8List? _mapImageBytes;
  bool _mapLoading = false;
  // 拍照快照
  Uint8List? _cachedFrame;
  bool _showSnapshot = false;
  double _speed = 0.5;
  int _fps = 0;
  Timer? _fpsTimer;

  @override
  void initState() {
    super.initState();
    _lockLandscape();
    _loadLayout();
    _fpsTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() => _fps = 28 + (DateTime.now().millisecond % 5));
    });
  }

  // ═══ BGM 播放(长按播放，松开暂停) ═══
  Future<void> _playBgm() async {
    if (_bgmPlaying) return;
    final ok = await widget.carState.api.musicPlay();
    if (mounted && ok) {
      setState(() => _bgmPlaying = true);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('BGM 播放中'), duration: Duration(seconds: 1)),
      );
    }
  }

  Future<void> _pauseBgm() async {
    if (!_bgmPlaying) return;
    await widget.carState.api.musicStop();
    if (mounted) setState(() => _bgmPlaying = false);
  }

  // ═══ 人脸识别 ═══
  Future<void> _doFaceRecognition() async {
    if (_cachedFrame == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('视频流未连接，无法识别'), duration: Duration(seconds: 1)),
      );
      return;
    }
    setState(() { _faceRecognizing = true; _faceResult = ''; });
    final result = await widget.carState.api.faceRecognition(_cachedFrame!);
    if (mounted) {
      setState(() => _faceRecognizing = false);
      if (result != null && result['identity'] != null) {
        final name = result['identity'] as String;
        final user = result['user'] as Map<String, dynamic>?;
        final score = user?['score']?.toString() ?? '?';
        _faceResult = '$name ($score分)';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('识别结果: $_faceResult', style: const TextStyle(fontSize: 16)),
            backgroundColor: AppTheme.statusGreen,
            duration: const Duration(seconds: 3),
          ),
        );
      } else {
        _faceResult = result?['msg'] as String? ?? '未识别到人脸';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(_faceResult), duration: const Duration(seconds: 2)),
        );
      }
    }
  }

  Future<void> _loadLayout() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_layoutKey);
    if (raw != null) {
      final json = jsonDecode(raw) as Map<String, dynamic>;
      setState(() => _layout.fromJson(json));
    }
  }

  Future<void> _saveLayout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_layoutKey, jsonEncode(_layout.toJson()));
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
          onSave: (edited) {
            setState(() => _layout.copyFrom(edited));
            _saveLayout();
          },
        ),
      ),
    );
    _lockLandscape();
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
    widget.carState.setSpeed(((dy.abs() > dx.abs() ? dy.abs() : dx.abs()) * _speed * 100).round().clamp(10, 100));
    if (dy.abs() > dx.abs()) { if (dy < -0.3) widget.carState.moveForward(); else if (dy > 0.3) widget.carState.moveBackward(); else widget.carState.stop(); }
    else { if (dx < -0.3) widget.carState.shiftLeft(); else if (dx > 0.3) widget.carState.shiftRight(); else widget.carState.stop(); }
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
  /// 根据电量区间返回对应电池图标
  Widget _batteryIcon(int pct) {
    final icon = pct >= 90 ? Icons.battery_full
        : pct >= 60 ? Icons.battery_5_bar
        : pct >= 30 ? Icons.battery_3_bar
        : Icons.battery_1_bar;
    final color = pct >= 30 ? AppTheme.statusGreen
        : pct >= 15 ? AppTheme.accent
        : AppTheme.statusRed;
    return Icon(icon, size: 14, color: color);
  }

  void _cycleSpeed() {
    setState(() {
      final speeds = [0.25, 0.50, 0.75, 1.0];
      final idx = speeds.indexOf(_speed);
      _speed = speeds[(idx + 1) % speeds.length];
    });
  }

  // ═══ TTS 文字播报（点击按钮弹窗输入） ═══
  void _showTtsDialog() {
    final ctrl = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF172233),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppTheme.cardBorder),
        ),
        title: const Text('语音播报', style: AppTheme.pageTitle),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          maxLines: 3,
          style: const TextStyle(color: AppTheme.textPrimary, fontSize: 15),
          decoration: InputDecoration(
            hintText: '输入要播报的文字…',
            hintStyle: const TextStyle(color: AppTheme.textSecondary, fontSize: 14),
            filled: true,
            fillColor: const Color(0xFF0C1520),
            contentPadding: const EdgeInsets.all(14),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: AppTheme.cardBorder),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: AppTheme.cardBorder),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: AppTheme.accent),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('取消', style: TextStyle(color: AppTheme.textSecondary)),
          ),
          TextButton(
            onPressed: () {
              final text = ctrl.text.trim();
              if (text.isNotEmpty) widget.carState.ttsSay(text);
              Navigator.of(ctx).pop();
            },
            child: const Text('播报', style: TextStyle(color: AppTheme.accent, fontWeight: FontWeight.w700)),
          ),
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════
  // 地图弹窗
  // ═══════════════════════════════════════════
  void _openMapOverlay() async {
    setState(() { _showMapOverlay = true; _mapLoading = true; _mapImageBytes = null; });
    _navService.updateConfig(widget.carState.host);
    final img = await _navService.fetchMapImage();
    if (mounted) setState(() { _mapImageBytes = img != null ? Uint8List.fromList(img) : null; _mapLoading = false; });
  }

  void _closeMapOverlay() {
    setState(() => _showMapOverlay = false);
  }

  Widget _buildSnapshotOverlay() {
    return GestureDetector(
      onTap: () => setState(() => _showSnapshot = false),
      child: Container(
        color: const Color.fromRGBO(0, 0, 0, 0.88),
        width: double.infinity,
        height: double.infinity,
        child: Stack(
          children: [
            Center(
              child: InteractiveViewer(
                minScale: 0.5,
                maxScale: 4.0,
                child: Image.memory(_cachedFrame!, fit: BoxFit.contain),
              ),
            ),
            // 关闭按钮
            Positioned(
              top: 16, right: 16,
              child: GestureDetector(
                onTap: () => setState(() => _showSnapshot = false),
                child: Container(
                  width: 36, height: 36,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: const Color.fromRGBO(0, 0, 0, 0.6),
                    border: Border.all(color: const Color.fromRGBO(255, 255, 255, 0.2)),
                  ),
                  child: const Icon(Icons.close, size: 18, color: Colors.white),
                ),
              ),
            ),
            // 顶部标签
            Positioned(
              top: 20, left: 0, right: 0,
              child: Center(
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  const Icon(Icons.camera_alt, size: 14, color: AppTheme.accent),
                  const SizedBox(width: 6),
                  const Text('快照', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
                ]),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMapOverlay() {
    return GestureDetector(
      onTap: _closeMapOverlay,
      child: Container(
        color: const Color.fromRGBO(0, 0, 0, 0.85),
        width: double.infinity,
        height: double.infinity,
        child: Stack(
          children: [
            Center(
              child: _mapLoading
                  ? const Column(mainAxisSize: MainAxisSize.min, children: [
                      CircularProgressIndicator(strokeWidth: 2, color: AppTheme.accent),
                      SizedBox(height: 12),
                      Text('加载地图…', style: TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
                    ])
                  : _mapImageBytes != null
                      ? InteractiveViewer(
                          minScale: 0.5,
                          maxScale: 4.0,
                          child: Image.memory(_mapImageBytes!, fit: BoxFit.contain),
                        )
                      : const Column(mainAxisSize: MainAxisSize.min, children: [
                          Icon(Icons.error_outline, size: 48, color: AppTheme.textSecondary),
                          SizedBox(height: 8),
                          Text('地图不可用', style: TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
                        ]),
            ),
            // 关闭按钮
            Positioned(
              top: 16, right: 16,
              child: GestureDetector(
                onTap: _closeMapOverlay,
                child: Container(
                  width: 36, height: 36,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: const Color.fromRGBO(0, 0, 0, 0.6),
                    border: Border.all(color: const Color.fromRGBO(255, 255, 255, 0.2)),
                  ),
                  child: const Icon(Icons.close, size: 18, color: Colors.white),
                ),
              ),
            ),
            // 顶部标签
            const Positioned(
              top: 20, left: 0, right: 0,
              child: Center(
                child: Text('地图', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
              ),
            ),
          ],
        ),
      ),
    );
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
                Container(color: const Color.fromRGBO(0, 0, 0, 0.0)),
                // 顶部状态栏
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
                // 地图弹窗
                if (_showMapOverlay)
                  _buildMapOverlay(),
                // 拍照快照
                if (_showSnapshot && _cachedFrame != null)
                  _buildSnapshotOverlay(),
                // BGM / 人脸识别状态指示
                if (_bgmPlaying || _faceRecognizing || _faceResult.isNotEmpty)
                  Positioned(
                    top: 60, left: 0, right: 0,
                    child: Center(
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                        decoration: BoxDecoration(
                          color: const Color.fromRGBO(0, 0, 0, 0.75),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(color: _bgmPlaying ? AppTheme.statusGreen : AppTheme.accent, width: 1.5),
                        ),
                        child: Row(mainAxisSize: MainAxisSize.min, children: [
                          if (_faceRecognizing)
                            const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.accent))
                          else if (_bgmPlaying)
                            const Icon(Icons.music_note, size: 16, color: AppTheme.statusGreen)
                          else
                            const Icon(Icons.face, size: 16, color: AppTheme.accent),
                          const SizedBox(width: 8),
                          Text(
                            _faceRecognizing ? '识别中…' : (_bgmPlaying ? 'BGM 播放中' : _faceResult),
                            style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: _bgmPlaying ? AppTheme.statusGreen : AppTheme.accent),
                          ),
                        ]),
                      ),
                    ),
                  ),
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
    return Positioned.fill(
      child: MjpegStream(
              host: widget.carState.host,
              width: size.width,
              height: size.height,
              placeholder: (ctx) => _buildVideoFallback(size),
              errorBuilder: (ctx) => _buildVideoFallback(size),
              onFrame: (f) => _cachedFrame = f,
            )
    );
  }

  Widget _buildVideoFallback(Size size, [String? msg]) {
    return Center(
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.videocam, color: Color.fromRGBO(255, 255, 255, 0.18), size: 60),
        const SizedBox(height: 8),
        Text(msg ?? "视频未连接", style: const TextStyle(color: Color(0xFF9AA8BF), fontSize: 12)),
      ]),
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
              _batteryIcon(widget.carState.batteryPercent),
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
                  child: AppIcons.settings(size: 14, color: AppTheme.textSecondary),
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
        _sideBtnItem(_layout.btnLight, parent,
            AppIcons.lightbulb(size: 18, color: AppTheme.textSecondary),
            AppTheme.textSecondary, () {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("灯光仅 TCP 6000 通道可用"), duration: Duration(seconds: 1)));
        }),
        _sideBtnItem(_layout.btnMic, parent,
            AppIcons.mic(size: 18, color: _bgmPlaying ? AppTheme.statusGreen : AppTheme.textPrimary),
            _bgmPlaying ? AppTheme.statusGreen : AppTheme.textPrimary,
            _showTtsDialog,
            onLongPressStart: (_) => _playBgm(),
            onLongPressEnd: (_) => _pauseBgm(),
            onLongPressCancel: _pauseBgm,
          ),
        _sideBtnItem(
            _layout.btnRecord, parent,
            AppIcons.camera(size: 18, color: _cachedFrame != null ? AppTheme.textPrimary : AppTheme.textSecondary),
            _cachedFrame != null ? AppTheme.textPrimary : AppTheme.textSecondary, () {
          if (_cachedFrame != null) {
            setState(() => _showSnapshot = true);
          } else {
            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('视频流未连接，无法拍照'), duration: Duration(seconds: 1)));
          }
        }),
        _sideBtnItem(_layout.btnMap, parent,
            AppIcons.map(size: 18, color: AppTheme.textPrimary),
            AppTheme.textPrimary, _openMapOverlay),
        _sideBtnItem(_layout.btnRadar, parent,
            Icon(Icons.face, size: 18,
                color: _faceRecognizing ? AppTheme.accent : AppTheme.textPrimary),
            _faceRecognizing ? AppTheme.accent : AppTheme.textPrimary,
            () => _doFaceRecognition()),
        const SizedBox(),
      ],
    );
  }

  Widget _sideBtnItem(ComponentConfig cfg, Size parent, Widget icon,
      Color color, VoidCallback onTap,
      {VoidCallback? onLongPress,
       GestureLongPressStartCallback? onLongPressStart,
       GestureLongPressEndCallback? onLongPressEnd,
       GestureLongPressUpCallback? onLongPressUp,
       VoidCallback? onLongPressCancel}) {
    final sz = cfg.toSize(parent);
    final offset = cfg.toOffset(parent);
    if (!cfg.visible) return const SizedBox.shrink();

    final useLongPressDetail = onLongPressStart != null;

    // 当同时有 onTap 和 onLongPressStart 时，不用 GestureDetector 内置的 onTap
    // （会和 long press recognizer 冲突导致 tap 不触发），
    // 改为用 onTapDown/onTapUp + flag 手动判断短按 vs 长按
    return Positioned(
      left: offset.dx,
      top: offset.dy,
      child: Opacity(
        opacity: cfg.opacity,
        child: StatefulBuilder(
          builder: (ctx, setLocal) {
            bool inLongPress = false;
            return GestureDetector(
              onTap: useLongPressDetail ? null : onTap,
              onTapDown: useLongPressDetail ? (_) => inLongPress = false : null,
              onTapUp: useLongPressDetail ? (_) { if (!inLongPress) onTap(); } : null,
              onLongPress: useLongPressDetail ? null : onLongPress,
              onLongPressStart: useLongPressDetail
                  ? (d) { inLongPress = true; onLongPressStart(d); }
                  : null,
              onLongPressEnd: useLongPressDetail && onLongPressEnd != null
                  ? (d) { onLongPressEnd(d); inLongPress = false; }
                  : null,
              onLongPressUp: onLongPressUp != null
                  ? () { onLongPressUp(); }
                  : null,
              onLongPressCancel: useLongPressDetail
                  ? () { onLongPressCancel?.call(); inLongPress = false; }
                  : null,
              child: Container(
                width: sz.width,
                height: sz.height,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(sz.width * 0.28),
                  color: const Color.fromRGBO(0, 0, 0, 0.4),
                  border:
                      Border.all(color: const Color.fromRGBO(255, 255, 255, 0.10)),
                ),
                child: Center(child: icon),
              ),
            );
          },
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
          _bottomBtn(_layout.btnBack, parent,
              AppIcons.arrowLeft(size: 16, color: AppTheme.textSecondary), '返回', () {
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
          _bottomBtn(_layout.btnSpeed, parent,
              const Icon(Icons.speed, size: 16, color: AppTheme.accent),
              '${(_speed * 100).round()}%', _cycleSpeed,
              accent: true),
      ],
    );
  }

  Widget _bottomBtn(ComponentConfig cfg, Size parent, Widget icon,
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
                  icon,
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
