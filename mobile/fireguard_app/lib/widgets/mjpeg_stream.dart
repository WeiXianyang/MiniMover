import 'dart:async';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';

/// MJPEG 视频流组件
///
/// 直连小车 ROS2 web_video_server (8080)，dart:io HttpClient 确保流式兼容
/// 解析 multipart/x-mixed-replace 流并逐帧渲染
class MjpegStream extends StatefulWidget {
  final String host;
  final int port;
  final String path;
  final double? width;
  final double? height;
  final WidgetBuilder? placeholder;
  final WidgetBuilder? errorBuilder;
  final void Function(Uint8List frame)? onFrame;

  const MjpegStream({
    super.key,
    required this.host,
    this.port = 8080,
    this.path = '/stream?topic=/camera/color/image_raw',
    this.width,
    this.height,
    this.placeholder,
    this.errorBuilder,
    this.onFrame,
  });

  String get url => 'http://$host:$port$path';

  @override
  State<MjpegStream> createState() => _MjpegStreamState();
}

class _MjpegStreamState extends State<MjpegStream> {
  HttpClient? _client;
  StreamSubscription<Uint8List>? _subscription;
  Uint8List? _latestFrame;
  String? _error;
  bool _loading = true;
  int _lastFrameMs = 0;

  @override
  void initState() {
    super.initState();
    _connect();
  }

  @override
  void didUpdateWidget(MjpegStream oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.host != widget.host || oldWidget.port != widget.port) {
      _disconnect();
      _connect();
    }
  }

  void _connect() {
    _disconnect();
    _client = HttpClient();
    _loading = true;
    _error = null;

    _client!
        .getUrl(Uri.parse(widget.url))
        .then((req) {
          req.headers.set('Accept', 'multipart/x-mixed-replace, image/jpeg');
          return req.close();
        })
        .then((resp) {
          if (resp.statusCode != 200) {
            setState(() { _error = 'HTTP ${resp.statusCode}'; _loading = false; });
            return;
          }
          setState(() => _loading = false);
          _subscription = resp
              .map((chunk) => chunk is Uint8List ? chunk : Uint8List.fromList(chunk))
              .transform(_MjpegTransformer())
              .listen(
                (frame) {
                final now = DateTime.now().millisecondsSinceEpoch;
                if (now - _lastFrameMs < 80) return; // 节流 ~12fps
                _lastFrameMs = now;
                widget.onFrame?.call(frame);
                if (mounted) setState(() => _latestFrame = frame);
              },
                onError: (e) {
                  if (mounted) setState(() { _error = e.toString(); _loading = false; });
                },
                onDone: () {
                  if (mounted) Future.delayed(const Duration(seconds: 2), () { if (mounted) _connect(); });
                },
                cancelOnError: false,
              );
        })
        .catchError((e) {
          if (mounted) {
            setState(() { _error = e.toString(); _loading = false; });
            Future.delayed(const Duration(seconds: 3), () { if (mounted) _connect(); });
          }
        });
  }

  void _disconnect() {
    _subscription?.cancel();
    _subscription = null;
    _client?.close(force: true);
    _client = null;
  }

  @override
  void dispose() {
    _disconnect();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // 错误状态
    if (_error != null && _latestFrame == null) {
      return widget.errorBuilder?.call(context) ??
          _buildPlaceholder(_error!);
    }

    // 加载中
    if (_loading && _latestFrame == null) {
      return widget.placeholder?.call(context) ??
          _buildPlaceholder('正在连接视频流...');
    }

    // 有画面
    if (_latestFrame != null) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(10),
        child: Image.memory(
          _latestFrame!,
          width: widget.width ?? double.infinity,
          height: widget.height ?? 242,
          fit: BoxFit.contain,
          gaplessPlayback: true,
        ),
      );
    }

    return _buildPlaceholder('等待视频流...');
  }

  Widget _buildPlaceholder(String text) {
    return Container(
      width: widget.width ?? double.infinity,
      height: widget.height ?? 242,
      color: const Color(0xFF0A0F18),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.videocam,
                color: Color(0xFF9AA8BF), size: 48),
            const SizedBox(height: 8),
            Text('实时视频流', style: const TextStyle(
                fontWeight: FontWeight.w400,
                fontSize: 13,
                color: Color(0xFF9AA8BF))),
            const SizedBox(height: 4),
            Text(text, style: const TextStyle(
                fontWeight: FontWeight.w400,
                fontSize: 12,
                color: Color(0xFF9AA8BF))),
          ],
        ),
      ),
    );
  }
}

/// 将 MJPEG multipart 流转换为逐帧 Uint8List
class _MjpegTransformer extends StreamTransformerBase<Uint8List, Uint8List> {
  final _ChunkedBuffer _buffer = _ChunkedBuffer();

  _MjpegTransformer();

  @override
  Stream<Uint8List> bind(Stream<Uint8List> stream) {
    return stream.transform(
      StreamTransformer<Uint8List, Uint8List>.fromHandlers(
        handleData: (data, sink) {
          _processChunk(data, sink);
        },
        handleDone: (sink) {
          sink.close();
        },
      ),
    );
  }

  void _processChunk(Uint8List chunk, EventSink<Uint8List> sink) {
    _buffer.add(chunk);

    // MJPEG 流的 JPEG 帧以 0xFF 0xD8 开始，0xFF 0xD9 结束
    while (true) {
      final bytes = _buffer.toUint8List();
      final soi = _findSoi(bytes);   // Start of Image
      final eoi = _findEoi(bytes);   // End of Image

      if (soi == -1 || eoi == -1 || eoi <= soi) break;

      // 提取完整 JPEG（至少 1KB，确保是有效帧）
      final frame = Uint8List.sublistView(bytes, soi, eoi + 2);
      if (frame.length > 1000) sink.add(frame);

      // 丢弃已处理的数据
      _buffer.discard(eoi + 2);
    }
  }

  int _findSoi(Uint8List data) {
    for (int i = 0; i < data.length - 1; i++) {
      if (data[i] == 0xFF && data[i + 1] == 0xD8) return i;
    }
    return -1;
  }

  int _findEoi(Uint8List data) {
    for (int i = 0; i < data.length - 1; i++) {
      if (data[i] == 0xFF && data[i + 1] == 0xD9) return i;
    }
    return -1;
  }
}

/// 高效的字节缓冲区
class _ChunkedBuffer {
  final List<Uint8List> _chunks = [];
  int _totalLength = 0;
  int _discardOffset = 0;

  void add(Uint8List chunk) {
    if (chunk.isNotEmpty) {
      _chunks.add(chunk);
      _totalLength += chunk.length;
    }
  }

  Uint8List toUint8List() {
    if (_chunks.isEmpty) return Uint8List(0);
    if (_chunks.length == 1 && _discardOffset == 0) return _chunks.first;

    final result = Uint8List(_totalLength - _discardOffset);
    int offset = 0;
    int remaining = _discardOffset;

    for (final chunk in _chunks) {
      if (remaining > 0) {
        if (chunk.length <= remaining) {
          remaining -= chunk.length;
          continue;
        }
        final useful = chunk.length - remaining;
        result.setRange(offset, offset + useful, chunk.sublist(remaining));
        offset += useful;
        remaining = 0;
      } else {
        result.setRange(offset, offset + chunk.length, chunk);
        offset += chunk.length;
      }
    }
    return result;
  }

  void discard(int count) {
    _discardOffset += count;
    // 清理已完全消耗的块
    while (_chunks.isNotEmpty && _discardOffset >= _chunks.first.length) {
      _discardOffset -= _chunks.first.length;
      _totalLength -= _chunks.first.length;
      _chunks.removeAt(0);
    }
  }
}
