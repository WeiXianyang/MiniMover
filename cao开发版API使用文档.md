# FireGuard API 接口文档 & 启动指南

---

## 一、后端启动

### 一键启动（推荐）

```bash
bash ~/MiniMover/scripts/start_services.sh
```

自动完成：摄像头修复 → 启动容器 → VNC → 彩色相机 → 视频流 → API

### 手动分步启动

```bash
# 终端 1：启动容器
s

# 终端 2：进入容器启动相机
d
ros2 launch astra_camera astro_pro_plus.launch.xml &

# 终端 3：视频流
d
ros2 run web_video_server web_video_server &

# 终端 4：API 服务
cd ~/MiniMover
python3 api_server.py &
```

### 多车协同调度中心（在 PC 端运行）

```bash
cd ~/MiniMover
python multi_car_coordinator.py 
```

启动后访问：
- 可视化面板：`http://localhost:8888/dashboard`
- 车辆状态：`http://localhost:8888/api/status`

### 启动后访问

| 服务 | 地址 |
|---|---|
| 控制面板 | `http://<小车IP>:5000/` |
| 地图导航 | `http://<小车IP>:5000/nav` |
| 视频流列表 | `http://<小车IP>:8080/` |
| 视频流(彩色) | `http://<小车IP>:8080/stream?topic=/camera/color/image_raw` |
| VNC | `<小车IP>:5900` |

### 火灾检测服务（可选）

在车辆服务启动后，额外启动 YOLOv5 火灾/烟雾识别：

```bash
# 一键启动（CPU 模式）
bash ~/MiniMover/scripts/start_fire_detection.sh

# GPU 模式（Jetson NX）
bash ~/MiniMover/scripts/start_fire_detection.sh --device 0

# 与全套服务一起启动（API + 火灾检测）
FIRE_DETECT=1 bash ~/MiniMover/scripts/start_services.sh
```

启动后，控制面板 `http://<小车IP>:5000/` 的「检测状态」面板会自动显示：
- 检测器状态（待命中 / AI复核中 / 火灾确认 / 烟雾报警）
- YOLO 触发进度
- AI 复核结果
- 最近报警记录

停止检测：
```bash
pkill -f detector.py
```

---

## 二、API 接口总表

### 2.1 系统状态

| 接口 | 方法 | 功能 | 返回示例 |
|---|---|---|---|
| `/api/health` | GET | 健康检查 | `{"code":0,"msg":"FireGuard API Running"}` |
| `/api/status` | GET | 全状态（传感器+电池+IP） | `{"code":0,"data":{"sensors":{...},"battery":12.0,"ip":"192.168.1.100"}}` |
| `/api/sensors` | GET | 传感器数据详情 | `{"code":0,"data":{"temperature":25.0,"humidity":50.0,"smoke":0,"pm25":0,"pressure":1013,"light":500,"co2":400,"gps":{"lat":0,"lon":0}}}` |

### 2.2 小车控制

| 接口 | 方法 | 功能 | POST Body |
|---|---|---|---|
| `/api/move` | POST | 控制小车移动 | `{"cmd":"forward", "speed":50, "duration":0.5}` |

**cmd 参数说明：**

| cmd 值 | 动作 | 说明 |
|---|---|---|
| `forward` | 前进 |  |
| `backward` | 后退 |  |
| `left` | 左转 |  |
| `right` | 右转 |  |
| `left_shift` | 左平移 | 麦克纳姆轮特有 |
| `right_shift` | 右平移 | 麦克纳姆轮特有 |
| `stop` | 停止 | 忽略 duration |

**speed 范围：** 10 ~ 100（百分比）

**调用示例：**
```bash
# 前进 50% 速度，持续 0.5 秒
curl -X POST http://<小车IP>:5000/api/move \
  -H "Content-Type: application/json" \
  -d '{"cmd":"forward","speed":50,"duration":0.5}'

# 停止
curl -X POST http://<小车IP>:5000/api/move \
  -H "Content-Type: application/json" \
  -d '{"cmd":"stop"}'
```

### 2.3 火灾检测

| 接口 | 方法 | 功能 | 返回 |
|---|---|---|---|
| `/api/detection/status` | GET | 检测链路状态 + 近期报警 | `{"code":0,"data":{"fire_monitor":{"running":true,"state":"idle","hits":0},"last_alarm":null,"recent_alarms":[]}}` |

**返回字段说明：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `fire_monitor.running` | bool | YOLO 检测进程是否运行 |
| `fire_monitor.state` | string | 当前状态: `idle` / `ai_reviewing` / `alarmed_fire` / `alarmed_smoke` / `ai_rejected` / `ai_failed` |
| `fire_monitor.hits` | int | YOLO 当前命中帧数（触发阈值 5 帧） |
| `fire_monitor.ai_state` | string | AI 复核状态: `queued` / `completed` / `failed` |
| `fire_monitor.ai_result` | string | AI 复核结论: `confirmed_fire` / `suspected_smoke` / `no_fire` |
| `fire_monitor.ai_confidence` | float | AI 复核置信度 |
| `last_alarm` | object | 最近一次报警（含类型/时间/置信度） |
| `recent_alarms` | array | 最近 5 条报警历史 |

**调用示例：**
```bash
curl http://<小车IP>:5000/api/detection/status
```

### 2.4 视频流

| 接口 | 方法 | 功能 | 返回 |
|---|---|---|---|
| `/video_feed` | GET | MJPEG 视频流 | multipart/x-mixed-replace 流 |
| `/api/camera` | GET | 视频流地址信息 | `{"code":0,"stream":"http://..."}` |

**视频流网页嵌入：**
```html
<img src="http://<小车IP>:5000/video_feed">
```

### 2.5 地图导航

| 接口 | 方法 | 功能 | 说明 |
|---|---|---|---|
| `/api/map` | GET | 地图信息 | 返回分辨率/原点/尺寸 |
| `/api/map_image` | GET | 地图图片 | 返回 JPEG 地图图像 |
| `/api/navigate` | POST | 发送导航目标 | 见下方详情 |

**`/api/navigate` 请求体：**
```json
{
  "x": 1.0,      // 目标点 X (map 坐标系，单位 米)
  "y": 2.0,      // 目标点 Y
  "theta": 0.0   // 朝向角度
}
```

**调用示例：**
```bash
curl -X POST http://<小车IP>:5000/api/navigate \
  -H "Content-Type: application/json" \
  -d '{"x":1.5,"y":2.0,"theta":0}'
```

### 2.6 前端页面

| 路由 | 功能 |
|---|---|
| `/` | 控制面板（传感器 + 视频 + 方向控制 + 速度调节 + 检测告警面板 + 录音/TTS） |
| `/nav` | 地图导航页面（点击地图选点 → 自动导航） |（还未实现导航） |

### 2.7 视频流访问

**直接访问小车：**

| 说明 | car_A (192.168.137.23) | car_B (192.168.137.254) |
|---|---|---|
| 控制面板（含视频） | `http://192.168.137.23:5000/` | `http://192.168.137.254:5000/` |
| 纯 MJPEG 流 | `http://192.168.137.23:5000/video_feed` | `http://192.168.137.254:5000/video_feed` |
| ROS 话题列表 | `http://192.168.137.23:8080/` | `http://192.168.137.254:8080/` |
| 直播流查看器 | `http://192.168.137.23:8080/stream_viewer?topic=/camera/color/image_raw` | 同 car_A |

**通过协调中心代理：**

| 说明 | 地址 |
|---|---|
| 多车面板 | `http://localhost:8888/dashboard` |
| car_A 代理流 | `http://localhost:8888/proxy/camera/car_A` |
| car_B 代理流 | `http://localhost:8888/proxy/camera/car_B` |

**供开发用（Python/OpenCV 直接拉取）：**
```python
# 直接从小车取（推荐，低延迟）
cap = cv2.VideoCapture("http://192.168.137.23:8080/stream?topic=/camera/color/image_raw")

# 通过 API 取（多一层转发）
cap = cv2.VideoCapture("http://192.168.137.23:5000/video_feed")

# 通过协调中心取
cap = cv2.VideoCapture("http://localhost:8888/proxy/camera/car_A")
```

---

### 2.8 音频（录音 / 播放 / TTS）

| 接口 | 方法 | 功能 | 说明 |
|---|---|---|---|
| `/api/audio/devices` | GET | 音频设备信息 | 麦克风+扬声器+语音引擎状态 |
| `/api/audio/record/start` | POST | 开始录音 | `{"duration": 3}` 定秒, 0=手动停止 |
| `/api/audio/record/status` | GET | 查询录音状态 | `{"status":"idle\|recording\|done"}` |
| `/api/audio/record/stop` | POST | 停止录音 | 返回 record_id + 文件大小 |
| `/api/audio/record/<id>.wav` | GET | 下载录音 WAV | 可直接用作 `<audio src>` |
| `/api/audio/play` | POST | 上传 WAV 播放 | multipart/form-data, field: `file` |
| `/api/audio/say` | POST | TTS 文本转语音 | `{"text":"你好","lang":"zh"}` |
| `/api/audio/stop` | POST | 停止播放 | |

**语音识别对接流程：**
```
[点击录音] → start → [用户说话] → stop → 拿到 record_id
→ 下载 WAV → 发给语音识别服务 → 拿到文本
→ 执行指令或通过 /api/audio/say 语音反馈
```

**调用示例：**
```bash
# 查看设备
curl http://<小车IP>:5000/api/audio/devices

# 开始录音
curl -X POST http://<小车IP>:5000/api/audio/record/start \
  -H "Content-Type: application/json" -d '{"duration":0}'

# 停止录音
curl -X POST http://<小车IP>:5000/api/audio/record/stop

# TTS 朗读
curl -X POST http://<小车IP>:5000/api/audio/say \
  -H "Content-Type: application/json" -d '{"text":"你好小车","lang":"zh"}'
```

**前端 JavaScript 调用（语音识别流程）：**
```javascript
// 开始录音
fetch(API+'/api/audio/record/start', {method:'POST',
  headers:{'Content-Type':'application/json'}, body:'{"duration":0}'});

// 停止录音 + 下载播放
fetch(API+'/api/audio/record/stop', {method:'POST'})
  .then(r=>r.json()).then(j=>{
    var audio = new Audio(API+'/api/audio/record/'+j.data.record_id+'.wav');
    audio.play();
  });

// TTS 朗读
fetch(API+'/api/audio/say', {method:'POST',
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify({text:'你好小车', lang:'zh'})});
```

**硬件信息：**

| 组件 | 设备 | 规格 |
|---|---|---|
| 麦克风 | 讯飞 XFM-DP-V0.0.18 | mono 16kHz, ALSA hw:2,0 |
| 扬声器 | PulseAudio 默认输出 | 自动格式转换（mono→stereo） |
| TTS引擎 | espeak-ng 1.50 | 中文/英文/日文 |

**Python 直接调用（绕过 HTTP）：**
```python
from audio.icar_audio import *

# 设备信息
print(get_devices())

# 录音
rid = record_start(duration_sec=3)    # 录 3 秒
_, wav_bytes = record_stop()          # 返回 (record_id, wav数据)

# 播放
play_wav(wav_bytes)                   # 播放 WAV 字节

# TTS
wav = say('你好', lang='zh')          # 生成 WAV
play_wav(wav)                         # 直接播放
```

---

### 2.9 多车协同（调度中心 :8888）

在 PC 运行 `python3 multi_car_coordinator.py` 后，以下接口可用：

| 接口 | 方法 | 功能 | 说明 |
|---|---|---|---|
| `/api/cars` | GET | 车辆注册列表 | 返回所有已注册车辆 IP/端口 |
| `/api/status` | GET | 所有车辆状态 | 含传感器、位置、碰撞告警 |
| `/api/move_all` | POST | 并行控制所有车辆 | `{"cmd":"forward","speed":50}` |
| `/api/move_one` | POST | 控制指定车辆 | `{"car_id":"car_A","cmd":"left"}` |
| `/api/navigate` | POST | 多车导航目标 | `{"car_ids":["car_A","car_B"],"x":1,"y":2}` |
| `/api/formation` | POST | 队形控制 | 见下方详情 |
| `/api/register` | POST | 动态注册新车 | `{"car_id":"car_C","ip":"192.168.1.103"}` |
| `/api/register_batch` | POST | 批量注册 | `{"cars":{"car_C":{"ip":"..."}}}` |
| `/proxy/camera/<car_id>` | GET | 代理视频流 | MJPEG 无跨域 |
| `/dashboard` | GET | 可视化面板 | 浏览器访问 |

**队形控制 `POST /api/formation`：**
```json
{
  "type": "line",          // line(纵队) | row(横排) | triangle(三角)
  "spacing": 2.0,          // 车间距(米)
  "car_ids": ["car_A", "car_B"]
}
```

**可视化面板** (`http://localhost:8888/dashboard`) 功能：
- 所有车辆实时传感器/位置/电池
- 视频流直接内嵌显示
- 碰撞检测告警（<0.5m 红色 CRITICAL，<1.0m 黄色 WARNING）
- 一键全停、队形切换按钮

**启动示例：**
```bash
# PC 端，先确保每辆车已启动 api_server.py
cd ~/MiniMover
python3 multi_car_coordinator.py &
# 打开 http://localhost:8888/dashboard
```

---

## 三、Android APP 调用示例 (Kotlin)

```kotlin
// Retrofit 接口定义
interface FireGuardApi {
    @GET("api/status")
    suspend fun getStatus(): StatusResponse
    
    @POST("api/move")
    suspend fun move(@Body cmd: MoveCmd): MoveResponse
    
    @GET("api/sensors")
    suspend fun getSensors(): SensorResponse
    
    @POST("api/navigate")
    suspend fun navigate(@Body goal: GoalPose): ApiResponse

    // 音频
    @GET("api/audio/devices")
    suspend fun getAudioDevices(): DeviceResponse

    @POST("api/audio/record/start")
    suspend fun recordStart(@Body body: Map<String, Int>): ApiResponse

    @POST("api/audio/record/stop")
    suspend fun recordStop(): ApiResponse

    @POST("api/audio/say")
    suspend fun say(@Body body: Map<String, String>): ApiResponse
}

// 数据结构
data class MoveCmd(val cmd: String, val speed: Int, val duration: Double)
data class GoalPose(val x: Double, val y: Double, val theta: Double = 0.0)
data class SayCmd(val text: String, val lang: String = "zh")

// 视频流 (用 ImageView 或 WebView)
// val url = "http://<小车IP>:5000/video_feed"

// 录音 WAV 下载
// val wavUrl = "http://<小车IP>:5000/api/audio/record/${recordId}.wav"
```

---

## 四、可视化识别同学获取视频流

```python
import cv2

# 方式 1：从 ROS 2 web_video_server 直接取（推荐，延迟低）
url = "http://<小车IP>:8080/stream?topic=/camera/color/image_raw"
cap = cv2.VideoCapture(url)
while True:
    ret, frame = cap.read()
    if ret:
        # 在这里做视觉识别
        # fire_detection(frame)
        pass

# 方式 2：从 API 取（多一层转发）
url = "http://<小车IP>:5000/video_feed"
cap = cv2.VideoCapture(url)
```

---

## 五、关闭后端

### 一键停止（推荐）

```bash
# 在小车终端执行，停止所有服务
bash ~/MiniMover/scripts/stop_services.sh
```

自动停止：API 服务 → 视频流 → 相机驱动 → VNC → Docker 容器，并检查残留进程。

### 分开控制

```bash
# 仅停止 API（摄像头流仍可独立访问 :8080）
sudo systemctl stop fireguard-api

# 仅停止摄像头和视频流（API 仍可控制底盘）
sudo docker stop fireguard_cam

# 重启 API
sudo systemctl restart fireguard-api

# 查看服务状态
sudo systemctl status fireguard-api
sudo docker ps
```

### 完全禁用（开机不自启）

```bash
sudo systemctl disable fireguard-api
```

### 重新启动所有服务

```bash
bash ~/MiniMover/scripts/start_services.sh
```
