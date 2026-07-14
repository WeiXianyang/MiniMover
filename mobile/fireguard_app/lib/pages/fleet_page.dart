import 'dart:async';
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../models/fleet_info.dart';
import '../services/fleet_service.dart';
import '../services/car_state.dart';
import '../widgets/common_widgets.dart';
import '../widgets/app_icons.dart';

/// S08 — 车队编队页面（对接多车协同调度中心 :8888）
class FleetPage extends StatefulWidget {
  final FleetService fleetService;
  final CarState carState;
  final bool embedded;
  const FleetPage({
    super.key,
    required this.fleetService,
    required this.carState,
    this.embedded = false,
  });

  @override
  State<FleetPage> createState() => _FleetPageState();
}

class _FleetPageState extends State<FleetPage> {
  FleetState _fleet = const FleetState();
  StreamSubscription<FleetState>? _sub;

  // ── 协调器连接输入 ──
  final _hostCtrl = TextEditingController(text: '192.168.137.1');
  final _portCtrl = TextEditingController(text: '8888');

  // ── 运动参数 ──
  int _speed = 50;
  double _duration = 0.5;

  // ── 队形参数 ──
  String _formationType = 'line';
  double _formationSpacing = 2.0;

  // ── 新增车辆输入 ──
  final _regIdCtrl = TextEditingController(text: 'car_C');
  final _regIpCtrl = TextEditingController(text: '192.168.1.100');
  final _regPortCtrl = TextEditingController(text: '5000');

  // ── 展示轮询 ──
  Timer? _demoPollTimer;
  bool _connecting = false;

  @override
  void initState() {
    super.initState();
    _sub = widget.fleetService.stateStream.listen((s) {
      if (mounted) setState(() => _fleet = s);
    });
  }

  @override
  void dispose() {
    _sub?.cancel();
    _demoPollTimer?.cancel();
    _hostCtrl.dispose();
    _portCtrl.dispose();
    _regIdCtrl.dispose();
    _regIpCtrl.dispose();
    _regPortCtrl.dispose();
    super.dispose();
  }

  // ═══════════════════════════════════════════════════
  // 连接 / 断开
  // ═══════════════════════════════════════════════════

  Future<void> _connect() async {
    setState(() => _connecting = true);
    final err = await widget.fleetService.connectCoordinator(
      _hostCtrl.text.trim(),
      int.tryParse(_portCtrl.text.trim()) ?? 8888,
    );
    setState(() => _connecting = false);
    if (err != null && mounted) {
      _showSnack(err, isError: true);
    }
  }

  void _disconnect() {
    _demoPollTimer?.cancel();
    widget.fleetService.disconnectCoordinator();
  }

  // ═══════════════════════════════════════════════════
  // 运动控制
  // ═══════════════════════════════════════════════════

  Future<void> _moveAll(String cmd) async {
    final result = await widget.fleetService.moveAll(
      cmd,
      speed: _speed,
      duration: _duration,
    );
    if (result != null && mounted) {
      final ok = result['code'] == 0;
      _showSnack(
        ok
            ? '已发送: $cmd (速度 $_speed%%)'
            : '发送失败: ${result['msg'] ?? '未知错误'}',
        isError: !ok,
      );
    }
  }

  // ═══════════════════════════════════════════════════
  // 队形
  // ═══════════════════════════════════════════════════

  Future<void> _applyFormation() async {
    final result = await widget.fleetService.applyFormation(
      _formationType,
      spacing: _formationSpacing,
    );
    if (result != null && mounted) {
      final ok = result['code'] == 0;
      _showSnack(
        ok
            ? '队形已应用: ${FleetService.formationLabels[_formationType]}'
            : '队形失败: ${result['msg'] ?? '未知错误'}',
        isError: !ok,
      );
    }
  }

  // ═══════════════════════════════════════════════════
  // 车辆管理
  // ═══════════════════════════════════════════════════

  void _showRegisterDialog() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF172233),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppTheme.cardBorder),
        ),
        title: const Text('注册新车', style: AppTheme.pageTitle),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _regField(_regIdCtrl, '车辆 ID (e.g. car_C)'),
            const SizedBox(height: 12),
            _regField(_regIpCtrl, 'IP 地址'),
            const SizedBox(height: 12),
            _regField(_regPortCtrl, '端口', isNum: true),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('取消', style: AppTheme.bodyLabel),
          ),
          TextButton(
            onPressed: () async {
              Navigator.of(ctx).pop();
              final result = await widget.fleetService.registerCar(
                _regIdCtrl.text.trim(),
                _regIpCtrl.text.trim(),
                port: int.tryParse(_regPortCtrl.text.trim()) ?? 5000,
              );
              if (result != null && mounted) {
                _showSnack(
                  result['code'] == 0
                      ? result['msg'] ?? '注册成功'
                      : result['msg'] ?? '注册失败',
                  isError: result['code'] != 0,
                );
              }
            },
            child: const Text('注册', style: TextStyle(color: AppTheme.accent)),
          ),
        ],
      ),
    );
  }

  Widget _regField(TextEditingController ctrl, String label, {bool isNum = false}) {
    return TextField(
      controller: ctrl,
      style: AppTheme.bodyValue,
      keyboardType: isNum ? TextInputType.number : TextInputType.text,
      decoration: InputDecoration(
        labelText: label,
        labelStyle: AppTheme.bodyLabel,
        enabledBorder: const UnderlineInputBorder(
            borderSide: BorderSide(color: AppTheme.cardBorder)),
        focusedBorder: const UnderlineInputBorder(
            borderSide: BorderSide(color: AppTheme.accent)),
      ),
    );
  }

  Future<void> _removeCar(String carId) async {
    final result = await widget.fleetService.removeCar(carId);
    if (result != null && mounted) {
      _showSnack(
        result['code'] == 0 ? '已移除 $carId' : result['msg'] ?? '移除失败',
        isError: result['code'] != 0,
      );
    }
  }

  // ═══════════════════════════════════════════════════
  // 协同展示
  // ═══════════════════════════════════════════════════

  void _startDemoPolling() {
    _demoPollTimer?.cancel();
    _demoPollTimer = Timer.periodic(
      const Duration(seconds: 1),
      (_) => widget.fleetService.getDemoStatus(),
    );
  }

  Future<void> _startDemo() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF172233),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppTheme.cardBorder),
        ),
        title: const Text('一键协同展示', style: AppTheme.pageTitle),
        content: const Text(
          '请确认两车周围各方向均有净空且有人监护。\n\n'
          '展示会以 50% 速度依次执行前进、后退、左右转、'
          '左右旋、左右移，每项 0.8 秒；随后播报和录音。',
          style: AppTheme.bodyLabel,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('取消', style: AppTheme.bodyLabel),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('开始展示',
                style: TextStyle(color: AppTheme.accent)),
          ),
        ],
      ),
    );
    if (ok != true) return;

    final result = await widget.fleetService.startDemo();
    if (result != null && mounted) {
      if (result['code'] == 0) {
        _startDemoPolling();
        _showSnack('协同展示已启动');
      } else {
        _showSnack(result['msg'] ?? '启动失败', isError: true);
      }
    }
  }

  Future<void> _stopDemo() async {
    final result = await widget.fleetService.stopDemo();
    if (result != null && mounted) {
      _showSnack(
        result['code'] == 0 ? '已发送紧急停止' : result['msg'] ?? '停止失败',
        isError: result['code'] != 0,
      );
    }
  }

  Future<void> _resetDemo() async {
    _demoPollTimer?.cancel();
    final result = await widget.fleetService.resetDemo();
    if (result != null && mounted) {
      _showSnack(
        result['code'] == 0 ? '展示已重置' : result['msg'] ?? '重置失败',
        isError: result['code'] != 0,
      );
    }
  }

  // ═══════════════════════════════════════════════════
  // 工具
  // ═══════════════════════════════════════════════════

  void _showSnack(String msg, {bool isError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg),
      backgroundColor: isError ? AppTheme.statusRed : const Color(0xFF238636),
      duration: const Duration(seconds: 2),
    ));
  }

  String _statusText(FleetStatus s) {
    switch (s) {
      case FleetStatus.idle:
        return '空闲';
      case FleetStatus.connecting:
        return '连接中…';
      case FleetStatus.ready:
        return '编队就绪';
      case FleetStatus.moving:
        return '行进中…';
      case FleetStatus.stopped:
        return '已停止';
    }
  }

  String _elapsedText(Duration d) {
    final m = d.inMinutes.toString().padLeft(2, '0');
    final s = (d.inSeconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  Color _demoStateColor(String s) {
    switch (s) {
      case 'running':
        return const Color(0xFFD29922);
      case 'completed':
        return const Color(0xFF3FB950);
      case 'failed':
      case 'stopped':
        return AppTheme.statusRed;
      default:
        return AppTheme.textPrimary;
    }
  }

  String _demoStateLabel(String s) {
    switch (s) {
      case 'running':
        return '运行中';
      case 'completed':
        return '已完成';
      case 'failed':
        return '失败';
      case 'stopped':
        return '已停止';
      default:
        return '空闲';
    }
  }

  // ═══════════════════════════════════════════════════
  // Build
  // ═══════════════════════════════════════════════════

  @override
  Widget build(BuildContext context) {
    final hasCars = _fleet.cars.isNotEmpty;

    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // ── 页头 ──
        PageHeader(
          title: '车队编队',
          subTitle: widget.fleetService.connected
              ? '协调器 ${_fleet.coordinatorHost}:${_fleet.coordinatorPort} · ${_fleet.carCount} 辆车'
              : '连接多车协同调度中心',
          badgeText: widget.fleetService.connected
              ? _statusText(_fleet.status)
              : '未连接',
          badgeActive: widget.fleetService.connected &&
              _fleet.status != FleetStatus.idle,
        ),
        const SizedBox(height: 16),

        // ── 碰撞告警横幅 ──
        if (hasCars && _fleet.hasCollisions) _buildCollisionBanner(),
        if (hasCars && _fleet.hasCollisions) const SizedBox(height: 12),

        // ═══════════════════════════════════
        // 未连接协调器 — 显示连接面板
        // ═══════════════════════════════════
        if (!widget.fleetService.connected) _buildConnectPanel(),

        // ═══════════════════════════════════
        // 已连接，无车 — 提示
        // ═══════════════════════════════════
        if (widget.fleetService.connected && !hasCars)
          _buildEmptyHint(),

        // ═══════════════════════════════════
        // 已连接，有车 — 完整面板
        // ═══════════════════════════════════
        if (widget.fleetService.connected && hasCars) ...[
          // 车辆卡片列表
          if (_fleet.leader != null)
            _buildCarCard(_fleet.leader!, isLeader: true),
          ..._fleet.followers.map((c) => _buildCarCard(c)),
          _buildAddButton(),
          const SizedBox(height: 16),

          // ── 编队命令 ──
          const Divider(color: AppTheme.dividerLine),
          const SizedBox(height: 14),
          const Text('编队命令', style: AppTheme.bodyValue),
          const SizedBox(height: 12),

          // 速度参数
          Row(
            children: [
              const Text('速度', style: AppTheme.bodyLabel),
              Expanded(
                child: Slider(
                  value: _speed.toDouble(),
                  min: 10,
                  max: 100,
                  divisions: 18,
                  activeColor: AppTheme.accent,
                  inactiveColor: AppTheme.cardBorder,
                  onChanged: (v) => setState(() => _speed = v.round()),
                ),
              ),
              SizedBox(
                width: 40,
                child: Text('$_speed%',
                    style: AppTheme.bodyValue, textAlign: TextAlign.right),
              ),
            ],
          ),
          const SizedBox(height: 4),
          // 动作时长
          Row(
            children: [
              const Text('时长', style: AppTheme.bodyLabel),
              Expanded(
                child: Slider(
                  value: _duration,
                  min: 0.1,
                  max: 2.0,
                  divisions: 19,
                  activeColor: AppTheme.accent,
                  inactiveColor: AppTheme.cardBorder,
                  onChanged: (v) => setState(() => _duration = v),
                ),
              ),
              SizedBox(
                width: 40,
                child: Text('${_duration.toStringAsFixed(1)}s',
                    style: AppTheme.bodyValue, textAlign: TextAlign.right),
              ),
            ],
          ),
          const SizedBox(height: 8),

          // 运动按钮网格
          _buildMoveGrid(),
          const SizedBox(height: 16),

          // ── 队形控制 ──
          const Divider(color: AppTheme.dividerLine),
          const SizedBox(height: 14),
          const Text('队形控制', style: AppTheme.bodyValue),
          const SizedBox(height: 12),
          _buildFormationPanel(),
          const SizedBox(height: 16),

          // ── 协同展示 ──
          const Divider(color: AppTheme.dividerLine),
          const SizedBox(height: 14),
          const Text('双车协同展示', style: AppTheme.bodyValue),
          const SizedBox(height: 12),
          _buildDemoPanel(),
          const SizedBox(height: 16),

          // ── 统计 ──
          const Divider(color: AppTheme.dividerLine),
          const SizedBox(height: 14),
          const Text('编队统计', style: AppTheme.bodyValue),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: GlassCard(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                  child: StatBlock(
                    value: '${_fleet.carCount}',
                    label: '车辆总数',
                    icon: Icons.precision_manufacturing,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: GlassCard(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                  child: StatBlock(
                    value: '${_fleet.avgBattery.round()}%',
                    label: '平均电量',
                    icon: Icons.battery_charging_full,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: GlassCard(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                  child: StatBlock(
                    value: _elapsedText(_fleet.elapsed),
                    label: '编队运行',
                    icon: Icons.timer_outlined,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // ── 断开按钮 ──
          GestureDetector(
            onTap: _disconnect,
            child: Container(
              width: double.infinity,
              height: AppTheme.btnHeight,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(AppTheme.btnRadius),
                border: Border.all(color: AppTheme.statusRed.withAlpha(40)),
                gradient: const LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [Color(0xFF3A1515), Color(0xFF2A1010)],
                ),
              ),
              alignment: Alignment.center,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  AppIcons.unlink(size: 18, color: const Color(0xFFFF6B6B)),
                  const SizedBox(width: 8),
                  const Text(
                    '断开协调器',
                    style: TextStyle(
                      fontWeight: FontWeight.w700,
                      fontSize: 15,
                      color: Color(0xFFFF6B6B),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          const Center(
            child: Text(
              '左滑卡片移除车辆 · 长按查看视频',
              style: TextStyle(fontSize: 11, color: Color.fromRGBO(255, 255, 255, 0.25)),
            ),
          ),
        ],
      ],
    );

    return _wrap(context, content);
  }

  // ═══════════════════════════════════════════════════
  // 连接面板
  // ═══════════════════════════════════════════════════

  Widget _buildConnectPanel() {
    return GlassCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('协调器地址', style: AppTheme.bodyValue),
          const SizedBox(height: 4),
          const Text(
            '连接到运行 multi_car_coordinator.py 的 PC',
            style: AppTheme.subtitle,
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                flex: 3,
                child: TextField(
                  controller: _hostCtrl,
                  style: AppTheme.bodyValue,
                  decoration: const InputDecoration(
                    labelText: 'IP 地址',
                    labelStyle: AppTheme.bodyLabel,
                    enabledBorder: OutlineInputBorder(
                      borderSide: BorderSide(color: AppTheme.cardBorder),
                      borderRadius: BorderRadius.all(Radius.circular(8)),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderSide: BorderSide(color: AppTheme.accent),
                      borderRadius: BorderRadius.all(Radius.circular(8)),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                flex: 1,
                child: TextField(
                  controller: _portCtrl,
                  style: AppTheme.bodyValue,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: '端口',
                    labelStyle: AppTheme.bodyLabel,
                    enabledBorder: OutlineInputBorder(
                      borderSide: BorderSide(color: AppTheme.cardBorder),
                      borderRadius: BorderRadius.all(Radius.circular(8)),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderSide: BorderSide(color: AppTheme.accent),
                      borderRadius: BorderRadius.all(Radius.circular(8)),
                    ),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            child: GradientButton(
              text: _connecting ? '连接中…' : '连接协调器',
              onTap: _connecting ? null : _connect,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyHint() {
    return GlassCard(
      padding: const EdgeInsets.all(40),
      child: Center(
        child: Column(
          children: [
            AppIcons.car(size: 64, color: AppTheme.textSecondary),
            const SizedBox(height: 16),
            const Text('协调器上暂无已注册车辆', style: AppTheme.bodyLabel),
            const SizedBox(height: 8),
            const Text(
              '请在协调器端配置车辆或使用下方注册功能',
              style: AppTheme.subtitle,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            _buildAddButton(),
            const SizedBox(height: 16),
            GestureDetector(
              onTap: _disconnect,
              child: const Text('断开协调器',
                  style: TextStyle(color: AppTheme.statusRed, fontSize: 13)),
            ),
          ],
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════════════
  // 碰撞告警横幅
  // ═══════════════════════════════════════════════════

  Widget _buildCollisionBanner() {
    final critical = _fleet.hasCriticalCollision;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: critical
            ? AppTheme.statusRed.withAlpha(30)
            : const Color(0xFFD29922).withAlpha(25),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: critical ? AppTheme.statusRed : const Color(0xFFD29922),
        ),
      ),
      child: Row(
        children: [
          Icon(
            Icons.warning_amber_rounded,
            color: critical ? AppTheme.statusRed : const Color(0xFFD29922),
            size: 22,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  critical ? '碰撞告警 (CRITICAL)' : '接近预警 (WARNING)',
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 14,
                    color:
                        critical ? AppTheme.statusRed : const Color(0xFFD29922),
                  ),
                ),
                const SizedBox(height: 4),
                ..._fleet.collisions.values.map(
                  (c) => Text(
                    c.displayText,
                    style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════════════
  // 车辆卡片
  // ═══════════════════════════════════════════════════

  Widget _buildCarCard(CarInfo car, {bool isLeader = false}) {
    // 碰撞样式
    final inCollision = _fleet.collisions.values
        .any((c) => c.carA == car.id || c.carB == car.id);
    final isCritical = inCollision &&
        _fleet.collisions.values.any((c) =>
            (c.carA == car.id || c.carB == car.id) &&
            c.level == CollisionLevel.critical);

    return Dismissible(
      key: Key(car.id),
      direction:
          isLeader ? DismissDirection.none : DismissDirection.endToStart,
      confirmDismiss: (_) async {
        final ok = await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            backgroundColor: const Color(0xFF172233),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
              side: const BorderSide(color: AppTheme.cardBorder),
            ),
            title: const Text('移除车辆', style: AppTheme.pageTitle),
            content: Text(
              '确定要从协调器移除 ${car.id} 吗？小车自身服务不受影响。',
              style: AppTheme.bodyLabel,
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(false),
                child: const Text('取消', style: AppTheme.bodyLabel),
              ),
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(true),
                child: const Text('移除',
                    style: TextStyle(color: AppTheme.statusRed)),
              ),
            ],
          ),
        );
        if (ok == true) _removeCar(car.id);
        return false; // 不依赖 Dismissible 的动画移除
      },
      background: Container(
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: AppTheme.statusRed.withAlpha(40),
          borderRadius: BorderRadius.circular(AppTheme.cardRadius),
        ),
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        child: const Icon(Icons.delete_outline, color: AppTheme.statusRed),
      ),
      child: GestureDetector(
        onLongPress: () => _showCarDetail(car),
        child: Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: const Color(0xFF1B2638),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: isLeader
                  ? AppTheme.accent
                  : isCritical
                      ? AppTheme.statusRed
                      : const Color(0xFF2C3F57),
              width: isLeader || isCritical ? 1.5 : 1,
            ),
            boxShadow: isLeader
                ? [
                    const BoxShadow(
                        color: Color.fromRGBO(255, 151, 72, 0.28),
                        blurRadius: 0,
                        spreadRadius: 1)
                  ]
                : isCritical
                    ? [
                        const BoxShadow(
                            color: Color.fromRGBO(255, 107, 107, 0.28),
                            blurRadius: 0,
                            spreadRadius: 1)
                      ]
                    : null,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── 第一行：图标 + 名称 + 电量 ──
              Row(
                children: [
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(10),
                      color: isLeader
                          ? const Color(0xFF3A4454)
                          : const Color(0xFF2E3746),
                    ),
                    alignment: Alignment.center,
                    child: car.online
                        ? AppIcons.car(
                            size: 18,
                            color: isLeader
                                ? const Color(0xFFFF9A57)
                                : const Color(0xFF99A6B8))
                        : const Icon(Icons.link_off,
                            size: 18, color: AppTheme.textSecondary),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          isLeader ? '${car.name} · 队长' : car.name,
                          style: TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: 16,
                            color: isLeader
                                ? AppTheme.accent
                                : AppTheme.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          '${car.ip}:${car.httpPort}',
                          style: const TextStyle(
                              fontSize: 11, color: AppTheme.textSecondary),
                        ),
                      ],
                    ),
                  ),
                  // 电量徽标
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(999),
                      color: car.online
                          ? const Color.fromRGBO(47, 224, 173, 0.12)
                          : const Color.fromRGBO(150, 150, 150, 0.12),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.circle,
                            size: 10,
                            color: car.online
                                ? const Color(0xFF2FE0AD)
                                : AppTheme.textSecondary),
                        const SizedBox(width: 6),
                        Text(
                          car.online ? '${car.batteryPercent}%' : '离线',
                          style: TextStyle(
                            fontWeight: FontWeight.w800,
                            fontSize: 12,
                            color: car.online
                                ? const Color(0xFF2FE0AD)
                                : AppTheme.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),

              // ── 第二行：传感器 + 位置数据 ──
              Row(
                children: [
                  _miniDataChip('${car.batteryVoltage.toStringAsFixed(1)}V', Icons.battery_std),
                  const SizedBox(width: 8),
                  _miniDataChip(car.positionDisplay, Icons.location_on_outlined),
                  if (car.temperature > 0) ...[
                    const SizedBox(width: 8),
                    _miniDataChip('${car.temperature.toStringAsFixed(1)}°C', Icons.thermostat_outlined),
                  ],
                  if (car.humidity > 0) ...[
                    const SizedBox(width: 8),
                    _miniDataChip('${car.humidity.toStringAsFixed(0)}%', Icons.water_drop_outlined),
                  ],
                ],
              ),
              if (car.smoke > 0 || car.pm25 > 0) ...[
                const SizedBox(height: 6),
                Row(
                  children: [
                    if (car.smoke > 0) _miniDataChip('烟雾 ${car.smoke.toStringAsFixed(0)}', Icons.smoke_free),
                    if (car.smoke > 0 && car.pm25 > 0) const SizedBox(width: 8),
                    if (car.pm25 > 0) _miniDataChip('PM2.5 ${car.pm25.toStringAsFixed(0)}', Icons.air),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _miniDataChip(String text, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: const Color(0xFF111827),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: AppTheme.textSecondary),
          const SizedBox(width: 4),
          Text(text,
              style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
        ],
      ),
    );
  }

  void _showCarDetail(CarInfo car) {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF172233),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('${car.name} 详情', style: AppTheme.pageTitle),
              const SizedBox(height: 16),
              InfoRow(label: 'ID', value: car.id),
              InfoRow(label: 'IP', value: '${car.ip}:${car.httpPort}'),
              InfoRow(label: 'TCP 端口', value: '${car.tcpPort}'),
              InfoRow(label: '在线', value: car.online ? '是' : '否'),
              InfoRow(label: '电池', value: '${car.batteryVoltage.toStringAsFixed(1)}V (${car.batteryPercent}%)'),
              InfoRow(label: '位置', value: car.positionDisplay),
              InfoRow(label: '温度', value: car.temperature > 0 ? '${car.temperature.toStringAsFixed(1)}°C' : '—'),
              InfoRow(label: '湿度', value: car.humidity > 0 ? '${car.humidity.toStringAsFixed(0)}%' : '—'),
              InfoRow(label: '烟雾', value: car.smoke > 0 ? '${car.smoke.toStringAsFixed(0)}' : '—'),
              InfoRow(label: 'PM2.5', value: car.pm25 > 0 ? '${car.pm25.toStringAsFixed(0)}' : '—'),
              const SizedBox(height: 16),
              if (car.online)
                SizedBox(
                  width: double.infinity,
                  child: GradientButton(
                    text: '查看视频流',
                    onTap: () {
                      Navigator.of(ctx).pop();
                      _showVideoStream(car);
                    },
                  ),
                ),
            ],
          ),
        );
      },
    );
  }

  void _showVideoStream(CarInfo car) {
    final url = widget.fleetService.getCameraProxyUrl(car.id);
    showDialog(
      context: context,
      builder: (ctx) => Dialog(
        backgroundColor: Colors.black,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AppBar(
              backgroundColor: Colors.transparent,
              title: Text('${car.name} 视频流', style: const TextStyle(fontSize: 14)),
              actions: [
                IconButton(
                  icon: const Icon(Icons.close, color: Colors.white),
                  onPressed: () => Navigator.of(ctx).pop(),
                ),
              ],
            ),
            SizedBox(
              width: double.infinity,
              height: 300,
              child: Image.network(
                url,
                fit: BoxFit.contain,
                loadingBuilder: (_, child, progress) {
                  if (progress == null) return child;
                  return const Center(
                    child: CircularProgressIndicator(color: AppTheme.accent),
                  );
                },
                errorBuilder: (_, __, ___) => const Center(
                  child: Text('无法加载视频流',
                      style: TextStyle(color: AppTheme.textSecondary)),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════════════
  // 添加车辆按钮
  // ═══════════════════════════════════════════════════

  Widget _buildAddButton() {
    return GestureDetector(
      onTap: _showRegisterDialog,
      child: Container(
        width: double.infinity,
        height: 44,
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: AppTheme.cardBorder,
            width: 1,
          ),
        ),
        alignment: Alignment.center,
        child: const Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.add, size: 18, color: AppTheme.textSecondary),
            SizedBox(width: 4),
            Text(
              '注册新车',
              style: TextStyle(
                fontWeight: FontWeight.w700,
                fontSize: 13,
                color: AppTheme.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════════════
  // 运动控制网格
  // ═══════════════════════════════════════════════════

  Widget _buildMoveGrid() {
    final btn = (String label, String cmd, {Color? color}) => Expanded(
          child: SizedBox(
            height: 46,
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: color ?? const Color(0xFF21262D),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                  side: BorderSide(
                    color: cmd == 'stop'
                        ? AppTheme.statusRed
                        : const Color(0xFF30363D),
                  ),
                ),
                padding: EdgeInsets.zero,
              ),
              onPressed: () => _moveAll(cmd),
              child: Text(
                label,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: cmd == 'stop' ? AppTheme.statusRed : AppTheme.textPrimary,
                ),
              ),
            ),
          ),
        );

    return Column(
      children: [
        // 第一行：前进
        Row(children: [btn('前进', 'forward'), const SizedBox(width: 6), const Spacer(flex: 2)]),
        const SizedBox(height: 6),
        // 第二行：左移 — 停止 — 右移
        Row(children: [
          btn('左移', 'left_shift'),
          const SizedBox(width: 6),
          btn('停止', 'stop', color: const Color(0xFF3A1515)),
          const SizedBox(width: 6),
          btn('右移', 'right_shift'),
        ]),
        const SizedBox(height: 6),
        // 第三行：左转 — 后退 — 右转
        Row(children: [
          btn('左转', 'left'),
          const SizedBox(width: 6),
          btn('后退', 'backward'),
          const SizedBox(width: 6),
          btn('右转', 'right'),
        ]),
        const SizedBox(height: 6),
        // 第四行：左旋 — 右旋
        Row(children: [
          btn('左旋', 'rotate_left'),
          const SizedBox(width: 6),
          btn('右旋', 'rotate_right'),
          const SizedBox(width: 6),
          const Spacer(flex: 1),
        ]),
      ],
    );
  }

  // ═══════════════════════════════════════════════════
  // 队形面板
  // ═══════════════════════════════════════════════════

  Widget _buildFormationPanel() {
    return GlassCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 队形选择
          Row(
            children: [
              const Text('队形', style: AppTheme.bodyLabel),
              const SizedBox(width: 12),
              Expanded(
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  decoration: BoxDecoration(
                    color: const Color(0xFF0D1117),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppTheme.cardBorder),
                  ),
                  child: DropdownButtonHideUnderline(
                    child: DropdownButton<String>(
                      value: _formationType,
                      dropdownColor: const Color(0xFF172233),
                      style: AppTheme.bodyValue,
                      isExpanded: true,
                      items: FleetService.formationTypes.map((t) {
                        return DropdownMenuItem(
                          value: t,
                          child: Text(FleetService.formationLabels[t] ?? t),
                        );
                      }).toList(),
                      onChanged: (v) {
                        if (v != null) setState(() => _formationType = v);
                      },
                    ),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // 间距
          Row(
            children: [
              const Text('间距', style: AppTheme.bodyLabel),
              Expanded(
                child: Slider(
                  value: _formationSpacing,
                  min: 0.5,
                  max: 5.0,
                  divisions: 9,
                  activeColor: AppTheme.accent,
                  inactiveColor: AppTheme.cardBorder,
                  onChanged: (v) => setState(() => _formationSpacing = v),
                ),
              ),
              SizedBox(
                width: 50,
                child: Text('${_formationSpacing.toStringAsFixed(1)}m',
                    style: AppTheme.bodyValue, textAlign: TextAlign.right),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: GradientButton(
              text: '应用队形',
              onTap: _applyFormation,
            ),
          ),
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════════════
  // 协同展示面板
  // ═══════════════════════════════════════════════════

  Widget _buildDemoPanel() {
    final demoRunning = _fleet.demoState == 'running';
    final demoCompleted = _fleet.demoState == 'completed';

    return GlassCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 状态行
          Row(
            children: [
              Container(
                width: 10,
                height: 10,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: _demoStateColor(_fleet.demoState),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '状态: ${_demoStateLabel(_fleet.demoState)}',
                style: TextStyle(
                  fontWeight: FontWeight.w700,
                  fontSize: 14,
                  color: _demoStateColor(_fleet.demoState),
                ),
              ),
              if (_fleet.demoStep.isNotEmpty) ...[
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    _fleet.demoStep,
                    style: const TextStyle(
                        fontSize: 12, color: AppTheme.textSecondary),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ],
          ),
          if (_fleet.demoMessage.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(_fleet.demoMessage,
                style:
                    const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          ],
          const SizedBox(height: 12),

          // 按钮行
          Row(
            children: [
              Expanded(
                child: SizedBox(
                  height: 40,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF238636),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(8)),
                    ),
                    onPressed: demoRunning ? null : _startDemo,
                    child: Text(
                      demoRunning ? '运行中…' : '一键展示',
                      style: const TextStyle(
                          fontWeight: FontWeight.w700, color: Colors.white),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: SizedBox(
                  height: 40,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFFDA3633),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(8)),
                    ),
                    onPressed: demoRunning ? _stopDemo : null,
                    child: const Text('紧急停止',
                        style: TextStyle(
                            fontWeight: FontWeight.w700, color: Colors.white)),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: SizedBox(
                  height: 40,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF21262D),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(8),
                          side: BorderSide(color: AppTheme.cardBorder)),
                    ),
                    onPressed: demoRunning ? null : _resetDemo,
                    child: const Text('重置',
                        style: TextStyle(
                            fontWeight: FontWeight.w700,
                            color: AppTheme.textSecondary)),
                  ),
                ),
              ),
            ],
          ),

          // 录音回放（展示完成后）
          if (demoCompleted && _fleet.demoRecordings.isNotEmpty) ...[
            const SizedBox(height: 14),
            const Text('录音回放', style: AppTheme.bodyLabel),
            const SizedBox(height: 8),
            ..._fleet.demoRecordings.entries.map((e) {
              final url = 'http://${_fleet.coordinatorHost}:${_fleet.coordinatorPort}/api/demo/recording/${e.key}';
              return Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  children: [
                    Text(e.key, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                    const SizedBox(width: 8),
                    const Icon(Icons.mic, size: 14, color: AppTheme.textSecondary),
                    const SizedBox(width: 4),
                    Text(e.value, style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                    const Spacer(),
                    GestureDetector(
                      onTap: () => _showSnack('录音地址: $url'),
                      child: const Icon(Icons.download, size: 16, color: AppTheme.accent),
                    ),
                  ],
                ),
              );
            }),
          ],
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════════════
  // 页面包装
  // ═══════════════════════════════════════════════════

  Widget _wrap(BuildContext context, Widget content) {
    if (widget.embedded) {
      return SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(
            AppTheme.pagePadding, 16, AppTheme.pagePadding, AppTheme.tabBarInset),
        child: content,
      );
    }
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
            child: content,
          ),
        ),
      ),
    );
  }
}
