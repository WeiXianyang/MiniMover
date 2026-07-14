/// 车辆角色
enum CarRole { leader, follower }

/// 碰撞告警等级
enum CollisionLevel { warning, critical }

/// 碰撞告警
class CollisionAlert {
  final String carA;
  final String carB;
  final double distance;
  final CollisionLevel level;

  const CollisionAlert({
    required this.carA,
    required this.carB,
    required this.distance,
    required this.level,
  });

  factory CollisionAlert.fromCoordinator(String key, Map<String, dynamic> data) {
    final cars = (data['cars'] as List<dynamic>?)?.cast<String>() ?? ['?', '?'];
    return CollisionAlert(
      carA: cars.isNotEmpty ? cars[0] : '?',
      carB: cars.length > 1 ? cars[1] : '?',
      distance: (data['distance'] as num?)?.toDouble() ?? 0,
      level: data['level'] == 'CRITICAL' ? CollisionLevel.critical : CollisionLevel.warning,
    );
  }

  String get displayText => '$carA ↔ $carB : ${distance.toStringAsFixed(2)}m';
}

/// 单台小车信息
class CarInfo {
  final String id;
  final String name;
  final String ip;
  final int httpPort; // 小车 HTTP API 端口，默认 5000（协调器使用）
  final int tcpPort; // TCP 控制端口，默认 6000
  final CarRole role;
  final bool online;
  final double distance; // 编队内间距 (m)
  final double speed; // 当前速度 (m/s)

  // ── 来自协调器 /api/status ──
  final double? posX;
  final double? posY;
  final double batteryVoltage; // 电池电压 (V)
  final double temperature;
  final double humidity;
  final double smoke;
  final double pm25;

  const CarInfo({
    required this.id,
    required this.name,
    required this.ip,
    this.httpPort = 5000,
    this.tcpPort = 6000,
    required this.role,
    this.batteryVoltage = 0,
    this.online = false,
    this.distance = 0,
    this.speed = 0,
    this.posX,
    this.posY,
    this.temperature = 0,
    this.humidity = 0,
    this.smoke = 0,
    this.pm25 = 0,
  });

  /// 电池百分比估算 (12.6V 满电，9V 亏电)
  int get batteryPercent {
    if (batteryVoltage <= 0) return 0;
    return ((batteryVoltage - 9.0) / (12.6 - 9.0) * 100).round().clamp(0, 100);
  }

  String get positionDisplay {
    if (posX == null || posY == null) return 'N/A';
    return '${posX!.toStringAsFixed(2)}, ${posY!.toStringAsFixed(2)}';
  }

  CarInfo copyWith({
    String? id,
    String? name,
    String? ip,
    int? httpPort,
    int? tcpPort,
    CarRole? role,
    bool? online,
    double? distance,
    double? speed,
    double? posX,
    double? posY,
    double? batteryVoltage,
    double? temperature,
    double? humidity,
    double? smoke,
    double? pm25,
  }) {
    return CarInfo(
      id: id ?? this.id,
      name: name ?? this.name,
      ip: ip ?? this.ip,
      httpPort: httpPort ?? this.httpPort,
      tcpPort: tcpPort ?? this.tcpPort,
      role: role ?? this.role,
      online: online ?? this.online,
      distance: distance ?? this.distance,
      speed: speed ?? this.speed,
      posX: posX ?? this.posX,
      posY: posY ?? this.posY,
      batteryVoltage: batteryVoltage ?? this.batteryVoltage,
      temperature: temperature ?? this.temperature,
      humidity: humidity ?? this.humidity,
      smoke: smoke ?? this.smoke,
      pm25: pm25 ?? this.pm25,
    );
  }
}

/// 编队状态
enum FleetStatus { idle, connecting, ready, moving, stopped }

/// 编队整体状态
class FleetState {
  final FleetStatus status;
  final Duration elapsed;
  final List<CarInfo> cars;
  final String leaderId;
  final Map<String, CollisionAlert> collisions;
  final String coordinatorHost;
  final int coordinatorPort;
  final String demoState; // idle | running | completed | failed | stopped
  final String demoStep;
  final String demoMessage;
  final Map<String, String> demoRecordings; // car_id -> record_id

  const FleetState({
    this.status = FleetStatus.idle,
    this.elapsed = Duration.zero,
    this.cars = const [],
    this.leaderId = '',
    this.collisions = const {},
    this.coordinatorHost = '',
    this.coordinatorPort = 8888,
    this.demoState = 'idle',
    this.demoStep = '',
    this.demoMessage = '',
    this.demoRecordings = const {},
  });

  CarInfo? get leader {
    try {
      return cars.firstWhere((c) => c.id == leaderId);
    } catch (_) {
      return cars.isNotEmpty
          ? cars.firstWhere((c) => c.role == CarRole.leader)
          : null;
    }
  }

  List<CarInfo> get followers =>
      cars.where((c) => c.role == CarRole.follower).toList();

  int get carCount => cars.length;
  int get onlineCount => cars.where((c) => c.online).length;

  double get avgBattery {
    if (cars.isEmpty) return 0;
    final total = cars
        .map((c) => c.batteryPercent)
        .reduce((a, b) => a + b);
    return total / cars.length;
  }

  bool get hasCollisions => collisions.isNotEmpty;
  bool get hasCriticalCollision =>
      collisions.values.any((c) => c.level == CollisionLevel.critical);

  FleetState copyWith({
    FleetStatus? status,
    Duration? elapsed,
    List<CarInfo>? cars,
    String? leaderId,
    Map<String, CollisionAlert>? collisions,
    String? coordinatorHost,
    int? coordinatorPort,
    String? demoState,
    String? demoStep,
    String? demoMessage,
    Map<String, String>? demoRecordings,
  }) {
    return FleetState(
      status: status ?? this.status,
      elapsed: elapsed ?? this.elapsed,
      cars: cars ?? this.cars,
      leaderId: leaderId ?? this.leaderId,
      collisions: collisions ?? this.collisions,
      coordinatorHost: coordinatorHost ?? this.coordinatorHost,
      coordinatorPort: coordinatorPort ?? this.coordinatorPort,
      demoState: demoState ?? this.demoState,
      demoStep: demoStep ?? this.demoStep,
      demoMessage: demoMessage ?? this.demoMessage,
      demoRecordings: demoRecordings ?? this.demoRecordings,
    );
  }
}
