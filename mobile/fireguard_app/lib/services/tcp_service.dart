import 'dart:async';
import 'dart:io';

/// 小车 TCP 通信服务
///
/// 协议格式 (ASCII hex 字符串): $TT FF LL DD... CC #
/// - TT = 车型 (0x01=X3_PLUS)
/// - FF = 功能码
/// - LL = 数据字节数
/// - DD... = 数据 (每个字节 2 个 hex 字符)
/// - CC = 校验和 (TT+FF+LL+所有数据字节之和 mod 256, 2 hex 字符)
/// - $ 开头, # 结尾
///
/// 对应后端 rosmaster_main_ori.py parse_data()
class TcpService {
  Socket? _socket;
  String _host = '192.168.1.11';
  int _port = 6000;
  int _carType = 1; // X3_PLUS
  bool _connected = false;

  final StreamController<String> _eventController =
      StreamController<String>.broadcast();

  bool get connected => _connected;
  Stream<String> get events => _eventController.stream;

  void updateConfig(String host, int port, {int carType = 1}) {
    _host = host;
    _port = port;
    _carType = carType;
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
        (data) {
          // 后端返回 hex 字符串帧，也以 $ 开头 # 结尾
          final str = String.fromCharCodes(data);
          _eventController.add(str);
        },
        onDone: () {
          _connected = false;
          _eventController.add('DISCONNECTED');
        },
        onError: (e) {
          _connected = false;
          _eventController.add('ERROR: $e');
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

  /// 构建并发送协议帧
  /// [func] 功能码, [payload] 数据字节列表
  void _sendFrame(int func, List<int> payload) {
    if (_socket == null || !_connected) return;

    // 构建帧：$ TT FF LL D0 D1 ... CC #
    final buf = StringBuffer();
    buf.write('\$');
    buf.write(_hex2(_carType)); // TT
    buf.write(_hex2(func)); // FF
    buf.write(_hex2(payload.length)); // LL

    int checksum = _carType + func + payload.length;
    for (final b in payload) {
      buf.write(_hex2(b));
      checksum += b;
    }
    checksum %= 256;

    buf.write(_hex2(checksum)); // CC
    buf.write('#'); // 结束符

    _socket!.write(buf.toString());
  }

  static String _hex2(int v) => (v & 0xFF).toRadixString(16).padLeft(2, '0');

  /// 将 -100~100 的有符号速度值转为协议所需的 unsigned byte
  static int _speedByte(int v) => v >= 0 ? v : 256 + v;

  /// 查询版本号 (0x01)
  void queryVersion() => _sendFrame(0x01, []);

  /// 查询电压 (0x02)
  void queryVoltage() => _sendFrame(0x02, []);

  /// 移动控制 (0x10)
  /// [forward] 前后速度：正=前进, 负=后退 (-100~100)
  /// [lateral] 左右平移：正=右移, 负=左移 (-100~100)
  void move(int forward, int lateral) {
    // 后端协议: num_x→lateral(speed_y=-num_x/100), num_y→forward(speed_x=num_y/100)
    final numX = _speedByte(-lateral); // 右移→speed_y正→-num_x正→num_x负
    final numY = _speedByte(forward);
    _sendFrame(0x10, [numX, numY]);
  }

  /// 舵机控制 (0x11)
  void servo(int id, int angle) => _sendFrame(0x11, [id, angle]);

  /// 蜂鸣器 (0x13)
  /// [state] 0=关, 非0=响
  void beep(int state) => _sendFrame(0x13, [state]);

  /// 设置速度百分比 (0x16)
  void setSpeed(int pct) => _sendFrame(0x16, [pct]);

  /// 灯光控制 RGB (0x30)
  void setLight(int r, int g, int b) => _sendFrame(0x30, [r, g, b]);

  /// 开始循线 (0x63)
  void startFollowLine() => _sendFrame(0x63, [1]);

  /// 停止循线 (0x64)
  void stopFollowLine() => _sendFrame(0x64, [0]);

  /// 急停
  void emergencyStop() => move(0, 0);

  /// 进入遥控界面 (0x0F, func=1)
  void enterRemoteMode() => _sendFrame(0x0F, [1]);

  /// 进入首页 (0x0F, func=0)
  void enterHomeMode() => _sendFrame(0x0F, [0]);

  /// 查询当前速度 (0x22)
  void queryCurrentSpeed() => _sendFrame(0x22, []);

  void dispose() {
    disconnect();
    _eventController.close();
  }
}
