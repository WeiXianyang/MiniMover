import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/tcp_service.dart';
import '../widgets/common_widgets.dart';

/// S07 - 巡检报告页面
class ReportPage extends StatelessWidget {
  final TcpService tcpService;
  const ReportPage({super.key, required this.tcpService});

  @override
  Widget build(BuildContext context) {
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
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 20),
                Text('S07-巡检报告',
                    style: AppTheme.sectionLabel.copyWith(fontSize: 14)),
                const SizedBox(height: 16),
                Container(
                  width: AppTheme.phoneWidth - 64,
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppTheme.cardBorder),
                    gradient: const LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [Color(0xFF172233), Color(0xFF0F1622)],
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const PageHeader(
                        title: '巡检报告',
                        subTitle: '一次任务结束后的摘要视图',
                        badgeText: '已归档',
                      ),
                      const SizedBox(height: 24),
                      // 统计卡片 2x2
                      Row(
                        children: [
                          const Expanded(
                            child: GlassCard(
                              padding: EdgeInsets.all(16),
                              child: StatBlock(
                                value: '6m 28s',
                                label: '巡检耗时',
                                icon: Icons.timer_outlined,
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          const Expanded(
                            child: GlassCard(
                              padding: EdgeInsets.all(16),
                              child: StatBlock(
                                value: '4/4',
                                label: '完成点位',
                                icon: Icons.check_circle_outline,
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
                              child: StatBlock(
                                value: '1 次',
                                label: '高等级告警',
                                icon: Icons.warning_amber_outlined,
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          const Expanded(
                            child: GlassCard(
                              padding: EdgeInsets.all(16),
                              child: StatBlock(
                                value: '2 次',
                                label: '动态避障',
                                icon: Icons.alt_route,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      // 事件列表
                      GlassCard(
                        padding:
                            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                        child: Column(
                          children: [
                            const InfoRow(
                              label: '事件 01',
                              value: '配电柜A 发现疑似烟雾',
                            ),
                            const Divider(
                                color: AppTheme.dividerLine, height: 20),
                            const InfoRow(
                              label: '事件 02',
                              value: '仓储通道纸箱避障成功',
                            ),
                            const Divider(
                                color: AppTheme.dividerLine, height: 20),
                            const InfoRow(
                              label: '处理结果',
                              value: '应急配送完成，车辆已返航',
                              valueBold: true,
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 14),
                      // 导出能力
                      GlassCard(
                        padding:
                            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                        child: const Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('导出能力', style: AppTheme.bodyValue),
                            SizedBox(height: 8),
                            Text(
                              '支持导出图片、视频片段、任务时间线和组会汇报摘要。',
                              style: AppTheme.bodyLabel,
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 20),
                      // 导出按钮
                      Row(
                        children: [
                          const Expanded(
                              child: SmallButton(text: '导出 PDF 报告')),
                          const SizedBox(width: 12),
                          const Expanded(
                              child: SmallButton(text: '分享给老师 / 组员')),
                        ],
                      ),
                      const SizedBox(height: 16),
                      // 返回首页
                      GradientButton(
                        text: '返回设备连接',
                        secondary: true,
                        onTap: () {
                          Navigator.of(context).popUntil((route) => route.isFirst);
                        },
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
