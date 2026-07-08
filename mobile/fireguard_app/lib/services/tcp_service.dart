import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

/// 小车 TCP 通信服务
///
/// 协议格式: $T_CARTYPE T_FUNC T_LEN DATA CHECKSUM#
/// 所有字段为 2 位十六进制字符串
class TcpService {
  Socket? _socket;
  String _host = '192.168.1.11';
  int _port = 6000;
  bool _connected = false;

  final StreamController<Uint8List> _dataController =
      StreamController<Uint8List>.broadcast();

  bool get connected => _connected;
  Stream<Uint8List> get dataStream => _dataController.stream;

  void updateConfig(String host, int port) {
    _host = host;
    _port = port;
  }

  Future<bool> connect() async {
    try {
      _socket = await Socket.connect(
        _host,
        _port,
        timeout: const Duration(seconds: 5),
      );
      _connected = true;
      _socket!.listen(
        (data) => _dataController.add(data),
        onDone: () {
          _connected = false;
        },
        onError: (e) {
          _connected = false;
        },
      );
      return true;
    } catch (e) {
      _connected = false;
      return false;
    }
  }

  void disconnect() {
    _socket?.destroy();
    _socket = null;
    _connected = false;
  }

  /// 计算异或校验和
  int _checksum(List<int> data) {
    return data.fold(0, (prev, b) => prev ^ b);
  }

  /// 发送指令帧
  /// [cartype] 默认 0x01, [func] 功能码, [payload] 数据字节
  void sendCommand(int func, List<int> payload) {
    if (_socket == null || !_connected) return;

    final cartype = 0x01;
    final len = payload.length;
    final frame = <int>[
      0x24, // '$'
      cartype,
      func,
      len,
      ...payload,
    ];
    final checksum = _checksum(frame.sublist(1)); // 跳过 $
    frame.add(checksum);
    frame.add(0x23); // '#'

    _socket!.add(Uint8List.fromList(frame));
  }

  /// 查询版本号
  void queryVersion() {
    sendCommand(0x02, [0x01]);
  }

  /// 移动控制
  /// [speedXY] 前后速度 (-100~100), [speedZ] 旋转速度 (-100~100)
  void move(int speedXY, int speedZ) {
    sendCommand(0x03, [speedXY & 0xFF, speedZ & 0xFF]);
  }

  /// 舵机控制
  void servo(int id, int angle) {
    sendCommand(0x07, [id & 0xFF, angle & 0xFF]);
  }

  /// 蜂鸣器
  void beep(int state) {
    sendCommand(0x16, [state & 0xFF]);
  }

  /// 灯光控制 (RGB)
  void setLight(int r, int g, int b) {
    sendCommand(0x13, [r & 0xFF, g & 0xFF, b & 0xFF]);
  }

  /// 循线模式
  void followLine(int state) {
    sendCommand(0x1A, [state & 0xFF]);
  }

  /// 急停
  void emergencyStop() {
    move(0, 0);
  }

  void dispose() {
    disconnect();
    _dataController.close();
  }
}
