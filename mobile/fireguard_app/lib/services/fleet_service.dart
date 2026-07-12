import 'dart:async';
import '../models/fleet_info.dart';
import 'tcp_service.dart';

/// 编队管理服务
///
/// 当前为 Mock 实现，后续会对接多车 TCP 连接管理。
/// 每个从车会有自己的 TcpService 实例。
class FleetService {
  final List<TcpService> _carServices = [];
  FleetState _state = const FleetState();
  Timer? _elapsedTimer;

  final StreamController<FleetState> _stateController =
      StreamController<FleetState>.broadcast();

  FleetState get state => _state;
  Stream<FleetState> get stateStream => _stateController.stream;

  /// Mock 初始化：创建 1 主车 + 2 从车
  void initMockFleet() {
    final leader = CarInfo(
      id: 'leader-01',
      name: '主车',
      ip: '192.168.1.11',
      role: CarRole.leader,
      battery: 86,
      online: true,
      distance: 0,
      speed: 0,
    );
    final f1 = CarInfo(
      id: 'follower-01',
      name: '从车 1',
      ip: '192.168.1.12',
      role: CarRole.follower,
      battery: 72,
      online: true,
      distance: 1.2,
      speed: 0.5,
    );
    final f2 = CarInfo(
      id: 'follower-02',
      name: '从车 2',
      ip: '192.168.1.13',
      role: CarRole.follower,
      battery: 65,
      online: true,
      distance: 1.5,
      speed: 0.5,
    );

    _state = FleetState(
      status: FleetStatus.ready,
      cars: [leader, f1, f2],
      leaderId: leader.id,
    );
    _carServices.add(TcpService());
    _carServices.add(TcpService());
    _carServices.add(TcpService());
    _notify();
  }

  /// 添加从车
  void addFollower(String ip, {int port = 6000}) {
    final idx = _state.cars.where((c) => c.role == CarRole.follower).length + 1;
    final car = CarInfo(
      id: 'follower-${DateTime.now().millisecondsSinceEpoch}',
      name: '从车 $idx',
      ip: ip,
      tcpPort: port,
      role: CarRole.follower,
      battery: 100,
      online: true,
      distance: 0,
      speed: 0,
    );
    final newCars = [..._state.cars, car];
    _state = _state.copyWith(cars: newCars);
    _carServices.add(TcpService());
    _notify();
  }

  /// 移除从车
  void removeFollower(String carId) {
    final idx = _state.cars.indexWhere((c) => c.id == carId);
    if (idx < 0) return;
    if (_state.cars[idx].role == CarRole.leader) return;
    final newCars = [..._state.cars]..removeAt(idx);
    _state = _state.copyWith(cars: newCars);
    if (idx < _carServices.length) {
      _carServices[idx].dispose();
      _carServices.removeAt(idx);
    }
    _notify();
  }

  /// 编队出发
  void startFleet() {
    _state = _state.copyWith(status: FleetStatus.moving);
    _elapsedTimer?.cancel();
    _elapsedTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      _state = _state.copyWith(elapsed: _state.elapsed + const Duration(seconds: 1));
      _notify();
    });
    // TODO: 向所有车辆发送移动指令
    _notify();
  }

  /// 编队停止
  void stopFleet() {
    _state = _state.copyWith(status: FleetStatus.stopped);
    _elapsedTimer?.cancel();
    // TODO: 向所有车辆发送急停指令
    _notify();
  }

  /// 解散编队
  void disbandFleet() {
    _elapsedTimer?.cancel();
    _state = const FleetState(status: FleetStatus.idle);
    for (final s in _carServices) {
      s.dispose();
    }
    _carServices.clear();
    _notify();
  }

  void _notify() => _stateController.add(_state);

  void dispose() {
    _elapsedTimer?.cancel();
    for (final s in _carServices) {
      s.dispose();
    }
    _stateController.close();
  }
}
