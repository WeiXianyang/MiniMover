import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/tcp_service.dart';
import '../widgets/common_widgets.dart';
import 'report_page.dart';

/// S06 - 手动接管页面
class ManualControlPage extends StatefulWidget {
  final TcpService tcpService;
  const ManualControlPage({super.key, required this.tcpService});

  @override
  State<ManualControlPage> createState() => _ManualControlPageState();
}

class _ManualControlPageState extends State<ManualControlPage> {
  Offset _joystickPos = Offset.zero;
  bool _emergencyStopped = false;

  void _onJoystickUpdate(Offset delta) {
    setState(() => _joystickPos = delta);
    // 映射到小车的 xy 和 z 速度
    final speedXY = (-delta.dy * 100).clamp(-100, 100).toInt();
    final speedZ = (delta.dx * 100).clamp(-100, 100).toInt();
    widget.tcpService.move(speedXY, speedZ);
  }

  void _onJoystickRelease() {
    setState(() => _joystickPos = Offset.zero);
    widget.tcpService.move(0, 0);
  }

  void _emergencyStop() {
    setState(() => _emergencyStopped = true);
    widget.tcpService.emergencyStop();
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => _emergencyStopped = false);
    });
  }

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
                Text('S06-手动接管',
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
                        title: '手动接管',
                        subTitle: '异常情况下的人机协同',
                        badgeText: '接管中',
                      ),
                      const SizedBox(height: 20),
                      // 视频画面
                      GlassCard(
                        height: 242,
                        padding: const EdgeInsets.all(2),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(10),
                          child: Container(
                            color: const Color(0xFF0A0F18),
                            child: const Center(
                              child: Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(Icons.videocam,
                                      color: AppTheme.textSecondary, size: 48),
                                  SizedBox(height: 8),
                                  Text('实时视频流',
                                      style: AppTheme.bodyLabel),
                                  Text('MJPEG Stream :6500',
                                      style: AppTheme.subtitle),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),
                      // 虚拟摇杆
                      Center(
                        child: GestureDetector(
                          onPanUpdate: (details) {
                            final dx = details.localPosition.dx - 80;
                            final dy = details.localPosition.dy - 80;
                            _onJoystickUpdate(
                              Offset(
                                (dx / 80).clamp(-1.0, 1.0),
                                (dy / 80).clamp(-1.0, 1.0),
                              ),
                            );
                          },
                          onPanEnd: (_) => _onJoystickRelease(),
                          child: Container(
                            width: 160,
                            height: 160,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: AppTheme.cardFill,
                              border:
                                  Border.all(color: AppTheme.cardBorder, width: 2),
                            ),
                            child: Center(
                              child: Container(
                                width: 60,
                                height: 60,
                                transform: Matrix4.translationValues(
                                  _joystickPos.dx * 40,
                                  _joystickPos.dy * 40,
                                  0,
                                ),
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  gradient: const LinearGradient(
                                    begin: Alignment.topLeft,
                                    end: Alignment.bottomRight,
                                    colors: AppTheme.btnGradient,
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 20),
                      // 功能按钮
                      Row(
                        children: [
                          const Expanded(
                              child: SmallButton(text: '录制现场视频')),
                          const SizedBox(width: 12),
                          const Expanded(
                              child: SmallButton(text: '切换灯带警示')),
                        ],
                      ),
                      const SizedBox(height: 14),
                      // 急停按钮
                      GestureDetector(
                        onTap: _emergencyStop,
                        child: Container(
                          width: AppTheme.cardWidth,
                          height: 54,
                          decoration: BoxDecoration(
                            color: _emergencyStopped
                                ? AppTheme.statusGreen
                                : AppTheme.statusRed,
                            borderRadius:
                                BorderRadius.circular(AppTheme.btnRadius),
                          ),
                          alignment: Alignment.center,
                          child: Text(
                            _emergencyStopped ? '已急停' : '急停',
                            style: const TextStyle(
                              fontFamily: 'Inter',
                              fontWeight: FontWeight.w700,
                              fontSize: 15,
                              color: Colors.white,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 14),
                      GradientButton(
                        text: '查看巡检报告',
                        onTap: () {
                          widget.tcpService.emergencyStop();
                          Navigator.of(context).push(MaterialPageRoute(
                            builder: (_) =>
                                ReportPage(tcpService: widget.tcpService),
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
