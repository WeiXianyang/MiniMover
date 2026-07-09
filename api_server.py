#!/usr/bin/env python3
""" iCar REST API Server - 提供给 Android APP 调用 """
from flask import Flask, jsonify, request
from flask_cors import CORS
import subprocess, threading, time, json, serial, struct

app = Flask(__name__)
CORS(app)

# ===== 传感器数据缓存 =====
sensor_data = {
    'temperature': 25.0,
    'humidity': 50.0,
    'smoke': 0,
    'pm25': 0,
    'pressure': 1013,
    'light': 500,
    'battery': 0,
    'gps': {'lat': 0, 'lon': 0}
}

def read_sensor_thread():
    """后台读取 IoT 传感器 (ttyUSB2)"""
    global sensor_data
    try:
        ser = serial.Serial('/dev/ttyUSB2', 115200, timeout=1)
        while True:
            if ser.in_waiting >= 6:
                d = ser.read(6)
                if d[0] == 0xa5:
                    node = d[1]
                    stype = d[2]
                    value = struct.unpack('<H', bytes(d[3:5]))[0]
                    # 根据 node:type 映射到传感器
                    if node == 1 and stype == 1:
                        sensor_data['temperature'] = value / 10.0
            time.sleep(0.1)
    except Exception as e:
        print(f'传感器读取失败: {e}')

def read_battery():
    """读取电池 (通过 Rosmaster_Lib)"""
    global sensor_data
    while True:
        try:
            from Rosmaster_Lib import Rosmaster
            bot = Rosmaster(debug=False)
            bot.create_receive_threading()
            time.sleep(0.5)
            sensor_data['battery'] = bot.get_battery_voltage()
            del bot
        except:
            pass
        time.sleep(5)

# ===== API 接口 =====

@app.route('/api/status')
def get_status():
    """获取小车状态"""
    return jsonify({'code': 0, 'data': sensor_data})

@app.route('/api/move', methods=['POST'])
def move():
    """控制小车移动
    POST JSON: {"cmd": "forward", "speed": 50, "duration": 1.0}
    cmd: forward/backward/left/right/stop/left_shift/right_shift
    """
    data = request.json
    cmd = data.get('cmd', 'stop')
    speed = data.get('speed', 50) / 100.0  # 0-100 -> 0-1 m/s
    duration = data.get('duration', 0.5)
    
    # 速度映射
    vel_map = {
        'forward':       (speed, 0, 0),
        'backward':      (-speed, 0, 0),
        'left':          (0, 0, speed),
        'right':         (0, 0, -speed),
        'left_shift':    (0, speed, 0),
        'right_shift':   (0, -speed, 0),
        'stop':          (0, 0, 0),
    }
    
    vx, vy, vz = vel_map.get(cmd, (0, 0, 0))
    
    # 通过 ros2 topic pub 控制
    if cmd != 'stop' and duration > 0:
        subprocess.Popen([
            'docker', 'exec', 'cbf404514e06',
            'bash', '-c',
            f'source /root/icar_ros2_ws/icar_ws/install/setup.bash && ros2 topic pub /cmd_vel geometry_msgs/Twist "{{linear: {{x: {vx}, y: {vy}, z: 0.0}}, angular: {{z: {vz}}}}}" --once'
        ])
        # 定时停止
        def stop_after(t):
            time.sleep(t)
            subprocess.run([
                'docker', 'exec', 'cbf404514e06',
                'bash', '-c',
                'source /root/icar_ros2_ws/icar_ws/install/setup.bash && ros2 topic pub /cmd_vel geometry_msgs/Twist "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {z: 0.0}}" --once'
            ], capture_output=True)
        threading.Thread(target=stop_after, args=(duration,), daemon=True).start()
    else:
        subprocess.run([
            'docker', 'exec', 'cbf404514e06',
            'bash', '-c',
            'source /root/icar_ros2_ws/icar_ws/install/setup.bash && ros2 topic pub /cmd_vel geometry_msgs/Twist "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {z: 0.0}}" --once'
        ], capture_output=True)
    
    return jsonify({'code': 0, 'msg': f'{cmd} done'})

@app.route('/api/camera')
def camera_info():
    """返回摄像头流地址"""
    import socket
    hostname = socket.gethostname()
    ip = subprocess.getoutput('hostname -I').split()[0]
    return jsonify({
        'code': 0,
        'streams': {
            'ir': f'http://{ip}:8080/stream_viewer?topic=/camera/ir/image_raw',
            'depth': f'http://{ip}:8080/stream_viewer?topic=/camera/depth/colorized',
        }
    })

@app.route('/api/health')
def health():
    return jsonify({'code': 0, 'msg': 'ok'})

if __name__ == '__main__':
    # 启动传感器读取线程
    # threading.Thread(target=read_sensor_thread, daemon=True).start()
    # threading.Thread(target=read_battery, daemon=True).start()
    
    app.run(host='0.0.0.0', port=5000, debug=False)
    print('API Server running on port 5000')
