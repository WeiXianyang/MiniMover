import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/car_state.dart';
import '../widgets/common_widgets.dart';
import '../widgets/page_shell.dart';

/// S07 - 巡检报告页面
class ReportPage extends StatefulWidget {
  final CarState carState;
  final bool embedded;
  const ReportPage({
    super.key,
    required this.carState,
    this.embedded = false,
  });

  @override
  State<ReportPage> createState() => _ReportPageState();
}

class _ReportPageState extends State<ReportPage> {
  bool _exporting = false;

  @override
  Widget build(BuildContext context) {
    final cs = widget.carState;
    final events = cs.eventLog.where((e) => !e.contains('进度')).toList();
    final displayEvents =
        events.length > 5 ? events.sublist(events.length - 5) : events;

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
                title: '巡检报告',
                subTitle: '一次任务结束后的摘要视图',
                badgeText: cs.taskRunning ? '进行中' : '已归档',
                badgeActive: !cs.taskRunning,
              ),
              const SizedBox(height: 24),
              Row(
                children: [
                  const Expanded(
                    child: GlassCard(
                      padding: EdgeInsets.all(16),
                      child: StatBlock(
                          value: '—',
                          label: '巡检耗时',
                          icon: Icons.timer_outlined),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: GlassCard(
                      padding: const EdgeInsets.all(16),
                      child: StatBlock(
                          value: '${cs.completedPoints}/${cs.totalPoints}',
                          label: '完成点位',
                          icon: Icons.check_circle_outline),
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
                      child: StatBlock(
                          value: '—',
                          label: '高等级告警',
                          icon: Icons.warning_amber_outlined),
                    ),
                  ),
                  const SizedBox(width: 12),
                  const Expanded(
                    child: GlassCard(
                      padding: EdgeInsets.all(16),
                      child: StatBlock(
                          value: '—',
                          label: '动态避障',
                          icon: Icons.alt_route),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              // 事件日志
              if (displayEvents.isNotEmpty) ...[
                GlassCard(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('事件日志', style: AppTheme.bodyValue),
                      const SizedBox(height: 8),
                      ...displayEvents.map((e) => Padding(
                            padding: const EdgeInsets.only(bottom: 6),
                            child: Text(e,
                                style: const TextStyle(
                                    fontSize: 12,
                                    color: AppTheme.textSecondary)),
                          )),
                    ],
                  ),
                ),
                const SizedBox(height: 14),
              ],
              GlassCard(
                padding: const EdgeInsets.symmetric(
                    horizontal: 16, vertical: 14),
                child: const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('导出能力', style: AppTheme.bodyValue),
                    SizedBox(height: 8),
                    Text('支持导出图片、视频片段、任务时间线和组会汇报摘要。',
                        style: AppTheme.bodyLabel),
                  ],
                ),
              ),
              const SizedBox(height: 20),
              Row(
                children: [
                  Expanded(
                    child: SmallButton(
                      text: _exporting ? '导出中...' : '导出 PDF 报告',
                      onTap: _exporting
                          ? null
                          : () => _handleExport(context),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: SmallButton(
                      text: '分享给老师 / 组员',
                      onTap: () => _handleShare(context),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              GradientButton(
                text: '返回设备连接',
                secondary: true,
                onTap: () =>
                    Navigator.of(context).popUntil((route) => route.isFirst),
              ),
            ],
          ),
        ),
      ],
    );

    return _wrap(context, content);
  }

  void _handleExport(BuildContext context) {
    setState(() => _exporting = true);
    // TODO: 使用 pdf 或 share_plus 包生成 PDF
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('PDF 报告导出功能开发中… 将包含任务时间线和事件摘要'),
      ),
    );
    Future.delayed(const Duration(seconds: 1), () {
      if (mounted) setState(() => _exporting = false);
    });
  }

  void _handleShare(BuildContext context) {
    // TODO: 使用 share_plus 包分享
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('分享功能开发中… 将支持微信/飞书/邮件分享'),
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
