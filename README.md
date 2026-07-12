# Rosmaster 小车项目总体介绍

## 一、项目概述

本项目是 **Yahboom（亚博智能）Rosmaster 系列教育机器人小车** 的上位机控制程序，运行在小车内置的 **NVIDIA Jetson**（aarch64）嵌入式电脑上。程序提供基于 Web 的视频流和控制接口，用户可通过手机 APP 或浏览器远程操控小车。

## 二、目录结构

```
~/Rosmaster-App/
├── rosmaster/                          # 主应用程序
│   ├── app.py                          # ★ 主入口：Flask Web 服务器 (端口 6500)
│   ├── app_sim.py                      # Tkinter 桌面 GUI 控制面板
│   ├── app_sim_run.py                  # GUI 启动器
│   ├── app_sim.c / .cpython-*.so      # Cython 编译产物
│   ├── rosmaster_main_ori.py          # ★ 核心业务逻辑源码 (962 行)
│   ├── rosmaster_main.c / .cpython-*.so # Cython 编译后的主模块
│   ├── rosmaster_pid2.c / .cpython-*.so # PID 控制器编译产物
│   ├── rosmaster_no_control.py         # 纯摄像头流 (无运动控制)
│   ├── rosmaster_test.py               # 手动运动测试脚本
│   ├── camera_rosmaster.py             # 摄像头封装 (深度/USB/广角)
│   ├── wifi_rosmaster.py              # WiFi QR 码配网
│   ├── joystick_rosmaster.py          # 物理手柄支持
│   ├── pid.py                          # PID 调参入口
│   ├── drive.py                        # CLI 手动驱动
│   ├── followline.py / stopline.py     # 循线模式开关
│   ├── license.c / .cpython-*.so      # 授权验证模块
│   ├── license.json                    # 授权文件
│   ├── setup.py                        # Cython 编译脚本
│   ├── start_app.sh                    # 开机自启脚本
│   ├── kill_rosmaster.sh               # 进程终止脚本
│   ├── cmd.txt                         # ★ 常用命令速查
│   ├── templates/                      # HTML 模板
│   │   ├── index.html                  # 视频流页面
│   │   ├── index2.html                 # 全屏视频流
│   │   └── init.html                   # 初始化页面
│   ├── static/                         # 静态资源
│   └── capture/                        # 截图/录像存储
│
└── py_install_V3.3.1/                  # Rosmaster Python 基础库
    └── Rosmaster_Lib/
        ├── Rosmaster_Lib.py            # ★ 底层串口驱动库 (1346 行)
        ├── Rosmaster_Lib_PID.py        # PID 算法
        └── __init__.py
```

## 三、技术栈


| 层次          | 技术                | 说明                              |
| ------------- | ------------------- | --------------------------------- |
| **语言**      | Python 3.8          | 主体逻辑                          |
| **Web 框架**  | Flask + gevent WSGI | HTTP 服务 + MJPEG 视频流          |
| **摄像头**    | OpenCV (cv2)        | 视频采集、编码、显示              |
| **串口通信**  | pyserial            | 与小车 MCU 底层通信 (115200 baud) |
| **WiFi 配网** | pyzbar + nmcli      | QR 码扫描 + NetworkManager        |
| **GPIO**      | RPi.GPIO            | 物理按键 & LED (引脚 17/18)       |
| **许可保护**  | Cython              | 源码编译为 .so，防逆向            |
| **桌面 GUI**  | Tkinter             | 本地控制面板                      |
| **ROS2**      | Docker 容器         | 激光雷达、颜色追踪等高级功能      |

## 四、核心架构

### 4.1 通信架构

```
┌──────────┐  TCP:6000 (二进制协议)  ┌──────────────────┐  UART /dev/myserial  ┌─────────┐
│ 手机APP   │ ◄──────────────────────► │  Rosmaster 上位机  │ ◄───────────────────► │ 小车 MCU │
│ / 浏览器  │                          │  (Jetson)          │  115200 baud          │ (底层控制)│
└──────────┘  HTTP:6500 (MJPEG 视频流) └──────────────────┘                        └─────────┘
                     ◄────────────────────
```

- **APP ↔ 上位机**：手机 APP 通过 TCP 端口 6000 发送运动控制指令（二进制协议，`$...#` 帧格式）
- **浏览器 ↔ 上位机**：HTTP 端口 6500，Flask 提供 Web 页面和 MJPEG 视频流
- **上位机 ↔ MCU**：UART 串口 `/dev/myserial`，私有协议（`0xFF` 帧头，设备 ID `0xFC`）

### 4.2 核心模块职责


| 模块          | 文件                    | 职责                                                                 |
| ------------- | ----------------------- | -------------------------------------------------------------------- |
| **Web 入口**  | `app.py`                | 创建 Flask 应用，启动 gevent 服务器                                  |
| **业务核心**  | `rosmaster_main_ori.py` | TCP 服务器、指令解析、运动控制、摄像头切换、RGB 灯效、循线、拍照录像 |
| **底层驱动**  | `Rosmaster_Lib.py`      | 串口收发、电机控制、舵机控制、IMU/编码器读取、PID 参数设置           |
| **摄像头**    | `camera_rosmaster.py`   | 支持 3 种摄像头（深度/ USB / 广角），自动重连，JPEG 编码             |
| **WiFi 配网** | `wifi_rosmaster.py`     | 摄像头扫描 QR 码 → 解析 SSID/密码 → nmcli 联网                     |
| **手柄**      | `joystick_rosmaster.py` | 读取`/dev/input/js*`，映射摇杆/按钮到小车动作                        |

### 4.3 支持的小车底盘类型


| 类型    | 参数值 | 说明                         |
| ------- | ------ | ---------------------------- |
| X3      | `0x01` | 4WD 麦克纳姆轮               |
| X3 Plus | `0x02` | X3 + 机械臂                  |
| X1      | `0x04` | 2WD 差速驱动                 |
| R2      | `0x05` | 阿克曼转向（像汽车一样转向） |

## 五、通信协议

### 5.1 APP ↔ 上位机（TCP 端口 6000）

二进制协议，帧格式：`$<cmd><len><data>...#`


| 命令        | 功能                     |
| ----------- | ------------------------ |
| `0x01`      | 查询硬件版本             |
| `0x02`      | 查询电池电压             |
| `0x10`      | 小车运动 (X, Y 方向速度) |
| `0x11`      | PWM 舵机控制             |
| `0x12`      | UART 机械臂舵机          |
| `0x13`      | 蜂鸣器                   |
| `0x15`      | 按钮方向控制 (8 方向)    |
| `0x16`      | 速度百分比               |
| `0x18`      | 切换摄像头类型           |
| `0x20-0x21` | 麦轮独立控制             |
| `0x30-0x32` | RGB 灯效                 |
| `0x40-0x43` | 机械臂校准/力矩/姿态     |
| `0x50-0x53` | 阿克曼转向角校准         |
| `0x60-0x62` | 拍照/录像                |
| `0x63-0x64` | 循线模式                 |

### 5.2 上位机 ↔ MCU（UART `/dev/myserial`, 115200）

私有协议，帧头 `0xFF`，设备 ID `0xFC`，带校验和。具体实现见 `Rosmaster_Lib.py`。

## 六、常用命令速查

参考 `cmd.txt`：

```bash
# 查看串口设备
ll /dev | grep ttyUSB*

# 查看摄像头
lsusb

# 启动主程序
python3 ~/Rosmaster-App/rosmaster/app.py          # 正常模式
python3 ~/Rosmaster-App/rosmaster/app.py debug    # 调试模式

# 启动 Docker (ROS2 功能)
./run_docker.sh

# 进入 Docker
docker ps -a
docker exec -it <container_id> /bin/bash

# 手动控制小车
python3 drive.py <方向> <速度>

# 循线模式
python3 followline.py
python3 stopline.py
```

### ROS2 高级功能（Docker 内运行）

```bash
# 激光雷达避障
ros2 run icar_bringup Mcnamu_driver_X3
ros2 launch sllidar_ros2 sllidar_launch.py
ros2 run icar_laser laser_Avoidance_a1_X3

# 颜色追踪
ros2 run icar_bringup Mcnamu_driver_X3
ros2 run icar_astra colorHSV
ros2 run icar_astra colorTracker
ros2 launch astra_camera astra.launch.xml

# 摄像头循线
ros2 run icar_bringup Mcnamu_driver_X3
ros2 launch sllidar_ros2 sllidar_launch.py
ros2 launch astra_camera astra.launch.xml
ros2 run icar_linefollow follow_line_a1_X3
```

## 七、启动流程

1. Jetson 开机后，`start_app.sh` 会延迟 8 秒后自动启动 `app.py`
2. `app.py` 做以下初始化：
   - 创建 `Rosmaster` 底层驱动对象，启动串口接收线程
   - 创建 `Rosmaster_Camera` 摄像头对象（默认深度摄像头）
   - 启动 TCP Socket 监听端口 6000
   - 蜂鸣器响 3 声表示启动完成
   - 启动 gevent WSGI 服务器监听端口 6500
3. 手机 APP 连接小车 WiFi 热点后，通过 TCP 6000 发指令
4. 浏览器访问 `http://<小车IP>:6500` 查看视频流

## 八、开发注意事项

1. **Cython 编译**：主模块 `rosmaster_main.py` 已编译为 `.so` 文件，修改后需重新编译：

   ```bash
   python3 setup.py build_ext --inplace
   ```

   对应的原始源码是 `rosmaster_main_ori.py`（仅供参考，实际运行的是 `.so`）
2. **硬件依赖**：代码依赖 `/dev/myserial`（串口设备）和 `/dev/camera_*`（摄像头设备），在没有硬件的 PC 上无法直接运行
3. **授权机制**：`license.cpython-*.so` 会检查 `license.json` 中的 MAC 地址和过期时间
4. **Python 版本**：项目基于 Python 3.8，部分 `.so` 文件绑定了特定 Python 版本
5. **安装底层库**：

   ```bash
   cd ~/Rosmaster-App/py_install_V3.3.1/
   sudo python3 setup.py install
   ```

## 九、关键文件索引


| 想了解...          | 看这个文件                                                           |
| ------------------ | -------------------------------------------------------------------- |
| 程序入口和启动流程 | `app.py:35-62`                                                       |
| APP 指令解析协议   | `rosmaster_main_ori.py` 中的 `parse_data()` 函数                     |
| 小车运动控制实现   | `rosmaster_main_ori.py` 中的 `car_motion_handle()`                   |
| 串口底层通信       | `Rosmaster_Lib.py` 中的 `Rosmaster` 类                               |
| 摄像头视频流       | `camera_rosmaster.py` + `rosmaster_main_ori.py` 中的 `mode_handle()` |
| WiFi 配网流程      | `wifi_rosmaster.py` 中的 `Rosmaster_WIFI` 类                         |
| 手柄控制           | `joystick_rosmaster.py` 中的 `Rosmaster_Joystick` 类                 |
| Web 页面           | `templates/index.html`                                               |