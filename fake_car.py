#!/usr/bin/env python3
"""模拟小车 API 服务器 — 在 PC 上运行，可启动多实例模拟多台小车"""
import argparse
from flask import Flask, jsonify, request
from flask_cors import CORS
import threading, time, math

app = Flask(__name__)
CORS(app)

# ===== 模拟状态 =====
CAR_ID = "car_B"
PORT = 5001

fake_pos = {'x': 0.0, 'y': 0.0, 'theta': 0.0}
fake_sensors = {
    'temperature': 26.3, 'humidity': 55.0, 'smoke': 0,
    'pm25': 12, 'pressure': 1015, 'light': 480, 'co2': 420,
    'gps': {'lat': 22.5431, 'lon': 113.9540}
}
fake_battery = 12.3
nav_goal = None  # 当前导航目标: (x, y, theta)
lock = threading.Lock()


def get_ip():
    return '127.0.0.1'


def sim_motion_loop():
    """模拟运动线程：驱动轮速、导航"""
    while True:
        time.sleep(0.1)
        with lock:
            global nav_goal
            # 导航模式：向目标点移动
            if nav_goal is not None:
                dx = nav_goal[0] - fake_pos['x']
                dy = nav_goal[1] - fake_pos['y']
                dist = math.hypot(dx, dy)
                if dist < 0.05:  # 到达
                    fake_pos['x'] = nav_goal[0]
                    fake_pos['y'] = nav_goal[1]
                    nav_goal = None
                else:
                    # 每步移动 0.03m（约 0.3m/s）
                    step = min(0.03, dist)
                    fake_pos['x'] += (dx / dist) * step
                    fake_pos['y'] += (dy / dist) * step
                    fake_pos['theta'] = math.atan2(dy, dx)


threading.Thread(target=sim_motion_loop, daemon=True).start()


# ===== API =====

@app.route('/api/status')
def get_status():
    with lock:
        return jsonify({'code': 0, 'data': {
            'car_id': CAR_ID,
            'sensors': dict(fake_sensors),
            'battery': fake_battery,
            'ip': get_ip(),
            'position': dict(fake_pos),
            'nav_goal': nav_goal,
        }})


@app.route('/api/move', methods=['POST'])
def move():
    data = request.json
    cmd = data.get('cmd', 'stop')
    s = min(data.get('speed', 50), 100)
    speed = s / 100.0

    with lock:
        global nav_goal
        nav_goal = None  # move 指令取消导航
        theta = fake_pos['theta']
        if cmd == 'forward':
            fake_pos['x'] += speed * 0.3 * math.cos(theta)
            fake_pos['y'] += speed * 0.3 * math.sin(theta)
        elif cmd == 'backward':
            fake_pos['x'] -= speed * 0.15 * math.cos(theta)
            fake_pos['y'] -= speed * 0.15 * math.sin(theta)
        elif cmd == 'left':
            fake_pos['theta'] += speed * 0.2
        elif cmd == 'right':
            fake_pos['theta'] -= speed * 0.2

    return jsonify({'code': 0, 'msg': f'[{CAR_ID}] {cmd} @ {s}%'})


@app.route('/api/navigate', methods=['POST'])
def navigate():
    """模拟导航：设置目标点，运动线程自动向目标移动"""
    data = request.json
    x, y, theta = data.get('x', 0), data.get('y', 0), data.get('theta', 0)
    with lock:
        global nav_goal
        nav_goal = (x, y, theta)
    return jsonify({'code': 0, 'msg': f'[{CAR_ID}] navigate to ({x:.2f}, {y:.2f})'})


@app.route('/api/sensors')
def get_sensors():
    return jsonify({'code': 0, 'data': fake_sensors})


@app.route('/api/health')
def health():
    return jsonify({'code': 0, 'msg': f'[{CAR_ID}] Simulated API Running'})


@app.route('/video_feed')
def video_feed():
    """模拟摄像头：返回纯色占位图"""
    import io
    from PIL import Image
    w, h = 320, 240
    img = Image.new('RGB', (w, h),
                    color=(30 + hash(CAR_ID) % 200,
                           30 + hash(CAR_ID * 2) % 200,
                           60))
    import cv2, numpy as np
    frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    cv2.putText(frame, CAR_ID, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(frame, f'POS:({fake_pos["x"]:.1f},{fake_pos["y"]:.1f})',
                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    _, jpg = cv2.imencode('.jpg', frame)
    return jpg.tobytes(), 200, {'Content-Type': 'image/jpeg'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='模拟小车 API')
    parser.add_argument('--port', type=int, default=5001, help='监听端口')
    parser.add_argument('--id', type=str, default='car_B', help='小车 ID')
    args = parser.parse_args()
    CAR_ID = args.id
    PORT = args.port
    print(f'[{CAR_ID}] 模拟小车 API 启动于端口 {PORT}')
    print(f'  http://localhost:{PORT}/api/health')
    print(f'  http://localhost:{PORT}/api/status')
    print(f'  http://localhost:{PORT}/api/move')
    print(f'  http://localhost:{PORT}/api/navigate')
    print(f'  http://localhost:{PORT}/video_feed')
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)