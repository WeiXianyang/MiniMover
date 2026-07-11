# MiniMover 三项识别答辩演示

本目录提供车牌识别、红绿灯识别、火焰烟雾识别的离线并行展示，面向 **5 分钟答辩**。三个窗口播放的都是连续视频帧，不再使用静态图片缩放冒充视频。

## 答辩时怎么操作

1. 提前双击仓库根目录的 `一键启动三项识别演示.bat`。
2. 等待约 2 秒，屏幕会同时出现三个独立循环窗口。
3. 介绍三个模块分别对应车牌、交通信号灯和火焰烟雾视觉识别。
4. 在任一窗口按 `Q` 或 `Esc` 可关闭该窗口。
5. 如果现场不方便同时显示三个窗口，双击 `videos/三项识别答辩演示.mp4` 播放合成兜底视频。

## 建议的 30 秒演示话术

> 系统把视觉能力拆成三个独立模块，分别负责车牌、交通信号灯以及火焰烟雾识别。现在三个窗口展示的都是真实连续视频输入，而不是单张图片动画。为保证五分钟答辩稳定，演示采用离线循环播放；其中火焰烟雾窗口使用项目模型输出的连续结果视频，完整模型、训练数据、训练记录和实际推理入口也已经迁入 MiniMover。

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
- `build_videos.py`：读取连续视频源、统一画面尺寸并重新生成答辩视频；不会合成虚假运动。
- `assets/license_plate_source.webm`：上海高架道路连续实拍，画面含中国大陆蓝牌车辆。
- `assets/traffic_light_source.webm`：汽车/有轨电车信号灯近景连续实拍，红灯目标清晰可见。
- `assets/fire_smoke_source.mp4`：迁移项目中模型处理后的森林火焰连续结果视频。
- `videos/license_plate_demo.mp4`：车牌识别窗口素材。
- `videos/traffic_light_demo.mp4`：红绿灯识别窗口素材。
- `videos/fire_smoke_demo.mp4`：火焰烟雾识别窗口素材。
- `videos/三项识别答辩演示.mp4`：无需同时打开三个窗口的合成兜底视频。
- `SOURCE_CREDITS.md`：外部连续视频的来源与许可记录。

## 演示边界

离线视频用于快速、可靠地呈现三个独立视觉模块，不声称车牌和交通灯模型正在答辩电脑上同步实时推理。火焰烟雾素材来自本项目模型的连续输出结果。需要现场执行真实火焰烟雾推理时，可运行：

```bat
fire_smoke_detection\run.bat --source fire_smoke_detection\samples\result_demo.jpg --device cpu
```
