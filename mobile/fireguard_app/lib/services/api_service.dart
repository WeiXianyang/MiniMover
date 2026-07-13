import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

/// 传感器数据
class SensorData {
  final double temperature;
  final double humidity;
  final int smoke;
  final int pm25;
  final double pressure;
  final int co2;
  final int light;

  const SensorData({
    this.temperature = 0, this.humidity = 0, this.smoke = 0,
    this.pm25 = 0, this.pressure = 0, this.co2 = 0, this.light = 0,
  });

  factory SensorData.fromJson(Map<String, dynamic> j) => SensorData(
    temperature: (j['temperature'] as num?)?.toDouble() ?? 0,
    humidity: (j['humidity'] as num?)?.toDouble() ?? 0,
    smoke: (j['smoke'] as num?)?.toInt() ?? 0,
    pm25: (j['pm25'] as num?)?.toInt() ?? 0,
    pressure: (j['pressure'] as num?)?.toDouble() ?? 0,
    co2: (j['co2'] as num?)?.toInt() ?? 0,
    light: (j['light'] as num?)?.toInt() ?? 0,
  );
}

/// 小车全状态
class CarStatus {
  final SensorData sensors;
  final double battery;
  final String ip;
  const CarStatus({this.sensors = const SensorData(), this.battery = 0, this.ip = ''});

  factory CarStatus.fromJson(Map<String, dynamic> j) => CarStatus(
    sensors: j['sensors'] != null ? SensorData.fromJson(j['sensors'] as Map<String, dynamic>) : const SensorData(),
    battery: (j['battery'] as num?)?.toDouble() ?? 0,
    ip: (j['ip'] as String?) ?? '',
  );
}

/// HTTP REST 通信 — 对接 api_server.py (Flask :5000)
class ApiService {
  String _host = '192.168.8.188';
  int _port = 5000;
  bool _connected = false;
  final http.Client _client = http.Client();
  Timer? _pollTimer;

  final _statusCtrl = StreamController<CarStatus>.broadcast();
  final _connCtrl = StreamController<bool>.broadcast();

  bool get connected => _connected;
  String get host => _host;
  int get port => _port;
  String get baseUrl => 'http://$_host:$_port';
  String get videoUrl => '$baseUrl/video_feed';
  Stream<CarStatus> get statusStream => _statusCtrl.stream;
  Stream<bool> get connectionChanges => _connCtrl.stream;

  CarStatus? _last;
  CarStatus? get lastStatus => _last;

  void updateConfig(String host, int port) { _host = host; _port = port; }

  Future<bool> connect() async {
    try {
      final r = await _client.get(Uri.parse('$baseUrl/api/health')).timeout(const Duration(seconds: 3));
      if (r.statusCode == 200) {
        _connected = true; _connCtrl.add(true);
        await _fetchStatus();
        _pollTimer?.cancel();
        _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) => _fetchStatus());
        return true;
      }
    } catch (_) {}
    return false;
  }

  void disconnect() {
    _pollTimer?.cancel(); _pollTimer = null;
    _connected = false; _connCtrl.add(false);
  }

  Future<void> _fetchStatus() async {
    try {
      final r = await _client.get(Uri.parse('$baseUrl/api/status')).timeout(const Duration(seconds: 2));
      if (r.statusCode == 200) {
        final j = jsonDecode(r.body);
        if (j['code'] == 0) { _last = CarStatus.fromJson(j['data']); _statusCtrl.add(_last!); }
      }
    } catch (_) {}
  }

  Future<CarStatus?> fetchNow() async { await _fetchStatus(); return _last; }

  // ── 控制 ──
  Future<void> move(String cmd, {int speed = 50, double duration = 0.3}) async {
    if (!_connected) return;
    try {
      await _client.post(Uri.parse('$baseUrl/api/move'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'cmd': cmd, 'speed': speed.clamp(10, 100), 'duration': duration}),
      ).timeout(const Duration(seconds: 2));
    } catch (_) {}
  }

  Future<void> stop() => move('stop', duration: 0);
  Future<void> emergencyStop() => move('stop', duration: 0);

  Future<void> navigate(double x, double y, {double theta = 0}) async {
    if (!_connected) return;
    try {
      await _client.post(Uri.parse('$baseUrl/api/navigate'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'x': x, 'y': y, 'theta': theta}),
      ).timeout(const Duration(seconds: 3));
    } catch (_) {}
  }

  void dispose() { disconnect(); _statusCtrl.close(); _connCtrl.close(); }
}
