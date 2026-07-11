# MiniMover 三项识别答辩演示

本目录提供车牌识别、红绿灯识别、火焰烟雾识别的离线并行展示，面向 **5 分钟答辩**。默认不调用摄像头，也不同时加载三个大型模型，适合现场快速、稳定展示。

## 答辩时怎么操作

1. 提前双击仓库根目录的 `一键启动三项识别演示.bat`。
2. 等待约 2 秒，屏幕会同时出现三个独立循环窗口。
3. 介绍三个模块分别对应车牌、交通信号灯和火焰烟雾视觉识别。
4. 在任一窗口按 `Q` 或 `Esc` 可关闭该窗口。
5. 如果 Python 或 OpenCV 临时不可用，直接双击 `videos/三项识别答辩演示.mp4` 作为兜底。

## 建议的 30 秒演示话术

> 系统把视觉能力拆成三个独立模块，分别负责车牌、交通信号灯以及火焰烟雾识别。三个模块能够独立部署和运行。这里为了保证答辩稳定，使用项目已有识别结果制作了离线循环演示；火焰烟雾模块同时保留完整模型、训练数据、训练记录和实际推理入口。

## 演示前自检

在 PowerShell 或 CMD 中运行：

```bat
一键启动三项识别演示.bat --check
```

成功时输出：

```text
[PASS] Python, OpenCV and all demo videos are ready.
```

仅播放合成兜底视频：

```bat
一键启动三项识别演示.bat --fallback
```

## 文件说明

- `player.py`：三个独立窗口共用的本地视频播放器。
- `build_videos.py`：从证据帧重新生成演示视频。
- `assets/`：生成视频所用的项目结果帧副本。
- `videos/license_plate_demo.mp4`：车牌识别窗口素材。
- `videos/traffic_light_demo.mp4`：红绿灯识别窗口素材。
- `videos/fire_smoke_demo.mp4`：火焰烟雾识别窗口素材。
- `videos/三项识别答辩演示.mp4`：无需同时打开三个窗口的合成兜底视频。

## 说明

离线视频用于快速呈现模块效果，不声称三项模型正在现场同步推理。需要展示真实火焰烟雾推理时，可运行：

```bat
fire_smoke_detection\run.bat --source fire_smoke_detection\samples\result_demo.jpg --device cpu
```
