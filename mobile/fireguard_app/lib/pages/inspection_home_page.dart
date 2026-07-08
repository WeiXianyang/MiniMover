import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/tcp_service.dart';
import '../widgets/common_widgets.dart';
import 'map_task_page.dart';
import 'manual_control_page.dart';

/// S02 - 巡检主页
class InspectionHomePage extends StatelessWidget {
  final TcpService tcpService;
  const InspectionHomePage({super.key, required this.tcpService});

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
                Text('S02-巡检主页',
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
                        title: '巡检主页',
                        subTitle: '今日任务总览',
                        badgeText: '自动巡检待命',
                      ),
                      const SizedBox(height: 24),
                      // 当前区域 & 任务
                      GlassCard(
                        padding:
                            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                        child: const Column(
                          children: [
                            InfoRow(label: '当前区域', value: '园区 A 栋一层'),
                            Divider(color: AppTheme.dividerLine, height: 20),
                            InfoRow(label: '当前任务', value: '配电房与仓储通道巡检'),
                          ],
                        ),
                      ),
                      const SizedBox(height: 16),
                      // 统计数值
                      Row(
                        children: [
                          const Expanded(
                            child: GlassCard(
                              padding: EdgeInsets.all(16),
                              child: StatBlock(value: '86%', label: '电量'),
                            ),
                          ),
                          const SizedBox(width: 12),
                          const Expanded(
                            child: GlassCard(
                              padding: EdgeInsets.all(16),
                              child: StatBlock(
                                  value: '4', label: '待巡检点'),
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
                              child: StatBlock(value: '正常', label: '烟雾值'),
                            ),
                          ),
                          const SizedBox(width: 12),
                          const Expanded(
                            child: GlassCard(
                              padding: EdgeInsets.all(16),
                              child: StatBlock(
                                  value: '29°C', label: '机柜环境温度'),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      // 推荐动作
                      GlassCard(
                        padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('推荐动作', style: AppTheme.bodyLabel),
                            const SizedBox(height: 6),
                            const Text(
                              '开始自动巡检，预计 6 分钟完成',
                              style: TextStyle(
                                fontFamily: 'Inter',
                                fontWeight: FontWeight.w700,
                                fontSize: 18,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 20),
                      // 操作按钮
                      GradientButton(
                        text: '开始自动巡检',
                        onTap: () {
                          Navigator.of(context).push(MaterialPageRoute(
                            builder: (_) => MapTaskPage(tcpService: tcpService),
                          ));
                        },
                      ),
                      const SizedBox(height: 12),
                      GradientButton(
                        text: '切换到手动接管',
                        secondary: true,
                        onTap: () {
                          Navigator.of(context).push(MaterialPageRoute(
                            builder: (_) =>
                                ManualControlPage(tcpService: tcpService),
                          ));
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
