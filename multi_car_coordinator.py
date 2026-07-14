#!/usr/bin/env python3
"""多车协同调度中心 — 车辆注册/状态轮询/队形控制/碰撞检测/可视化面板"""
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor
import threading, time, math, requests, io, os, subprocess, sys

import logging as _logging
_logging.basicConfig(
    level=_logging.INFO,
    format='%(asctime)s [coordinator] %(message)s',
    datefmt='%H:%M:%S',
)
_log = _logging.getLogger('coordinator')

COORDINATOR_PORT = 8888
POLL_INTERVAL = 5.0  # 状态轮询间隔(秒)，车慢时不堆积
POLL_TIMEOUT = 3     # 单个车请求超时(秒)
MOVE_CONNECT_TIMEOUT = 4  # 运动指令建立连接的最长等待时间(秒)
MOVE_READ_TIMEOUT = 5     # 运动指令等待车辆响应的最长时间(秒)
COLLISION_CRITICAL = 0.5  # 碰撞临界距离(米)
COLLISION_WARNING = 1.0   # 碰撞预警距离(米)

# ===== 车辆注册表 =====
CARS = {
    'car_A':  {'ip': '192.168.137.23',  'port': 5000, 'real': True},
    'car_B':  {'ip': '192.168.137.254', 'port': 5000, 'real': True},
}

app = Flask(__name__)
CORS(app)

# 后台状态缓存
_status_cache = {}
_position_cache = {}
_collision_alerts = {}
_lock = threading.Lock()
_voice_process = None
_voice_car_id = None
_voice_lock = threading.RLock()
_voice_log_path = os.path.join(os.path.dirname(__file__), "tmp", "voice_service.log")
os.makedirs(os.path.dirname(_voice_log_path), exist_ok=True)


# ========== 工具函数 ==========

MOVE_COMMANDS = frozenset({
    'forward', 'backward', 'left', 'right',
    'rotate_left', 'rotate_right', 'left_shift', 'right_shift', 'stop',
})


def api(car_id, endpoint, method='GET', data=None, timeout=3):
    """通过车辆自身的 5000 端口 API 访问车辆服务。"""
    info = CARS.get(car_id)
    if not info:
        return {'code': -1, 'msg': 'unknown car'}
    url = f"http://{info['ip']}:{info['port']}{endpoint}"
    try:
        response = requests.request(method, url, json=data, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.ConnectTimeout:
        return {'code': -1, 'msg': f'{url}: 连接车辆超时'}
    except requests.ReadTimeout:
        return {'code': -1, 'msg': f'{url}: 等待车辆响应超时'}
    except requests.RequestException as error:
        return {'code': -1, 'msg': f'{url}: {error}'}
    except ValueError:
        return {'code': -1, 'msg': f'{url}: 响应不是 JSON'}


def _move_payload(data):
    """将总控面板输入规整为与车辆 /api/move 相同的请求体。"""
    command = data.get('cmd', 'stop')
    if command not in MOVE_COMMANDS:
        raise ValueError(f'不支持的运动指令: {command}')

    try:
        speed = max(0, min(int(data.get('speed', 50)), 100))
        duration = max(0, float(data.get('duration', 0.5)))
    except (TypeError, ValueError) as error:
        raise ValueError('speed 必须是 0-100 的整数，duration 必须是非负秒数') from error

    return {'cmd': command, 'speed': speed, 'duration': duration}


def poll_all():
    """并行轮询所有车辆"""
    def poll(cid):
        result = api(cid, '/api/status', timeout=POLL_TIMEOUT)
        pos = None
        if result.get('code') == 0:
            pos = result['data'].get('position')
        return cid, (result, pos)  # (key, value) pair for dict()

    with ThreadPoolExecutor(max_workers=len(CARS)) as pool:
        results = dict(pool.map(lambda cid: poll(cid), list(CARS.keys())))

    with _lock:
        for cid, (result, pos) in results.items():
            _status_cache[cid] = result
            if pos:
                _position_cache[cid] = (pos['x'], pos['y'])

    # 碰撞检测
    _check_collisions()


def _check_collisions():
    """基于位置缓存计算两两碰撞风险"""
    global _collision_alerts
    alerts = {}
    items = [(cid, pos) for cid, pos in _position_cache.items() if pos]
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            cid_a, (x1, y1) = items[i]
            cid_b, (x2, y2) = items[j]
            dist = math.hypot(x2 - x1, y2 - y1)
            if dist < COLLISION_CRITICAL:
                level = 'CRITICAL'
            elif dist < COLLISION_WARNING:
                level = 'WARNING'
            else:
                continue
            alerts[f'{cid_a}_{cid_b}'] = {
                'cars': (cid_a, cid_b),
                'distance': round(dist, 2),
                'level': level,
            }
    _collision_alerts = alerts


_poll_lock = threading.Lock()

def poll_loop():
    """后台状态轮询线程，防止请求堆积"""
    while True:
        if _poll_lock.acquire(blocking=False):
            try:
                poll_all()
            finally:
                _poll_lock.release()
        time.sleep(POLL_INTERVAL)


threading.Thread(target=poll_loop, daemon=True).start()


# ========== 队形控制 ==========

def _formation_positions(fmt, spacing, car_ids):
    """计算各车的目标位置列表，返回 [(cid, x, y), ...]"""
    results = []
    n = len(car_ids)
    if fmt == 'line':       # 一字纵队: 沿 x 轴排列
        for i, cid in enumerate(car_ids):
            results.append((cid, -i * spacing, 0.0))
    elif fmt == 'row':      # 一字横排: 沿 y 轴排列
        offset = (n - 1) * spacing / 2.0
        for i, cid in enumerate(car_ids):
            results.append((cid, 0.0, i * spacing - offset))
    elif fmt == 'triangle': # 三角队形: 领头车在前，其余在后两翼
        results.append((car_ids[0], 0.0, 0.0))
        for i, cid in enumerate(car_ids[1:], start=1):
            side = 1 if i % 2 == 1 else -1
            row = (i + 1) // 2
            results.append((cid, -row * spacing, side * spacing * 0.5))
    return results


# ========== API ==========

@app.route('/api/cars')
def list_cars():
    """返回车辆注册表"""
    return jsonify({'code': 0, 'cars': {k: {kk: vv for kk, vv in v.items() if kk != 'status'}
                                        for k, v in CARS.items()}})


@app.route('/api/status')
def all_status():
    """所有车辆的状态快照"""
    with _lock:
        return jsonify({
            'code': 0,
            'cars': {
                cid: _status_cache.get(cid, {'code': -1, 'msg': 'no data'})
                for cid in CARS
            },
            'positions': dict(_position_cache),
            'collisions': _collision_alerts,
        })


@app.route('/api/move_all', methods=['POST'])
def move_all():
    """将与车辆 API 一致的运动指令并行转发给所有已注册车辆。"""
    try:
        payload = _move_payload(request.get_json(silent=True) or {})
    except ValueError as error:
        return jsonify({'code': -1, 'msg': str(error)}), 400

    car_ids = list(CARS)
    if not car_ids:
        return jsonify({'code': -1, 'msg': '没有已注册车辆'}), 409

    _log.info('BUTTON | %s speed=%s%% duration=%ss',
              payload['cmd'].upper(), payload['speed'], payload['duration'])

    def ctrl(car_id):
        result = api(
            car_id,
            '/api/move',
            'POST',
            payload,
            timeout=(MOVE_CONNECT_TIMEOUT, MOVE_READ_TIMEOUT),
        )
        _log.info('CAR %s | %s -> %s', car_id, payload['cmd'], result.get('msg', result))
        return car_id, result

    with ThreadPoolExecutor(max_workers=len(car_ids)) as pool:
        results = dict(pool.map(ctrl, car_ids))

    failed = [car_id for car_id, result in results.items() if result.get('code') != 0]
    return jsonify({
        'code': 0 if not failed else -1,
        'cmd': payload['cmd'],
        'speed': payload['speed'],
        'duration': payload['duration'],
        'results': results,
        'failed_cars': failed,
    }), 200 if not failed else 502


@app.route('/api/move_one', methods=['POST'])
def move_one():
    """将与车辆 API 一致的运动指令转发给指定车辆。"""
    data = request.get_json(silent=True) or {}
    car_id = data.get('car_id')
    if car_id not in CARS:
        return jsonify({'code': -1, 'msg': f'car {car_id} not found'}), 404

    try:
        payload = _move_payload(data)
    except ValueError as error:
        return jsonify({'code': -1, 'msg': str(error)}), 400

    _log.info('BUTTON | %s -> %s speed=%s%% duration=%ss',
              car_id, payload['cmd'].upper(), payload['speed'], payload['duration'])
    result = api(car_id, '/api/move', 'POST', payload)
    _log.info('CAR %s | %s -> %s', car_id, payload['cmd'], result.get('msg', result))
    return jsonify(result), 200 if result.get('code') == 0 else 502


@app.route('/api/navigate', methods=['POST'])
def navigate():
    """并行发送导航目标给指定车辆列表"""
    data = request.json
    car_ids = data.get('car_ids', list(CARS.keys()))
    x = data.get('x', 0)
    y = data.get('y', 0)
    theta = data.get('theta', 0)

    def nav(cid):
        return cid, api(cid, '/api/navigate', 'POST',
                        {'x': x, 'y': y, 'theta': theta})
    with ThreadPoolExecutor(max_workers=len(car_ids)) as pool:
        results = dict(pool.map(lambda cid: nav(cid), car_ids))
    return jsonify({'code': 0, 'results': results})


@app.route('/api/formation', methods=['POST'])
def set_formation():
    """队形控制
    POST: {"type": "line|row|triangle", "spacing": 2.0, "car_ids": [...]}
    """
    data = request.json
    fmt = data.get('type', 'line')
    spacing = data.get('spacing', 2.0)
    car_ids = data.get('car_ids', list(CARS.keys()))
    if len(car_ids) < 2:
        return jsonify({'code': -1, 'msg': 'need at least 2 cars'})

    targets = _formation_positions(fmt, spacing, car_ids)
    results = {}
    for cid, tx, ty in targets:
        r = api(cid, '/api/navigate', 'POST', {'x': tx, 'y': ty, 'theta': 0})
        results[cid] = r.get('msg', 'ok')
    return jsonify({
        'code': 0,
        'formation': fmt,
        'spacing': spacing,
        'targets': {cid: (tx, ty) for cid, tx, ty in targets},
        'results': results,
    })


@app.route('/api/register', methods=['POST'])
def register_car():
    """动态注册新车
    POST: {"car_id": "car_C", "ip": "192.168.1.103", "port": 5000}
    """
    data = request.json
    cid = data.get('car_id')
    ip = data.get('ip')
    port = data.get('port', 5000)
    if not cid or not ip:
        return jsonify({'code': -1, 'msg': 'car_id and ip required'}), 400
    if cid in CARS:
        return jsonify({'code': -1, 'msg': f'{cid} already registered'})

    CARS[cid] = {'ip': ip, 'port': port, 'real': True}
    print(f'[coordinator] 新车注册: {cid} @ {ip}:{port}')
    return jsonify({'code': 0, 'msg': f'{cid} registered'})


@app.route('/api/register_batch', methods=['POST'])
def register_batch():
    """批量注册 (部署脚本用)
    POST: {"cars": {"car_C": {"ip":"10.227.111.206", "port":5000}, ...}}
    """
    cars = request.json.get('cars', {})
    for cid, info in cars.items():
        CARS[cid] = {'ip': info['ip'], 'port': info.get('port', 5000), 'real': True}
        print(f'[coordinator] 批量注册: {cid} @ {info["ip"]}:{info.get("port", 5000)}')
    return jsonify({'code': 0, 'msg': f'{len(cars)} cars registered'})




@app.route('/api/cars/<car_id>', methods=['DELETE'])
def disconnect_car(car_id):
    """Remove a car from this coordinator without stopping its own services."""
    global _voice_process, _voice_car_id
    if car_id not in CARS:
        return jsonify({'code': -1, 'msg': f'car {car_id} not found'}), 404
    with _voice_lock:
        if _voice_car_id == car_id and _voice_process is not None and _voice_process.poll() is None:
            _voice_process.terminate()
            try:
                _voice_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                _voice_process.kill()
                _voice_process.wait(timeout=3)
            _voice_process = None
            _voice_car_id = None
    CARS.pop(car_id, None)
    with _lock:
        _status_cache.pop(car_id, None)
        _position_cache.pop(car_id, None)
        for key in list(_collision_alerts):
            if car_id in _collision_alerts[key].get('cars', ()):
                _collision_alerts.pop(key, None)
    return jsonify({'code': 0, 'msg': f'{car_id} disconnected'})

@app.route('/proxy/camera/<car_id>')
def proxy_camera(car_id):
    """代理各车的 MJPEG 视频流，避免跨域"""
    if car_id not in CARS:
        return 'car not found', 404
    info = CARS[car_id]
    stream_url = f"http://{info['ip']}:{info['port']}/video_feed"

    def generate():
        fail_count = 0
        while True:
            try:
                r = requests.get(stream_url, stream=True,
                                 timeout=(3, 30))  # (connect, read)
                fail_count = 0
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            except GeneratorExit:
                return
            except:
                fail_count += 1
                if fail_count >= 3:
                    # 连续失败 3 次，返回离线占位图，不会冻结在旧画面
                    import cv2, numpy as np
                    img = np.zeros((240, 320, 3), dtype=np.uint8)
                    cv2.putText(img, f'{car_id} offline', (20, 120),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    _, jpg = cv2.imencode('.jpg', img)
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                           jpg.tobytes() + b'\r\n')
                    time.sleep(3)
                else:
                    time.sleep(1)

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame',
                    headers={'Cache-Control': 'no-cache, no-store, must-revalidate',
                             'Pragma': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/dashboard')
def dashboard():
    """可视化面板"""
    return HTML_DASHBOARD


@app.route('/')
def index():
    return jsonify({
        'service': 'Multi-Car Coordinator',
        'dashboard': f'http://localhost:{COORDINATOR_PORT}/dashboard',
        'cars': f'http://localhost:{COORDINATOR_PORT}/api/cars',
        'status': f'http://localhost:{COORDINATOR_PORT}/api/status',
    })



# ========== 语音控制服务管理 ==========

def _voice_status():
    with _voice_lock:
        running = _voice_process is not None and _voice_process.poll() is None
        return {'running': running, 'pid': _voice_process.pid if running else None, 'car_id': _voice_car_id if running else None, 'log': _voice_log_path}


@app.route('/api/voice/status')
def voice_status():
    return jsonify({'code': 0, 'data': _voice_status()})


@app.route('/api/voice/start', methods=['POST'])
def voice_start():
    global _voice_process, _voice_car_id
    data = request.get_json(silent=True) or {}
    car_id = data.get('car_id', 'car_A')
    if car_id not in CARS:
        return jsonify({'code': -1, 'msg': f'car {car_id} not found'}), 404
    info = CARS[car_id]
    whisper_url = os.environ.get('MINIMOVER_WHISPER_URL', '').strip()
    api_key = os.environ.get('MINIMOVER_API_KEY', '').strip()
    if not whisper_url or not api_key:
        return jsonify({
            'code': -1,
            'msg': '缺少语音识别配置：请设置 MINIMOVER_WHISPER_URL 和 MINIMOVER_API_KEY',
            'data': {'required': ['MINIMOVER_WHISPER_URL', 'MINIMOVER_API_KEY']},
        }), 503
    with _voice_lock:
        if _voice_process is not None and _voice_process.poll() is None:
            return jsonify({'code': -1, 'msg': 'voice service is already running', 'data': _voice_status()}), 409
        env = os.environ.copy()
        env['MINIMOVER_CAR_URL'] = f"http://{info['ip']}:{info['port']}"
        env['MINIMOVER_ASR_BACKEND'] = 'remote_whisper'
        env['MINIMOVER_CAR_SPEAKER'] = '1'
        env['MINIMOVER_WHISPER_URL'] = whisper_url
        env['MINIMOVER_API_KEY'] = api_key
        log_file = open(_voice_log_path, 'a', encoding='utf-8')
        try:
            _voice_process = subprocess.Popen(
                [sys.executable, '-m', 'voice_assistant.voice_service', '--asr', 'remote_whisper'],
                cwd=os.path.dirname(os.path.abspath(__file__)), env=env,
                stdout=log_file, stderr=subprocess.STDOUT)
            _voice_car_id = car_id
        except Exception:
            log_file.close()
            raise
    return jsonify({'code': 0, 'msg': f'voice service started for {car_id}', 'data': _voice_status()})


@app.route('/api/voice/stop', methods=['POST'])
def voice_stop():
    global _voice_process, _voice_car_id
    with _voice_lock:
        process = _voice_process
        if process is None or process.poll() is not None:
            _voice_process = None
            _voice_car_id = None
            return jsonify({'code': 0, 'msg': 'voice service is not running', 'data': _voice_status()})
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        _voice_process = None
        _voice_car_id = None
    return jsonify({'code': 0, 'msg': 'voice service stopped', 'data': _voice_status()})

# ========== 内嵌 HTML 面板 (避免额外模板文件) ==========

HTML_DASHBOARD = f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Multi-Car Coordinator</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0d1117;color:#c9d1d9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto;padding:16px;max-width:1400px;margin:0 auto}}
h1{{font-size:20px;color:#58a6ff;margin-bottom:12px}}
h1 small{{font-size:12px;color:#8b949e;margin-left:8px}}
h2{{font-size:15px;color:#8b949e;margin:12px 0 6px}}

/* 车辆卡片网格 */
.car-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:12px;margin-bottom:16px}}
.car-card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;position:relative}}
.car-card.offline{{opacity:.5}}
.car-card.collision-critical{{border-color:#f85149;box-shadow:0 0 8px rgba(248,81,73,.3)}}
.car-card.collision-warning{{border-color:#d29922;box-shadow:0 0 8px rgba(210,153,34,.2)}}
.car-card.online{{border-color:#238636}}

.car-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}}
.car-name{{font-size:16px;font-weight:600;color:#58a6ff}}
.car-name .id{{color:#c9d1d9}}
.car-badge{{font-size:11px;padding:2px 6px;border-radius:4px;color:#fff}}
.badge-real{{background:#1f6feb}}
.badge-sim{{background:#6e7681}}
.badge-critical{{background:#f85149}}
.badge-warning{{background:#d29922;color:#0d1117}}

.car-body{{display:flex;gap:12px;flex-wrap:wrap}}
.car-info{{flex:1;min-width:140px;font-size:12px;line-height:1.8;color:#8b949e}}
.car-info span{{color:#c9d1d9}}

.car-video{{width:200px;height:150px;background:#0d1117;border-radius:4px;overflow:hidden;flex-shrink:0}}
.car-video img{{width:100%;height:100%;object-fit:cover}}

.car-collision{{margin-top:6px;font-size:12px;padding:4px 8px;border-radius:4px}}
.collision-critical{{background:#f8514933;color:#f85149;border:1px solid #f85149}}
.collision-warning{{background:#d2992233;color:#d29922;border:1px solid #d29922}}

/* 控制面板 */
.control-panel{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;margin-bottom:16px}}
.ctrl-row{{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin:6px 0}}
.ctrl-row button{{padding:8px 18px;border:1px solid #30363d;border-radius:6px;cursor:pointer;font-size:13px;background:#21262d;color:#c9d1d9}}
.ctrl-row button:hover{{background:#30363d}}
.ctrl-row button:active{{transform:scale(.95)}}
.ctrl-row .stop{{background:#da3633;border-color:#da3633;color:#fff}}
.ctrl-row .stop:hover{{background:#f85149}}
.ctrl-row .danger{{border-color:#f85149;color:#f85149}}
.disconnect{{padding:3px 7px;border:1px solid #d29922;border-radius:4px;cursor:pointer;background:#21262d;color:#d29922;font-size:11px}}
.ctrl-row label{{font-size:12px;color:#8b949e;margin-right:4px}}
.ctrl-row select,.ctrl-row input{{background:#0d1117;border:1px solid #30363d;border-radius:4px;color:#c9d1d9;padding:4px 8px;font-size:12px}}

/* 注册表单 */
.register-form{{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:6px 0}}
.register-form input{{background:#0d1117;border:1px solid #30363d;border-radius:4px;color:#c9d1d9;padding:6px 10px;font-size:12px;width:150px}}

/* 告警条 */
.alert-bar{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;margin-bottom:12px;font-size:13px}}
.alert-bar.warning{{border-color:#d29922}}
.alert-bar.critical{{border-color:#f85149}}
</style>
</head>
<body>
<h1>Multi-Car Coordinator <small>{COORDINATOR_PORT}</small></h1>

<div id="alertBar" class="alert-bar" style="display:none">Loading...</div>

<div class="car-grid" id="carGrid"></div>

<div class="control-panel">
  <div class="ctrl-row">
    <button onclick="moveAll('forward',50)">Forward</button>
    <button onclick="moveAll('backward',50)">Backward</button>
    <button onclick="moveAll('left',50)">Left</button>
    <button onclick="moveAll('right',50)">Right</button>
    <button onclick="moveAll('stop')" class="stop">STOP ALL</button>
  </div>
  <div class="ctrl-row">
    <label>Speed:</label>
    <input type="range" id="speedRange" min="10" max="100" value="50" oninput="sv.textContent=this.value" style="width:100px">
    <span id="sv">50</span>
  </div>
  <div class="ctrl-row">
    <label>Formation:</label>
    <select id="fmtSelect"><option value="line">Line (纵队)</option><option value="row">Row (横排)</option><option value="triangle">Triangle (三角)</option></select>
    <label>Spacing(m):</label>
    <input type="number" id="spacingInput" value="2.0" step="0.5" min="0.5" style="width:60px">
    <button onclick="applyFormation()">Apply Formation</button>
  </div>
</div>

<div class="control-panel">
  <h2>Register New Car</h2>
  <div class="register-form">
    <input id="regId" placeholder="car_id (e.g. car_D)" value="car_C">
    <input id="regIp" placeholder="IP (e.g. 10.227.111.206)" value="127.0.0.1">
    <input id="regPort" placeholder="Port" value="5002" style="width:80px">
    <button onclick="registerCar()">Register</button>
    <span id="regMsg" style="font-size:12px;color:#8b949e"></span>
  </div>
</div>

<div class="control-panel">
  <h2>车载语音控制</h2>
  <div class="ctrl-row">
    <label>Car:</label>
    <select id="voiceCar"><option value="car_A">car_A</option><option value="car_B">car_B</option></select>
    <button onclick="startVoice()">启动语音</button>
    <button onclick="stopVoice()" class="stop">停止语音</button>
    <span id="voiceStatus" style="font-size:12px;color:#8b949e">未启动</span>
  </div>
  <div style="font-size:12px;color:#8b949e">小车麦克风 → Whisper → 控车；反馈通过小车扬声器播放</div>
</div>

<script>
var API=window.location.origin;
var SPEED=50;


function disconnectCar(car){{
  if(!confirm('断开 '+car+'？只会从当前总控台移除，不会停止对方小车服务。')) return;
  fetch(API+'/api/cars/'+encodeURIComponent(car),{{method:'DELETE'}})
    .then(function(r){{return r.json()}}).then(function(d){{
      if(d.code!==0){{alert(d.msg||'断开失败');return;}}
      update();
    }});
}}

function updateVoiceStatus(){{
  fetch(API+'/api/voice/status').then(function(r){{return r.json()}}).then(function(data){{
    var d=data.data||{{}}, el=document.getElementById('voiceStatus');
    el.textContent=d.running?'运行中 PID='+d.pid:'未启动';
    el.style.color=d.running?'#3fb950':'#8b949e';
  }});
}}
function startVoice(){{
  var car=document.getElementById('voiceCar').value;
  fetch(API+'/api/voice/start',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{car_id:car}})}})
    .then(function(r){{return r.json()}}).then(function(d){{
      var el=document.getElementById('voiceStatus');
      el.textContent=d.msg||'启动完成';
      el.style.color=d.code===0?'#3fb950':'#f85149';
      if(d.code===0) updateVoiceStatus();
    }});
}}
function stopVoice(){{
  fetch(API+'/api/voice/stop',{{method:'POST'}}).then(function(r){{return r.json()}}).then(function(d){{document.getElementById('voiceStatus').textContent=d.msg||'已停止';updateVoiceStatus();}});
}}

function renderCars(data){{
  var grid=document.getElementById('carGrid');
  var cars=data.cars||{{}}, cols=data.collisions||{{}};
  var previousVideos={{}};
  Array.prototype.forEach.call(grid.querySelectorAll('.car-video img[data-car-id]'),function(video){{
    previousVideos[video.dataset.carId]=video;
  }});
  grid.innerHTML='';
  var keys=Object.keys(cars);
  if(!keys.length){{grid.innerHTML='<div style="color:#8b949e;padding:20px">No cars registered.</div>';return}}

  // 碰撞状态汇总
  var collMsg='';
  for(var k in cols){{
    var c=cols[k];
    collMsg+='<div class="collision-'+c.level.toLowerCase()+'">'+c.cars[0]+' <-> '+cars[1]+' : '+c.distance+'m</div>';
  }}

  for(var ci=0;ci<keys.length;ci++){{
    var cid=keys[ci];
    var s=cars[cid];
    var ok=s&&s.code===0;
    var d=ok?s.data:{{}};
    var pos=d.position||{{}};
    var bat=d.battery||'?';
    var ip=d.ip||'?';
    // 防抖：一次在线则保持在线，避免闪烁
    var ck='_ok_'+cid;
    if(ok){{window[ck]=1}}else if(window[ck]!==1){{window[ck]=0}}
    var online=window[ck]?'online':'offline';
    var cls='car-card '+online;

    // 碰撞标记
    var hasColl=false;
    for(var k in cols){{if(cols[k].cars.indexOf(cid)>=0){{cls+=' collision-'+cols[k].level.toLowerCase();hasColl=true;break;}}}}

    grid.innerHTML+=
      '<div class="'+cls+'">'+
        '<div class="car-header">'+
          '<div class="car-name"><span class="id">'+cid+'</span></div>'+
          '<div><span class="car-badge badge-real">REAL</span> '+
           '<button class="disconnect" onclick="disconnectCar(' + "'" + cid + "'" + ')">断开</button></div>'+
        '</div>'+
        '<div class="car-body">'+
          '<div class="car-info">'+
            'IP: <span>'+ip+'</span><br>'+
            'BAT: <span>'+bat+'V</span><br>'+
            'POS: <span>'+(pos.x!==undefined?pos.x.toFixed(2)+','+pos.y.toFixed(2):'N/A')+'</span><br>'+
            'T: <span>'+(d.sensors?d.sensors.temperature:'?')+'C</span> | '+
            'H: <span>'+(d.sensors?d.sensors.humidity:'?')+'%</span><br>'+
            'SMK: <span>'+(d.sensors?d.sensors.smoke:'?')+'</span> | '+
            'PM: <span>'+(d.sensors?d.sensors.pm25:'?')+'</span>'+
          '</div>'+
          '<div class="car-video" data-car-id="'+cid+'"></div>'+
        '</div>'+
        (hasColl&&cols[Object.keys(cols).find(function(k){{return cols[k].cars.indexOf(cid)>=0}})]?
          '<div class="car-collision collision-'+cols[Object.keys(cols).find(function(k){{return cols[k].cars.indexOf(cid)>=0}})].level.toLowerCase()+'">'+
            'Collision: '+cols[Object.keys(cols).find(function(k){{return cols[k].cars.indexOf(cid)>=0}})].distance+'m'+
          '</div>':'')+
      '</div>';

    var videoContainer=grid.querySelector('.car-video[data-car-id="'+cid+'"]');
    videoContainer.replaceChildren();
    var video=previousVideos[cid]||document.createElement('img');
    video.dataset.carId=cid;
    if(!video.src){{
      video.src='/proxy/camera/'+cid;
    }}
    video.onerror=function(){{this.remove();}};
    videoContainer.appendChild(video);
  }}
}}

function update(){{
  fetch(API+'/api/status').then(function(r){{return r.json()}}).then(function(data){{
    renderCars(data);
    // 告警栏
    var cols=data.collisions||{{}};
    var keys=Object.keys(cols);
    var bar=document.getElementById('alertBar');
    if(keys.length>0){{
      var msgs=[];
      for(var k in cols){{msgs.push(cols[k].cars[0]+' <-> '+cols[k].cars[1]+' : '+cols[k].distance+'m ('+cols[k].level+')');}}
      bar.style.display='block';
      bar.className='alert-bar';
      var maxLvl=Math.max.apply(null,keys.map(function(k){{return cols[k].level==='CRITICAL'?2:1}}));
      bar.className+=' '+(maxLvl===2?'critical':'warning');
      bar.innerHTML='Collision Alert: '+msgs.join(' | ');
    }}else{{
      bar.style.display='block';
      bar.className='alert-bar';
      bar.innerHTML='No collision alerts.';
    }}
  }}).catch(function(e){{document.getElementById('carGrid').innerHTML='<div style="color:#f85149">Error: '+e+'</div>';}});
}}

function moveAll(cmd,speed){{
  if(window.moveRequestInFlight){{
    return;
  }}

  var selectedSpeed=parseInt(document.getElementById('speedRange').value,10);
  SPEED=Number.isFinite(selectedSpeed)?selectedSpeed:(speed||50);
  var requestBody={{cmd:cmd,speed:SPEED,duration:0.5}};
  var bar=document.getElementById('alertBar');
  var controller=new AbortController();
  var timeoutId=window.setTimeout(function(){{controller.abort();}},12000);
  window.moveRequestInFlight=true;
  bar.style.display='block';
  bar.className='alert-bar';
  bar.textContent='正在向车辆转发 '+cmd+' 指令...';

  fetch(API+'/api/move_all',{{
    method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify(requestBody),
    signal:controller.signal
  }}).then(function(response){{
    return response.json().then(function(body){{return {{ok:response.ok,body:body}};}});
  }}).then(function(result){{
    var body=result.body;
    var details=Object.keys(body.results||{{}}).map(function(carId){{
      var carResult=body.results[carId]||{{}};
      return carId+': '+(carResult.msg||('code='+carResult.code));
    }});
    if(result.ok){{
      bar.className='alert-bar';
      bar.textContent='已转发 '+cmd+'。'+details.join(' | ');
    }}else{{
      bar.className='alert-bar critical';
      bar.textContent='转发失败。'+(body.msg||details.join(' | ')||'未知错误');
    }}
  }}).catch(function(error){{
    bar.className='alert-bar critical';
    bar.textContent=error.name==='AbortError'
      ? '转发超时，请检查车辆网络或服务后重试。'
      : '无法连接调度服务: '+error;
  }}).finally(function(){{
    window.clearTimeout(timeoutId);
    window.moveRequestInFlight=false;
  }});
}}

function applyFormation(){{
  var fmt=document.getElementById('fmtSelect').value;
  var spc=parseFloat(document.getElementById('spacingInput').value);
  var r=new XMLHttpRequest();
  r.open('POST',API+'/api/formation',true);
  r.setRequestHeader('Content-Type','application/json');
  r.send(JSON.stringify({{type:fmt,spacing:spc}}));
}}

function registerCar(){{
  var id=document.getElementById('regId').value;
  var ip=document.getElementById('regIp').value;
  var port=parseInt(document.getElementById('regPort').value);
  var r=new XMLHttpRequest();
  r.open('POST',API+'/api/register',true);
  r.setRequestHeader('Content-Type','application/json');
  r.onload=function(){{document.getElementById('regMsg').textContent=JSON.parse(r.responseText).msg;}};
  r.send(JSON.stringify({{car_id:id,ip:ip,port:port}}));
}}

setInterval(update,3000);update();
</script>
</body>
</html>'''


if __name__ == '__main__':
    print(f'[coordinator] 多车协同调度中心启动 http://localhost:{COORDINATOR_PORT}')
    print(f'  可视化面板: http://localhost:{COORDINATOR_PORT}/dashboard')
    print(f'  车辆状态:   http://localhost:{COORDINATOR_PORT}/api/status')
    print(f'  队形控制:   POST /api/formation')
    print(f'  碰撞检测:   GET  /api/status (collisions 字段)')
    app.run(
        host='0.0.0.0',
        port=COORDINATOR_PORT,
        debug=False,
        use_reloader=False,
        threaded=True,
    )