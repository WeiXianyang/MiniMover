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

### 启动后访问

| 服务 | 地址 |
|---|---|
| 控制面板 | `http://<小车IP>:5000/` |
| 地图导航 | `http://<小车IP>:5000/nav` |
| 视频流列表 | `http://<小车IP>:8080/` |
| 视频流(彩色) | `http://<小车IP>:8080/stream?topic=/camera/color/image_raw` |
| VNC | `<小车IP>:5900` |

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

### 2.3 视频流

| 接口 | 方法 | 功能 | 返回 |
|---|---|---|---|
| `/video_feed` | GET | MJPEG 视频流 | multipart/x-mixed-replace 流 |
| `/api/camera` | GET | 视频流地址信息 | `{"code":0,"stream":"http://..."}` |

**视频流网页嵌入：**
```html
<img src="http://<小车IP>:5000/video_feed">
```

### 2.4 地图导航

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

### 2.5 前端页面

| 路由 | 功能 |
|---|---|
| `/` | 控制面板（传感器 + 视频 + 方向控制 + 速度调节） |
| `/nav` | 地图导航页面（点击地图选点 → 自动导航） |（还未实现导航）

### 2.6 视频流访问

**直接访问小车：**

| 说明 | 地址 |
|---|---|
| 控制面板（含视频） | `http://<小车IP>:5000/` |
| 纯 MJPEG 视频流 | `http://<小车IP>:5000/video_feed` |
| ROS 话题列表 | `http://<小车IP>:8080/` |
| 直播流查看器 | `http://<小车IP>:8080/stream_viewer?topic=/camera/color/image_raw` |

**通过协调中心代理：**

| 说明 | 地址 |
|---|---|
| 多车控制面板 | `http://localhost:8888/dashboard` |
| car_A 视频代理 | `http://localhost:8888/proxy/camera/car_A` |
| car_B 视频代理 | `http://localhost:8888/proxy/camera/car_B` |

**供开发用（Python/OpenCV 拉取）：**
```python
# 直接从 ROS 流拉取（推荐，低延迟）
cap = cv2.VideoCapture("http://<小车IP>:8080/stream?topic=/camera/color/image_raw")

# 通过 API 拉取（多一层转发）
cap = cv2.VideoCapture("http://<小车IP>:5000/video_feed")

# 通过协调中心拉取
cap = cv2.VideoCapture("http://localhost:8888/proxy/camera/car_A")
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
}

// 数据结构
data class MoveCmd(val cmd: String, val speed: Int, val duration: Double)
data class GoalPose(val x: Double, val y: Double, val theta: Double = 0.0)

// 视频流 (用 ImageView 或 WebView)
// val url = "http://<小车IP>:5000/video_feed"
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
