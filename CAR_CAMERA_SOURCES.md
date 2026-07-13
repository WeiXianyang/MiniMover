# 小车视频源接入说明

火情识别、红绿灯识别和车牌号识别现在共用同一组视频源别名。默认别名直连小车 ROS 图像流，延迟低；原先的本机摄像头索引、本地视频文件和完整 URL 仍然可用。

## 视频源别名

| 参数 | 实际视频流 | 用途 |
| --- | --- | --- |
| `car_A` | `http://192.168.137.23:8080/stream?topic=/camera/color/image_raw` | 直接连接 car_A（推荐） |
| `car_B` | `http://192.168.137.254:8080/stream?topic=/camera/color/image_raw` | 直接连接 car_B（推荐） |
| `proxy:car_A` | `http://localhost:8888/proxy/camera/car_A` | 通过协调中心转发 car_A |
| `proxy:car_B` | `http://localhost:8888/proxy/camera/car_B` | 通过协调中心转发 car_B |

## 启动命令

从仓库根目录执行：

```bat
fire_smoke_detection\run.bat --source car_A --device cpu
traffic_light\run.bat car_A
traffic_light\plate_run.bat car_A
```

也可以指定 car_B 或协调中心代理：

```bat
traffic_light\run.bat proxy:car_B
traffic_light\plate_run.bat proxy:car_A --confidence 0.8
```

车牌入口使用仓库内 `traffic_light\lp-HyperLPR` 的 Python 3 识别流水线。首次启动时会加载其模型。入口已兼容当前 Keras 中已改名的 `PReLU` 和 `adam` 导入；如果仍出现模型加载依赖错误，请按 `traffic_light\lp-HyperLPR\requirements.txt` 使用该项目原有兼容环境。

按每个识别窗口中的 `Q` 可退出，按 `S` 可保存当前识别画面。
