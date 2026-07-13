import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../models/fleet_info.dart';
import '../services/fleet_service.dart';
import '../services/car_state.dart';
import '../widgets/common_widgets.dart';
import '../widgets/app_icons.dart';

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
                Column(
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
                Center(
                  child: AppIcons.car(
                      size: 64, color: AppTheme.textSecondary),
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
                  text: '组建车队（演示）',
                  onTap: _buildFleet,
                ),
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
                        icon: AppIcons.play(size: 16),
                        onTap: halted
                            ? null
                            : () => widget.fleetService.startFleet(),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: GradientButton(
                        text: '停止',
                        icon: AppIcons.square(size: 16),
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
                      children: [
                        AppIcons.unlink(
                            size: 18, color: const Color(0xFFFF6B6B)),
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
          color: const Color(0xFF1B2638),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: isLeader ? AppTheme.accent : const Color(0xFF2C3F57),
            width: 1,
          ),
          boxShadow: isLeader
              ? [const BoxShadow(color: Color.fromRGBO(255, 151, 72, 0.28), blurRadius: 0, spreadRadius: 1)]
              : null,
        ),
        child: Row(
          children: [
            Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(10),
                color: isLeader ? const Color(0xFF3A4454) : const Color(0xFF2E3746),
              ),
              alignment: Alignment.center,
              child: AppIcons.car(
                size: 18,
                color: isLeader ? const Color(0xFFFF9A57) : const Color(0xFF99A6B8)),
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
                      color:
                          isLeader ? AppTheme.accent : AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 5),
                  Text(
                    isLeader
                        ? '${car.ip} · 任务: 编队领航'
                        : '编队距离: ${car.distance.toStringAsFixed(1)}m  ·  速度: ${car.speed.toStringAsFixed(1)} m/s',
                    style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                  ),
                ],
              ),
            ),
            Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(999),
                color: const Color.fromRGBO(47, 224, 173, 0.12),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.circle, size: 10, color: Color(0xFF2FE0AD)),
                  SizedBox(width: 6),
                  Text(
                    '86%',
                    style: TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 12,
                      color: Color(0xFF2FE0AD),
                    ),
                  ),
                ],
              ),
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
