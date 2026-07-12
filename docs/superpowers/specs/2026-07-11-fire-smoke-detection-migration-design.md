# MiniMover 烟火识别独立模块迁移设计

## 状态

已批准。

## 日期

2026-07-11

## 背景

现有烟火检测项目位于 `E:\fire-smoke-detect-yolov4`，MiniMover 中已有 `traffic_light/` 等独立视觉识别目录。目标是将烟火检测能力作为一个独立模块迁入 `E:\MiniMover`，同时支持 Windows PC 和 Linux/Jetson，不在本阶段接入 MiniMover Web 页面。

源项目不仅包含运行模型，还包含完整训练数据、训练记录、辅助脚本、检测结果，以及已提交和未提交的本地工作。迁移需要同时满足：

1. 烟雾和火焰识别可以独立运行；
2. 完整保留可体现并复现实验工作量的资料；
3. 不把 Python 虚拟环境、缓存或嵌套 Git 仓库直接带入 MiniMover；
4. 迁移验证成功后，安全删除原项目目录；
5. 不影响 MiniMover 中现有车牌、红绿灯和小车控制代码。

## 方案选择

采用“整理后的运行模块 + 完整训练成果证明”方案，而不是原样嵌套整个项目，也不在本阶段转换 ONNX/TensorRT。

### 选择理由

- 独立目录和启动脚本与 MiniMover 现有视觉模块组织方式一致；
- 保留旧版 YOLOv5 运行代码可降低模型兼容风险；
- 完整迁移 `VOC2020`、训练记录和训练源码可以复现实验；
- Git bundle 和工作区补丁既能保存历史，又不会形成嵌套仓库；
- 暂不进行模型格式升级，避免将迁移任务扩大为推理框架重构。

## 目标目录结构

```text
E:\MiniMover\fire_smoke_detection\
├── detector.py
├── run.bat
├── run.sh
├── requirements.txt
├── requirements-jetson.txt
├── README.md
├── model\
│   └── best.pt
├── yolov5_runtime\
├── samples\
├── training\
│   ├── VOC2020\
│   ├── runs\
│   ├── scripts\
│   ├── fire_smoke.yaml
│   └── source\
├── evidence\
│   ├── results\
│   ├── source-history.bundle
│   ├── working-tree.patch
│   ├── untracked-files.txt
│   ├── checksums.sha256
│   └── provenance.txt
└── output\
```

`output/` 是运行时输出目录，应通过 `.gitignore` 排除。训练记录和数据集属于迁移成果，不应被通配规则误排除。

## 运行接口

统一入口为：

```bash
python detector.py --source 0
python detector.py --source path/to/image.jpg
python detector.py --source path/to/video.mp4
```

接口要求：

- 默认模型为模块内的 `model/best.pt`；
- `--source 0` 使用默认摄像头；
- 支持图片、视频、目录以及旧版 YOLOv5 已支持的输入形式；
- 默认结果写入模块内的 `output/`；
- 所有内置路径均根据 `detector.py` 所在目录解析，而不是依赖调用者的当前工作目录；
- 支持 `--device cpu` 和 CUDA 设备选择；
- 保留置信度、IoU 阈值、显示窗口和结果保存等必要参数；
- Windows 使用 `run.bat`，Linux/Jetson 使用 `run.sh`；
- 启动脚本只负责环境检查和参数转发，不隐式修改训练资料。

## 平台支持

### Windows PC

- 提供 `run.bat`；
- 支持摄像头、图片和视频输入；
- 无 CUDA 时可使用 CPU；
- README 说明推荐 Python 版本和 PyTorch 安装方式。

### Linux/Jetson

- 提供可执行的 `run.sh`；
- 不在脚本中强制安装通用 PyPI CUDA 版 PyTorch；
- `requirements-jetson.txt` 说明 Jetson 的 PyTorch 应匹配 JetPack/CUDA 环境安装；
- 推理入口与 Windows 保持一致。

## 运行代码迁移范围

迁入以下运行所需内容：

- `yolov5/best.pt`，重定位为 `model/best.pt`；
- 旧版 YOLOv5 的 `models/`、`utils/` 及推理需要的源码；
- 经整理的统一入口 `detector.py`；
- 必要的数据配置和类别名称；
- 少量原有检测样例，用于迁移后冒烟测试。

不把 `yolov5s.pt` 作为默认或必要模型迁入，因为烟火识别使用训练后的 `best.pt`。

## 训练资料迁移范围

完整迁入：

- `VOC2020/` 中的原始图片、XML 标注、YOLO 标签、训练/验证划分和缓存以外的必要资料；
- `yolov5/runs/` 中的训练、验证和检测记录；
- `yolov5/scripts/`；
- 已修改的 `train.py`、数据加载、模型和工具源码；
- `yolov5/data/fire_smoke.yaml`；
- `result/` 和 `xml_lab/`；
- 原项目 README、中文/英文说明和 LICENSE。

缓存、`__pycache__`、`.pyc`、虚拟环境和可重新生成的临时文件不属于训练成果证明，不迁入。

## 来源和工作量证明

在删除源目录前生成：

1. `source-history.bundle`：使用 `git bundle create ... --all` 保存原仓库完整 Git 历史和分支引用；
2. `working-tree.patch`：保存已跟踪文件的未提交修改，包括二进制差异信息；
3. `untracked-files.txt`：记录迁移前未跟踪文件列表；
4. `provenance.txt`：记录原绝对路径、当前提交 ID、分支、迁移日期、Git 状态和迁移规则；
5. `checksums.sha256`：记录关键模型、训练记录、数据配置和数据集文件的 SHA-256，用于迁移校验。

未跟踪但属于训练资料的实体文件必须迁入目标目录，不能只记录文件名。

## 验证策略

删除源目录前必须完成以下检查：

1. `model/best.pt` 与源模型 SHA-256 一致；
2. `VOC2020` 的文件数、总大小和关键文件哈希与源目录一致；
3. `runs/`、`scripts/`、结果文件和训练源码均存在；
4. Git bundle 可通过 `git bundle verify` 验证；
5. 工作区补丁和来源说明非空且可读；
6. Python 文件通过语法编译检查；
7. 模型能够被 PyTorch 加载；
8. 至少使用一张样例图片完成一次端到端推理，并在 `output/` 生成结果；
9. Windows 启动脚本参数转发通过静态检查或实际执行验证；
10. Linux 脚本通过 Bash 语法检查；如果当前 Windows 环境没有 Bash，则明确记录该项未在本机动态执行；
11. MiniMover 现有文件的 Git 状态除本次新增模块和文档外不发生变化。

如果受当前依赖或硬件限制无法完成 GPU/Jetson 实机验证，可以完成 CPU 冒烟测试并在迁移报告中明确说明未验证项；但不能在关键文件校验失败时删除源目录。

## 安全删除策略

迁移采用“先复制、后验证、最后删除”的逻辑，以实现最终的真正移动：

1. 解析并确认源路径严格等于 `E:\fire-smoke-detect-yolov4`；
2. 确认目标路径位于 `E:\MiniMover\fire_smoke_detection`；
3. 生成历史、补丁、清单和哈希；
4. 复制运行代码、训练资料和证明文件；
5. 执行全部可用验证；
6. 验证成功后，再次确认源路径不等于 MiniMover 根目录或其父目录；
7. 使用 PowerShell 原生命令按字面路径删除源目录，不跨 Shell 拼接删除命令；
8. 删除后确认目标目录和关键文件仍存在。

如果任何关键验证失败，保留源目录并报告失败原因，不执行删除。

## 不在本阶段实施

- 不接入 MiniMover Flask/Web 页面；
- 不修改车牌、红绿灯或小车控制模块；
- 不重新训练模型；
- 不升级到新版 YOLOv5/Ultralytics API；
- 不转换 ONNX 或 TensorRT；
- 不迁移 `.venv`、`.git` 目录、Python 缓存或临时输出；
- YOLOv4 不作为本模块的运行入口。仅在其配置或结果对训练证明必要时，将相关材料放入训练证据目录，而不迁入完整 Darknet 构建树。

## 成功标准

迁移完成时应满足：

- `E:\MiniMover\fire_smoke_detection` 是可独立理解和启动的模块；
- Windows 和 Linux/Jetson 均有明确启动入口；
- `best.pt` 可加载，且至少完成一次样例推理；
- 完整训练集、训练记录、训练脚本、修改源码和结果资料均已保存；
- 原 Git 历史和未提交工作均有可验证归档；
- 原目录只有在全部关键校验通过后才被删除；
- MiniMover 现有识别和控制模块未被修改。
