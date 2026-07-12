import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/car_state.dart';
import '../widgets/common_widgets.dart';
import '../widgets/page_shell.dart';
import 'map_task_page.dart';
import 'manual_control_page.dart';

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

    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('S02-巡检主页',
            style: AppTheme.sectionLabel.copyWith(fontSize: 14)),
        const SizedBox(height: 16),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(20),
          decoration: _frameDeco(),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              PageHeader(
                title: '巡检主页',
                subTitle: '今日任务总览',
                badgeText: cs.taskRunning
                    ? (cs.taskPaused ? '已暂停' : '巡检中')
                    : '自动巡检待命',
                badgeActive: cs.taskRunning,
              ),
              const SizedBox(height: 24),
              GlassCard(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                child: Column(
                  children: [
                    InfoRow(
                        label: '当前区域', value: cs.currentArea),
                    const Divider(color: AppTheme.dividerLine, height: 20),
                    InfoRow(
                        label: '当前任务',
                        value: cs.taskRunning ? '配电房与仓储通道巡检' : '待命'),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: GlassCard(
                      padding: const EdgeInsets.all(16),
                      child: StatBlock(
                        value: cs.connected
                            ? '${cs.batteryPercent}%'
                            : '—',
                        label: '电量',
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: GlassCard(
                      padding: const EdgeInsets.all(16),
                      child: StatBlock(
                        value: '${cs.remainingPoints}',
                        label: '待巡检点',
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  const Expanded(
                    child: GlassCard(
                      padding: EdgeInsets.all(16),
                      child:
                          StatBlock(value: '正常', label: '烟雾值'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  const Expanded(
                    child: GlassCard(
                      padding: EdgeInsets.all(16),
                      child: StatBlock(value: '29°C', label: '机柜环境温度'),
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
                      cs.taskRunning
                          ? '巡检进行中… 约 ${((1 - cs.taskProgress) * 6).ceil()} 分钟'
                          : '开始自动巡检，预计 6 分钟完成',
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
                text: cs.taskRunning ? '巡检进行中…' : '开始自动巡检',
                onTap: cs.taskRunning
                    ? null
                    : () {
                        cs.startTask();
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
                        tcpService: cs.tcpService, embedded: true)),
              ),
            ],
          ),
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
