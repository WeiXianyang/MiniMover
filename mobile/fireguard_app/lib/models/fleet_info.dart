/// 车辆角色
enum CarRole { leader, follower }

/// 单台小车信息
class CarInfo {
  final String id;
  final String name;
  final String ip;
  final int tcpPort;
  final int videoPort;
  final CarRole role;
  final int battery;
  final bool online;
  final double distance;
  final double speed;

  const CarInfo({
    required this.id,
    required this.name,
    required this.ip,
    this.tcpPort = 6000,
    this.videoPort = 6500,
    required this.role,
    this.battery = 0,
    this.online = false,
    this.distance = 0,
    this.speed = 0,
  });

  CarInfo copyWith({
    String? id,
    String? name,
    String? ip,
    int? tcpPort,
    int? videoPort,
    CarRole? role,
    int? battery,
    bool? online,
    double? distance,
    double? speed,
  }) {
    return CarInfo(
      id: id ?? this.id,
      name: name ?? this.name,
      ip: ip ?? this.ip,
      tcpPort: tcpPort ?? this.tcpPort,
      videoPort: videoPort ?? this.videoPort,
      role: role ?? this.role,
      battery: battery ?? this.battery,
      online: online ?? this.online,
      distance: distance ?? this.distance,
      speed: speed ?? this.speed,
    );
  }
}

/// 编队状态
enum FleetStatus { idle, ready, moving, stopped }

/// 编队整体状态
class FleetState {
  final FleetStatus status;
  final Duration elapsed;
  final List<CarInfo> cars;
  final String leaderId;

  const FleetState({
    this.status = FleetStatus.ready,
    this.elapsed = Duration.zero,
    this.cars = const [],
    this.leaderId = '',
  });

  CarInfo? get leader {
    try {
      return cars.firstWhere((c) => c.id == leaderId);
    } catch (_) {
      return cars.isNotEmpty ? cars.firstWhere((c) => c.role == CarRole.leader) : null;
    }
  }

  List<CarInfo> get followers =>
      cars.where((c) => c.role == CarRole.follower).toList();

  int get carCount => cars.length;
  int get onlineCount => cars.where((c) => c.online).length;

  double get avgBattery {
    if (cars.isEmpty) return 0;
    return cars.map((c) => c.battery).reduce((a, b) => a + b) / cars.length;
  }

  FleetState copyWith({
    FleetStatus? status,
    Duration? elapsed,
    List<CarInfo>? cars,
    String? leaderId,
  }) {
    return FleetState(
      status: status ?? this.status,
      elapsed: elapsed ?? this.elapsed,
      cars: cars ?? this.cars,
      leaderId: leaderId ?? this.leaderId,
    );
  }
}
