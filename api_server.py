#!/usr/bin/env python3
# MiniMover api_server — auto-load env files (systemd EnvironmentFile fallback)
import os as _os
_base = _os.path.dirname(_os.path.abspath(__file__))
for _env_file in (".env.voice", ".tts.env"):
    _path = _os.path.join(_base, _env_file)
    if _os.path.isfile(_path):
        with open(_path, encoding="utf-8-sig") as _env_handle:
            for _line in _env_handle:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _os.environ[_k.strip()] = _v.strip()

import sys as _sys
_env_voice_path = _os.path.join(_base, ".env.voice")
if _os.path.isfile(_env_voice_path):
    with open(_env_voice_path, encoding="utf-8-sig") as _env_handle:
        _env_var_count = sum(1 for _line in _env_handle if "=" in _line and not _line.startswith("#"))
else:
    _env_var_count = 0
print(f"[api_server] Loaded {_env_var_count} env vars, TTS_PROVIDER={_os.environ.get('MINIMOVER_TTS_PROVIDER','MISSING')}", file=_sys.stderr, flush=True)

from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import threading, time, os, sys, subprocess, socket

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sensors.icar_sensor_driver import iCarSensorDriver
from Rosmaster_Lib import Rosmaster
from audio.icar_audio import record_start, record_status, record_stop, record_get
from audio.icar_audio import play_wav, stop_playback, say as tts_say, get_devices as audio_devices
from voice_assistant.audio_turn_safety import wav_duration_ms
from navigation import nav_bp, register_legacy_routes, register_patrol_page
from face import register_face_routes
from hospital_guide_console import register_hospital_guide_console
from hospital_guide_bridge import register_hospital_guide_bridge
from hospital_guide_demo import HospitalGuideDemoController, register_hospital_guide_demo

app = Flask(__name__)
CORS(app)
app.register_blueprint(nav_bp, url_prefix='/api/nav')
register_legacy_routes(app)
register_patrol_page(app)
register_hospital_guide_console(
    app,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_assistant", "data", "hospital_guide_runtime.json"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_assistant", "data", "hospital_guide_template.json"),
)
hospital_guide_bridge = register_hospital_guide_bridge(
    app,
    config_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_assistant", "data", "hospital_guide_template.json"),
    knowledge_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_assistant", "data", "shortmedkg", "input_v4.jsonl"),
    telemetry_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_assistant", "data", "hospital_guide_runtime.json"),
)
hospital_guide_demo = HospitalGuideDemoController(bridge=hospital_guide_bridge)
hospital_guide_bridge.set_guide_event_handler(hospital_guide_demo.on_guide_event)
register_hospital_guide_demo(app, hospital_guide_demo)
register_face_routes(app)
sensor = iCarSensorDriver()
_NAV_OWNS_CHASSIS = os.environ.get('MINIMOVER_NAV_OWNS_CHASSIS', '0').strip().lower() in (
    '1', 'true', 'yes', 'on',
)
bot = None
if not _NAV_OWNS_CHASSIS:
    bot = Rosmaster(debug=False)
    bot.create_receive_threading()
else:
    print('[api_server] legacy chassis control disabled; Nav2 owns /dev/myserial', flush=True)
_bot_lock = threading.Lock()

def get_ip():
    return os.popen('hostname -I').read().split()[0]

@app.route('/api/status')
def get_status():
    ip = get_ip()
    vol = None
    if bot is not None:
        with _bot_lock:
            vol = bot.get_battery_voltage()
    return jsonify({'code':0, 'data':{
        'sensors': sensor.get_data(),
        'battery': round(vol, 1) if vol else 12.0,
        'ip': ip,
        'legacy_chassis_control': bot is not None,
    }})

# 底盘访问锁 + 看门狗线程（杜绝 Timer 漏触发导致一直转）
_stop_deadline = 0.0
_stop_deadline_lock = threading.Lock()

def _stop_if_deadline_elapsed():
    """Stop only when the watchdog deadline is still expired after locking."""
    global _stop_deadline
    if bot is None:
        with _stop_deadline_lock:
            _stop_deadline = 0.0
        return False
    with _stop_deadline_lock:
        deadline_elapsed = _stop_deadline > 0 and time.monotonic() >= _stop_deadline
    if not deadline_elapsed:
        return False

    # Keep the same lock order as _execute_move. Re-checking after acquiring both
    # locks prevents an old deadline from stopping a newly issued movement command.
    with _bot_lock:
        with _stop_deadline_lock:
            if _stop_deadline <= 0 or time.monotonic() < _stop_deadline:
                return False
            bot.set_car_motion(0, 0, 0)
            _stop_deadline = 0.0
            return True


def _watchdog():
    """底盘运动看门狗，每 0.2 秒检查一次。"""
    while True:
        _stop_if_deadline_elapsed()
        time.sleep(0.2)


threading.Thread(target=_watchdog, daemon=True).start()

_VALID_MOVE_COMMANDS = frozenset({
    'forward', 'backward', 'left', 'right', 'rotate_left', 'rotate_right',
    'left_shift', 'right_shift', 'stop',
})


def _execute_move(cmd, speed_pct, duration):
    """Apply one validated movement command for both HTTP and TCP control."""
    global _stop_deadline

    if bot is None:
        raise RuntimeError('legacy movement is disabled while Nav2 owns the chassis')
    if not isinstance(cmd, str) or cmd not in _VALID_MOVE_COMMANDS:
        raise ValueError(f'unsupported movement command: {cmd!r}')
    try:
        speed_percent = max(0, min(int(float(speed_pct)), 100))
        duration_seconds = max(0.0, float(duration))
    except (TypeError, ValueError) as error:
        raise ValueError('speed and duration must be numeric') from error

    speed = speed_percent / 100.0
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

    # Match the watchdog's lock order so a timed-out older command cannot
    # stop this new command between its chassis write and deadline update.
    with _bot_lock:
        bot.set_car_motion(vx, vy, vz)
        with _stop_deadline_lock:
            _stop_deadline = (
                0.0 if cmd == 'stop' or duration_seconds <= 0
                else time.monotonic() + duration_seconds
            )
    return speed_percent


@app.route('/api/move', methods=['POST'])
def move():
    data = request.get_json(silent=True) or {}
    try:
        cmd = data.get('cmd', 'stop')
        speed_percent = _execute_move(
            cmd, data.get('speed', 50), data.get('duration', 0.5)
        )
    except ValueError as error:
        return jsonify({'code': -1, 'msg': str(error)}), 400
    except RuntimeError as error:
        return jsonify({'code': -1, 'msg': str(error)}), 409
    return jsonify({'code': 0, 'msg': f'{cmd} @ {speed_percent}%'})

@app.route('/api/sensors')
def get_sensors():
    return jsonify({'code':0,'data':sensor.get_data()})

@app.route('/api/health')
def health():
    return jsonify({'code':0,'msg':'MiniMover API Running'})

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
        duration_ms = wav_duration_ms(wav)
        play_wav(wav)
        return jsonify({
            'code': 0,
            'msg': f'TTS: {text[:20]}...' if len(text)>20 else f'TTS: {text}',
            'data': {'playback_duration_ms': duration_ms},
        })
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

@app.route('/')
def dashboard():
    return '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0,user-scalable=no"><title>MiniMover</title><style>
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

</style></head><body>
<h1>MiniMover</h1>
<a class="nav-link" href="/nav/patrol">🗺️ 地图巡逻</a>
<a class="nav-link" href="/nav">📍 单点导航</a>
<a class="nav-link" href="/hospital-guide">Hospital Guide</a>
<a class="nav-link" href="/face">👤 人脸识别</a>
<div class="ip-bar" id="ipBar">连接中...</div>
<div class="sensors" id="sensorBar"></div>
<div class="video-wrap" id="videoWrap"><img id="videoFeed" src="" alt="video"><div id="camHint" style="font-size:12px;color:#888;padding:6px"></div></div>


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
    _control_running = True

    def _start_control_server(port=5001):
        """Serve newline-delimited low-latency movement commands on TCP."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(1.0)
        sock.bind(('0.0.0.0', port))
        sock.listen(1)
        print(f"[tcp-ctrl] listening on :{port}")
        try:
            while _control_running:
                try:
                    conn, addr = sock.accept()
                except socket.timeout:
                    continue
                except OSError as error:
                    if _control_running:
                        print(f"[tcp-ctrl] accept error: {error}")
                    continue
                print(f"[tcp-ctrl] connected: {addr}")
                with conn:
                    conn.settimeout(1.0)
                    buffer = b''
                    while _control_running:
                        try:
                            data = conn.recv(4096)
                        except socket.timeout:
                            continue
                        if not data:
                            break
                        buffer += data
                        while b'\n' in buffer:
                            line, buffer = buffer.split(b'\n', 1)
                            if not line.strip():
                                continue
                            try:
                                parts = line.decode('utf-8').split()
                                command = parts[0]
                                speed = parts[1] if len(parts) > 1 else 50
                                duration = parts[2] if len(parts) > 2 else 0.5
                                _execute_move(command, speed, duration)
                            except (UnicodeDecodeError, ValueError, RuntimeError, IndexError) as error:
                                print(f"[tcp-ctrl] parse error: {error} (line={line!r})")
                print("[tcp-ctrl] disconnected")
        finally:
            sock.close()
            print("[tcp-ctrl] stopped")

    if _NAV_OWNS_CHASSIS:
        print('[tcp-ctrl] disabled because Nav2 owns the chassis')
    else:
        threading.Thread(target=_start_control_server, args=(5001,), daemon=True).start()
    sensor.start()
    try:
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            use_reloader=False,
            threaded=True,
        )
    finally:
        _control_running = False
