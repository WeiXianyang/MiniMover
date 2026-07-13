# FireGuard 工业巡检小车 RAG 文本知识库

知识库版本：1.0
整理日期：2026-07-11
项目名称：FireGuard 工业巡检小车
适用场景：项目问答、答辩辅助、需求追踪、技术说明、开发交接、演示讲解
数据来源：中期检查 PPT、MiniMover 当前仓库代码与说明文档

## 使用与可信度规则

1. 本知识库只包含文本，不包含图片、向量或二进制模型。
2. 每个知识块使用独立 CHUNK_ID，可按分隔线切分后建立向量索引。
3. STATUS=代码验证 表示在当前仓库中可找到直接实现或验证记录。
4. STATUS=PPT阶段结论 表示来自 2026-07-11 中期检查 PPT，可能是汇报口径，不等同于完整代码已集成。
5. STATUS=规划 表示尚未完整落地，不应回答为“已经实现”。
6. STATUS=平台能力 表示厂家材料、课程材料或命令记录证明硬件/平台具备该能力，但当前仓库不一定包含完整 ROS 2 工程。
7. 当 PPT 与仓库存在差异时，以“当前仓库代码验证”作为实现状态的优先依据，并明确指出差异。
8. 当前磁盘未发现 AGENTS.md 所描述的 wpr_simulation2_src ROS 2 仿真包，因此不能把该包当作本仓库现有实现。

---
CHUNK_ID: FG-001
TITLE: 项目一句话定义
STATUS: PPT阶段结论
KEYWORDS: FireGuard, 工业巡检小车, 配电房, 仓储通道, 端边云, 自主巡检
SOURCE: PPT第1页、第9页
CONTENT:
FireGuard 是面向配电房与仓储通道的工业巡检小车原型系统，目标是把移动端控制、车端服务、ROS 2 与导航能力、边缘视觉识别、异常告警、云端归档和报告输出串成端—边—云业务闭环。项目强调低成本、可演示、可答辩、可部署，并为多车协同和 Agent 语音交互预留扩展方向。

---
CHUNK_ID: FG-002
TITLE: 项目背景与核心痛点
STATUS: PPT阶段结论
KEYWORDS: 巡检频次, 人工巡检, 安全风险, 告警滞后, 信息碎片化
SOURCE: PPT第4页
CONTENT:
项目针对四类现场痛点：第一，人工巡检间隔长，配电房和仓储重点区域难以高频覆盖；第二，夜间或危险区域人工进入成本高且存在人身安全风险；第三，异常发现和告警滞后，可能错过最佳处置窗口；第四，现场记录不结构化，事后追溯和责任界定困难。FireGuard 的目标响应包括 7×24 小时自动巡检、YOLO 边缘推理、多源融合告警、远程视频接管、告警归档和结构化报告。

---
CHUNK_ID: FG-003
TITLE: 应用场景边界
STATUS: PPT阶段结论
KEYWORDS: 配电房, 仓储通道, 配电柜, 变压器, 货架, 电缆沟, 机房
SOURCE: PPT第6页、第10页
CONTENT:
项目聚焦室内或半结构化的配电房与仓储通道，不以户外长距离巡检为当前重点。典型环境包括配电柜、变压器、货架通道、消防点、电缆沟和机房。典型风险包括电气过热、烟雾与火焰、通道堆物或障碍阻挡、人员误入危险区域。

---
CHUNK_ID: FG-004
TITLE: 目标用户与职责
STATUS: PPT阶段结论
KEYWORDS: 巡检员, 管理者, APP, 告警, 巡检点
SOURCE: PPT第10页
CONTENT:
主要用户角色有巡检员和管理者。巡检员通过 APP 发起任务、查看实时视频并在必要时远程接管小车；管理者负责配置巡检点、查看告警、监督系统运行和审阅巡检结果。后续 Agent 语音交互可作为更自然的任务入口，但不能替代急停等安全控制。

---
CHUNK_ID: FG-005
TITLE: 核心业务能力
STATUS: PPT阶段结论
KEYWORDS: 自动巡检, 火灾检测, 定点配送, 事后复盘, 抓拍, 报告
SOURCE: PPT第10页
CONTENT:
FireGuard 的四类业务能力是：自动巡检，按预设点位依次移动并避障；火灾检测，通过视觉与传感器数据识别烟雾或火焰，异常时停车、抓拍并告警；定点配送，将灭火器、急救包等应急物资送到指定位置；事后复盘，将任务过程、识别结果和告警记录整理为结构化巡检报告。

---
CHUNK_ID: FG-006
TITLE: 功能需求拆解
STATUS: PPT阶段结论
KEYWORDS: TCP控车, 视频流, SLAM, 多点导航, 传感融合, WebSocket, Docker
SOURCE: PPT第11页
CONTENT:
功能需求分为六组：设备控制包括 TCP 控车、实时视频、手动接管和一键急停；自动巡检包括 SLAM 建图、多点导航、雷达避障和到点检测；火灾检测包括视觉识别、传感器融合、多源判定和告警联动；定点配送包括起止点选择、Nav2 导航和到点确认；告警报告包括实时推送、记录归档和报告导出；系统支撑包括 Docker 部署、CI/CD、WebSocket 和核心参数配置化。

---
CHUNK_ID: FG-007
TITLE: 非功能指标
STATUS: PPT目标指标
KEYWORDS: 500ms, 3s, 三步操作, 配置化, 异常提示
SOURCE: PPT第11页
CONTENT:
中期方案提出的非功能约束为：控制响应时间不高于 500 毫秒；告警推送时间不高于 3 秒；常用操作路径不超过 3 步；异常状态必须给出明确提示；核心参数应配置化。以上是目标指标，当前仓库没有完整的端到端基准测试结果，不能直接回答为已经达标。

---
CHUNK_ID: FG-008
TITLE: 总体系统架构
STATUS: PPT阶段结论
KEYWORDS: 移动端, 协议层, 车端服务, ROS2, 云平台, CI/CD, Agent
SOURCE: PPT第13页
CONTENT:
总体架构分为五层：移动端 APP，包括已适配的鸿蒙端和规划并行开发的 Android 端；通信协议层，包括 TCP 控车、HTTP 视频、JSON 业务接口和 WebSocket 状态推送；车端服务层，包括控车接口、视频流、状态推送和任务编排；ROS 2 能力层，包括底盘、雷达、相机、视觉识别和传感器桥接；云平台与 CI/CD 层，包括状态归档、告警记录、巡检报告和 Docker 镜像构建。Agent 语音链路作为横向入口调用控车或任务接口。

---
CHUNK_ID: FG-009
TITLE: 当前仓库总体结构
STATUS: 代码验证
KEYWORDS: MiniMover, 根目录, fire_smoke_detection, traffic_light, oh-ai-car-ros-app, demo_showcase
SOURCE: 当前仓库目录结构
CONTENT:
当前 MiniMover 仓库的主要实现包括：根目录的小车 Web 服务、PC 调试服务、摄像头与底盘控制脚本；fire_smoke_detection 独立烟火识别模块；traffic_light 红绿灯识别与车牌相关第三方代码；oh-ai-car-ros-app 鸿蒙控制端；demo_showcase 三项识别答辩演示；智能小车课程材料和底盘固件资料。当前未发现 wpr_simulation2_src 目录，也未发现可直接 colcon build 的本仓库 ROS 2 包。

---
CHUNK_ID: FG-010
TITLE: 当前实现状态的事实边界
STATUS: 代码验证
KEYWORDS: 已实现, 未集成, 状态边界, 防止幻觉
SOURCE: 当前仓库与PPT交叉核对
CONTENT:
当前仓库可直接验证的能力包括小车 TCP 控制协议、Flask MJPEG 视频服务、鸿蒙基础控制页面、火焰烟雾识别、轻量红绿灯识别和三项识别离线演示。PPT 中的完整自主巡检闭环、多点任务编排、多传感器融合、云端归档、巡检报告、多车协同、改进 DARP、Android 完整业务端和 Agent 语音控制仍应视为方案、进行中工作或后续规划，除非后续补充对应代码与联调记录。

---
CHUNK_ID: FG-011
TITLE: 小车 Web 与视频服务
STATUS: 代码验证
KEYWORDS: Flask, gevent, MJPEG, 6500, video_feed, index2
SOURCE: app.py, app_pc.py, templates/index.html, templates/index2.html
CONTENT:
车端 app.py 使用 Flask 和 gevent WSGIServer，在 0.0.0.0:6500 提供 Web 服务。根路径和 /index2 返回视频页面，/video_feed 以 multipart/x-mixed-replace 形式输出 MJPEG 视频流，/init 用于初始化 TCP Socket。app_pc.py 是 PC 前端调试版本，优先读取本机摄像头，没有摄像头时生成“NO CAMERA”测试帧，并明确不提供真实小车控制功能。

---
CHUNK_ID: FG-012
TITLE: 小车 TCP 控制服务
STATUS: 代码验证
KEYWORDS: TCP, 6000, rosmaster, socket, 控车, 状态返回
SOURCE: rosmaster_main_ori.py, app.py
CONTENT:
小车控制服务在车端监听 TCP 6000 端口。控制程序接收以特定起止符封装的命令，解析后调用 Rosmaster 底盘接口，并可返回底盘版本、电池电压、机械臂角度、车辆速度、稳定状态和相机类型等信息。app.py 启动 TCP 服务、底盘线程和 6500 端口视频服务，真实硬件运行依赖 Rosmaster_Lib、摄像头和 Jetson/树莓派相关环境。

---
CHUNK_ID: FG-013
TITLE: 鸿蒙端通信参数
STATUS: 代码验证
KEYWORDS: HarmonyOS, IP, 6000, 6500, NetworkSettings, Preferences
SOURCE: oh-ai-car-ros-app/entry/src/main/ets/pages/NetworkSettings.ets
CONTENT:
鸿蒙端网络设置页默认 IP 为 192.168.1.11，TCP 端口为 6000，视频端口为 6500。用户可编辑这些参数，连接时由 TCPClientManager 建立 TCP 连接，视频组件使用单独的视频端口。IP、TCP 端口和视频端口会通过 PreferencesUtils 保存和恢复，因此部署时应修改为实际车端地址。

---
CHUNK_ID: FG-014
TITLE: 鸿蒙端视频访问方式
STATUS: 代码验证
KEYWORDS: HarmonyOS, Web组件, HTTP, index2, 视频流
SOURCE: oh-ai-car-ros-app/entry/src/main/ets/components/VideoComponents.ets
CONTENT:
鸿蒙端 VideoComponents 通过 Web 组件访问 http://车端IP:视频端口/index2。index2 页面再加载 /video_feed 的 MJPEG 流。默认视频端口为 6500。该链路适合基础实时画面展示，但当前代码没有展示 WebRTC、低延迟编码或端到端时延测量。

---
CHUNK_ID: FG-015
TITLE: 鸿蒙端现有页面
STATUS: 代码验证
KEYWORDS: NetworkSettings, Index, RemoteControl, MecanumWheel, 摇杆, 按钮
SOURCE: oh-ai-car-ros-app/entry/src/main/ets/pages
CONTENT:
当前鸿蒙工程包含 NetworkSettings、Index、RemoteControl 和 MecanumWheel 四个主要页面。NetworkSettings 配置车端地址并建立连接；Index 提供功能入口；RemoteControl 支持按钮控制、摇杆控制、视频查看和自动循迹开关；MecanumWheel 支持四个轮子的独立速度调节、更新速度和全部归零。巡检任务、告警列表、报告导出等业务页面尚未在当前页面目录中形成完整实现。

---
CHUNK_ID: FG-016
TITLE: 鸿蒙端控车报文格式
STATUS: 代码验证
KEYWORDS: CarEncode, 十六进制, 校验和, $#, 命令类型
SOURCE: oh-ai-car-ros-app/entry/src/main/ets/CarUtill/CarEncode.ets
CONTENT:
鸿蒙端 CarEncode 将控车消息编码为十六进制文本帧，格式为“$ + 车辆类型 + 命令类型 + 长度 + 数据 + 校验和 + #”。车辆类型当前固定为 01，校验和为各字节累加后对 256 取模。已有命令包括循迹开启 63、循迹关闭 64、拍照 60、开始录像 61、停止录像 62、摇杆控制 10、按钮方向控制 15、四轮独立控制 21。

---
CHUNK_ID: FG-017
TITLE: 鸿蒙工具链适配过程
STATUS: PPT阶段结论与工程证据
KEYWORDS: hvigor, API23, ArkTS, DevEco, SDK, 签名, hdc
SOURCE: PPT第15页, oh-ai-car-ros-app工程配置
CONTENT:
鸿蒙端从旧版工具链迁移到 hvigor 6.x 和 API 23。主要问题包括 hvigor 依赖无法从 npm/ohpm 获取、SDK 目录布局变化、ArkTS 严格类型规则产生编译错误、Node realpath 导致模块加载实例分裂、签名证书和模拟器 hdc 连接问题。中期解决方法是使用 DevEco 本地依赖路径、对齐 API 23 SDK、补齐 ArkTS 类型和成员初始化、统一 NODE_PATH、使用 DevEco 签名并通过 hdc tconn 连接模拟器。

---
CHUNK_ID: FG-018
TITLE: Android 端定位
STATUS: 规划
KEYWORDS: Android, 双端APP, WebSocket, 告警详情, 报告导出
SOURCE: PPT第14页、第20页、第25页
CONTENT:
Android 端被规划为与鸿蒙端并行的业务终端，目标功能包括巡检任务下发、任务状态追踪、告警详情和截图查看、巡检报告导出与分享、WebSocket 实时推送。当前仓库未发现独立的 FireGuard Android 业务 APP 源码，因此不应回答为 Android 端已经完成；PPT 中“安卓端 UI 初步实现”和“并行开发规划 30%”需要以后续代码仓库或安装包进一步核验。

---
CHUNK_ID: FG-019
TITLE: 烟火识别模块概述
STATUS: 代码验证
KEYWORDS: YOLOv5, fire, smoke, best.pt, Jetson, detector.py
SOURCE: fire_smoke_detection/README.md, fire_smoke_detection/detector.py
CONTENT:
fire_smoke_detection 是独立迁移的烟火识别模块，使用与模型匹配的旧版 YOLOv5 运行时代码和 model/best.pt 权重，检测类别为 fire 与 smoke。detector.py 是路径稳定的启动器，会调用 yolov5_runtime/detect.py，将模型和输出目录固定到模块内部，同时允许摄像头编号、图片、视频、HTTP、RTSP 或 RTMP 作为输入。结果默认写入 fire_smoke_detection/output。

---
CHUNK_ID: FG-020
TITLE: 烟火识别运行命令
STATUS: 代码验证
KEYWORDS: run.bat, run.sh, source, device, conf-thres, iou-thres
SOURCE: fire_smoke_detection/README.md, run.bat, run.sh
CONTENT:
Windows 可在 fire_smoke_detection 目录运行 run.bat --source 0 --view-img，或指定图片、视频。Linux/Jetson 可运行 bash run.sh --source 0 --view-img，并可用 PYTHON_BIN 指定 Python。常用参数包括 --source、--device、--conf-thres 和 --iou-thres。Jetson 应优先安装与 JetPack/CUDA 匹配的 NVIDIA PyTorch 与 torchvision，不要用通用 CUDA wheel 覆盖 JetPack 配套版本。

---
CHUNK_ID: FG-021
TITLE: 烟火训练数据与模型规模
STATUS: 代码验证
KEYWORDS: 数据集, 2059, VOC2020, XML, best.pt, 14.76MB
SOURCE: fire_smoke_detection/training, evidence/migration-report.txt
CONTENT:
当前仓库统计到烟火训练数据包含 2059 张图像和 2059 个 XML 标注文件，数据配置 fire_smoke.yaml 定义两个类别 fire、smoke。模型 best.pt 大小为 14,758,954 字节，SHA256 为 d1eae6859229ac1f5699c60f9445fa054dafc6a2cc59f00fc30ea6379dc3247e。迁移报告记录数据集总文件数为 8241，总大小约 186,978,694 字节。

---
CHUNK_ID: FG-022
TITLE: 烟火模型训练记录
STATUS: 代码验证
KEYWORDS: 300 epochs, batch 8, 640, precision, recall, mAP
SOURCE: fire_smoke_detection/training/runs/exp_Re10/opt.yaml, exp_Re13/results.txt
CONTENT:
现存训练配置记录使用 300 个 epoch、batch size 8、图像尺寸 640，并采用 fire_smoke 数据配置。exp_Re13 最后一个 epoch 的记录中，Precision 约为 0.6307、Recall 约为 0.6606、mAP@0.5 约为 0.6115、mAP@0.5:0.95 约为 0.2901。该数值是训练记录中的最终轮结果，不等于专门挑选的最佳轮指标，也不等于真实配电房现场的最终验收精度。

---
CHUNK_ID: FG-023
TITLE: 烟火模块验证结果
STATUS: 代码验证
KEYWORDS: migration verification, CPU加载, sample inference, PASS, Jetson未验证
SOURCE: fire_smoke_detection/evidence/migration-report.txt
CONTENT:
迁移验证报告记录：源目标目录校验通过，Git 历史归档通过，7 个单元测试通过，Python 语法编译通过，模型可在 CPU 加载并识别 fire、smoke，样例推理检测到 1 个 fire，Windows 启动器帮助检查通过。Jetson GPU 推理未运行，原因是缺少 Jetson 硬件；Linux Bash 动态语法检查在当时环境中也未运行。因此不能声称 Jetson GPU 性能已经完成实机验证。

---
CHUNK_ID: FG-024
TITLE: 红绿灯识别算法
STATUS: 代码验证
KEYWORDS: OpenCV, HSV, HoughCircles, red, yellow, green, ROI
SOURCE: traffic_light/detector.py
CONTENT:
当前轻量红绿灯检测器由纯 OpenCV 实现，不依赖 YOLO。算法只处理画面上半部分，先转 HSV 和灰度图并进行高斯模糊，再用 HoughCircles 检测圆形候选；在圆形区域内统计红、黄、绿 HSV 像素比例，比例大于 0.3 时判定颜色，并保留最大匹配圆。输出状态为 red、yellow、green 或 none。

---
CHUNK_ID: FG-025
TITLE: 红绿灯模块限制与运行方式
STATUS: 代码验证
KEYWORDS: 光照, 阈值, 摄像头, 截图, run.bat, 可移植性
SOURCE: traffic_light/detector.py, traffic_light/run.bat
CONTENT:
红绿灯模块可读取摄像头或视频，按 q 退出、按 s 保存 screenshot.jpg。算法依赖固定 HSV 阈值、圆形结构和目标位于画面上半部的假设，强光、反光、距离过远、非圆形灯具和遮挡可能导致误检或漏检。traffic_light/run.bat 当前硬编码 E:\MiniMover\traffic_light 路径，可移植部署时应改为基于脚本目录的相对路径。

---
CHUNK_ID: FG-026
TITLE: 车牌识别当前实现边界
STATUS: 代码验证
KEYWORDS: 车牌, HyperLPR, cascade, 蓝牌, 答辩演示, OCR
SOURCE: demo_showcase/build_videos.py, demo_showcase/SOURCE_CREDITS.md
CONTENT:
当前仓库可验证的车牌演示使用 HyperLPR 级联分类器定位候选区域，再用 HSV 蓝色比例过滤中国大陆蓝牌，并在演示视频上标注“CHINA PLATE”。该实现证明了车牌区域检测与演示链路，但当前 demo_showcase 代码没有完成字符分割、字符识别或车牌号码结构化输出，因此不能把它描述为完整车牌 OCR 业务系统。

---
CHUNK_ID: FG-027
TITLE: 三项识别答辩演示
STATUS: 代码验证
KEYWORDS: 车牌, 红绿灯, 火焰烟雾, 三窗口, 离线视频, 5分钟答辩
SOURCE: demo_showcase/README.md, 一键启动三项识别演示.bat
CONTENT:
三项识别答辩演示用于 5 分钟现场展示。双击根目录“一键启动三项识别演示.bat”后，会启动车牌、红绿灯、火焰烟雾三个独立循环窗口；任一窗口可按 Q 或 Esc 关闭。脚本 --check 模式会检查 Python、OpenCV、三个模块视频和合成兜底视频。若不方便同时展示三个窗口，可播放 demo_showcase/videos 下的三项识别合成视频。

---
CHUNK_ID: FG-028
TITLE: 答辩演示与实时系统的区别
STATUS: 代码验证
KEYWORDS: 离线演示, 实时推理, 连续视频, 兜底, 答辩稳定性
SOURCE: demo_showcase/README.md, build_videos.py
CONTENT:
答辩演示播放的是连续真实视频帧，不是单张图片缩放动画，但为了现场稳定采用离线循环素材。火焰烟雾视频来自项目模型已有输出；车牌和红绿灯演示由轻量离线标注器处理公开视频素材。该演示能证明模块展示能力和工程稳定性，不等同于三个模型已经同时接入小车实时摄像头并形成统一告警闭环。

---
CHUNK_ID: FG-029
TITLE: ROS 2、雷达与导航平台能力
STATUS: 平台能力
KEYWORDS: ROS2, RPLiDAR, SLAM, Nav2, 雷达避障, 自动导航, cmd.txt
SOURCE: cmd.txt, 智能小车课程材料/1-智能小车使用和固件烧录/材料校验与烧录说明.md
CONTENT:
平台资料记录了 ROS 2 底盘驱动、SLLidar 启动、雷达避障、雷达跟随、雷达警卫、Astra 相机、颜色追踪、循线、SLAM 建图和自动导航的操作能力。课程材料说明 iCar.bin 固件支持常规 ROS 功能、雷达功能、建图、自动导航和 APP 控制。但当前仓库缺少这些 ROS 2 包的完整源码与 launch 文件，因此更准确的表述是“硬件平台和配套环境具备或曾验证过该能力”，而不是“本仓库已经集成完整 Nav2 巡检流程”。

---
CHUNK_ID: FG-030
TITLE: 多车协同与改进 DARP 方案
STATUS: 规划
KEYWORDS: DARP, A星, 多机器人, 区域划分, 协同遍历, 任务锁定
SOURCE: PPT第17页、第20页、第25页
CONTENT:
多车协同方案计划采用改进 DARP。方案将巡检路线离散为节点或区域，由中心节点维护未遍历、锁定、已完成状态，多车通过申请机制动态获取任务，以减少重复和遗漏。区域代价评估计划用 A* 启发式路径代价替代传统欧氏距离，使分区能考虑障碍物、路径长度和转弯次数。当前仓库未发现 DARP 或多车调度实现代码，该能力处于待完成或拓展阶段。

---
CHUNK_ID: FG-031
TITLE: 多源融合告警方案
STATUS: 规划
KEYWORDS: RGB, 深度, YOLO, 烟雾传感器, 温度传感器, 告警分级
SOURCE: PPT第16页
CONTENT:
计划中的多源融合流程为：采集 RGB 与深度图像，执行 YOLO 推理，同时采集烟雾、温度等传感器数据，最后进行融合判定并输出正常、待确认、高等级等告警等级。融合的价值是降低单一视觉模型受光照、遮挡和相似目标影响造成的误报。当前仓库可验证的是独立视觉模块，尚未发现传感器融合规则、时间窗、置信度加权或告警分级代码。

---
CHUNK_ID: FG-032
TITLE: 标准巡检业务闭环
STATUS: 规划
KEYWORDS: 任务下发, 点位导航, 到点识别, 告警, 云同步, 巡检报告
SOURCE: PPT第18页、第25页
CONTENT:
目标业务闭环是：APP 下发巡检任务；小车按点位自主导航；到达点位后执行车牌、红绿灯、烟雾或火焰识别；发现异常时停车、抓拍并告警；任务状态和证据同步到移动端与云端；完成后返回起点并生成巡检报告。当前仓库尚未提供统一任务状态机、点位数据模型、告警 API、云端数据库和报告生成器，因此该流程是系统集成目标而非当前完整实现。

---
CHUNK_ID: FG-033
TITLE: Agent 语音交互方案
STATUS: 规划
KEYWORDS: ASR, Agent, 意图理解, TTS, 语音控制, 固定口令
SOURCE: PPT第18页、第24页、第25页
CONTENT:
Agent 语音链路计划由麦克风输入、ASR 语音识别、Agent 意图理解、控车或任务接口调用、TTS 语音播报组成。示例口令包括“前进”“停止”“开始巡检”“返回起点”“查看当前状态”。安全设计上应把语音作为高层任务入口，对停止和急停保留确定性本地控制，并为答辩准备固定口令兜底。当前仓库未发现 ASR、LLM Agent、工具调用或 TTS 的完整实现。

---
CHUNK_ID: FG-034
TITLE: 云平台与 CI/CD 方案
STATUS: PPT阶段结论与待核验
KEYWORDS: 云平台, CI/CD, Docker, GitHub, 告警归档, 镜像, 回滚
SOURCE: PPT第13页、第20页、第22页、第25页
CONTENT:
方案中的云平台负责状态归档、告警记录和巡检报告，CI/CD 负责 Docker 镜像构建、部署和稳定版本回滚。PPT 声称 GitHub CI 构建 Docker 镜像已完成，并展示了构建成功截图；当前本地仓库未发现明显的 .github/workflows 或完整 Dockerfile 证据，因此该结论应标记为 PPT 阶段成果，后续需用远程仓库工作流、镜像地址或构建日志核验。

---
CHUNK_ID: FG-035
TITLE: 中期进展概况
STATUS: PPT阶段结论
KEYWORDS: 中期进度, 已完成, 进行中, 待完成
SOURCE: PPT第20页、第26页
CONTENT:
中期汇报将项目定位与场景分析、系统架构设计、鸿蒙工程适配、车牌与红绿灯演示、Android UI 初步设计、GitHub CI 镜像构建列为阶段成果。进行中事项包括 Android 并行开发规划、车端任务编排、云平台方案和鸿蒙业务页面完善。待完成事项包括多点巡检联调、告警闭环、多车协同、灯光秀、Agent 语音、云端归档和报告导出。仓库现状还证明烟火识别模块已经迁入并通过 CPU 样例推理。

---
CHUNK_ID: FG-036
TITLE: 团队分工
STATUS: PPT阶段结论
KEYWORDS: 魏贤炀, 曹晋豪, 李沐宸, 朱宇帆, 张佳炅, 团队协作
SOURCE: PPT第21页
CONTENT:
魏贤炀负责场景定位、进度协调、风险管理、小车环境、火情/车牌/红绿灯识别、YOLO 部署调优、视觉模型和 Agent 语音；曹晋豪负责多车协作、灯光秀、ROS 2 配置及摄像头设备对接；李沐宸负责 Android APP、UI、手动遥控和动态交互；朱宇帆负责云平台、CI/CD、鸿蒙端调试开发和项目文档；张佳炅负责 SLAM、Nav2、自主路径规划与 ROS 2 基础配置。团队协作方式包括每日例会、Git 分支协作、接口文档共享和模块联调。

---
CHUNK_ID: FG-037
TITLE: 风险与兜底策略
STATUS: PPT阶段结论
KEYWORDS: 风险控制, 缩短路线, 截图, 鸿蒙优先, 固定口令, 镜像回滚
SOURCE: PPT第25页
CONTENT:
答辩与联调风险控制包括：导航不稳定时缩短路线；实时识别不稳定时保留模型输出截图和连续结果视频；移动端开发优先保证鸿蒙端可用；语音交互准备固定口令；部署异常时使用稳定 Docker 镜像回滚；三项识别演示保留合成视频作为兜底。兜底材料用于保证展示连续性，但答辩时应明确离线演示与实时闭环的区别。

---
CHUNK_ID: FG-038
TITLE: 推荐的统一告警数据结构
STATUS: 设计建议
KEYWORDS: alert_id, task_id, robot_id, evidence, severity, timestamp
SOURCE: 根据PPT业务闭环与当前模块接口整理
CONTENT:
后续系统集成可统一使用告警对象：alert_id 表示告警唯一编号；task_id 表示所属巡检任务；robot_id 表示小车；point_id 表示巡检点；type 表示 fire、smoke、traffic_light、plate 或 obstacle；severity 表示 normal、confirm、high；confidence 表示模型置信度；sensor_values 保存温度和烟雾等数据；image_uri 或 video_uri 保存证据；created_at 保存时间；status 表示 new、acknowledged、resolved。该结构是知识库建议，不是当前仓库既有接口。

---
CHUNK_ID: FG-039
TITLE: 推荐的巡检任务状态机
STATUS: 设计建议
KEYWORDS: task state, created, navigating, inspecting, alerting, returning, completed, failed
SOURCE: 根据PPT第18页业务闭环整理
CONTENT:
后续任务编排建议采用明确状态机：CREATED 已创建；DISPATCHED 已下发；NAVIGATING 前往点位；ARRIVED 已到点；INSPECTING 正在识别；ALERTING 正在处理异常；NEXT_POINT 前往下一点；RETURNING 返回起点；COMPLETED 完成；PAUSED 暂停；CANCELLED 取消；FAILED 失败。每次状态迁移应记录时间、操作者、原因和证据，避免 APP、车端和云端状态不一致。该状态机尚未在当前仓库实现。

---
CHUNK_ID: FG-040
TITLE: 项目演示推荐话术
STATUS: 基于现状整理
KEYWORDS: 答辩话术, 演示, 三项识别, 鸿蒙, 闭环
SOURCE: PPT与demo_showcase/README.md
CONTENT:
推荐表述：FireGuard 面向配电房和仓储通道，当前已经完成小车基础控制与视频链路、鸿蒙端工具链适配、车牌区域检测、红绿灯检测和火焰烟雾模型迁移，并准备了三项连续视频演示。项目下一步不是简单增加更多模型，而是把任务下发、导航、到点识别、异常停车抓拍、移动端推送、云端归档和报告生成联调成可复现的巡检业务闭环。

---
CHUNK_ID: FG-041
TITLE: 常见问答—项目创新点
STATUS: 综合总结
KEYWORDS: 创新点, 低成本, 全栈, 双端APP, 多源融合, Agent
SOURCE: PPT第8页、第9页、第13页
CONTENT:
FireGuard 的创新点不在单个算法，而在面向中小配电房和仓储通道的低成本全栈验证：把小车控制、视频、ROS 2/SLAM、边缘视觉、双端 APP、告警、云平台和 CI/CD 放入同一业务链路；用车牌、交通灯、火焰烟雾覆盖多类视觉任务；规划多源融合、多车协同和 Agent 语音交互。答辩时应把“已实现模块”和“系统级规划”分开陈述。

---
CHUNK_ID: FG-042
TITLE: 常见问答—为什么选择 YOLO 与边缘推理
STATUS: 综合总结
KEYWORDS: YOLO, Jetson Orin Nano, 边缘计算, 时延, 隐私, 断网
SOURCE: PPT第5页、第7页、第16页, fire_smoke_detection模块
CONTENT:
YOLO 适合对火焰、烟雾等目标做统一目标检测，能够输出类别、位置和置信度，并可在 Jetson Orin Nano 上进行边缘部署。边缘推理可以减少视频持续上传带来的带宽压力，在云端网络不稳定时保留本地识别能力，并有利于缩短告警链路。当前项目实际迁入的是旧版 YOLOv5 烟火模型，YOLOv8 属于调研或后续升级方向。

---
CHUNK_ID: FG-043
TITLE: 常见问答—为什么当前红绿灯不用 YOLO
STATUS: 代码验证与技术解释
KEYWORDS: HSV, HoughCircles, 轻量算法, YOLO, 算力
SOURCE: traffic_light/detector.py
CONTENT:
当前红绿灯模块采用 HSV 阈值和 Hough 圆检测，因为目标类别少、颜色特征强、实现轻量、无需训练模型，适合快速验证和答辩演示。缺点是对光照、反光、形状和拍摄位置敏感。后续若需要复杂环境鲁棒性、远距离目标或多目标检测，可以替换为训练型检测模型，并保留颜色规则作为二次校验。

---
CHUNK_ID: FG-044
TITLE: 常见问答—当前最大技术缺口
STATUS: 综合总结
KEYWORDS: 系统集成, 任务编排, 实时闭环, 接口统一, 测试
SOURCE: 当前仓库与PPT交叉核对
CONTENT:
当前最大缺口不是单个识别算法，而是系统集成：缺少统一任务模型和状态机；缺少导航到点事件与视觉推理触发机制；缺少统一告警 API 和多源融合规则；缺少移动端业务页面、云端持久化和报告生成；缺少真实小车端到端时延、准确率、稳定性和异常恢复测试。后续应优先完成单车最短闭环，再扩展多车、Agent 和灯光秀。

---
CHUNK_ID: FG-045
TITLE: 后续开发优先级
STATUS: 设计建议
KEYWORDS: 优先级, 单车闭环, API, 联调, 多车, Agent
SOURCE: PPT第6页、第25页与当前代码现状
CONTENT:
建议优先级为：第一，固定一个短路线和少量巡检点，完成单车导航与到点事件；第二，把烟火或红绿灯模块封装为统一推理接口；第三，完成异常停车、抓拍和本地告警；第四，打通鸿蒙端任务与告警页面；第五，增加云端归档和报告；第六，建立端到端测试与稳定镜像；最后再实现 Android、多车 DARP、Agent 语音和灯光秀。该顺序符合“单机闭环优先”的中期结论。

---
CHUNK_ID: FG-046
TITLE: 知识库回答约束
STATUS: 事实校验规则
KEYWORDS: 回答规范, 不确定性, 证据, 已实现, 规划
SOURCE: 本知识库整理规则
CONTENT:
回答 FireGuard 问题时应遵守：对代码中存在的功能使用“已实现”或“可验证”；对 PPT 汇报但本地缺少代码的内容使用“PPT 声称”“正在推进”或“规划”；对 ROS 2、SLAM、Nav2 等只有课程材料和命令记录的能力使用“平台支持或曾配置”；对 Jetson GPU 性能、500 毫秒控制响应、3 秒告警、多传感器融合精度等缺少实测报告的指标明确说“尚未完成实机或端到端验证”；不要虚构云端地址、API、数据库表、模型精度或实时帧率。
