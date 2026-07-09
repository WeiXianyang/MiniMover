import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/tcp_service.dart';
import '../widgets/common_widgets.dart';
import '../widgets/page_shell.dart';
import 'report_page.dart';

/// S06 - 手动接管页面
class ManualControlPage extends StatefulWidget {
  final TcpService tcpService;
  final bool embedded;
  const ManualControlPage({
    super.key,
    required this.tcpService,
    this.embedded = false,
  });

  @override
  State<ManualControlPage> createState() => _ManualControlPageState();
}

class _ManualControlPageState extends State<ManualControlPage> {
  Offset _joystickPos = Offset.zero;
  bool _emergencyStopped = false;

  void _onJoystickUpdate(Offset delta) {
    setState(() => _joystickPos = delta);
    final spdXY = (-delta.dy * 100).clamp(-100, 100).toInt();
    final spdZ = (delta.dx * 100).clamp(-100, 100).toInt();
    widget.tcpService.move(spdXY, spdZ);
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
    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('S06-手动接管',
            style: AppTheme.sectionLabel.copyWith(fontSize: 14)),
        const SizedBox(height: 16),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(20),
          decoration: _frameDeco(),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const PageHeader(
                title: '手动接管',
                subTitle: '异常情况下的人机协同',
                badgeText: '接管中',
              ),
              const SizedBox(height: 20),
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
                          Icon(Icons.videocam, color: AppTheme.textSecondary, size: 48),
                          SizedBox(height: 8),
                          Text('实时视频流', style: AppTheme.bodyLabel),
                          Text('MJPEG Stream :6500', style: AppTheme.subtitle),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Center(child: _buildJoystick()),
              const SizedBox(height: 20),
              const Row(
                children: [
                  Expanded(child: SmallButton(text: '录制现场视频')),
                  SizedBox(width: 12),
                  Expanded(child: SmallButton(text: '切换灯带警示')),
                ],
              ),
              const SizedBox(height: 14),
              GestureDetector(
                onTap: _emergencyStop,
                child: Container(
                  width: double.infinity,
                  height: 54,
                  decoration: BoxDecoration(
                    color: _emergencyStopped ? AppTheme.statusGreen : AppTheme.statusRed,
                    borderRadius: BorderRadius.circular(AppTheme.btnRadius),
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    _emergencyStopped ? '已急停' : '急停',
                    style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15, color: Colors.white),
                  ),
                ),
              ),
              const SizedBox(height: 14),
              GradientButton(
                text: '查看巡检报告',
                onTap: () {
                  widget.tcpService.emergencyStop();
                  _push(context, '巡检报告', ReportPage(tcpService: widget.tcpService, embedded: true));
                },
              ),
            ],
          ),
        ),
      ],
    );

    return _wrap(context, content);
  }

  Widget _buildJoystick() {
    return GestureDetector(
      onPanUpdate: (d) {
        final dx = d.localPosition.dx - 80;
        final dy = d.localPosition.dy - 80;
        _onJoystickUpdate(
            Offset((dx / 80).clamp(-1.0, 1.0), (dy / 80).clamp(-1.0, 1.0)));
      },
      onPanEnd: (_) => _onJoystickRelease(),
      child: Container(
        width: 160,
        height: 160,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: AppTheme.cardFill,
          border: Border.all(color: AppTheme.cardBorder, width: 2),
        ),
        child: Center(
          child: Container(
            width: 60,
            height: 60,
            transform: Matrix4.translationValues(
                _joystickPos.dx * 40, _joystickPos.dy * 40, 0),
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: AppTheme.btnGradient,
              ),
            ),
          ),
        ),
      ),
    );
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
        padding: const EdgeInsets.fromLTRB(AppTheme.pagePadding, 16, AppTheme.pagePadding, 8),
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
