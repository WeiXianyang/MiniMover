import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/tcp_service.dart';
import '../widgets/common_widgets.dart';

/// S05 - 定点配送页面
class DeliveryPage extends StatelessWidget {
  final TcpService tcpService;
  const DeliveryPage({super.key, required this.tcpService});

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
                Text('S05-定点配送',
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
                        title: '定点配送',
                        subTitle: '同一地图上的应急调度',
                        badgeText: '配送中',
                      ),
                      const SizedBox(height: 20),
                      // 配送信息
                      GlassCard(
                        padding:
                            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                        child: const Column(
                          children: [
                            InfoRow(
                                label: '配送物资', value: '灭火器模型 / 急救包'),
                            Divider(
                                color: AppTheme.dividerLine, height: 20),
                            InfoRow(label: '起点', value: '应急物资点D'),
                            Divider(
                                color: AppTheme.dividerLine, height: 20),
                            InfoRow(label: '终点', value: '配电柜A'),
                          ],
                        ),
                      ),
                      const SizedBox(height: 14),
                      // 配送路径
                      GlassCard(
                        padding:
                            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('配送路径', style: AppTheme.bodyLabel),
                            const SizedBox(height: 8),
                            const Text(
                              'D 点装载 → 主通道 → 配电柜A',
                              style: TextStyle(
                                fontFamily: 'Inter',
                                fontWeight: FontWeight.w700,
                                fontSize: 16,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                            const SizedBox(height: 16),
                            ClipRRect(
                              borderRadius: BorderRadius.circular(4),
                              child: LinearProgressIndicator(
                                value: 0.68,
                                minHeight: 4,
                                backgroundColor: AppTheme.cardBorder,
                                color: AppTheme.accent,
                              ),
                            ),
                            const SizedBox(height: 8),
                            const Text(
                              '已完成 68%，当前绕过临时障碍物后继续前进。',
                              style: AppTheme.bodyLabel,
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 14),
                      // 任务状态
                      GlassCard(
                        padding:
                            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                        child: const Column(
                          children: [
                            InfoRow(label: '任务状态', value: '配送中'),
                            Divider(
                                color: AppTheme.dividerLine, height: 20),
                            InfoRow(label: '载荷舱', value: '已锁定'),
                            Divider(
                                color: AppTheme.dividerLine, height: 20),
                            InfoRow(label: '目标确认', value: '待现场人员签收'),
                          ],
                        ),
                      ),
                      const SizedBox(height: 20),
                      GradientButton(
                        text: '取消配送并返回待命点',
                        secondary: true,
                        onTap: () => Navigator.of(context).pop(),
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
