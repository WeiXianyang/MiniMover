import 'dart:async';
import 'dart:io';

/// 小车返回的解析后数据
class CarResponse {
  final int carType;
  final int funcCode;
  final List<int> data;
  final String rawFrame;

  const CarResponse({
    required this.carType,
    required this.funcCode,
    required this.data,
    required this.rawFrame,
  });

  /// 解析电压值（0x02 返回）
  double? get voltage {
    if (funcCode == 0x02 && data.isNotEmpty) {
      return data[0] / 10.0;
    }
    return null;
  }

  /// 解析版本号（0x01 返回）
  double? get version {
    if (funcCode == 0x01 && data.isNotEmpty) {
      return data[0] / 10.0;
    }
    return null;
  }

  /// 解析当前速度（0x22 返回）
  /// data: [speed_xy_unsigned, speed_z_unsigned]
  CarSpeed? get carSpeed {
    if (funcCode == 0x22 && data.length >= 2) {
      int xy = data[0] > 127 ? data[0] - 256 : data[0];
      int z = data[1] > 127 ? data[1] - 256 : data[1];
      return CarSpeed(xy: xy, z: z);
    }
    return null;
  }

  /// 解析自稳状态（0x17 返回 / 0x0F 返回中含）
  int? get stabilizeState {
    if (funcCode == 0x17 && data.isNotEmpty) return data[0];
    if (funcCode == 0x0F && data.length >= 3) return data[1];
    return null;
  }

  /// 解析摄像头类型（0x18 / 0x0F 返回）
  int? get cameraType {
    if (funcCode == 0x18 && data.isNotEmpty) return data[0];
    if (funcCode == 0x0F && data.length >= 4) return data[2];
    return null;
  }

  @override
  String toString() => 'CarResponse(carType:$carType, func:0x${funcCode.toRadixString(16)}, data:$data)';
}

/// 小车速度
class CarSpeed {
  final int xy; // 前后速度 -100~100
  final int z;  // 旋转速度 -100~100
  const CarSpeed({required this.xy, required this.z});

  @override
  String toString() => 'CarSpeed(xy:$xy, z:$z)';
}

/// 小车 TCP 通信服务
///
/// 协议格式 (ASCII hex 字符串): $TT FF LL DD... CC #
/// - TT = 车型 (0x01=X3_PLUS)
/// - FF = 功能码
/// - LL = 数据字节数
/// - DD... = 数据 (每个字节 2 个 hex 字符)
/// - CC = 校验和 (TT+FF+LL+所有数据字节之和 mod 256, 2 hex 字符)
/// - $ 开头, # 结尾
class TcpService {
  Socket? _socket;
  String _host = '192.168.1.11';
  int _port = 6000;
  int _carType = 1; // X3_PLUS
  bool _connected = false;
  String _deviceVersion = '';
  double _batteryVoltage = 0.0;
  CarSpeed? _currentSpeed;
  int _stabilizeState = 0;
  int _cameraType = -1; // -1=未知, 0=无效, 1=USB, 2=深度相机

  // ── 广播流 ──
  final StreamController<String> _rawEventController =
      StreamController<String>.broadcast();
  final StreamController<CarResponse> _responseController =
      StreamController<CarResponse>.broadcast();
  final StreamController<bool> _connectionController =
      StreamController<bool>.broadcast();

  // ── 公开 getter ──
  bool get connected => _connected;
  String get host => _host;
  int get port => _port;
  String get deviceVersion => _deviceVersion;
  double get batteryVoltage => _batteryVoltage;
  int get batteryPercent {
    if (_batteryVoltage <= 0) return 0;
    final pct = ((_batteryVoltage - 6.5) / (8.4 - 6.5) * 100).round();
    return pct.clamp(0, 100);
  }
  CarSpeed? get currentSpeed => _currentSpeed;
  int get stabilizeState => _stabilizeState;
  int get cameraType => _cameraType;

  Stream<String> get rawEvents => _rawEventController.stream;
  Stream<CarResponse> get responses => _responseController.stream;
  Stream<bool> get connectionChanges => _connectionController.stream;

  /// 更新连接配置
  void updateConfig(String host, int port, {int carType = 1}) {
    _host = host;
    _port = port;
    _carType = carType;
  }

  /// 连接到小车
  Future<bool> connect() async {
    try {
      _socket = await Socket.connect(
        _host,
        _port,
        timeout: const Duration(seconds: 5),
      );
      _connected = true;
      _connectionController.add(true);

      // 缓冲不完整的帧
      String buffer = '';

      _socket!.listen(
        (data) {
          final chunk = String.fromCharCodes(data);
          buffer += chunk;

          // 按 $...# 边界提取完整帧
          while (true) {
            final start = buffer.indexOf('\$');
            if (start == -1) break; // 还没收到帧头
            final end = buffer.indexOf('#', start);
            if (end == -1) break; // 帧不完整，等更多数据

            final frame = buffer.substring(start, end + 1);
            buffer = buffer.substring(end + 1);

            _rawEventController.add(frame);

            // 解析帧
            final response = _parseFrame(frame);
            if (response != null) {
              _updateState(response);
              _responseController.add(response);
            }
          }
        },
        onDone: () {
          _connected = false;
          _connectionController.add(false);
          _rawEventController.add('DISCONNECTED');
        },
        onError: (e) {
          _connected = false;
          _connectionController.add(false);
          _rawEventController.add('ERROR: $e');
        },
      );

      // 连接成功后立即查询版本和电压
      queryVersion();
      await Future.delayed(const Duration(milliseconds: 100));
      queryVoltage();

      return true;
    } catch (e) {
      _connected = false;
      _connectionController.add(false);
      return false;
    }
  }

  /// 断开连接
  void disconnect() {
    _socket?.destroy();
    _socket = null;
    _connected = false;
    _connectionController.add(false);
  }

  /// 解析接收到的帧
  CarResponse? _parseFrame(String frame) {
    if (frame.length < 8) return null;
    if (!frame.startsWith('\$') || !frame.endsWith('#')) return null;

    try {
      final carType = int.parse(frame.substring(1, 3), radix: 16);
      final funcCode = int.parse(frame.substring(3, 5), radix: 16);
      final dataLen = int.parse(frame.substring(5, 7), radix: 16);

      // 长度校验
      if (dataLen != frame.length - 8) return null;

      // 校验和
      int checksum = 0;
      for (int i = 0; i < frame.length - 4; i += 2) {
        checksum += int.parse(frame.substring(i + 1, i + 3), radix: 16);
      }
      checksum %= 256;

      final recvChecksum =
          int.parse(frame.substring(frame.length - 3, frame.length - 1), radix: 16);
      if (checksum != recvChecksum) return null;

      // 提取数据段 (不含校验字节)
      // dataLen = 数据主体 hex 字符数 + 2(校验 hex 字符)
      final payloadByteCount = (dataLen - 2) ~/ 2;
      final data = <int>[];
      for (int i = 0; i < payloadByteCount; i++) {
        data.add(int.parse(frame.substring(7 + i * 2, 9 + i * 2), radix: 16));
      }

      return CarResponse(
        carType: carType,
        funcCode: funcCode,
        data: data,
        rawFrame: frame,
      );
    } catch (_) {
      return null;
    }
  }

  /// 根据返回帧更新本地状态
  void _updateState(CarResponse r) {
    switch (r.funcCode) {
      case 0x01: // 版本号
        final v = r.version;
        if (v != null) _deviceVersion = '$v';
        break;
      case 0x02: // 电压
        final v = r.voltage;
        if (v != null) _batteryVoltage = v;
        break;
      case 0x0F: // 进入界面返回
        if (r.data.length >= 1) {
          if (r.data[0] == 1) {
            // 遥控模式返回 speed + stabilize + camera
            _currentSpeed = r.carSpeed;
            _stabilizeState = r.stabilizeState ?? _stabilizeState;
            _cameraType = r.cameraType ?? _cameraType;
          }
        }
        break;
      case 0x17: // 自稳状态
        final s = r.stabilizeState;
        if (s != null) _stabilizeState = s;
        break;
      case 0x22: // 当前速度
        _currentSpeed = r.carSpeed;
        break;
    }
  }

  // ═══════════════════════════════════════════
  // 发送帧构建
  // ═══════════════════════════════════════════

  /// 构建并发送协议帧
  ///
  /// 格式: $TT FF LL DD... CC #
  /// - LL = 数据主体 hex 字符数 + 2（校验字节的 hex 字符数）
  /// - CC = (TT + FF + LL + 各数据字节) % 256
  void _sendFrame(int func, List<int> payload) {
    if (_socket == null || !_connected) return;

    // LL = payload hex chars + checksum hex chars (2)
    final ll = payload.length * 2 + 2;

    final buf = StringBuffer();
    buf.write('\$');
    buf.write(_hex2(_carType));
    buf.write(_hex2(func));
    buf.write(_hex2(ll));

    int checksum = _carType + func + ll;
    for (final b in payload) {
      buf.write(_hex2(b));
      checksum += b;
    }
    checksum %= 256;

    buf.write(_hex2(checksum));
    buf.write('#');

    _socket!.write(buf.toString());
  }

  static String _hex2(int v) =>
      (v & 0xFF).toRadixString(16).padLeft(2, '0');

  static int _speedByte(int v) => v >= 0 ? v : 256 + v;

  // ═══════════════════════════════════════════
  // 控制指令
  // ═══════════════════════════════════════════

  /// 查询版本号 (0x01)
  void queryVersion() => _sendFrame(0x01, []);

  /// 查询电压 (0x02)
  void queryVoltage() => _sendFrame(0x02, []);

  /// 移动控制 (0x10)
  /// [forward] 前后速度：正=前进, 负=后退 (-100~100)
  /// [lateral] 左右平移：正=右移, 负=左移 (-100~100)
  void move(int forward, int lateral) {
    final numX = _speedByte(-lateral);
    final numY = _speedByte(forward);
    _sendFrame(0x10, [numX, numY]);
  }

  /// 舵机控制 (0x11)
  void servo(int id, int angle) => _sendFrame(0x11, [id, angle]);

  /// 蜂鸣器 (0x13)
  /// [delayMs] 0=关, 1=持续响, 其他=毫秒数
  void beep(int delayMs) {
    int state = delayMs > 0 ? 1 : 0;
    int delayByte = 0;
    if (delayMs <= 0) {
      delayByte = 0;
    } else if (delayMs >= 2550) {
      delayByte = 255;
    } else {
      delayByte = (delayMs / 10).round().clamp(1, 254);
    }
    _sendFrame(0x13, [state, delayByte]);
  }

  /// 设置速度百分比 (0x16)
  void setSpeed(int xyPct, int zPct) =>
      _sendFrame(0x16, [xyPct.clamp(0, 100), zPct.clamp(0, 100)]);

  /// 自稳开关 (0x17)
  void setStabilize(bool on) => _sendFrame(0x17, [on ? 1 : 0]);

  /// 切换摄像头 (0x18) — 1=USB, 2=深度相机
  void switchCamera(int type) => _sendFrame(0x18, [type]);

  /// 灯光控制 RGB (0x30)
  void setLight(int r, int g, int b) => _sendFrame(0x30, [0, r, g, b]);

  /// 灯光特效 (0x31)
  void setLightEffect(int effect, int speed) =>
      _sendFrame(0x31, [effect, speed]);

  /// 保存单张图片 (0x60)
  void captureImage() => _sendFrame(0x60, []);

  /// 开始录制视频 (0x61)
  void startRecordVideo() => _sendFrame(0x61, []);

  /// 停止录制视频 (0x62)
  void stopRecordVideo() => _sendFrame(0x62, []);

  /// 开始循线 (0x63)
  void startFollowLine() => _sendFrame(0x63, []);

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

  /// 按键控制 (0x15) — 方向: 1前 2后 3左 4右 5停
  void keyControl(int dir) => _sendFrame(0x15, [dir]);

  void dispose() {
    disconnect();
    _rawEventController.close();
    _responseController.close();
    _connectionController.close();
  }
}
