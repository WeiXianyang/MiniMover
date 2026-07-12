import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/car_state.dart';
import '../widgets/common_widgets.dart';
import '../widgets/page_shell.dart';

/// S05 - 定点配送页面
class DeliveryPage extends StatefulWidget {
  final CarState carState;
  final bool embedded;
  const DeliveryPage({
    super.key,
    required this.carState,
    this.embedded = false,
  });

  @override
  State<DeliveryPage> createState() => _DeliveryPageState();
}

class _DeliveryPageState extends State<DeliveryPage> {
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
        Text('S05-定点配送',
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
                title: '定点配送',
                subTitle: '同一地图上的应急调度',
                badgeText: cs.deliveryActive ? cs.deliveryStatus : '待命',
                badgeActive: cs.deliveryActive,
              ),
              const SizedBox(height: 20),
              GlassCard(
                padding: const EdgeInsets.symmetric(
                    horizontal: 16, vertical: 14),
                child: const Column(
                  children: [
                    InfoRow(
                        label: '配送物资',
                        value: '灭火器模型 / 急救包'),
                    Divider(color: AppTheme.dividerLine, height: 20),
                    InfoRow(label: '起点', value: '应急物资点D'),
                    Divider(color: AppTheme.dividerLine, height: 20),
                    InfoRow(label: '终点', value: '配电柜A'),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              GlassCard(
                padding: const EdgeInsets.symmetric(
                    horizontal: 16, vertical: 14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('配送路径', style: AppTheme.bodyLabel),
                    const SizedBox(height: 8),
                    const Text('D 点装载 → 主通道 → 配电柜A',
                        style: TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: 16,
                            color: AppTheme.textPrimary)),
                    const SizedBox(height: 16),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                          value: cs.deliveryProgress > 0
                              ? cs.deliveryProgress
                              : 0.68, // fallback demo
                          minHeight: 4,
                          backgroundColor: AppTheme.cardBorder,
                          color: AppTheme.accent),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      cs.deliveryActive
                          ? '已完成 ${(cs.deliveryProgress * 100).round()}%，当前绕过临时障碍物后继续前进。'
                          : '配送未开始',
                      style: AppTheme.bodyLabel,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              GlassCard(
                padding: const EdgeInsets.symmetric(
                    horizontal: 16, vertical: 14),
                child: Column(
                  children: [
                    InfoRow(
                      label: '任务状态',
                      value:
                          cs.deliveryActive ? cs.deliveryStatus : '待命',
                    ),
                    const Divider(
                        color: AppTheme.dividerLine, height: 20),
                    const InfoRow(label: '载荷舱', value: '已锁定'),
                    const Divider(
                        color: AppTheme.dividerLine, height: 20),
                    const InfoRow(label: '目标确认', value: '待现场人员签收'),
                  ],
                ),
              ),
              const SizedBox(height: 20),
              if (!cs.deliveryActive) ...[
                GradientButton(
                  text: '发起配送',
                  onTap: () => cs.startDelivery(),
                ),
                const SizedBox(height: 12),
              ],
              if (cs.deliveryActive) ...[
                GradientButton(
                  text: '模拟配送进度 (+20%)',
                  secondary: true,
                  onTap: () =>
                      cs.updateDeliveryProgress(cs.deliveryProgress + 0.2),
                ),
                const SizedBox(height: 12),
              ],
              GradientButton(
                text: cs.deliveryActive
                    ? '取消配送并返回待命点'
                    : '返回',
                secondary: true,
                onTap: () {
                  if (cs.deliveryActive) cs.cancelDelivery();
                  Navigator.of(context).pop();
                },
              ),
            ],
          ),
        ),
      ],
    );

    return _wrap(context, content);
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
