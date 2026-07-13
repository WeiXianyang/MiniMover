import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../models/fleet_info.dart';
import '../services/fleet_service.dart';
import '../services/car_state.dart';
import '../widgets/common_widgets.dart';

/// S08 - 车队编队页面
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

  @override
  void initState() {
    super.initState();
    widget.fleetService.stateStream.listen((s) {
      if (mounted) setState(() => _fleet = s);
    });
    // 不再自动 mock 车队 — 用户需点击"组建车队"
  }

  bool get _hasFleet => _fleet.cars.isNotEmpty;

  void _buildFleet() {
    final cs = widget.carState;
    widget.fleetService.buildFleet(
      leaderIp: cs.host,
      leaderName: cs.connected ? '主车' : '主车 (未连接)',
      battery: cs.batteryPercent,
    );
  }

  void _addFollower() {
    final ipCtrl = TextEditingController(text: '192.168.1.1');
    final portCtrl = TextEditingController(text: '6000');
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF172233),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppTheme.cardBorder),
        ),
        title: const Text('添加从车', style: AppTheme.pageTitle),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: ipCtrl,
              style: AppTheme.bodyValue,
              decoration: const InputDecoration(
                labelText: 'IP 地址',
                labelStyle: AppTheme.bodyLabel,
                enabledBorder: UnderlineInputBorder(
                    borderSide: BorderSide(color: AppTheme.cardBorder)),
                focusedBorder: UnderlineInputBorder(
                    borderSide: BorderSide(color: AppTheme.accent)),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: portCtrl,
              style: AppTheme.bodyValue,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'TCP 端口',
                labelStyle: AppTheme.bodyLabel,
                enabledBorder: UnderlineInputBorder(
                    borderSide: BorderSide(color: AppTheme.cardBorder)),
                focusedBorder: UnderlineInputBorder(
                    borderSide: BorderSide(color: AppTheme.accent)),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('取消', style: AppTheme.bodyLabel),
          ),
          TextButton(
            onPressed: () {
              widget.fleetService.addFollower(
                ipCtrl.text.trim(),
                port: int.tryParse(portCtrl.text.trim()) ?? 6000,
              );
              Navigator.of(ctx).pop();
            },
            child:
                const Text('添加', style: TextStyle(color: AppTheme.accent)),
          ),
        ],
      ),
    );
  }

  void _disbandConfirm() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF172233),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppTheme.cardBorder),
        ),
        title: const Text('解散编队', style: AppTheme.pageTitle),
        content: const Text('确定要解散当前编队吗？所有从车将被移除。',
            style: AppTheme.bodyLabel),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('取消', style: AppTheme.bodyLabel),
          ),
          TextButton(
            onPressed: () {
              widget.fleetService.disbandFleet();
              Navigator.of(ctx).pop();
            },
            child: const Text('解散',
                style: TextStyle(color: AppTheme.statusRed)),
          ),
        ],
      ),
    );
  }

  String _statusText(FleetStatus s) {
    switch (s) {
      case FleetStatus.idle:
        return '空闲';
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

  @override
  Widget build(BuildContext context) {
    final halted = _fleet.status == FleetStatus.moving;

    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(20),
          decoration: _frameDeco(),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              PageHeader(
                title: '车队编队',
                subTitle: _hasFleet ? '主车领航 + 多从车跟随编队' : '点击下方按钮组建车队',
                badgeText: _hasFleet ? _statusText(_fleet.status) : '未组建',
                badgeActive: _hasFleet && _fleet.status != FleetStatus.idle,
              ),
              const SizedBox(height: 20),
              if (!_hasFleet) ...[
                // ── 未组建车队：显示组建按钮 ──
                const SizedBox(height: 40),
                const Center(
                  child: Icon(Icons.precision_manufacturing,
                      size: 64, color: Color.fromRGBO(255, 255, 255, 0.06)),
                ),
                const SizedBox(height: 16),
                const Center(
                  child: Text('尚未组建车队',
                      style: AppTheme.bodyLabel),
                ),
                const SizedBox(height: 8),
                const Center(
                  child: Text(
                    '以当前连接小车为主车，组建编队',
                    style: AppTheme.subtitle,
                    textAlign: TextAlign.center,
                  ),
                ),
                const SizedBox(height: 24),
                GradientButton(
                  text: '组建车队',
                  onTap: widget.carState.connected ? _buildFleet : null,
                ),
                if (!widget.carState.connected) ...[
                  const SizedBox(height: 8),
                  const Center(
                    child: Text('请先在设备连接页连接到小车',
                        style: AppTheme.subtitle),
                  ),
                ],
              ] else ...[
                // ── 已组建：车队列表 + 命令 ──
                if (_fleet.leader != null)
                  _buildCarCard(_fleet.leader!, isLeader: true),
                ..._fleet.followers.map((c) => _buildCarCard(c)),
                const SizedBox(height: 8),
                _buildAddButton(),
                const SizedBox(height: 16),
                const Divider(color: AppTheme.dividerLine),
                const SizedBox(height: 14),
                const Text('编队命令', style: AppTheme.bodyValue),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: GradientButton(
                        text: '出发',
                        onTap: halted
                            ? null
                            : () => widget.fleetService.startFleet(),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: GradientButton(
                        text: '停止',
                        secondary: true,
                        onTap: halted
                            ? () => widget.fleetService.stopFleet()
                            : null,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                GestureDetector(
                  onTap: _disbandConfirm,
                  child: Container(
                    width: double.infinity,
                    height: AppTheme.btnHeight,
                    decoration: BoxDecoration(
                      borderRadius:
                          BorderRadius.circular(AppTheme.btnRadius),
                      border: Border.all(
                          color: AppTheme.statusRed.withAlpha(40)),
                      gradient: const LinearGradient(
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                        colors: [Color(0xFF3A1515), Color(0xFF2A1010)],
                      ),
                    ),
                    alignment: Alignment.center,
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: const [
                        Icon(Icons.warning_amber_outlined,
                            size: 18, color: Color(0xFFFF6B6B)),
                        SizedBox(width: 8),
                        Text(
                          '解散编队',
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
                const SizedBox(height: 16),
                const Divider(color: AppTheme.dividerLine),
                const SizedBox(height: 14),
                const Text('编队统计', style: AppTheme.bodyValue),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: GlassCard(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 14, vertical: 12),
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
                        padding: const EdgeInsets.symmetric(
                            horizontal: 14, vertical: 12),
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
                        padding: const EdgeInsets.symmetric(
                            horizontal: 14, vertical: 12),
                        child: StatBlock(
                          value: _elapsedText(_fleet.elapsed),
                          label: '编队运行',
                          icon: Icons.timer_outlined,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                const Center(
                  child: Text(
                    '左滑卡片移除从车 · 点击查看详情',
                    style: TextStyle(
                      fontSize: 11,
                      color: Color.fromRGBO(255, 255, 255, 0.25),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    );

    return _wrap(context, content);
  }

  Widget _buildCarCard(CarInfo car, {bool isLeader = false}) {
    return Dismissible(
      key: Key(car.id),
      direction:
          isLeader ? DismissDirection.none : DismissDirection.endToStart,
      confirmDismiss: (_) async {
        widget.fleetService.removeFollower(car.id);
        return false;
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
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppTheme.cardFill,
          borderRadius: BorderRadius.circular(AppTheme.cardRadius),
          border: Border.all(
            color: isLeader ? AppTheme.accent : AppTheme.cardBorder,
            width: isLeader ? 1.5 : 1,
          ),
        ),
        child: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(8),
                color: isLeader
                    ? const Color.fromRGBO(255, 140, 66, 0.15)
                    : AppTheme.cardFill,
              ),
              alignment: Alignment.center,
              child: Icon(
                Icons.precision_manufacturing,
                size: 18,
                color: isLeader ? AppTheme.accent : AppTheme.textSecondary,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    isLeader ? '${car.name} · 队长' : car.name,
                    style: TextStyle(
                      fontWeight: FontWeight.w700,
                      fontSize: 14,
                      color:
                          isLeader ? AppTheme.accent : AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    isLeader
                        ? '${car.ip} · 任务: 编队领航'
                        : '编队距离: ${car.distance.toStringAsFixed(1)}m  ·  速度: ${car.speed.toStringAsFixed(1)} m/s',
                    style: AppTheme.subtitle,
                  ),
                ],
              ),
            ),
            Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(10),
                color: const Color.fromRGBO(45, 207, 159, 0.08),
                border: Border.all(
                    color: const Color.fromRGBO(45, 207, 159, 0.15)),
              ),
              child: Text(
                '${car.battery}%',
                style: const TextStyle(
                  fontWeight: FontWeight.w700,
                  fontSize: 10,
                  color: AppTheme.statusGreen,
                ),
              ),
            ),
            const SizedBox(width: 8),
            Icon(
              car.online ? Icons.circle : Icons.circle_outlined,
              size: 8,
              color:
                  car.online ? AppTheme.statusGreen : AppTheme.textSecondary,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAddButton() {
    return GestureDetector(
      onTap: _addFollower,
      child: Container(
        width: double.infinity,
        height: 44,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: AppTheme.cardBorder,
            width: 1,
            strokeAlign: BorderSide.strokeAlignInside,
          ),
        ),
        alignment: Alignment.center,
        child: const Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.add, size: 18, color: AppTheme.textSecondary),
            SizedBox(width: 4),
            Text(
              '添加从车',
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
