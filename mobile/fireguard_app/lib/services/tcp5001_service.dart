import 'dart:async';
import 'dart:io';

/// 5001 低延迟 TCP 控制通道
/// 协议：每行 `<cmd> [speed] [duration]\n`
/// 策略：优先 5001，失败回退 HTTP /api/move
class Tcp5001Service {
  String _host = '10.227.111.171';
  Socket? _socket;
  bool _connected = false;
  final _connCtrl = StreamController<bool>.broadcast();

  bool get connected => _connected;
  Stream<bool> get connectionChanges => _connCtrl.stream;

  void updateHost(String host) { _host = host; }

  Future<bool> connect() async {
    try {
      _socket?.destroy();
      _socket = await Socket.connect(_host, 5001, timeout: const Duration(seconds: 3));
      _connected = true;
      _connCtrl.add(true);
      _socket!.listen(
        (_) {}, // fire-and-forget，不读返回
        onError: (_) => _disconnected(),
        onDone: _disconnected,
      );
      return true;
    } catch (_) {
      return false;
    }
  }

  void _disconnected() {
    _connected = false;
    _connCtrl.add(false);
    _socket?.destroy();
    _socket = null;
  }

  /// 发送控制命令，失败返回 false（调用方应回退 HTTP）
  bool send(String cmd, {int speed = 50, double duration = 0.3}) {
    if (!_connected || _socket == null) return false;
    try {
      final line = duration > 0 ? '$cmd $speed $duration\n' : '$cmd\n';
      _socket!.write(line);
      return true;
    } catch (_) {
      _disconnected();
      return false;
    }
  }

  void stop() => send('stop', duration: 0);

  void dispose() {
    _disconnected();
    _connCtrl.close();
  }
}
