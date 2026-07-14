import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/fleet_info.dart';

/// 编队管理服务 — 对接多车协同调度中心 (multi_car_coordinator.py, 端口 8888)。
///
/// 通信拓扑：
///   Flutter App ──HTTP──▶ Coordinator (:8888) ──HTTP──▶ Car A (:5000)
///                                                   ──▶ Car B (:5000)
///
/// 协调器提供车辆注册表、状态轮询、广播/单车运动、队形控制、碰撞检测和协同展示。
class FleetService {
  String _host = '';
  int _port = 8888;
  FleetState _state = const FleetState();

  Timer? _pollTimer;
  Timer? _elapsedTimer;
  http.Client? _client;

  final StreamController<FleetState> _stateController =
      StreamController<FleetState>.broadcast();

  FleetState get state => _state;
  Stream<FleetState> get stateStream => _stateController.stream;
  bool get connected => _client != null;

  // ── 预定义运动指令 ──
  static const moveCommands = [
    'forward', 'backward', 'left', 'right',
    'rotate_left', 'rotate_right', 'left_shift', 'right_shift', 'stop',
  ];

  // ── 队形类型 ──
  static const formationTypes = ['line', 'row', 'triangle'];
  static const formationLabels = {
    'line': '纵队',
    'row': '横排',
    'triangle': '三角',
  };

  // ═══════════════════════════════════════════════════════════
  // 连接管理
  // ═══════════════════════════════════════════════════════════

  /// 连接到协调器并拉取车辆列表。
  Future<String?> connectCoordinator(String host, int port) async {
    _host = host;
    _port = port;
    _client?.close();
    _client = http.Client();

    _state = _state.copyWith(
      status: FleetStatus.connecting,
      coordinatorHost: host,
      coordinatorPort: port,
    );
    _notify();

    // 先拉取车辆注册表
    final cars = await _fetchCars();
    if (cars == null) {
      _client?.close();
      _client = null;
      _state = const FleetState(status: FleetStatus.idle);
      _notify();
      return '无法连接协调器 $host:$port，请检查地址和服务状态';
    }
    if (cars.isEmpty) {
      _client?.close();
      _client = null;
      _state = const FleetState(status: FleetStatus.idle);
      _notify();
      return '协调器上没有已注册的车辆，请先在协调器上注册车辆';
    }

    // 确定主车：取第一辆车，后续可扩展为匹配当前连接 IP
    final leaderId = cars.first.id;

    _state = FleetState(
      status: FleetStatus.ready,
      cars: cars,
      leaderId: leaderId,
      coordinatorHost: host,
      coordinatorPort: port,
    );
    _notify();

    // 启动状态轮询
    _startPolling();
    return null; // null 表示成功
  }

  /// 断开协调器连接。
  void disconnectCoordinator() {
    _pollTimer?.cancel();
    _pollTimer = null;
    _elapsedTimer?.cancel();
    _elapsedTimer = null;
    _client?.close();
    _client = null;
    _host = '';
    _state = const FleetState(status: FleetStatus.idle);
    _notify();
  }

  // ═══════════════════════════════════════════════════════════
  // 状态轮询
  // ═══════════════════════════════════════════════════════════

  void _startPolling() {
    _pollTimer?.cancel();
    // 先立即拉取一次
    _pollStatus();
    _pollTimer = Timer.periodic(const Duration(seconds: 3), (_) => _pollStatus());
  }

  Future<void> _pollStatus() async {
    if (_client == null) return;
    try {
      final response = await _client!.get(
        _url('/api/status'),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode != 200) return;
      final body = json.decode(response.body) as Map<String, dynamic>;
      if (body['code'] != 0) return;

      final carsData = body['cars'] as Map<String, dynamic>? ?? {};
      final positions = body['positions'] as Map<String, dynamic>? ?? {};
      final collisionsData = body['collisions'] as Map<String, dynamic>? ?? {};

      // 更新车辆数据
      final updatedCars = <CarInfo>[];
      for (final car in _state.cars) {
        final carStatus = carsData[car.id];
        if (carStatus == null) {
          updatedCars.add(car.copyWith(online: false));
          continue;
        }

        final data = (carStatus as Map<String, dynamic>)['data'] as Map<String, dynamic>?;
        final connected = (carStatus['code'] == 0) && data != null;
        final pos = positions[car.id] as List<dynamic>?;
        final sensors = data?['sensors'] as Map<String, dynamic>?;

        updatedCars.add(car.copyWith(
          online: connected,
          batteryVoltage: (data?['battery'] as num?)?.toDouble() ?? car.batteryVoltage,
          posX: pos != null && pos.length >= 2 ? (pos[0] as num).toDouble() : car.posX,
          posY: pos != null && pos.length >= 2 ? (pos[1] as num).toDouble() : car.posY,
          temperature: (sensors?['temperature'] as num?)?.toDouble() ?? car.temperature,
          humidity: (sensors?['humidity'] as num?)?.toDouble() ?? car.humidity,
          smoke: (sensors?['smoke'] as num?)?.toDouble() ?? car.smoke,
          pm25: (sensors?['pm25'] as num?)?.toDouble() ?? car.pm25,
          ip: (data?['ip'] as String?) ?? car.ip,
        ));
      }

      // 碰撞告警
      final collisions = <String, CollisionAlert>{};
      for (final entry in collisionsData.entries) {
        collisions[entry.key] = CollisionAlert.fromCoordinator(
          entry.key,
          entry.value as Map<String, dynamic>,
        );
      }

      _state = _state.copyWith(
        cars: updatedCars,
        collisions: collisions,
        // 如果有活跃碰撞，标记行动状态
        status: collisions.isNotEmpty &&
                collisions.values.any((c) => c.level == CollisionLevel.critical) &&
                _state.status == FleetStatus.moving
            ? FleetStatus.stopped
            : _state.status,
      );
      _notify();
    } catch (_) {
      // 静默处理：网络抖动不改变 online 状态
      // 连续失败才标记断开（由调用方处理）
    }
  }

  // ═══════════════════════════════════════════════════════════
  // 车辆注册表拉取
  // ═══════════════════════════════════════════════════════════

  Future<List<CarInfo>?> _fetchCars() async {
    if (_client == null) return null;
    try {
      final response = await _client!.get(
        _url('/api/cars'),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode != 200) return null;
      final body = json.decode(response.body) as Map<String, dynamic>;
      if (body['code'] != 0) return null;

      final carsData = body['cars'] as Map<String, dynamic>? ?? {};
      final cars = <CarInfo>[];
      for (final entry in carsData.entries) {
        final info = entry.value as Map<String, dynamic>;
        cars.add(CarInfo(
          id: entry.key,
          name: entry.key, // 默认用车 ID 作为名称
          ip: info['ip'] as String? ?? '',
          httpPort: (info['port'] as num?)?.toInt() ?? 5000,
          role: cars.isEmpty ? CarRole.leader : CarRole.follower,
          online: false, // 首次拉取时标记为离线，等 poll 更新
        ));
      }
      return cars;
    } catch (_) {
      return null;
    }
  }

  // ═══════════════════════════════════════════════════════════
  // 运动控制
  // ═══════════════════════════════════════════════════════════

  /// 向所有车辆广播运动指令。
  Future<Map<String, dynamic>?> moveAll(
    String cmd, {
    int speed = 50,
    double duration = 0.5,
  }) async {
    if (_client == null) return null;
    try {
      final response = await _client!.post(
        _url('/api/move_all'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'cmd': cmd,
          'speed': speed,
          'duration': duration,
        }),
      ).timeout(const Duration(seconds: 8));

      final body = json.decode(response.body) as Map<String, dynamic>;

      // 如果运动开始，更新状态
      if (body['code'] == 0 && cmd != 'stop') {
        _state = _state.copyWith(status: FleetStatus.moving);
        _notify();
      } else if (cmd == 'stop') {
        _state = _state.copyWith(status: FleetStatus.stopped);
        _notify();
      }

      return body;
    } catch (_) {
      return {'code': -1, 'msg': '协调器通信失败'};
    }
  }

  /// 向指定单车发送运动指令。
  Future<Map<String, dynamic>?> moveOne(
    String carId,
    String cmd, {
    int speed = 50,
    double duration = 0.5,
  }) async {
    if (_client == null) return null;
    try {
      final response = await _client!.post(
        _url('/api/move_one'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'car_id': carId,
          'cmd': cmd,
          'speed': speed,
          'duration': duration,
        }),
      ).timeout(const Duration(seconds: 8));
      return json.decode(response.body) as Map<String, dynamic>;
    } catch (_) {
      return {'code': -1, 'msg': '协调器通信失败'};
    }
  }

  // ═══════════════════════════════════════════════════════════
  // 队形控制
  // ═══════════════════════════════════════════════════════════

  /// 应用编队队形。
  Future<Map<String, dynamic>?> applyFormation(
    String type, {
    double spacing = 2.0,
    List<String>? carIds,
  }) async {
    if (_client == null) return null;
    try {
      final bodyMap = <String, dynamic>{
        'type': type,
        'spacing': spacing,
      };
      if (carIds != null && carIds.isNotEmpty) {
        bodyMap['car_ids'] = carIds;
      }
      final response = await _client!.post(
        _url('/api/formation'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode(bodyMap),
      ).timeout(const Duration(seconds: 10));
      return json.decode(response.body) as Map<String, dynamic>;
    } catch (_) {
      return {'code': -1, 'msg': '协调器通信失败'};
    }
  }

  // ═══════════════════════════════════════════════════════════
  // 车辆管理
  // ═══════════════════════════════════════════════════════════

  /// 向协调器注册新车。
  Future<Map<String, dynamic>?> registerCar(
    String carId,
    String ip, {
    int port = 5000,
  }) async {
    if (_client == null) return null;
    try {
      final response = await _client!.post(
        _url('/api/register'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'car_id': carId,
          'ip': ip,
          'port': port,
        }),
      ).timeout(const Duration(seconds: 5));

      final body = json.decode(response.body) as Map<String, dynamic>;

      // 注册成功后立即更新本地车辆列表
      if (body['code'] == 0) {
        final newCar = CarInfo(
          id: carId,
          name: carId,
          ip: ip,
          httpPort: port,
          role: CarRole.follower,
          online: false,
        );
        _state = _state.copyWith(cars: [..._state.cars, newCar]);
        _notify();
      }
      return body;
    } catch (_) {
      return {'code': -1, 'msg': '协调器通信失败'};
    }
  }

  /// 从协调器移除车辆。
  Future<Map<String, dynamic>?> removeCar(String carId) async {
    if (_client == null) return null;
    try {
      final response = await _client!.delete(
        _url('/api/cars/$carId'),
      ).timeout(const Duration(seconds: 5));

      final body = json.decode(response.body) as Map<String, dynamic>;

      if (body['code'] == 0) {
        final newCars = _state.cars.where((c) => c.id != carId).toList();
        // 如果移除的是主车，重新指定
        var newLeaderId = _state.leaderId;
        if (newLeaderId == carId && newCars.isNotEmpty) {
          newLeaderId = newCars.first.id;
          newCars[0] = newCars[0].copyWith(role: CarRole.leader);
        }
        _state = _state.copyWith(cars: newCars, leaderId: newLeaderId);
        _notify();
      }
      return body;
    } catch (_) {
      return {'code': -1, 'msg': '协调器通信失败'};
    }
  }

  // ═══════════════════════════════════════════════════════════
  // 编队出发/停止
  // ═══════════════════════════════════════════════════════════

  /// 编队出发 — 向所有车发送前进指令。
  void startFleet({int speed = 50}) {
    _state = _state.copyWith(status: FleetStatus.moving);
    _elapsedTimer?.cancel();
    _elapsedTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      _state = _state.copyWith(
          elapsed: _state.elapsed + const Duration(seconds: 1));
      _notify();
    });
    // 不在此处发送移动指令 — 由 UI 层调用 moveAll 配合具体的运动方向
    _notify();
  }

  /// 编队停止 — 向所有车发送急停指令。
  void stopFleet() {
    _state = _state.copyWith(status: FleetStatus.stopped);
    _elapsedTimer?.cancel();
    moveAll('stop', speed: 0, duration: 0);
    _notify();
  }

  // ═══════════════════════════════════════════════════════════
  // 协同展示
  // ═══════════════════════════════════════════════════════════

  /// 获取展示状态。
  Future<Map<String, dynamic>?> getDemoStatus() async {
    if (_client == null) return null;
    try {
      final response = await _client!.get(
        _url('/api/demo/status'),
      ).timeout(const Duration(seconds: 5));
      final body = json.decode(response.body) as Map<String, dynamic>;
      if (body['code'] == 0) {
        final data = body['data'] as Map<String, dynamic>? ?? {};
        _state = _state.copyWith(
          demoState: data['state'] as String? ?? _state.demoState,
          demoStep: data['step'] as String? ?? '',
          demoMessage: data['message'] as String? ?? '',
          demoRecordings: (data['recordings'] as Map<String, dynamic>?)
                  ?.map((k, v) => MapEntry(k, v.toString())) ??
              const {},
        );
        _notify();
      }
      return body;
    } catch (_) {
      return null;
    }
  }

  /// 启动协同展示。
  Future<Map<String, dynamic>?> startDemo() async {
    if (_client == null) return null;
    try {
      final response = await _client!.post(
        _url('/api/demo/start'),
        headers: {'Content-Type': 'application/json'},
        body: '{}',
      ).timeout(const Duration(seconds: 5));
      return json.decode(response.body) as Map<String, dynamic>;
    } catch (_) {
      return {'code': -1, 'msg': '协调器通信失败'};
    }
  }

  /// 紧急停止展示。
  Future<Map<String, dynamic>?> stopDemo() async {
    if (_client == null) return null;
    try {
      final response = await _client!.post(
        _url('/api/demo/stop'),
      ).timeout(const Duration(seconds: 5));
      return json.decode(response.body) as Map<String, dynamic>;
    } catch (_) {
      return {'code': -1, 'msg': '协调器通信失败'};
    }
  }

  /// 重置展示状态。
  Future<Map<String, dynamic>?> resetDemo() async {
    if (_client == null) return null;
    try {
      final response = await _client!.post(
        _url('/api/demo/reset'),
      ).timeout(const Duration(seconds: 5));
      return json.decode(response.body) as Map<String, dynamic>;
    } catch (_) {
      return {'code': -1, 'msg': '协调器通信失败'};
    }
  }

  // ═══════════════════════════════════════════════════════════
  // 视频代理
  // ═══════════════════════════════════════════════════════════

  /// 获取车辆视频流的代理 URL（通过协调器转发，避免跨域）。
  String getCameraProxyUrl(String carId) {
    return 'http://$_host:$_port/proxy/camera/$carId';
  }

  // ═══════════════════════════════════════════════════════════
  // 工具
  // ═══════════════════════════════════════════════════════════

  Uri _url(String path) => Uri.parse('http://$_host:$_port$path');

  void _notify() {
    if (!_stateController.isClosed) {
      _stateController.add(_state);
    }
  }

  void dispose() {
    _pollTimer?.cancel();
    _elapsedTimer?.cancel();
    _client?.close();
    _stateController.close();
  }
}
