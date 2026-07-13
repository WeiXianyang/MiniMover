import 'dart:async';
import 'package:flutter/foundation.dart';
import 'api_service.dart';

class CarState extends ChangeNotifier {
  final ApiService api;
  CarState({required this.api}) { _subscribe(); }

  bool get connected => api.connected;
  String get host => api.host;
  int get port => api.port;

  CarStatus? _status;
  CarStatus? get status => _status;
  double get batteryVoltage => _status?.battery ?? 0;
  int get batteryPercent {
    if (batteryVoltage <= 0) return 0;
    return ((batteryVoltage - 9.0) / (12.6 - 9.0) * 100).round().clamp(0, 100);
  }
  SensorData get sensors => _status?.sensors ?? const SensorData();

  String get deviceStatusDisplay {
    if (!connected) return '未连接';
    final p = <String>[];
    if (batteryVoltage > 0) p.add('${batteryVoltage.toStringAsFixed(1)}V');
    if (sensors.temperature > 0) p.add('${sensors.temperature.toStringAsFixed(1)}°C');
    return p.join(' · ');
  }

  String get batteryDisplay => (!connected || batteryVoltage <= 0) ? '—' : '${batteryVoltage.toStringAsFixed(1)}V (${batteryPercent}%)';
  String get currentAreaDisplay => '—';
  String get deviceVersion => '—';

  // ── 运动 ──
  int _speed = 50;
  int get speed => _speed;
  void setSpeed(int v) { _speed = v.clamp(10, 100); notifyListeners(); }

  // ── 任务（本地维护） ──
  bool _taskRunning = false, _taskPaused = false; double _taskProgress = 0.0;
  bool get taskRunning => _taskRunning; bool get taskPaused => _taskPaused; double get taskProgress => _taskProgress;
  String get currentTaskDisplay => connected ? (taskRunning ? (taskPaused ? '已暂停' : '巡检中') : '待命') : '—';

  // ── 告警 ──
  bool _hasAlarm = false; String _alarmLocation = ''; double _alarmConfidence = 0.0; String _alarmLevel = '';
  bool get hasAlarm => _hasAlarm; String get alarmLocation => _alarmLocation;
  double get alarmConfidence => _alarmConfidence; String get alarmLevel => _alarmLevel;

  // ── 配送 ──
  bool _deliveryActive = false; double _deliveryProgress = 0.0; String _deliveryStatus = '';
  bool get deliveryActive => _deliveryActive; double get deliveryProgress => _deliveryProgress; String get deliveryStatus => _deliveryStatus;

  // ── 事件日志 ──
  final List<String> _eventLog = [];
  List<String> get eventLog => List.unmodifiable(_eventLog);
  int _completedPoints = 0, _totalPoints = 4;
  int get completedPoints => _completedPoints; int get totalPoints => _totalPoints;

  StreamSubscription<CarStatus>? _sSub; StreamSubscription<bool>? _cSub;
  void _subscribe() { _cSub = api.connectionChanges.listen((_) => notifyListeners()); _sSub = api.statusStream.listen((s) { _status = s; notifyListeners(); }); }

  // ═══ 操作 ═══
  Future<bool> connect(String host, int port) async { api.updateConfig(host, port); final ok = await api.connect(); notifyListeners(); return ok; }
  void disconnect() { api.disconnect(); _taskRunning = false; notifyListeners(); }

  void moveForward() => api.move('forward', speed: _speed);
  void moveBackward() => api.move('backward', speed: _speed);
  void moveLeft() => api.move('left', speed: _speed);
  void moveRight() => api.move('right', speed: _speed);
  void shiftLeft() => api.move('left_shift', speed: _speed);
  void shiftRight() => api.move('right_shift', speed: _speed);
  void emergencyStop() { api.emergencyStop(); _addLog('急停'); notifyListeners(); }
  void stop() => api.stop();

  void startTask() { _taskRunning = true; _taskPaused = false; _taskProgress = 0.0; _addLog('巡检开始'); notifyListeners(); }
  void pauseTask() { _taskPaused = true; _addLog('暂停'); notifyListeners(); }
  void resumeTask() { _taskPaused = false; _addLog('恢复'); notifyListeners(); }
  void abortTask() { _taskRunning = false; _addLog('中止'); notifyListeners(); }
  void advanceProgress(double d) { _taskProgress = (_taskProgress + d).clamp(0.0, 1.0); notifyListeners(); }
  void startDelivery() { _deliveryActive = true; _deliveryProgress = 0.0; _deliveryStatus = '配送中'; notifyListeners(); }
  void updateDeliveryProgress(double p) { _deliveryProgress = p; if (p >= 1) { _deliveryActive = false; _deliveryStatus = '已送达'; } notifyListeners(); }
  void cancelDelivery() { _deliveryActive = false; _deliveryStatus = '已取消'; notifyListeners(); }
  void triggerAlarm({required String l, required double c, required String lv}) { _hasAlarm = true; _alarmLocation = l; _alarmConfidence = c; _alarmLevel = lv; _addLog('[$lv] $l'); notifyListeners(); }
  void clearAlarm() { _hasAlarm = false; notifyListeners(); }

  void _addLog(String m) { final t = DateTime.now().toIso8601String().substring(11,19); _eventLog.add('[$t] $m'); if (_eventLog.length > 100) _eventLog.removeAt(0); }

  @override
  void dispose() { _sSub?.cancel(); _cSub?.cancel(); api.dispose(); super.dispose(); }
}
