import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/tcp_service.dart';
import '../widgets/common_widgets.dart';
import 'delivery_page.dart';
import 'manual_control_page.dart';

/// S04 - 告警详情页面
class AlarmDetailPage extends StatelessWidget {
  final TcpService tcpService;
  const AlarmDetailPage({super.key, required this.tcpService});

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
                Text('S04-告警详情',
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
                        title: '告警详情',
                        subTitle: '视觉 + 传感器联合判定',
                        badgeText: '高等级告警',
                        badgeActive: false,
                      ),
                      const SizedBox(height: 20),
                      // 告警截图占位
                      GlassCard(
                        height: 182,
                        padding: const EdgeInsets.all(12),
                        child: Stack(
                          children: [
                            Center(
                              child: Container(
                                width: 280,
                                height: 140,
                                decoration: BoxDecoration(
                                  borderRadius: BorderRadius.circular(8),
                                  gradient: LinearGradient(
                                    begin: Alignment.topLeft,
                                    end: Alignment.bottomRight,
                                    colors: [
                                      Colors.red.shade900.withOpacity(0.3),
                                      Colors.orange.shade900.withOpacity(0.2),
                                    ],
                                  ),
                                ),
                                child: const Center(
                                  child: Icon(Icons.smoke_free,
                                      color: AppTheme.textSecondary, size: 40),
                                ),
                              ),
                            ),
                            const Positioned(
                              bottom: 8,
                              right: 16,
                              child: Text('疑似烟雾区',
                                  style: AppTheme.bodyValue),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 14),
                      // 传感器数据
                      GlassCard(
                        padding:
                            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                        child: const Column(
                          children: [
                            InfoRow(label: '告警位置', value: '配电柜A 北侧'),
                            Divider(
                                color: AppTheme.dividerLine, height: 20),
                            InfoRow(label: '视觉置信度', value: '0.93'),
                            Divider(
                                color: AppTheme.dividerLine, height: 20),
                            InfoRow(label: '烟雾值', value: '86 ppm'),
                            Divider(
                                color: AppTheme.dividerLine, height: 20),
                            InfoRow(label: '温度', value: '67°C'),
                          ],
                        ),
                      ),
                      const SizedBox(height: 14),
                      // 处置建议
                      GlassCard(
                        padding:
                            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                        child: const Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('处置建议', style: AppTheme.bodyValue),
                            SizedBox(height: 8),
                            Text(
                              '建议先停车并拉起远程接管，同时发起应急物资配送。',
                              style: AppTheme.bodyLabel,
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 20),
                      GradientButton(
                        text: '发起应急配送',
                        onTap: () {
                          Navigator.of(context).push(MaterialPageRoute(
                            builder: (_) =>
                                DeliveryPage(tcpService: tcpService),
                          ));
                        },
                      ),
                      const SizedBox(height: 12),
                      GradientButton(
                        text: '进入远程接管',
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
