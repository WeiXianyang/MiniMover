import 'dart:convert';
import 'package:http/http.dart' as http;

/// 导航栈状态
class NavStackStatus {
  final String container;
  final bool containerRunning;
  final bool patrolReady;
  final String rosDomainId;
  final String hint;
  const NavStackStatus({
    this.container = '', this.containerRunning = false, this.patrolReady = false,
    this.rosDomainId = '', this.hint = '',
  });
  factory NavStackStatus.fromJson(Map<String, dynamic> j) => NavStackStatus(
    container: (j['container'] as String?) ?? '',
    containerRunning: j['container_running'] == true,
    patrolReady: j['patrol_ready'] == true,
    rosDomainId: (j['ros_domain_id'] as String?) ?? '',
    hint: (j['hint'] as String?) ?? '',
  );
}

/// 地图元数据
class NavMapMeta {
  final String map;
  final int width, height;
  final double resolution;
  final List<double> origin;
  const NavMapMeta({this.map = '', this.width = 0, this.height = 0, this.resolution = 0, this.origin = const [0, 0, 0]});
  factory NavMapMeta.fromJson(Map<String, dynamic> j) => NavMapMeta(
    map: (j['map'] as String?) ?? '', width: (j['width'] as num?)?.toInt() ?? 0,
    height: (j['height'] as num?)?.toInt() ?? 0, resolution: (j['resolution'] as num?)?.toDouble() ?? 0,
    origin: (j['origin'] as List<dynamic>?)?.map((e) => (e as num).toDouble()).toList() ?? [0, 0, 0],
  );
}

/// 坐标换算结果
class NavCoordResult {
  final double x, y, pixelX, pixelY;
  const NavCoordResult({this.x = 0, this.y = 0, this.pixelX = 0, this.pixelY = 0});
  factory NavCoordResult.fromJson(Map<String, dynamic> j) => NavCoordResult(
    x: (j['x'] as num?)?.toDouble() ?? 0, y: (j['y'] as num?)?.toDouble() ?? 0,
    pixelX: (j['pixel_x'] as num?)?.toDouble() ?? 0, pixelY: (j['pixel_y'] as num?)?.toDouble() ?? 0,
  );
}

/// 巡逻路线点
class NavPoint {
  final double x, y;
  const NavPoint(this.x, this.y);
  Map<String, dynamic> toJson() => {'x': x, 'y': y};
}

/// 巡逻路线
class NavRoute {
  final List<NavPoint> points;
  final int pointCount;
  final bool patrolActive;
  final bool loop;
  const NavRoute({this.points = const [], this.pointCount = 0, this.patrolActive = false, this.loop = false});
  factory NavRoute.fromJson(Map<String, dynamic> j) {
    final pts = (j['points'] as List<dynamic>?)?.map((e) {
      if (e is Map) return NavPoint((e['x'] as num).toDouble(), (e['y'] as num).toDouble());
      if (e is List) return NavPoint((e[0] as num).toDouble(), (e[1] as num).toDouble());
      return null;
    }).whereType<NavPoint>().toList() ?? [];
    return NavRoute(points: pts, pointCount: (j['point_count'] as num?)?.toInt() ?? pts.length,
      patrolActive: j['patrol_active'] == true, loop: j['loop'] == true);
  }
}

/// 巡逻状态
class PatrolStatus {
  final String status;
  final bool patrolActive;
  final int pointCount;
  final bool loop;
  const PatrolStatus({this.status = '', this.patrolActive = false, this.pointCount = 0, this.loop = false});
  factory PatrolStatus.fromJson(Map<String, dynamic> j) => PatrolStatus(
    status: (j['status'] as String?) ?? '', patrolActive: j['patrol_active'] == true,
    pointCount: (j['point_count'] as num?)?.toInt() ?? 0, loop: j['loop'] == true,
  );
}

/// 导航巡逻 API 服务 — 对接 :5000/api/nav/*
class NavService {
  String _host = '10.227.111.171';
  int _port = 5000;
  final http.Client _client = http.Client();

  String get baseUrl => 'http://$_host:$_port';
  String get mapImageUrl => '$baseUrl/api/nav/map/image';

  void updateConfig(String host, [int port = 5000]) { _host = host; _port = port; }

  Future<Map<String, dynamic>> _post(String path, [Map<String, dynamic>? body]) async {
    final r = await _client.post(Uri.parse('$baseUrl$path'),
      headers: {'Content-Type': 'application/json'}, body: body != null ? jsonEncode(body) : null,
    ).timeout(const Duration(seconds: 50));
    if (r.statusCode == 200) return jsonDecode(r.body) as Map<String, dynamic>;
    throw Exception('HTTP ${r.statusCode}');
  }

  Future<Map<String, dynamic>> _get(String path) async {
    final r = await _client.get(Uri.parse('$baseUrl$path')).timeout(const Duration(seconds: 15));
    if (r.statusCode == 200) return jsonDecode(r.body) as Map<String, dynamic>;
    throw Exception('HTTP ${r.statusCode}');
  }

  // ═══ 导航栈 ═══
  Future<NavStackStatus> stackStatus() async {
    final j = await _get('/api/nav/stack/status');
    return NavStackStatus.fromJson(j['data'] ?? {});
  }

  Future<bool> stackStart({bool waitReady = true, int timeout = 45}) async {
    try {
      final j = await _post('/api/nav/stack/start', {'wait_ready': waitReady, 'timeout': timeout});
      return j['data']?['success'] == true;
    } catch (_) { return false; }
  }

  Future<bool> stackStop() async {
    try { await _post('/api/nav/stack/stop'); return true; } catch (_) { return false; }
  }

  // ═══ 地图 ═══
  Future<NavMapMeta?> fetchMapMeta() async {
    try {
      final j = await _get('/api/nav/map');
      return NavMapMeta.fromJson(j['data'] ?? {});
    } catch (_) { return null; }
  }

  Future<List<int>?> fetchMapImage() async {
    try {
      final r = await _client.get(Uri.parse(mapImageUrl)).timeout(const Duration(seconds: 10));
      if (r.statusCode == 200) return r.bodyBytes;
    } catch (_) {}
    return null;
  }

  // ═══ 坐标换算 ═══
  Future<NavCoordResult?> pixelToMap(int screenX, int screenY, int displayW, int displayH) async {
    try {
      final j = await _post('/api/nav/coord/pixel_to_map', {
        'screen_x': screenX, 'screen_y': screenY, 'display_width': displayW, 'display_height': displayH,
      });
      return NavCoordResult.fromJson(j['data'] ?? {});
    } catch (_) { return null; }
  }

  // ═══ 起点 ═══
  Future<bool> setInitialPose(double x, double y, {double yaw = 0}) async {
    try { await _post('/api/nav/initial_pose', {'x': x, 'y': y, 'yaw': yaw}); return true; } catch (_) { return false; }
  }

  // ═══ 巡逻路线 ═══
  Future<bool> setPatrolRoute(List<NavPoint> points, {bool loop = true}) async {
    try {
      await _post('/api/nav/patrol/route', {'points': points.map((p) => [p.x, p.y]).toList(), 'loop': loop});
      return true;
    } catch (_) { return false; }
  }

  Future<NavRoute?> getPatrolRoute() async {
    try {
      final j = await _get('/api/nav/patrol/route');
      return NavRoute.fromJson(j['data'] ?? {});
    } catch (_) { return null; }
  }

  Future<bool> startPatrol() async {
    try { await _post('/api/nav/patrol/start'); return true; } catch (_) { return false; }
  }

  Future<bool> stopPatrol() async {
    try { await _post('/api/nav/patrol/stop'); return true; } catch (_) { return false; }
  }

  Future<bool> clearPatrolRoute() async {
    try { await _post('/api/nav/patrol/clear'); return true; } catch (_) { return false; }
  }

  Future<PatrolStatus?> patrolStatus() async {
    try {
      final j = await _get('/api/nav/patrol/status');
      return PatrolStatus.fromJson(j['data'] ?? {});
    } catch (_) { return null; }
  }

  Future<bool> setPatrolLoop(bool loop) async {
    try { await _post('/api/nav/patrol/loop', {'loop': loop}); return true; } catch (_) { return false; }
  }

  // ═══ 保存/加载路线 ═══
  Future<List<String>?> listSavedRoutes() async {
    try {
      final j = await _get('/api/nav/patrol/routes');
      return (j['data'] as List<dynamic>?)?.cast<String>();
    } catch (_) { return null; }
  }

  Future<bool> saveRoute(String name, List<NavPoint> points, {double initialX = 0, double initialY = 0, bool loop = true}) async {
    try {
      await _post('/api/nav/patrol/routes/$name', {
        'points': points.map((p) => [p.x, p.y]).toList(), 'initial_pose': {'x': initialX, 'y': initialY, 'yaw': 0}, 'loop': loop,
      });
      return true;
    } catch (_) { return false; }
  }

  Future<NavRoute?> getRouteDetail(String name) async {
    try {
      final j = await _get('/api/nav/patrol/routes/$name');
      return NavRoute.fromJson(j['data'] ?? {});
    } catch (_) { return null; }
  }

  Future<bool> loadRoute(String name, {bool applyInitialPose = true}) async {
    try {
      await _post('/api/nav/patrol/routes/$name/load', {'apply_initial_pose': applyInitialPose});
      return true;
    } catch (_) { return false; }
  }

  void dispose() => _client.close();
}
