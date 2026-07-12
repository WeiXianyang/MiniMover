# Fire Monitor Test Window Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增加可用摄像头和视频验证真实火情抓拍、AI 上传及报警链路的临时桌面窗口。

**Architecture:** 现有检测器作为子进程运行，通过文件型调试遥测与 Tkinter 窗口解耦。调试模块负责原子状态/图片写入和事件追加，检测器、事件管理器与 AI reviewer 在关键节点上报。

**Tech Stack:** Python, Tkinter, Pillow, OpenCV, unittest

---

### Task 1: 调试遥测

**Files:**
- Create: `fire_smoke_detection/fire_monitor/debug_telemetry.py`
- Test: `fire_smoke_detection/tests/test_debug_telemetry.py`

- [ ] 用测试定义状态合并、图片原子写入、事件追加和敏感字段拒绝行为。
- [ ] 实现线程安全的文件型遥测并运行测试。

### Task 2: 接入真实检测链路

**Files:**
- Modify: `fire_smoke_detection/fire_monitor/ai_reviewer.py`
- Modify: `fire_smoke_detection/fire_monitor/event_manager.py`
- Modify: `fire_smoke_detection/yolov5_runtime/detect.py`
- Test: `fire_smoke_detection/tests/test_debug_hooks.py`

- [ ] 测试 AI 尝试、上传图、状态快照的调试钩子。
- [ ] 增加可选遥测依赖及 `--no-view`、`--monitor-debug-dir` 参数。
- [ ] 保持无遥测时原行为不变并运行全套单元测试。

### Task 3: Tkinter 临时窗口

**Files:**
- Create: `fire_smoke_detection/fire_monitor_test_window.py`
- Test: `fire_smoke_detection/tests/test_monitor_test_window.py`
- Modify: `fire_smoke_detection/README.md`

- [ ] 测试摄像头/视频命令构造和调试状态读取。
- [ ] 实现启动、停止、双图预览、状态和日志列表。
- [ ] 文档化启动方式并做编译、单测和离线视频链路验证。
