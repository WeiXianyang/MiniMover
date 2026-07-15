#!/usr/bin/env python3
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import threading, time, os, sys, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sensors.icar_sensor_driver import iCarSensorDriver
from Rosmaster_Lib import Rosmaster
from audio.icar_audio import record_start, record_status, record_stop, record_get
from audio.icar_audio import play_wav, stop_playback, say as tts_say, get_devices as audio_devices
from navigation import nav_bp, register_legacy_routes, register_patrol_page
from face import register_face_routes

app = Flask(__name__)
CORS(app)
app.register_blueprint(nav_bp, url_prefix='/api/nav')
register_legacy_routes(app)
register_patrol_page(app)
register_face_routes(app)
sensor = iCarSensorDriver()
bot = Rosmaster(debug=False)
bot.create_receive_threading()
_bot_lock = threading.Lock()

def get_ip():
    return os.popen('hostname -I').read().split()[0]

@app.route('/api/status')
def get_status():
    ip = get_ip()
    with _bot_lock:
        vol = bot.get_battery_voltage()
    return jsonify({'code':0, 'data':{
        'sensors': sensor.get_data(),
        'battery': round(vol, 1) if vol else 12.0,
        'ip': ip
    }})

# 底盘访问锁 + 看门狗线程（杜绝 Timer 漏触发导致一直转）
_stop_deadline = 0.0
_stop_deadline_lock = threading.Lock()

def _watchdog():
    """后台看门狗：到期后强制停止，每 0.2s 检查一次"""
    global _stop_deadline
    while True:
        with _stop_deadline_lock:
            deadline = _stop_deadline
        if deadline > 0 and time.monotonic() >= deadline:
            with _bot_lock:
                bot.set_car_motion(0, 0, 0)
            with _stop_deadline_lock:
                _stop_deadline = 0.0
        time.sleep(0.2)

threading.Thread(target=_watchdog, daemon=True).start()

@app.route('/api/move', methods=['POST'])
def move():
    global _stop_deadline
    data = request.json
    cmd = data.get('cmd', 'stop')
    s = min(data.get('speed', 50), 100)
    t = data.get('duration', 0.5)
    speed = s / 100.0
    vx = vy = vz = 0.0

    if cmd == 'forward':
        vx = speed
    elif cmd == 'backward':
        vx = -speed
    elif cmd in ('left', 'rotate_left'):
        vz = speed * 3
    elif cmd in ('right', 'rotate_right'):
        vz = -speed * 3
    elif cmd == 'left_shift':
        vy = speed
    elif cmd == 'right_shift':
        vy = -speed

    with _bot_lock:
        bot.set_car_motion(vx, vy, vz)

    if cmd == 'stop' or t <= 0:
        with _stop_deadline_lock:
            _stop_deadline = 0.0
    else:
        with _stop_deadline_lock:
            _stop_deadline = time.monotonic() + t

    return jsonify({'code': 0, 'msg': f'{cmd} @ {s}%'})

@app.route('/api/sensors')
def get_sensors():
    return jsonify({'code':0,'data':sensor.get_data()})

@app.route('/api/health')
def health():
    return jsonify({'code':0,'msg':'FireGuard API Running'})

# ===== 音频接口 =====
# /api/camera 与 /video_feed 见下方「视频流（可选）」

# 上一次录音的 ID (用于 stop 后前端知道下载哪个文件)
_last_record_id = ""

@app.route('/api/audio/devices')
def audio_devices_api():
    """返回音频设备信息"""
    return jsonify({'code': 0, 'data': audio_devices()})

@app.route('/api/audio/record/start', methods=['POST'])
def audio_record_start():
    """开始录音, POST: {"duration": 3}(可选秒数, 0=手动停止)"""
    global _last_record_id
    try:
        dur = float(request.json.get('duration', 0)) if request.json else 0
        rid = record_start(duration_sec=dur)
        _last_record_id = rid
        return jsonify({'code': 0, 'data': {'record_id': rid, 'msg': '录音已开始'}})
    except RuntimeError as e:
        return jsonify({'code': -1, 'msg': str(e)}), 409

@app.route('/api/audio/record/status')
def audio_record_status():
    """查询录音状态"""
    return jsonify({'code': 0, 'data': record_status()})

@app.route('/api/audio/record/stop', methods=['POST'])
def audio_record_stop():
    """停止录音, 返回 record_id 供前端下载"""
    global _last_record_id
    try:
        rid, wav_data = record_stop()
        _last_record_id = rid
        return jsonify({'code': 0, 'data': {
            'record_id': rid,
            'size': len(wav_data),
            'msg': f'录音完成 ({len(wav_data)} bytes)'
        }})
    except RuntimeError as e:
        return jsonify({'code': -1, 'msg': str(e)}), 409

@app.route('/api/audio/record/<record_id>.wav')
def audio_record_download(record_id):
    """下载指定录音的 WAV 文件"""
    try:
        wav_data = record_get(record_id)
        return Response(wav_data, mimetype='audio/wav',
                        headers={'Content-Disposition': f'attachment; filename="{record_id}.wav"'})
    except FileNotFoundError:
        return jsonify({'code': -1, 'msg': f'录音 {record_id} 不存在'}), 404

@app.route('/api/audio/play', methods=['POST'])
def audio_play():
    """上传 WAV 文件并播放 (multipart/form-data, field: file)"""
    if 'file' not in request.files:
        return jsonify({'code': -1, 'msg': '缺少 file 字段'}), 400
    f = request.files['file']
    try:
        play_wav(f.read())
        return jsonify({'code': 0, 'msg': '播放中'})
    except Exception as e:
        return jsonify({'code': -1, 'msg': str(e)}), 500

@app.route('/api/audio/say', methods=['POST'])
def audio_say():
    """TTS 文本转语音并播放, POST: {"text": "...", "lang": "zh"}"""
    data = request.json
    text = data.get('text', '')
    lang = data.get('lang', 'zh')
    if not text:
        return jsonify({'code': -1, 'msg': 'text 为空'}), 400
    try:
        wav = tts_say(text, lang)
        play_wav(wav)
        return jsonify({'code': 0, 'msg': f'TTS: {text[:20]}...' if len(text)>20 else f'TTS: {text}'})
    except Exception as e:
        return jsonify({'code': -1, 'msg': str(e)}), 500

@app.route('/api/audio/stop', methods=['POST'])
def audio_stop():
    """停止当前音频播放"""
    stop_playback()
    return jsonify({'code': 0, 'msg': '已停止'})

# ===== 音乐播放（BGM）=====
_BGM_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bgm.wav')
_music_playing = False

@app.route('/api/music/status')
def music_status():
    """查询 BGM 状态：文件是否存在、是否正在播放"""
    exists = os.path.isfile(_BGM_FILE)
    return jsonify({'code': 0, 'data': {
        'exists': exists,
        'playing': _music_playing,
        'file': 'bgm.wav' if exists else None,
        'size': os.path.getsize(_BGM_FILE) if exists else 0,
    }})

@app.route('/api/music/play', methods=['POST'])
def music_play():
    """播放 BGM（bgm.wav），若非 WAV 格式则自动用 ffmpeg 转码"""
    global _music_playing
    if not os.path.isfile(_BGM_FILE):
        return jsonify({'code': -1, 'msg': 'bgm.wav 不存在，请先上传到小车 ~/MiniMover/'}), 404
    try:
        # 检查文件头：WAV 以 RIFF 开头，MP3 以 ID3 或 0xFF 开头
        with open(_BGM_FILE, 'rb') as f:
            header = f.read(4)
        is_wav = header[:4] == b'RIFF'
        if is_wav:
            # 直接读取播放
            with open(_BGM_FILE, 'rb') as f:
                wav_data = f.read()
        else:
            # 非 WAV 格式（如 MP3），通过 ffmpeg 实时转码
            import subprocess as _sp
            proc = _sp.run(
                ['ffmpeg', '-i', _BGM_FILE, '-f', 'wav', '-acodec', 'pcm_s16le',
                 '-ar', '44100', '-ac', '2', '-y', '-loglevel', 'error', 'pipe:1'],
                capture_output=True, timeout=30)
            if proc.returncode != 0 or len(proc.stdout) < 44:
                raise RuntimeError(f'ffmpeg 转码失败: {proc.stderr.decode(errors="replace")[:200]}')
            wav_data = proc.stdout
        play_wav(wav_data)
        _music_playing = True
        return jsonify({'code': 0, 'msg': 'BGM 播放中'})
    except Exception as e:
        _music_playing = False
        return jsonify({'code': -1, 'msg': f'播放失败: {e}'}), 500

@app.route('/api/music/stop', methods=['POST'])
def music_stop():
    """停止 BGM 播放"""
    global _music_playing
    stop_playback()
    _music_playing = False
    return jsonify({'code': 0, 'msg': 'BGM 已停止'})

@app.route('/api/music/bgm.wav')
def music_download():
    """下载 bgm.wav 文件"""
    if not os.path.isfile(_BGM_FILE):
        return jsonify({'code': -1, 'msg': 'bgm.wav 不存在'}), 404
    return Response(
        open(_BGM_FILE, 'rb').read(),
        mimetype='audio/wav',
        headers={'Content-Disposition': 'attachment; filename="bgm.wav"'}
    )

# ===== 地图导航页面（单点导航；巡逻页见 /nav/patrol，API 见 /api/nav/*）=====
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

# ---- 视频流（可选）：巡逻/导航不需要相机；默认不强制占用 fireguard_cam ----
import urllib.request as _urllib_request

_SNAPSHOT_URL = 'http://localhost:8080/snapshot?topic=/camera/color/image_raw'
# MINIMOVER_DISABLE_CAMERA=1（start_nav_api.sh 默认）时完全不拉相机流
_DISABLE_CAMERA = os.environ.get('MINIMOVER_DISABLE_CAMERA', '0').strip() in ('1', 'true', 'True', 'yes')


def _placeholder_jpeg(text='No Camera'):
    """生成不依赖相机的占位图，避免 /video_feed 空转占连接。"""
    import cv2
    import numpy as np
    img = np.zeros((240, 320, 3), dtype=np.uint8)
    img[:] = (30, 30, 40)
    cv2.putText(img, text, (40, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
    cv2.putText(img, 'NAV mode OK without cam', (18, 160),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 180, 255), 1)
    _, jpg = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return jpg.tobytes()


_PLACEHOLDER_JPEG = None


def _get_placeholder():
    global _PLACEHOLDER_JPEG
    if _PLACEHOLDER_JPEG is None:
        try:
            _PLACEHOLDER_JPEG = _placeholder_jpeg()
        except Exception:
            # 极简 JPEG 头+占位，避免 cv2 不可用时崩溃
            _PLACEHOLDER_JPEG = (
                b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
                b'\xff\xd9'
            )
    return _PLACEHOLDER_JPEG


@app.route('/api/camera')
def camera_info():
    """返回视频流地址；disabled 时标明无需相机。"""
    ip = get_ip()
    return jsonify({'code': 0, 'data': {
        'enabled': not _DISABLE_CAMERA,
        'mjpeg': f'http://{ip}:5000/video_feed',
        'ros_stream': f'http://{ip}:8080/stream?topic=/camera/color/image_raw',
        'snapshot': f'http://{ip}:8080/snapshot?topic=/camera/color/image_raw',
        'hint': '相机已禁用（导航模式）' if _DISABLE_CAMERA else '需要 fireguard_cam + web_video_server',
    }})


@app.route('/video_feed')
def video_feed():
    if _DISABLE_CAMERA:
        def gen_off():
            jpg = _get_placeholder()
            while True:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpg + b'\r\n')
                time.sleep(2)
        return Response(gen_off(), mimetype='multipart/x-mixed-replace; boundary=frame')

    def gen():
        while True:
            try:
                with _urllib_request.urlopen(_SNAPSHOT_URL, timeout=2) as resp:
                    jpeg = resp.read()
                if len(jpeg) > 1000:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n')
                else:
                    time.sleep(0.3)
            except Exception:
                # 相机未就绪时给占位图，不再死循环空转
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                       + _get_placeholder() + b'\r\n')
                time.sleep(1.5)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ===== 检测状态接口：读取火灾检测遥测文件 =====
import json as _json

_DET_DEBUG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'fire_smoke_detection', 'runtime', 'debug')
_DET_ALARMS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'fire_smoke_detection', 'runtime', 'alarms.jsonl')

@app.route('/api/detection/status')
def detection_status():
    """返回火灾检测链路状态 + 最近报警"""
    data = {
        'fire_monitor': {'running': False, 'state': 'idle', 'hits': 0, 'trigger_min': 5},
        'last_alarm': None,
        'recent_alarms': [],
    }
    # 读取遥测 status.json
    status_path = os.path.join(_DET_DEBUG_DIR, 'status.json')
    try:
        with open(status_path, 'r', encoding='utf-8') as f:
            telemetry = _json.load(f)
        data['fire_monitor']['running'] = True
        data['fire_monitor']['state'] = telemetry.get('event', {}).get('state', 'idle')
        data['fire_monitor']['hits'] = telemetry.get('detector', {}).get('hit_count', 0)
        data['fire_monitor']['trigger_min'] = telemetry.get('detector', {}).get('trigger_min_hits', 5)
        data['fire_monitor']['classes'] = telemetry.get('detector', {}).get('classes', [])
        data['fire_monitor']['max_confidence'] = telemetry.get('detector', {}).get('max_confidence', 0)
        ai = telemetry.get('ai', {})
        data['fire_monitor']['ai_state'] = ai.get('state', '')
        data['fire_monitor']['ai_result'] = ai.get('result', '')
        data['fire_monitor']['ai_confidence'] = ai.get('confidence')
        alarm = telemetry.get('alarm', {})
        data['fire_monitor']['alarm_state'] = alarm.get('state', '')
        data['fire_monitor']['alarm_type'] = alarm.get('type', '')
    except Exception:
        pass

    # 读取最近报警
    try:
        if os.path.exists(_DET_ALARMS_FILE):
            with open(_DET_ALARMS_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            # 取最近 5 条
            for line in lines[-5:]:
                try:
                    alarm = _json.loads(line.strip())
                    data['recent_alarms'].append(alarm)
                except Exception:
                    pass
            if data['recent_alarms']:
                data['last_alarm'] = data['recent_alarms'][-1]
    except Exception:
        pass

    return jsonify({'code': 0, 'data': data})

@app.route('/')
def dashboard():
    return '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0,user-scalable=no"><title>FireGuard</title><style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#1a1a2e;color:#eee;font-family:Arial;text-align:center;padding:10px;max-width:480px;margin:0 auto}
h1{font-size:18px;color:#e94560;margin:6px 0}
.nav-link{font-size:13px;color:#38bdf8;text-decoration:none;margin:4px;display:inline-block}
.ip-bar{font-size:12px;color:#aaa;margin:4px 0}
.sensors{display:flex;flex-wrap:wrap;justify-content:center;gap:4px;margin:6px 0}
.sensors span{background:#0f3460;padding:3px 10px;border-radius:12px;font-size:12px}
.video-wrap{background:#16213e;border-radius:10px;padding:6px;margin:6px auto}
.video-wrap img{width:100%;border-radius:6px;display:block}

/* D-pad 方向控制 - 3x3 网格固定位置 */
.dpad{display:inline-grid;grid-template-columns:64px 64px 64px;grid-template-rows:56px 56px 56px;gap:5px;margin:8px auto}
.dpad button{height:56px;border:none;border-radius:10px;font-size:20px;cursor:pointer;background:#16213e;color:#eee;box-shadow:0 2px 6px rgba(0,0,0,.3)}
.dpad button:active{transform:scale(.92);opacity:.8}
.dpad .fwd{grid-column:2;grid-row:1;background:#1a3a6e}
.dpad .left{grid-column:1;grid-row:2}
.dpad .stop{grid-column:2;grid-row:2;background:#e94560;font-size:14px;height:46px}
.dpad .right{grid-column:3;grid-row:2}
.dpad .bk{grid-column:2;grid-row:3;background:#1a3a6e}

/* 功能按钮行 */
.func-row{display:flex;gap:6px;justify-content:center;flex-wrap:wrap;margin:4px 0}
.func-row button{padding:8px 14px;border:none;border-radius:8px;cursor:pointer;font-size:13px;background:#0f3460;color:#eee;min-width:70px}
.func-row button:active{transform:scale(.92)}

.speed-bar{display:flex;align-items:center;justify-content:center;gap:8px;margin:6px 0;font-size:13px}
.speed-bar input{width:120px}

/* 语音控制 */
.audio-bar{display:flex;gap:8px;justify-content:center;align-items:center;flex-wrap:wrap;margin:4px 0}
.audio-bar button{padding:8px 16px;border:none;border-radius:8px;cursor:pointer;font-size:14px;min-width:60px}
.audio-bar button:active{transform:scale(.92)}
.audio-bar .mic-btn{background:#0f3460;color:#eee}
.audio-bar .mic-btn.recording{background:#e94560;animation:pulse 1s infinite}
.audio-bar .say-btn{background:#1a3a6e;color:#eee}
.audio-bar input[type=text]{padding:6px 10px;border:none;border-radius:6px;font-size:13px;width:120px;background:#16213e;color:#eee}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
.audio-status{font-size:12px;color:#aaa;margin:2px 0}

/* 音乐播放器 */
.music-panel{background:#16213e;border-radius:10px;padding:8px 12px;margin:8px auto;text-align:left;font-size:13px}
.music-panel .music-title{color:#e94560;font-weight:bold;margin-bottom:6px;font-size:14px}
.music-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.music-bar button{padding:8px 16px;border:none;border-radius:8px;cursor:pointer;font-size:13px;min-width:60px}
.music-bar button:active{transform:scale(.92)}
.music-bar .play-btn{background:#22c55e;color:#fff}
.music-bar .stop-btn{background:#e94560;color:#fff}
.music-bar .upload-btn{background:#0f3460;color:#eee}
.music-status{font-size:12px;color:#aaa;margin-top:4px}
.music-progress{height:4px;background:#0f3460;border-radius:2px;margin:6px 0;overflow:hidden}
.music-progress .bar{height:100%;width:0%;background:#22c55e;border-radius:2px;transition:width .3s}

/* 检测告警面板 */
.detect-panel{background:#16213e;border-radius:10px;padding:8px 12px;margin:6px auto;text-align:left;font-size:13px}
.detect-panel .detect-title{color:#38bdf8;font-weight:bold;margin-bottom:4px;font-size:14px}
.detect-panel .detect-row{display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid #1a1a2e}
.detect-panel .detect-row:last-child{border:none}
.detect-panel .detect-val{font-weight:bold}
.detect-panel .alarm-fire{color:#e94560;animation:pulse 0.8s infinite}
.detect-panel .alarm-smoke{color:#f59e0b;animation:pulse 1.5s infinite}
.detect-panel .alarm-ai{color:#ef4444}
.detect-panel .ok{color:#22c55e}
.detect-panel .warn{color:#f59e0b}
</style></head><body>
<h1>FIRECUARD</h1>
<a class="nav-link" href="/nav/patrol">🗺️ 地图巡逻</a>
<a class="nav-link" href="/nav">📍 单点导航</a>
<a class="nav-link" href="/face">👤 人脸识别</a>
<div class="ip-bar" id="ipBar">连接中...</div>
<div class="sensors" id="sensorBar"></div>
<div class="video-wrap" id="videoWrap"><img id="videoFeed" src="" alt="video"><div id="camHint" style="font-size:12px;color:#888;padding:6px"></div></div>

<div class="detect-panel" id="detectPanel">
 <div class="detect-title">🔥 检测状态 <span id="detectBadge" style="font-size:11px;float:right"></span></div>
 <div class="detect-row"><span>火灾检测器</span><span class="detect-val" id="detState">未启动</span></div>
 <div class="detect-row"><span>触发进度</span><span class="detect-val" id="detHits">-</span></div>
 <div class="detect-row"><span>AI 复核</span><span class="detect-val" id="detAI">-</span></div>
 <div class="detect-row" id="detAlarmRow" style="display:none"><span>最近报警</span><span class="detect-val" id="detAlarm"></span></div>
</div>

<div class="dpad">
<button class="fwd" onpointerdown="m('forward')">▲</button>
<button class="left" onpointerdown="m('left')">◀</button>
<button class="stop" onpointerdown="m('stop')">■ STOP</button>
<button class="right" onpointerdown="m('right')">▶</button>
<button class="bk" onpointerdown="m('backward')">▼</button>
</div>

<div class="func-row">
<button onpointerdown="m('rotate_left')">↺ 左旋</button>
<button onpointerdown="m('rotate_right')">⟳ 右旋</button>
<button onpointerdown="m('left_shift')">← 平移</button>
<button onpointerdown="m('right_shift')">平移 →</button>
</div>

<div class="speed-bar">
<span>速度</span>
<input type="range" id="sp" min="10" max="100" value="50" oninput="document.getElementById('sv').textContent=this.value">
<span id="sv">50</span>
</div>

<div class="audio-bar">
<button class="mic-btn" id="micBtn" onclick="toggleMic()">🎤 录音</button>
<button class="mic-btn" id="playBtn" onclick="playLast()" style="display:none">▶ 播放</button>
<input type="text" id="ttsText" placeholder="输入文字..." value="你好小车">
<button class="say-btn" onclick="speak()">🔊 朗读</button>
</div>
<div class="audio-status" id="audioStatus"></div>
<audio id="audioPlayer" controls style="display:none"></audio>

<!-- 音乐播放器 -->
<div class="music-panel">
 <div class="music-title">🎵 音乐播放</div>
 <div class="music-bar">
  <button class="play-btn" id="musicPlayBtn" onclick="musicPlay()">▶ 播放 BGM</button>
  <button class="stop-btn" id="musicStopBtn" onclick="musicStop()">⏹ 停止</button>
  <label>
   <button class="upload-btn" onclick="document.getElementById('musicFileInput').click()">📁 上传音乐</button>
   <input type="file" id="musicFileInput" accept=".wav" style="display:none" onchange="uploadMusic(this)">
  </label>
 </div>
 <div class="music-progress" id="musicProgress"><div class="bar" id="musicBar"></div></div>
 <div class="music-status" id="musicStatus">就绪</div>
</div>

<script>
var API=window.location.origin;
var recording=false,lastRecordId='';
function toggleMic(){
 if(recording){
  var r=new XMLHttpRequest();
  r.open('POST',API+'/api/audio/record/stop',true);
  r.setRequestHeader('Content-Type','application/json');
  r.onload=function(){
   var j=JSON.parse(r.responseText);
   if(j.code==0){
    lastRecordId=j.data.record_id;
    document.getElementById('audioStatus').textContent='录音完成: '+(j.data.size/1024).toFixed(1)+'KB';
    document.getElementById('playBtn').style.display='inline-block';
   }else{
    document.getElementById('audioStatus').textContent='错误: '+j.msg;
   }
   document.getElementById('micBtn').textContent='🎤 录音';
   document.getElementById('micBtn').classList.remove('recording');
   recording=false;
  };
  r.send();
 }else{
  var r=new XMLHttpRequest();
  r.open('POST',API+'/api/audio/record/start',true);
  r.setRequestHeader('Content-Type','application/json');
  r.onload=function(){
   var j=JSON.parse(r.responseText);
   if(j.code==0){
    document.getElementById('audioStatus').textContent='录音中...';
    document.getElementById('micBtn').textContent='⏹ 停止';
    document.getElementById('micBtn').classList.add('recording');
    document.getElementById('playBtn').style.display='none';
    recording=true;
   }else{
    document.getElementById('audioStatus').textContent='错误: '+j.msg;
   }
  };
  r.send(JSON.stringify({duration:0}));
 }
}
function playLast(){
 if(!lastRecordId) return;
 var a=document.getElementById('audioPlayer');
 a.style.display='block';
 a.src=API+'/api/audio/record/'+lastRecordId+'.wav';
 a.play();
 document.getElementById('audioStatus').textContent='播放中...';
}
function speak(){
 var t=document.getElementById('ttsText').value;
 if(!t)return;
 document.getElementById('audioStatus').textContent='TTS: '+t;
 var r=new XMLHttpRequest();
 r.open('POST',API+'/api/audio/say',true);
 r.setRequestHeader('Content-Type','application/json');
 r.onload=function(){
  document.getElementById('audioStatus').textContent='播放完毕';
 };
 r.send(JSON.stringify({text:t,lang:'zh'}));
}
function updateDetectionUI(d){
 // 检测器运行状态
 var fm=d.fire_monitor;
 var badge=document.getElementById('detectBadge');
 var stateEl=document.getElementById('detState');
 if(!fm.running){stateEl.className='detect-val warn';stateEl.textContent='未启动';badge.textContent='';}
 else{
  var es=fm.state;
  if(es==='idle'){stateEl.className='detect-val ok';stateEl.textContent='待命中'}
  else if(es==='ai_reviewing'){stateEl.className='detect-val warn';stateEl.textContent='AI复核中'}
  else if(es==='alarmed_fire'){stateEl.className='detect-val alarm-fire';stateEl.textContent='🔥 火灾确认!'}
  else if(es==='alarmed_smoke'){stateEl.className='detect-val alarm-smoke';stateEl.textContent='💨 烟雾报警!'}
  else if(es==='ai_rejected'){stateEl.className='detect-val ok';stateEl.textContent='误报已排除'}
  else if(es==='ai_failed'){stateEl.className='detect-val alarm-ai';stateEl.textContent='AI失效!'}
  else{stateEl.className='detect-val';stateEl.textContent=es}
  badge.textContent=fm.running?'● 运行中':'';
  badge.style.color=fm.running?'#22c55e':'#aaa';
 }
 // 触发进度
 var hits=fm.hits||0, min=fm.trigger_min||5;
 document.getElementById('detHits').textContent=hits+'/'+min+(hits>=min?' ⚡':'');
 document.getElementById('detHits').className='detect-val'+(hits>=min?' warn':'');
 // AI 复核
 var ai=document.getElementById('detAI');
 if(fm.ai_state==='queued'){ai.textContent='排队中...';ai.className='detect-val'}
 else if(fm.ai_state==='completed'&&fm.ai_result==='confirmed_fire'){ai.textContent='确认: 火灾 ('+(fm.ai_confidence||0).toFixed(2)+')';ai.className='detect-val alarm-fire'}
 else if(fm.ai_state==='completed'&&fm.ai_result==='suspected_smoke'){ai.textContent='确认: 烟雾 ('+(fm.ai_confidence||0).toFixed(2)+')';ai.className='detect-val alarm-smoke'}
 else if(fm.ai_state==='completed'){ai.textContent=fm.ai_result||'已复核';ai.className='detect-val ok'}
 else if(fm.ai_state==='failed'){ai.textContent='复核失败';ai.className='detect-val alarm-ai'}
 else{ai.textContent=fm.ai_state||'-';ai.className='detect-val'}
 // 最近报警
 var row=document.getElementById('detAlarmRow');
 var el=document.getElementById('detAlarm');
 if(d.last_alarm){
  row.style.display='';
  var la=d.last_alarm;
  var typeMap={confirmed_fire:'🔥 火灾',suspected_smoke:'💨 烟雾',ai_unavailable:'⚠ AI失效'};
  el.textContent=(typeMap[la.alarm_type]||la.alarm_type)+' @'+(la.occurred_at||'').substr(11,8);
  el.className='detect-val '+(la.alarm_type==='confirmed_fire'?'alarm-fire':la.alarm_type==='suspected_smoke'?'alarm-smoke':'alarm-ai');
 }else{row.style.display='none'}
}
// ===== 音乐播放控制 =====
function musicPlay(){
 var btn=document.getElementById('musicPlayBtn');
 btn.textContent='⏳ 播放中...';
 btn.disabled=true;
 var r=new XMLHttpRequest();
 r.open('POST',API+'/api/music/play',true);
 r.onload=function(){
  var j=JSON.parse(r.responseText);
  document.getElementById('musicStatus').textContent=j.msg;
  if(j.code==0){
   document.getElementById('musicBar').style.width='100%';
   document.getElementById('musicStopBtn').style.display='inline-block';
  }
  btn.textContent='▶ 播放 BGM';
  btn.disabled=false;
 };
 r.onerror=function(){
  document.getElementById('musicStatus').textContent='请求失败，检查小车网络';
  btn.textContent='▶ 播放 BGM';
  btn.disabled=false;
 };
 r.send();
}
function musicStop(){
 var r=new XMLHttpRequest();
 r.open('POST',API+'/api/music/stop',true);
 r.onload=function(){
  var j=JSON.parse(r.responseText);
  document.getElementById('musicStatus').textContent=j.msg;
  document.getElementById('musicBar').style.width='0%';
  document.getElementById('musicStopBtn').style.display='none';
 };
 r.send();
}
function uploadMusic(input){
 var file=input.files[0];
 if(!file)return;
 if(!file.name.endsWith('.wav')){
  document.getElementById('musicStatus').textContent='仅支持 .wav 文件';
  return;
 }
 var fd=new FormData();
 fd.append('file',file);
 var r=new XMLHttpRequest();
 r.open('POST',API+'/api/audio/play',true);
 r.onload=function(){
  var j=JSON.parse(r.responseText);
  document.getElementById('musicStatus').textContent=j.code==0?'🎵 正在播放上传的音乐':'播放失败: '+j.msg;
 };
 r.send(fd);
}
// 初始化音乐状态
fetch(API+'/api/music/status').then(function(r){return r.json()}).then(function(j){
 var d=j.data||{};
 document.getElementById('musicStatus').textContent=d.exists
  ? '已加载 bgm.wav ('+(d.size/1024).toFixed(0)+'KB)'
  : '未找到 bgm.wav，请先上传到小车';
 document.getElementById('musicStopBtn').style.display='none';
}).catch(function(){});
function f(){
 var r=new XMLHttpRequest();
 r.open("GET",API+"/api/status",true);
 r.onload=function(){
  var j=JSON.parse(r.responseText);
  if(j.code!=0)return;
  document.getElementById("ipBar").textContent="IP: "+j.data.ip;
  var s=j.data.sensors;
  document.getElementById("sensorBar").innerHTML="<span>T:"+s.temperature.toFixed(1)+"C</span><span>H:"+s.humidity.toFixed(0)+"%</span><span>SMK:"+s.smoke+"</span><span>PM:"+s.pm25+"</span><span>P:"+s.pressure.toFixed(0)+"hPa</span><span>CO2:"+s.co2+"</span><span>BAT:"+j.data.battery+"V</span>";
  // 检测告警轮询
  fetch(API+"/api/detection/status").then(function(r2){return r2.json()}).then(function(dj){
   if(dj.code==0) updateDetectionUI(dj.data);
  }).catch(function(){});
 }; r.send();
}
// 导航模式可不启用相机；仅在 /api/camera.enabled 时拉流
fetch(API+"/api/camera").then(function(r){return r.json()}).then(function(j){
  var d=(j&&j.data)||{};
  var hint=document.getElementById("camHint");
  if(d.enabled===false){
    hint.textContent="导航模式：未启用相机（不影响巡逻/遥控）";
    document.getElementById("videoFeed").style.display="none";
  }else{
    document.getElementById("videoFeed").src=API+"/video_feed";
    hint.textContent="";
  }
}).catch(function(){document.getElementById("videoFeed").src=API+"/video_feed";});
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
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True,
    )
