import 'dart:convert';
import 'package:http/http.dart' as http;

/// 云平台火情告警
class CloudAlarm {
  final int id;
  final String alarmType;
  final String occurredAt;
  final double confidence;
  final String evidenceUrl;
  final List<String> detectionClasses;
  final String carId;

  const CloudAlarm({
    this.id = 0, this.alarmType = '', this.occurredAt = '',
    this.confidence = 0, this.evidenceUrl = '', this.detectionClasses = const [],
    this.carId = '',
  });

  factory CloudAlarm.fromJson(Map<String, dynamic> j) => CloudAlarm(
    id: (j['id'] as num?)?.toInt() ?? 0,
    alarmType: (j['alarm_type'] as String?) ?? '',
    occurredAt: (j['occurred_at'] as String?) ?? '',
    confidence: (j['confidence'] as num?)?.toDouble() ?? 0,
    evidenceUrl: (j['evidence_url'] as String?) ?? '',
    detectionClasses: (j['detection_classes'] as List<dynamic>?)?.cast<String>() ?? [],
    carId: (j['car_id'] as String?) ?? '',
  );

  String get typeLabel {
    switch (alarmType) {
      case 'confirmed_fire': return '确认火情';
      case 'suspected_smoke': return '疑似烟雾';
      case 'ai_unavailable': return 'AI 不可用';
      default: return alarmType;
    }
  }
}

/// 云平台告警 API — 端口 8000，与小车不同机
class CloudAlarmService {
  static const _base = 'http://8.140.28.233:8000';
  final http.Client _client = http.Client();

  Future<bool> healthCheck() async {
    try {
      final r = await _client.get(Uri.parse('$_base/healthz')).timeout(const Duration(seconds: 3));
      return r.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<List<CloudAlarm>> fetchAlarms({int page = 1, int size = 10}) async {
    try {
      final r = await _client
          .get(Uri.parse('$_base/api/v1/fire-alarms?page=$page&size=$size'))
          .timeout(const Duration(seconds: 5));
      if (r.statusCode == 200) {
        final j = jsonDecode(r.body);
        if (j['code'] == 0) {
          return (j['data'] as List<dynamic>?)
                  ?.map((e) => CloudAlarm.fromJson(e as Map<String, dynamic>))
                  .toList() ??
              [];
        }
      }
    } catch (_) {}
    return [];
  }

  Future<CloudAlarm?> fetchAlarmDetail(int id) async {
    try {
      final r = await _client
          .get(Uri.parse('$_base/api/v1/fire-alarms/$id'))
          .timeout(const Duration(seconds: 5));
      if (r.statusCode == 200) {
        final j = jsonDecode(r.body);
        if (j['code'] == 0) return CloudAlarm.fromJson(j['data']);
      }
    } catch (_) {}
    return null;
  }

  /// 取最新一条告警
  Future<CloudAlarm?> fetchLatest() async {
    final list = await fetchAlarms(page: 1, size: 1);
    return list.isNotEmpty ? list.first : null;
  }

  void dispose() => _client.close();
}
