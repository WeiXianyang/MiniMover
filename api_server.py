#!/usr/bin/env python3
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import threading, time, os, sys, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sensors.icar_sensor_driver import iCarSensorDriver
from Rosmaster_Lib import Rosmaster

app = Flask(__name__)
CORS(app)
sensor = iCarSensorDriver()
bot = Rosmaster(debug=False)
bot.create_receive_threading()

def get_ip():
    return os.popen('hostname -I').read().split()[0]

@app.route('/api/status')
def get_status():
    ip = get_ip()
    vol = bot.get_battery_voltage()
    return jsonify({'code':0, 'data':{
        'sensors': sensor.get_data(),
        'battery': round(vol, 1) if vol else 12.0,
        'ip': ip
    }})

@app.route('/api/move', methods=['POST'])
def move():
    data = request.json; cmd = data.get('cmd','stop')
    s = min(data.get('speed',50),100); t = data.get('duration',0.5)
    speed = s/100.0*50; vx=vy=vz=0
    if cmd=='forward': vx=speed
    elif cmd=='backward': vx=-speed
    elif cmd=='left': vz=speed*0.5
    elif cmd=='right': vz=-speed*0.5
    elif cmd=='left_shift': vy=speed
    elif cmd=='right_shift': vy=-speed
    bot.set_car_motion(vx,vy,vz)
    if cmd!='stop' and t>0:
        threading.Thread(target=lambda:(time.sleep(t),bot.set_car_motion(0,0,0)),daemon=True).start()
    return jsonify({'code':0,'msg':f'{cmd} @ {s}%'})

@app.route('/api/sensors')
def get_sensors():
    return jsonify({'code':0,'data':sensor.get_data()})

@app.route('/api/health')
def health():
    return jsonify({'code':0,'msg':'FireGuard API Running'})

# ===== 地图导航 =====

MAP_FILE = '/root/yahboomcar_ros2_ws/yahboomcar_ws/src/yahboomcar_nav/maps/icar.pgm'
MAP_YAML = '/root/yahboomcar_ros2_ws/yahboomcar_ws/src/yahboomcar_nav/maps/icar.yaml'
CID = subprocess.getoutput('sudo docker ps -q | head -1')

@app.route('/api/map')
def map_info():
    """返回地图信息"""
    CONTAINER_ID = subprocess.getoutput('sudo docker ps -q | head -1')
    info = {'width': 0, 'height': 0, 'resolution': 0.05, 'origin': [-10, -10, 0]}
    # 尝试读取 YAML
    try:
        yaml_text = subprocess.check_output(
            ['docker', 'exec', CONTAINER_ID, 'cat', MAP_YAML],
            timeout=3).decode()
        import re
        res = re.search(r'resolution:\s*([\d.]+)', yaml_text)
        org = re.search(r'origin:\s*\[([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)\]', yaml_text)
        img = re.search(r'image:\s*(.+)', yaml_text)
        if res: info['resolution'] = float(res.group(1))
        if org: info['origin'] = [float(org.group(1)), float(org.group(2)), float(org.group(3))]
    except:
        pass
    # 读取 PGM 获取尺寸
    try:
        pgm = subprocess.check_output(
            ['docker', 'exec', CONTAINER_ID, 'head', '-5', MAP_FILE],
            timeout=3).decode()
        lines = pgm.strip().split('\n')
        if len(lines) >= 3:
            w, h = map(int, lines[2].split())
            info['width'], info['height'] = w, h
    except:
        pass
    return jsonify({'code': 0, 'data': info})

@app.route('/api/map_image')
def map_image():
    """返回地图图片 (PNG)"""
    CONTAINER_ID = subprocess.getoutput('sudo docker ps -q | head -1')
    try:
        import cv2, numpy as np
        pgm_bytes = subprocess.check_output(
            ['docker', 'exec', CONTAINER_ID, 'cat', MAP_FILE],
            timeout=5)
        img = cv2.imdecode(np.frombuffer(pgm_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
        if img is None:
            # 直接读取 PGM 格式
            import struct
            header = pgm_bytes.split(b'\n', 4)
            data_start = pgm_bytes.find(b'\n', pgm_bytes.find(b'\n', pgm_bytes.find(b'\n')+1)+1) + 1
            raw = pgm_bytes[data_start:]
            dims = header[2].split()
            w, h = int(dims[0]), int(dims[1])
            img = np.frombuffer(raw[:w*h], dtype=np.uint8).reshape((h, w))
        # 彩色化：黑色=障碍物，白色=可通行，灰色=未知
        colored = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
        colored[img > 200] = [255, 255, 255]  # 白色-空闲
        colored[(img >= 50) & (img <= 200)] = [200, 200, 200]  # 灰色-未知
        colored[img < 50] = [30, 30, 30]  # 黑色-障碍物
        _, jpg = cv2.imencode('.jpg', colored, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return Response(jpg.tobytes(), mimetype='image/jpeg')
    except Exception as e:
        return str(e), 500

@app.route('/api/navigate', methods=['POST'])
def navigate():
    """发送导航目标点 (map 坐标系)
    POST: {"x": 1.0, "y": 2.0, "theta": 0.0}
    """
    data = request.json
    x, y, theta = data.get('x', 0), data.get('y', 0), data.get('theta', 0)
    CONTAINER_ID = subprocess.getoutput('sudo docker ps -q | head -1')
    if not CONTAINER_ID:
        return jsonify({'code': -1, 'msg': '容器未运行'})
    cmd = f'''source /root/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash && \
ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose "{{pose: {{pose: {{position: {{x: {x}, y: {y}}}, orientation: {{z: {theta}}}}}}}"'''
    subprocess.Popen(['docker', 'exec', CONTAINER_ID, 'bash', '-c', cmd],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return jsonify({'code': 0, 'msg': f'导航到 ({x:.2f}, {y:.2f})'})

@app.route('/nav')
def nav_page():
    """地图导航页面"""
    return '''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>地图导航</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#1a1a2e;color:#eee;font-family:Arial;text-align:center;padding:10px}
h1{font-size:18px;color:#e94560;margin:8px 0}
.map-wrap{position:relative;display:inline-block;margin:8px auto;border:2px solid #333;border-radius:8px;overflow:hidden}
.map-wrap img{display:block;max-width:100%;cursor:crosshair}
.info{font-size:13px;color:#aaa;margin:4px 0}
.btn{padding:8px 20px;border:none;border-radius:8px;cursor:pointer;margin:4px;font-size:14px}
.btn-nav{background:#0f3460;color:#eee}
.btn-stop{background:#e94560;color:#fff}
.marker{position:absolute;width:12px;height:12px;background:#e94560;border:2px solid #fff;border-radius:50%;transform:translate(-50%,-50%);pointer-events:none}
</style>
</head>
<body>
<h1>🗺️ 地图导航</h1>
<div class="info">点击地图设定目标点，小车自动导航过去</div>
<div class="info" id="coordInfo">请选择目标点</div>
<div class="map-wrap" id="mapWrap">
<img id="mapImg" src="/api/map_image" alt="地图">
</div>
<div>
<button class="btn btn-nav" onclick="sendGoal()">🚗 前往目标点</button>
<button class="btn btn-stop" onclick="cancelGoal()">⏹ 停止</button>
<button class="btn btn-nav" onclick="window.location='/'">🔙 返回控制面板</button>
</div>
<div class="info" id="statusInfo">等待操作...</div>
<script>
var API=window.location.origin;
var targetX=0,targetY=0,mapW=0,mapH=0;
var mapInfo={resolution:0.05,origin:[-10,-10,0]};

document.getElementById('mapImg').onload=function(){
 mapW=this.naturalWidth;mapH=this.naturalHeight;
 fetch(API+'/api/map').then(function(r){return r.json()}).then(function(j){
  if(j.code==0) mapInfo=j.data;
 }).catch(function(){});
};

document.getElementById('mapImg').onclick=function(e){
 var rect=this.getBoundingClientRect();
 var px=e.clientX-rect.left;
 var py=e.clientY-rect.top;
 // 像素比例
 var sx=mapW/this.width;var sy=mapH/this.height;
 var imgX=px*sx;var imgY=py*sy;
 // 转地图坐标
 targetX=imgX*mapInfo.resolution+mapInfo.origin[0];
 targetY=(mapH-imgY)*mapInfo.resolution+mapInfo.origin[1];
 document.getElementById('coordInfo').textContent=
  '目标点: ('+targetX.toFixed(2)+', '+targetY.toFixed(2)+')  像素: ('+Math.round(imgX)+', '+Math.round(imgY)+')';
 // 显示标记
 var old=document.querySelector('.marker');if(old)old.remove();
 var mk=document.createElement('div');mk.className='marker';
 mk.style.left=px+'px';mk.style.top=py+'px';
 document.getElementById('mapWrap').appendChild(mk);
};

function sendGoal(){
 if(!targetX&&!targetY) return;
 document.getElementById('statusInfo').textContent='正在导航到 ('+targetX.toFixed(2)+', '+targetY.toFixed(2)+')...';
 document.getElementById('statusInfo').style.color='#38bdf8';
 var r=new XMLHttpRequest();
 r.open('POST',API+'/api/navigate',true);
 r.setRequestHeader('Content-Type','application/json');
 r.send(JSON.stringify({x:targetX,y:targetY,theta:0}));
 r.onload=function(){
  var j=JSON.parse(r.responseText);
  document.getElementById('statusInfo').textContent=j.msg;
 };
}

function cancelGoal(){
 document.getElementById('statusInfo').textContent='已取消导航';
 document.getElementById('statusInfo').style.color='#e94560';
}
</script>
</body>
</html>'''

@app.route('/video_feed')
def video_feed():
    def gen():
        while True:
            try:
                jpeg = subprocess.check_output(
                    ['curl', '-s', 'http://localhost:8080/snapshot?topic=/camera/color/image_raw'],
                    timeout=3)
                if len(jpeg) > 1000:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n')
                else:
                    time.sleep(0.2)
            except:
                time.sleep(0.5)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def dashboard():
    return '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0,user-scalable=no"><title>FireGuard</title><style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#1a1a2e;color:#eee;font-family:Arial;text-align:center;padding:10px}
h1{font-size:18px;color:#e94560;margin:8px 0}
.video-wrap{background:#16213e;border-radius:10px;padding:8px;margin:8px auto;max-width:700px}
.video-wrap img{width:100%;border-radius:6px;display:block}
.ip-bar{font-size:13px;color:#aaa;margin:6px 0}
.sensors{display:flex;flex-wrap:wrap;justify-content:center;gap:6px;margin:8px 0}
.sensors span{background:#0f3460;padding:4px 12px;border-radius:15px;font-size:13px}
.ctrl-grid{display:inline-grid;grid-template-columns:70px 70px 70px;gap:6px;margin:10px 0}
.ctrl-grid button{height:60px;border:none;border-radius:10px;font-size:22px;cursor:pointer;background:#16213e;color:#eee}
.ctrl-grid button:active{transform:scale(.92)}
.ctrl-grid .fwd{grid-column:2;background:#0f3460}
.ctrl-grid .bk{grid-column:2;background:#0f3460}
.ctrl-grid .stop{grid-column:2;background:#e94560;font-size:16px;height:44px}
.speed-bar{display:flex;align-items:center;justify-content:center;gap:10px;margin:8px 0;font-size:14px}
.nav-link{display:inline-block;margin:6px;padding:6px 16px;border-radius:8px;background:#0f3460;color:#38bdf8;text-decoration:none;font-size:13px}
</style></head><body>
<h1>FIRECUARD</h1>
<a class="nav-link" href="/nav">🗺️ 地图导航</a>
<div class="ip-bar" id="ipBar">连接中...</div>
<div class="sensors" id="sensorBar"></div>
<div class="video-wrap"><img id="videoFeed" src="" alt="video"></div>
<div class="ctrl-grid">
<button class="fwd" ontouchstart="m("forward")" onmousedown="m("forward")">^</button>
<button ontouchstart="m("left")" onmousedown="m("left")"><</button>
<button class="stop" ontouchstart="m("stop")" onmousedown="m("stop")">STOP</button>
<button ontouchstart="m("right")" onmousedown="m("right")">></button>
<button class="bk" ontouchstart="m("backward")" onmousedown="m("backward")">v</button>
</div>
<div class="speed-bar"><span>速度</span><input type="range" id="sp" min="10" max="100" value="50" oninput="document.getElementById("sv").textContent=this.value"><span id="sv">50</span></div>
<script>
var API=window.location.origin;
function f(){
 var r=new XMLHttpRequest();
 r.open("GET",API+"/api/status",true);
 r.onload=function(){
  var j=JSON.parse(r.responseText);
  if(j.code!=0)return;
  document.getElementById("ipBar").textContent="IP: "+j.data.ip;
  document.getElementById("videoFeed").src=API+"/video_feed?"+Date.now();
  var s=j.data.sensors;
  document.getElementById("sensorBar").innerHTML="<span>T:"+s.temperature.toFixed(1)+"C</span><span>H:"+s.humidity.toFixed(0)+"%</span><span>SMK:"+s.smoke+"</span><span>PM:"+s.pm25+"</span><span>P:"+s.pressure.toFixed(0)+"hPa</span><span>CO2:"+s.co2+"</span><span>BAT:"+j.data.battery+"V</span>";
 }; r.send();
}
function m(c){
 var s=document.getElementById("sp").value;
 var r=new XMLHttpRequest();
 r.open("POST",API+"/api/move",true);
 r.setRequestHeader("Content-Type","application/json");
 r.send(JSON.stringify({cmd:c,speed:parseInt(s),duration:0.4}));
}
setInterval(f,3000);f();
</script></body></html>'''

if __name__ == '__main__':
    sensor.start()
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
