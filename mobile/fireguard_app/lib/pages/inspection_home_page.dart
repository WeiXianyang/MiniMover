import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/car_state.dart';
import '../widgets/common_widgets.dart';
import '../widgets/page_shell.dart';
import 'map_task_page.dart';
import 'manual_control_page.dart';
import 'model3d_page.dart';

/// S02 - 巡检主页
class InspectionHomePage extends StatefulWidget {
  final CarState carState;
  final bool embedded;
  const InspectionHomePage({
    super.key,
    required this.carState,
    this.embedded = false,
  });

  @override
  State<InspectionHomePage> createState() => _InspectionHomePageState();
}

class _InspectionHomePageState extends State<InspectionHomePage> {
  @override
  void initState() {
    super.initState();
    widget.carState.addListener(_onChanged);
  }

  @override
  void dispose() {
    widget.carState.removeListener(_onChanged);
    super.dispose();
  }

  void _onChanged() {
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final cs = widget.carState;
    final online = cs.connected;

    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
                Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              PageHeader(
                title: '巡检主页',
                subTitle: cs.deviceStatusDisplay,
                badgeText: online
                    ? (cs.taskRunning
                        ? (cs.taskPaused ? '已暂停' : '巡检中')
                        : '就绪')
                    : '离线',
                badgeActive: online,
              ),
              const SizedBox(height: 24),
              // ── 基本信息卡：对齐 prototype 2 行（当前区域 + 当前任务）──
              GlassCard(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                child: Column(
                  children: [
                    InfoRow(
                        label: '当前区域', value: '园区 A 栋一层'),
                    const Divider(color: AppTheme.dividerLine, height: 20),
                    InfoRow(
                        label: '当前任务',
                        value: online
                            ? (cs.taskRunning
                                ? (cs.taskPaused ? '已暂停' : '配电房与仓储通道巡检')
                                : '配电房与仓储通道巡检')
                            : '—'),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              // ── 统计卡片（2×2 Grid，对齐 prototype metrics）──
              Row(
                children: [
                  Expanded(
                    child: GlassCard(
                      padding: const EdgeInsets.all(15),
                      child: StatBlock(value: '${widget.carState.batteryPercent}%', label: '电量', icon: Icons.battery_charging_full),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: GlassCard(
                      padding: const EdgeInsets.all(15),
                      child: StatBlock(value: '${widget.carState.totalPoints - widget.carState.completedPoints}', label: '待巡检点', icon: Icons.checklist),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: GlassCard(
                      padding: const EdgeInsets.all(15),
                      child: StatBlock(
                        value: cs.connected && cs.sensors.smoke > 0 ? '${cs.sensors.smoke}' : '正常',
                        label: '烟雾值',
                        icon: Icons.smoke_free),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: GlassCard(
                      padding: const EdgeInsets.all(15),
                      child: StatBlock(
                        value: cs.connected && cs.sensors.temperature > 0 ? '${cs.sensors.temperature.toStringAsFixed(1)}°C' : '29°C',
                        label: '机柜环境温度',
                        icon: Icons.device_thermostat),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              GlassCard(
                padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('推荐动作', style: AppTheme.bodyLabel),
                    const SizedBox(height: 6),
                    Text(
                      online
                          ? (cs.taskRunning
                              ? (cs.taskPaused ? '已暂停，点击恢复继续巡检' : '巡检进行中…')
                              : '点击下方按钮开始自动巡检')
                          : '请先在「设备连接」页连接小车',
                      style: const TextStyle(
                          fontWeight: FontWeight.w700,
                          fontSize: 18,
                          color: AppTheme.textPrimary),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),
              GradientButton(
                text: online
                    ? (cs.taskRunning
                        ? (cs.taskPaused ? '恢复自动巡检' : '巡检进行中…')
                        : '开始自动巡检')
                    : '开始自动巡检',
                onTap: online && !cs.taskRunning
                    ? () {
                        cs.startTask();
                        _push(context, '地图任务',
                            MapTaskPage(carState: cs, embedded: true));
                      }
                    : () {
                        // 离线模式：直接跳转，不启动任务
                        _push(context, '地图任务',
                            MapTaskPage(carState: cs, embedded: true));
                      },
              ),
              const SizedBox(height: 12),
              GradientButton(
                text: '切换到手动接管',
                secondary: true,
                onTap: () => _push(
                    context,
                    '手动接管',
                    ManualControlPage(
                        carState: cs, embedded: true)),
              ),
              const SizedBox(height: 12),
              GradientButton(
                text: '部件信息展示',
                secondary: true,
                onTap: () => _push(
                    context,
                    '部件信息展示',
                    Model3DPage(carState: cs)),
              ),
            ],
          ),
      ],
    );

    return _wrap(context, content);
  }

  void _push(BuildContext context, String title, Widget page) {
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => PageShell(title: title, child: page),
    ));
  }


  Widget _wrap(BuildContext context, Widget content) {
    if (widget.embedded) {
      return SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(
            AppTheme.pagePadding, 16, AppTheme.pagePadding, AppTheme.tabBarInset),
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
