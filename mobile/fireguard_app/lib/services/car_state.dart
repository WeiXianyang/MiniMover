import 'dart:async';
import 'package:flutter/foundation.dart';
import 'tcp_service.dart';

/// 小车集中状态管理 — 通过 ChangeNotifier 通知 UI 刷新
class CarState extends ChangeNotifier {
  final TcpService tcpService;

  CarState({required this.tcpService}) {
    _subscribe();
  }

  // ── 连接状态 ──
  bool get connected => tcpService.connected;
  String get host => tcpService.host;
  int get port => tcpService.port;

  // ── 设备信息 ──
  String get deviceVersion => tcpService.deviceVersion;
  double get batteryVoltage => tcpService.batteryVoltage;
  int get batteryPercent {
    // 电压 → 电量百分比估算 (8.4V满电, 6.5V低电)
    if (batteryVoltage <= 0) return 0;
    final pct = ((batteryVoltage - 6.5) / (8.4 - 6.5) * 100).round();
    return pct.clamp(0, 100);
  }

  // ── 运动状态 ──
  CarSpeed? get currentSpeed => tcpService.currentSpeed;
  bool get stabilizeOn => tcpService.stabilizeState > 0;

  // ── 摄像头 ──
  int get cameraType => tcpService.cameraType;
  String get cameraTypeLabel {
    switch (cameraType) {
      case 1:
        return 'USB 摄像头';
      case 2:
        return '深度相机';
      default:
        return '深度相机';
    }
  }

  // ── 视频录制 ──
  bool _isRecording = false;
  bool get isRecording => _isRecording;

  // ── 灯带 ──
  bool _warningLight = false;
  bool get warningLightOn => _warningLight;

  // ── 巡检任务状态（App 本地维护） ──
  bool _taskRunning = false;
  bool _taskPaused = false;
  double _taskProgress = 0.0;
  String _currentArea = '配电柜A';
  int _totalPoints = 4;
  int _completedPoints = 0;

  bool get taskRunning => _taskRunning;
  bool get taskPaused => _taskPaused;
  double get taskProgress => _taskProgress;
  String get currentArea => _currentArea;
  int get totalPoints => _totalPoints;
  int get completedPoints => _completedPoints;
  int get remainingPoints => _totalPoints - _completedPoints;

  // ── 告警 ──
  bool _hasAlarm = false;
  String _alarmLocation = '';
  double _alarmConfidence = 0.0;
  String _alarmLevel = '';

  bool get hasAlarm => _hasAlarm;
  String get alarmLocation => _alarmLocation;
  double get alarmConfidence => _alarmConfidence;
  String get alarmLevel => _alarmLevel;

  // ── 事件日志 ──
  final List<String> _eventLog = [];
  List<String> get eventLog => List.unmodifiable(_eventLog);

  // ── 内部订阅 ──
  StreamSubscription<CarResponse>? _responseSub;
  StreamSubscription<bool>? _connSub;

  void _subscribe() {
    _connSub = tcpService.connectionChanges.listen((connected) {
      notifyListeners();
    });

    _responseSub = tcpService.responses.listen((r) {
      notifyListeners();
    });
  }

  // ═══════════════════════════════════════════
  // 控制操作（封装 TcpService + 本地状态）
  // ═══════════════════════════════════════════

  Future<bool> connect(String host, int port) async {
    tcpService.updateConfig(host, port);
    final ok = await tcpService.connect();
    if (ok) {
      tcpService.enterRemoteMode();
    }
    notifyListeners();
    return ok;
  }

  void disconnect() {
    tcpService.disconnect();
    _taskRunning = false;
    _taskPaused = false;
    _taskProgress = 0;
    notifyListeners();
  }

  void move(int forward, int lateral) {
    tcpService.move(forward, lateral);
  }

  void emergencyStop() {
    tcpService.emergencyStop();
    _addEvent('急停触发');
    notifyListeners();
  }

  void toggleWarningLight() {
    _warningLight = !_warningLight;
    if (_warningLight) {
      tcpService.setLight(255, 0, 0); // 红色警示
      tcpService.beep(200); // 短促蜂鸣
    } else {
      tcpService.setLight(0, 0, 0); // 关灯
      tcpService.beep(0);
    }
    notifyListeners();
  }

  void startRecordVideo() {
    _isRecording = true;
    tcpService.startRecordVideo();
    _addEvent('开始录制视频');
    notifyListeners();
  }

  void stopRecordVideo() {
    _isRecording = false;
    tcpService.stopRecordVideo();
    _addEvent('停止录制视频');
    notifyListeners();
  }

  void captureImage() {
    tcpService.captureImage();
    _addEvent('截取现场图片');
  }

  // ── 任务控制 ──

  void startTask() {
    _taskRunning = true;
    _taskPaused = false;
    _taskProgress = 0.0;
    _completedPoints = 0;
    _addEvent('自动巡检开始 — 预计 6 分钟');
    notifyListeners();
  }

  void pauseTask() {
    _taskPaused = true;
    tcpService.move(0, 0); // 停车
    _addEvent('任务已暂停');
    notifyListeners();
  }

  void resumeTask() {
    _taskPaused = false;
    _addEvent('任务已恢复');
    notifyListeners();
  }

  void abortTask() {
    _taskRunning = false;
    _taskPaused = false;
    tcpService.move(0, 0); // 停车
    _addEvent('巡检已中止 — 车辆待命');
    notifyListeners();
  }

  /// 模拟任务进度（后续可对接真实定位数据）
  void advanceProgress(double delta) {
    _taskProgress = (_taskProgress + delta).clamp(0.0, 1.0);
    if (_taskProgress >= 1.0) {
      _taskRunning = false;
      _completedPoints = _totalPoints;
      _addEvent('巡检完成');
    }
    notifyListeners();
  }

  // ── 告警 ──

  void triggerAlarm({
    required String location,
    required double confidence,
    required String level,
  }) {
    _hasAlarm = true;
    _alarmLocation = location;
    _alarmConfidence = confidence;
    _alarmLevel = level;
    _addEvent('[$level] $location — 置信度 $confidence');
    // 告警时自动停车
    tcpService.move(0, 0);
    notifyListeners();
  }

  void clearAlarm() {
    _hasAlarm = false;
    _alarmLocation = '';
    _alarmConfidence = 0;
    _alarmLevel = '';
    notifyListeners();
  }

  // ── 配送 ──

  bool _deliveryActive = false;
  double _deliveryProgress = 0.0;
  String _deliveryStatus = '';

  bool get deliveryActive => _deliveryActive;
  double get deliveryProgress => _deliveryProgress;
  String get deliveryStatus => _deliveryStatus;

  void startDelivery() {
    _deliveryActive = true;
    _deliveryProgress = 0.0;
    _deliveryStatus = '配送中';
    _addEvent('应急配送已发起');
    notifyListeners();
  }

  void updateDeliveryProgress(double pct) {
    _deliveryProgress = pct;
    if (pct >= 1.0) {
      _deliveryActive = false;
      _deliveryStatus = '已送达';
      _addEvent('配送完成 — 待签收');
    }
    notifyListeners();
  }

  void cancelDelivery() {
    _deliveryActive = false;
    _deliveryStatus = '已取消';
    _addEvent('配送已取消 — 返回待命点');
    tcpService.move(0, 0);
    notifyListeners();
  }

  // ── 内部 ──

  void _addEvent(String msg) {
    final ts = DateTime.now().toIso8601String().substring(11, 19); // HH:mm:ss
    _eventLog.add('[$ts] $msg');
    if (_eventLog.length > 100) _eventLog.removeAt(0); // 保留最近 100 条
  }

  @override
  void dispose() {
    _responseSub?.cancel();
    _connSub?.cancel();
    super.dispose();
  }
}
