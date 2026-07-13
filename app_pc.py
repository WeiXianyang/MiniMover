#!/usr/bin/env python3
"""
Rosmaster PC 开发版启动器
跳过硬件依赖，仅启动 Web 界面用于前端调试。
实际控制小车需在 Jetson 上运行原版 app.py。
"""
from flask import Flask, render_template, Response
from gevent import pywsgi
import time
import sys

app = Flask(__name__)

# 模拟摄像头：用本地图片或摄像头0作为视频源
try:
    import cv2
    cap = cv2.VideoCapture(0)
    HAS_CAMERA = cap.isOpened()
except Exception:
    HAS_CAMERA = False

def gen_frames():
    """MJPEG 视频流生成器（优先 USB 摄像头，否则生成测试帧）"""
    if HAS_CAMERA:
        while True:
            success, frame = cap.read()
            if not success:
                break
            _, buf = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')
    else:
        import numpy as np
        while True:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "NO CAMERA", (200, 240),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            _, buf = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')
            time.sleep(0.1)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    print("=" * 50)
    print("  Rosmaster PC Dev - Web Server (端口 6500)")
    print("  浏览器访问: http://localhost:6500")
    print("  视频流: http://localhost:6500/video_feed")
    print("  [警告] PC 模式无小车控制功能，仅用于 Web 调试")
    print("=" * 50)

    server = pywsgi.WSGIServer(('0.0.0.0', 6500), app)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBye.")
