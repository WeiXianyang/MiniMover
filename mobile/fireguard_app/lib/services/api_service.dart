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
  final GpsData? gps;

  const SensorData({
    this.temperature = 0, this.humidity = 0, this.smoke = 0,
    this.pm25 = 0, this.pressure = 0, this.co2 = 0, this.light = 0,
    this.gps,
  });

  factory SensorData.fromJson(Map<String, dynamic> j) => SensorData(
    temperature: (j['temperature'] as num?)?.toDouble() ?? 0,
    humidity: (j['humidity'] as num?)?.toDouble() ?? 0,
    smoke: (j['smoke'] as num?)?.toInt() ?? 0,
    pm25: (j['pm25'] as num?)?.toInt() ?? 0,
    pressure: (j['pressure'] as num?)?.toDouble() ?? 0,
    co2: (j['co2'] as num?)?.toInt() ?? 0,
    light: (j['light'] as num?)?.toInt() ?? 0,
    gps: j['gps'] != null ? GpsData.fromJson(j['gps'] as Map<String, dynamic>) : null,
  );
}

/// GPS 数据
class GpsData {
  final double lat;
  final double lon;
  const GpsData({this.lat = 0, this.lon = 0});

  factory GpsData.fromJson(Map<String, dynamic> j) => GpsData(
    lat: (j['lat'] as num?)?.toDouble() ?? 0,
    lon: (j['lon'] as num?)?.toDouble() ?? 0,
  );

  bool get valid => lat != 0 || lon != 0;
  String get display => valid ? '${lat.toStringAsFixed(5)}, ${lon.toStringAsFixed(5)}' : '—';
}

/// 摄像头流信息
class CameraInfo {
  final String mjpeg;
  final String rosStream;
  final String snapshot;
  const CameraInfo({this.mjpeg = '', this.rosStream = '', this.snapshot = ''});

  factory CameraInfo.fromJson(Map<String, dynamic> j) => CameraInfo(
    mjpeg: (j['mjpeg'] as String?) ?? '',
    rosStream: (j['ros_stream'] as String?) ?? '',
    snapshot: (j['snapshot'] as String?) ?? '',
  );
}

/// 地图元数据
class MapMeta {
  final int width;
  final int height;
  final double resolution;
  final List<double> origin;
  const MapMeta({this.width = 0, this.height = 0, this.resolution = 0, this.origin = const [0, 0, 0]});

  factory MapMeta.fromJson(Map<String, dynamic> j) => MapMeta(
    width: (j['width'] as num?)?.toInt() ?? 0,
    height: (j['height'] as num?)?.toInt() ?? 0,
    resolution: (j['resolution'] as num?)?.toDouble() ?? 0,
    origin: (j['origin'] as List<dynamic>?)?.map((e) => (e as num).toDouble()).toList() ?? [0, 0, 0],
  );
}

/// 音频录制状态
class AudioRecordInfo {
  final String recordId;
  final int size;
  final String msg;
  const AudioRecordInfo({this.recordId = '', this.size = 0, this.msg = ''});

  factory AudioRecordInfo.fromJson(Map<String, dynamic> j) => AudioRecordInfo(
    recordId: (j['record_id'] as String?) ?? '',
    size: (j['size'] as num?)?.toInt() ?? 0,
    msg: (j['msg'] as String?) ?? '',
  );
}

/// HTTP REST 通信 — 对接 api_server.py (Flask :5000)
class ApiService {
  String _host = '10.227.111.171';
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
  String get videoUrl => 'http://$_host:8080/stream?topic=/camera/color/image_raw';
  String get mapImageUrl => '$baseUrl/api/map_image';
  Stream<CarStatus> get statusStream => _statusCtrl.stream;
  Stream<bool> get connectionChanges => _connCtrl.stream;

  CarStatus? _last;
  CarStatus? get lastStatus => _last;

  void updateConfig(String host, int port) { _host = host; _port = port; }

  // ═══ 连接 ═══
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

  // ═══ 运动控制 ═══
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

  // ═══ 导航 ═══
  Future<void> navigate(double x, double y, {double theta = 0}) async {
    if (!_connected) return;
    try {
      await _client.post(Uri.parse('$baseUrl/api/navigate'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'x': x, 'y': y, 'theta': theta}),
      ).timeout(const Duration(seconds: 3));
    } catch (_) {}
  }

  // ═══ 传感器 ═══
  Future<SensorData?> fetchSensors() async {
    try {
      final r = await _client.get(Uri.parse('$baseUrl/api/sensors')).timeout(const Duration(seconds: 2));
      if (r.statusCode == 200) {
        final j = jsonDecode(r.body);
        if (j['code'] == 0) return SensorData.fromJson(j['data']);
      }
    } catch (_) {}
    return null;
  }

  // ═══ 摄像头 ═══
  Future<CameraInfo?> fetchCameraInfo() async {
    try {
      final r = await _client.get(Uri.parse('$baseUrl/api/camera')).timeout(const Duration(seconds: 2));
      if (r.statusCode == 200) {
        final j = jsonDecode(r.body);
        if (j['code'] == 0) return CameraInfo.fromJson(j['data']);
      }
    } catch (_) {}
    return null;
  }

  // ═══ 地图 ═══
  Future<MapMeta?> fetchMapMeta() async {
    try {
      final r = await _client.get(Uri.parse('$baseUrl/api/map')).timeout(const Duration(seconds: 2));
      if (r.statusCode == 200) {
        final j = jsonDecode(r.body);
        if (j['code'] == 0) return MapMeta.fromJson(j['data']);
      }
    } catch (_) {}
    return null;
  }

  // ═══ 音频 ═══
  Future<List<String>?> fetchAudioDevices() async {
    try {
      final r = await _client.get(Uri.parse('$baseUrl/api/audio/devices')).timeout(const Duration(seconds: 2));
      if (r.statusCode == 200) {
        final j = jsonDecode(r.body);
        if (j['code'] == 0) return (j['data'] as List<dynamic>?)?.cast<String>();
      }
    } catch (_) {}
    return null;
  }

  Future<AudioRecordInfo?> startRecording({int? duration}) async {
    try {
      final body = <String, dynamic>{};
      if (duration != null) body['duration'] = duration;
      final r = await _client.post(Uri.parse('$baseUrl/api/audio/record/start'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 3));
      if (r.statusCode == 200) {
        final j = jsonDecode(r.body);
        if (j['code'] == 0) return AudioRecordInfo.fromJson(j['data']);
      }
    } catch (_) {}
    return null;
  }

  Future<AudioRecordInfo?> stopRecording() async {
    try {
      final r = await _client.post(Uri.parse('$baseUrl/api/audio/record/stop')).timeout(const Duration(seconds: 3));
      if (r.statusCode == 200) {
        final j = jsonDecode(r.body);
        if (j['code'] == 0) return AudioRecordInfo.fromJson(j['data']);
      }
    } catch (_) {}
    return null;
  }

  Future<Map<String, dynamic>?> getRecordingStatus() async {
    try {
      final r = await _client.get(Uri.parse('$baseUrl/api/audio/record/status')).timeout(const Duration(seconds: 2));
      if (r.statusCode == 200) {
        final j = jsonDecode(r.body);
        if (j['code'] == 0) return j['data'] as Map<String, dynamic>;
      }
    } catch (_) {}
    return null;
  }

  String getRecordUrl(String recordId) => '$baseUrl/api/audio/record/$recordId.wav';

  /// 下载录音 WAV 文件，返回字节数据
  Future<List<int>?> downloadRecord(String recordId) async {
    try {
      final r = await _client.get(Uri.parse(getRecordUrl(recordId))).timeout(const Duration(seconds: 10));
      if (r.statusCode == 200 && r.bodyBytes.isNotEmpty) return r.bodyBytes;
    } catch (_) {}
    return null;
  }

  Future<bool> playAudioFile(String filePath) async {
    try {
      final r = await _client.post(Uri.parse('$baseUrl/api/audio/play')).timeout(const Duration(seconds: 5));
      return r.statusCode == 200;
    } catch (_) {}
    return false;
  }

  Future<String?> ttsSay(String text, {String lang = 'zh'}) async {
    try {
      final r = await _client.post(Uri.parse('$baseUrl/api/audio/say'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'text': text, 'lang': lang}),
      ).timeout(const Duration(seconds: 5));
      if (r.statusCode == 200) {
        final j = jsonDecode(r.body);
        if (j['code'] == 0) return j['msg'] as String?;
      }
    } catch (_) {}
    return null;
  }

  Future<bool> audioStop() async {
    try {
      final r = await _client.post(Uri.parse('$baseUrl/api/audio/stop')).timeout(const Duration(seconds: 2));
      return r.statusCode == 200;
    } catch (_) {}
    return false;
  }

  void dispose() { disconnect(); _statusCtrl.close(); _connCtrl.close(); }
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
