import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/car_state.dart';
import '../widgets/common_widgets.dart';
import '../widgets/page_shell.dart';
import 'delivery_page.dart';
import 'manual_control_page.dart';

/// S04 - 告警详情页面
class AlarmDetailPage extends StatefulWidget {
  final CarState carState;
  final bool embedded;
  const AlarmDetailPage({
    super.key,
    required this.carState,
    this.embedded = false,
  });

  @override
  State<AlarmDetailPage> createState() => _AlarmDetailPageState();
}

class _AlarmDetailPageState extends State<AlarmDetailPage> {
  bool _fetched = false;

  @override
  void initState() {
    super.initState();
    widget.carState.addListener(_onChanged);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_fetched) {
      _fetched = true;
      widget.carState.fetchCloudAlarm();
    }
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
                Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              PageHeader(
                title: '告警详情',
                subTitle: '视觉 + 传感器联合判定',
                badgeText: cs.hasAlarm ? cs.alarmLevel : '无告警',
                badgeActive: cs.hasAlarm,
              ),
              const SizedBox(height: 20),
              // 告警可视化区域
              GlassCard(
                height: cs.hasAlarm ? 182 : 120,
                padding: const EdgeInsets.all(12),
                child: Stack(children: [
                  Center(
                    child: Container(
                      width: 280,
                      height: cs.hasAlarm ? 140 : 80,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(8),
                        gradient: LinearGradient(
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                          colors: cs.hasAlarm
                              ? [
                                  Colors.red.shade900.withAlpha(77),
                                  Colors.orange.shade900.withAlpha(51),
                                ]
                              : [
                                  Colors.grey.shade900.withAlpha(40),
                                  Colors.grey.shade800.withAlpha(30),
                                ],
                        ),
                      ),
                      child: Center(
                        child: Icon(
                          cs.hasAlarm
                              ? Icons.smoke_free
                              : Icons.check_circle_outline,
                          color: AppTheme.textSecondary,
                          size: 40,
                        ),
                      ),
                    ),
                  ),
                  if (cs.hasAlarm)
                    const Positioned(
                      bottom: 8,
                      right: 16,
                      child: Text('疑似烟雾区', style: AppTheme.bodyValue),
                    ),
                ]),
              ),
              const SizedBox(height: 14),
              GlassCard(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                child: Column(
                  children: [
                    InfoRow(
                      label: '识别类型',
                      value: cs.hasAlarm ? '疑似烟雾 / 明火风险' : '—',
                    ),
                    const Divider(color: AppTheme.dividerLine, height: 20),
                    InfoRow(
                      label: '视觉置信度',
                      value: cs.hasAlarm
                          ? '${(cs.alarmConfidence * 100).round()}%'
                          : '—',
                    ),
                    const Divider(color: AppTheme.dividerLine, height: 20),
                    InfoRow(
                      label: '烟雾值',
                      value: cs.connected && cs.sensors.smoke > 0
                          ? '${cs.sensors.smoke}'
                          : '—',
                    ),
                    const Divider(color: AppTheme.dividerLine, height: 20),
                    InfoRow(
                      label: '温度',
                      value: cs.connected && cs.sensors.temperature > 0
                          ? '${cs.sensors.temperature.toStringAsFixed(1)}°C'
                          : '—',
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              GlassCard(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('处置建议', style: AppTheme.bodyValue),
                    const SizedBox(height: 8),
                    Text(
                      cs.hasAlarm
                          ? '建议先停车并拉起远程接管，同时发起应急物资配送。'
                          : '当前无告警，可正常巡检。',
                      style: AppTheme.bodyLabel,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),
              GradientButton(
                text: '发起应急配送',
                onTap: () {
                  cs.startDelivery();
                  _push(context, '定点配送',
                      DeliveryPage(carState: cs, embedded: true));
                },
              ),
              const SizedBox(height: 12),
              GradientButton(
                text: cs.hasAlarm ? '进入远程接管' : '手动接管',
                secondary: true,
                onTap: () => _push(
                    context,
                    '手动接管',
                    ManualControlPage(
                        carState: cs, embedded: true)),
              ),
              if (cs.hasAlarm) ...[
                const SizedBox(height: 12),
                GradientButton(
                  text: '清除告警',
                  secondary: true,
                  onTap: () => cs.clearAlarm(),
                ),
              ],
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
