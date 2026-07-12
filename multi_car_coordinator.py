#!/usr/bin/env python3
"""多车协同调度中心 — 车辆注册/状态轮询/队形控制/碰撞检测/可视化面板"""
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor
import threading, time, math, requests, io, os

COORDINATOR_PORT = 8888
POLL_INTERVAL = 1.0  # 状态轮询间隔(秒)
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


# ========== 工具函数 ==========

def api(car_id, endpoint, method='GET', data=None, timeout=3):
    info = CARS.get(car_id)
    if not info:
        return {'code': -1, 'msg': 'unknown car'}
    url = f"http://{info['ip']}:{info['port']}{endpoint}"
    try:
        if method == 'GET':
            r = requests.get(url, timeout=timeout)
        else:
            r = requests.post(url, json=data, timeout=timeout)
        return r.json()
    except Exception as e:
        return {'code': -1, 'msg': str(e)}


def poll_all():
    """并行轮询所有车辆"""
    def poll(cid):
        result = api(cid, '/api/status', timeout=2)
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


def poll_loop():
    """后台状态轮询线程"""
    while True:
        poll_all()
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
    """并行控制所有车辆"""
    data = request.json
    cmd = data.get('cmd', 'stop')
    speed = data.get('speed', 50)

    def ctrl(cid):
        return cid, api(cid, '/api/move', 'POST',
                        {'cmd': cmd, 'speed': speed, 'duration': 0.5})

    with ThreadPoolExecutor(max_workers=len(CARS)) as pool:
        results = dict(pool.map(lambda cid: ctrl(cid), list(CARS.keys())))
    return jsonify({'code': 0, 'results': results, 'cmd': cmd})


@app.route('/api/move_one', methods=['POST'])
def move_one():
    """控制指定车辆"""
    data = request.json
    cid = data.get('car_id')
    if cid not in CARS:
        return jsonify({'code': -1, 'msg': f'car {cid} not found'}), 404
    result = api(cid, '/api/move', 'POST', {
        'cmd': data.get('cmd', 'stop'),
        'speed': data.get('speed', 50),
        'duration': data.get('duration', 0.5),
    })
    return jsonify(result)


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


@app.route('/proxy/camera/<car_id>')
def proxy_camera(car_id):
    """代理各车的 MJPEG 视频流，避免跨域"""
    if car_id not in CARS:
        return 'car not found', 404
    info = CARS[car_id]
    stream_url = f"http://{info['ip']}:{info['port']}/video_feed"

    def generate():
        try:
            r = requests.get(stream_url, stream=True, timeout=5)
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    yield chunk
        except:
            # 返回占位图
            import cv2, numpy as np
            img = np.zeros((240, 320, 3), dtype=np.uint8)
            cv2.putText(img, f'{car_id} offline', (20, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            _, jpg = cv2.imencode('.jpg', img)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                   jpg.tobytes() + b'\r\n')

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


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

<script>
var API=window.location.origin;
var SPEED=50;

function renderCars(data){{
  var grid=document.getElementById('carGrid');
  var cars=data.cars||{{}}, cols=data.collisions||{{}};
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
    var online=ok?'online':'offline';
    var cls='car-card '+online;

    // 碰撞标记
    var hasColl=false;
    for(var k in cols){{if(cols[k].cars.indexOf(cid)>=0){{cls+=' collision-'+cols[k].level.toLowerCase();hasColl=true;break;}}}}

    grid.innerHTML+=
      '<div class="'+cls+'">'+
        '<div class="car-header">'+
          '<div class="car-name"><span class="id">'+cid+'</span></div>'+
          '<div><span class="car-badge badge-real">REAL</span></div>'+
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
          '<div class="car-video"><img src="/proxy/camera/'+cid+'?'+Date.now()+'" onerror="this.style.display=' + "'none'" + '"></div>'+
        '</div>'+
        (hasColl&&cols[Object.keys(cols).find(function(k){{return cols[k].cars.indexOf(cid)>=0}})]?
          '<div class="car-collision collision-'+cols[Object.keys(cols).find(function(k){{return cols[k].cars.indexOf(cid)>=0}})].level.toLowerCase()+'">'+
            'Collision: '+cols[Object.keys(cols).find(function(k){{return cols[k].cars.indexOf(cid)>=0}})].distance+'m'+
          '</div>':'')+
      '</div>';
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
  SPEED=speed||parseInt(document.getElementById('speedRange').value);
  var r=new XMLHttpRequest();
  r.open('POST',API+'/api/move_all',true);
  r.setRequestHeader('Content-Type','application/json');
  r.send(JSON.stringify({{cmd:cmd,speed:SPEED}}));
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

setInterval(update,2000);update();
</script>
</body>
</html>'''


if __name__ == '__main__':
    print(f'[coordinator] 多车协同调度中心启动 http://localhost:{COORDINATOR_PORT}')
    print(f'  可视化面板: http://localhost:{COORDINATOR_PORT}/dashboard')
    print(f'  车辆状态:   http://localhost:{COORDINATOR_PORT}/api/status')
    print(f'  队形控制:   POST /api/formation')
    print(f'  碰撞检测:   GET  /api/status (collisions 字段)')
    app.run(host='0.0.0.0', port=COORDINATOR_PORT, debug=False, use_reloader=False)