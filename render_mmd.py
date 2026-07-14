"""
FireGuard Mermaid 图表生成器
使用 mmdc (mermaid-cli) 渲染专业图表，替代 matplotlib 版本
"""

import os
import subprocess
import sys

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "charts_mmd")
THEME = "default"  # default | forest | dark | neutral
BG = "white"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def mmdc_render(input_path, output_name, width=1400, height=600):
    """调用 mmdc 渲染 mermaid 文件为 PNG"""
    output_path = os.path.join(OUTPUT_DIR, output_name)
    cmd = [
        "C:/Users/wxy/AppData/Roaming/npm/mmdc.cmd",
        "-i", input_path,
        "-o", output_path,
        "-w", str(width),
        "-H", str(height),
        "-b", BG,
        "-t", THEME,
        "-s", "2",
    ]
    print(f"  渲染: {output_name} ...", end=" ")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, shell=False)
        if result.returncode == 0:
            size = os.path.getsize(output_path)
            print(f"OK ({size:,} bytes)")
            return output_path
        else:
            print(f"FAIL: {result.stderr.strip()[:200]}")
            return None
    except FileNotFoundError:
        print("FAIL: mmdc not found. Install with: npm i -g @mermaid-js/mermaid-cli")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("FAIL: timeout")
        return None


def write_mmd(filename, content):
    """写入 .mmd 文件"""
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


# ═══════════════════════════════════════════════════════════
#  甘特图
# ═══════════════════════════════════════════════════════════
def make_gantt():
    content = """gantt
    title FireGuard 项目甘特图 (2026.07.06 ~ 07.14)
    dateFormat YYYY-MM-DD
    axisFormat %m/%d
    tickInterval 1day

    section 魏贤炀  64 commits
    项目初始化 ROS导入 小车环境搭建    :done,    wx0, 2026-07-06, 2d
    YOLOv5烟火检测 车牌识别 AI复核     :done,    wx1, 2026-07-07, 3d
    语音助手 ASR-LLM-TTS Agent控制    :done,    wx2, 2026-07-09, 3d
    视觉LLM接入 检测Demo 视频录制       :done,    wx3, 2026-07-11, 2d
    进度协调 风险管理 答辩准备         :active,  wx4, 2026-07-13, 2d

    section 曹晋豪  20 commits
    REST API服务 车端ROS2配置部署     :done,    cj1, 2026-07-06, 3d
    传感器驱动 启动脚本 摄像头对接     :done,    cj2, 2026-07-08, 2d
    多车协调器编队 地图导航 音频模块   :done,    cj3, 2026-07-10, 3d
    系统联调 SLAM导航 容器适配         :active,  cj4, 2026-07-13, 2d

    section 张佳炅  4 commits 中期计划SLAM/ROS2
    车端ROS2基础配置 环境建模准备       :done,    zj0, 2026-07-06, 2d
    人脸识别注册 Django 百度API       :done,    zj1, 2026-07-07, 3d
    1比N识别 摄像头视频流连接测试      :done,    zj2, 2026-07-10, 2d
    答辩演示准备 文档完善              :active,  zj3, 2026-07-12, 3d

    section 朱宇帆  26 commits
    需求拆解 项目文档初始化            :done,    zy0, 2026-07-06, 2d
    云平台后端 CloudAlarmService     :done,    zy1, 2026-07-07, 3d
    云平台前端 Vite React Tailwind   :done,    zy2, 2026-07-09, 3d
    Docker CI/CD 鸿蒙APP改造          :done,    zy3, 2026-07-11, 2d
    模块设计图 PPT维护                :active,  zy4, 2026-07-13, 2d

    section 李沐宸  21 commits  dev分支
    Flutter APP初始化 UI设计 页面重构  :done,    lm1, 2026-07-06, 3d
    手动遥控界面 车队编队 TCP通信      :done,    lm2, 2026-07-08, 3d
    3D模型 图标系统 动态交互开发       :done,    lm3, 2026-07-11, 2d
    Android构建 原型同步 文档完善       :active,  lm4, 2026-07-13, 2d
"""

    path = write_mmd("gantt.mmd", content)
    mmdc_render(path, "01_甘特图.png", width=1600, height=700)
# ═══════════════════════════════════════════════════════════
#  里程碑图 (Timeline)
# ═══════════════════════════════════════════════════════════
def make_timeline():
    """里程碑图 — 使用 flowchart subgraph 布局，文字自动换行不超框"""
    content = """%%{init: {'theme': 'default', 'flowchart': {'nodeSpacing': 15, 'rankSpacing': 50}}}%%
flowchart LR
    subgraph M1["M1 基础环境搭建<br/>7/6 ~ 7/7 · 9 commits"]
        direction TB
        m1a["仓库初始化<br/>小车代码导入"]
        m1b["底盘·摄像头<br/>SLAM就绪"]
        m1c["AGENTS.md<br/>使用指南"]
    end

    subgraph M2["M2 服务化与初始开发<br/>7/8 ~ 7/9 · 7 commits"]
        direction TB
        m2a["REST API<br/>服务器上线"]
        m2b["9种传感器<br/>驱动就绪"]
        m2c["Docker CI/CD<br/>鸿蒙APP初始化"]
    end

    subgraph M3["M3 核心模块开发<br/>7/10 ~ 7/11 · 24 commits"]
        direction TB
        m3a["YOLOv5烟火<br/>车牌检测迁移"]
        m3b["检测器Demo<br/>答辩演示准备"]
        m3c["地图导航<br/>功能实现"]
    end

    subgraph M4["M4 多模块全面开发<br/>7/12 · 41 commits"]
        direction TB
        m4a["AI复核<br/>状态机+告警"]
        m4b["人脸识别<br/>注册+1:N"]
        m4c["多车协调器<br/>编队+碰撞"]
    end

    subgraph M5["M5 全栈联调与集成<br/>7/13 · 52 commits"]
        direction TB
        m5a["语音助手全链路<br/>ASR-LLM-TTS"]
        m5b["鸿蒙APP迭代<br/>云平台上线"]
        m5c["RAG知识库<br/>3D模型+文档"]
    end

    subgraph M6["M6 答辩交付准备<br/>7/14"]
        direction TB
        m6a["巡检闭环联调<br/>演示视频录制"]
        m6b["最终PPT<br/>需求分析报告"]
        m6c["测试报告+日报<br/>稳定镜像+回滚"]
    end

    M1 --> M2 --> M3 --> M4 --> M5 --> M6

    style M1 fill:#e8f5e9,stroke:#34a853,stroke-width:2px,color:#202124
    style M2 fill:#e8f5e9,stroke:#34a853,stroke-width:2px,color:#202124
    style M3 fill:#e8f5e9,stroke:#34a853,stroke-width:2px,color:#202124
    style M4 fill:#e8f5e9,stroke:#34a853,stroke-width:2px,color:#202124
    style M5 fill:#fff3e0,stroke:#fbbc04,stroke-width:2px,color:#202124
    style M6 fill:#fce8e6,stroke:#ea4335,stroke-width:2px,color:#202124
"""

    path = write_mmd("timeline.mmd", content)
    mmdc_render(path, "02_里程碑图.png", width=2200, height=900)


# ═══════════════════════════════════════════════════════════
#  燃尽图 (XYChart)
# ═══════════════════════════════════════════════════════════
def make_burndown():
    content = """---
config:
    xychart:
        width: 1400
        height: 500
---
xychart-beta
    title "FireGuard 燃尽图 — 135 任务点 × 8 天"
    x-axis ["7/6", "7/7", "7/8", "7/9", "7/10", "7/11", "7/12", "7/13", "7/14"]
    y-axis "剩余任务点" 0 --> 140
    line [133, 118, 104, 93, 78, 58, 35, 18, 0]
    line [133, 116, 100, 83, 67, 50, 33, 17, 0]
"""
    path = write_mmd("burndown.mmd", content)
    mmdc_render(path, "03_燃尽图.png", width=1600, height=600)


# ═══════════════════════════════════════════════════════════
#  贡献饼图 (Pie)
# ═══════════════════════════════════════════════════════════
def make_pie():
    content = """pie showData
    title FireGuard 提交贡献分布 (135 commits 含dev分支)
    "魏贤炀" : 64
    "朱宇帆" : 26
    "李沐宸" : 21
    "曹晋豪" : 20
    "张佳炅" : 4
"""
    path = write_mmd("pie.mmd", content)
    mmdc_render(path, "04_贡献度饼图.png", width=1000, height=600)


# ═══════════════════════════════════════════════════════════
#  ER图
# ═══════════════════════════════════════════════════════════
def make_er():
    content = """erDiagram
    alarm_event ||--o{ alarm_evidence : "产生"
    alarm_event ||--o{ alarm_review : "触发"
    alarm_event }o--|| inspection_robot : "上报来源"

    alarm_event {
        int id PK "自增主键"
        varchar event_id UK "事件UUID"
        varchar alarm_type "fire/smoke/obstacle"
        text alarm_message "告警描述"
        varchar device_sn "设备序列号"
        varchar status "PENDING/CONFIRMED/RESOLVED"
        text position "GPS/坐标JSON"
        datetime created_at "创建时间"
        datetime updated_at "更新时间"
    }

    alarm_evidence {
        int id PK "自增主键"
        varchar event_id FK "关联告警事件"
        varchar evidence_type "image/video/log"
        varchar file_path "证据文件路径"
        datetime captured_at "采集时间"
    }

    alarm_review {
        int id PK "自增主键"
        varchar event_id FK "关联告警事件"
        varchar reviewer "AI/Manual"
        varchar decision "FIRE/NO_FIRE/UNCERTAIN"
        float confidence "置信度0~1"
        text detail "复核详情JSON"
        datetime reviewed_at "复核时间"
    }

    inspection_robot {
        int id PK "自增主键"
        varchar device_sn UK "设备序列号"
        varchar name "设备名称"
        varchar status "ONLINE/OFFLINE/CHARGING"
        json config "巡检配置JSON"
        datetime last_heartbeat "最后心跳"
    }
"""
    path = write_mmd("er.mmd", content)
    mmdc_render(path, "05_ER图.png", width=1400, height=800)


# ═══════════════════════════════════════════════════════════
#  数据模型类图
# ═══════════════════════════════════════════════════════════
def make_class():
    content = """classDiagram
    class AlarmEvent {
        +int id
        +string event_id
        +string alarm_type
        +string alarm_message
        +string device_sn
        +string status
        +JSON position
        +datetime created_at
        +datetime updated_at
        +confirm()
        +resolve()
        +add_evidence()
    }

    class AlarmEvidence {
        +int id
        +string event_id
        +string evidence_type
        +string file_path
        +datetime captured_at
        +upload()
        +rotate(max_count)
    }

    class AlarmReview {
        +int id
        +string event_id
        +string reviewer
        +string decision
        +float confidence
        +JSON detail
        +datetime reviewed_at
        +run_ai_review()
        +request_manual()
    }

    class SensorFrame {
        +uint8 header
        +uint8 node_id
        +uint8 sensor_type
        +uint16 value
        +uint8 checksum
        +parse(buffer)
        +validate()
    }

    class SensorReading {
        +string sensor_type
        +float value
        +string unit
        +datetime timestamp
        +to_json()
    }

    class FireDetectConfig {
        +float conf_threshold
        +float trigger_window_sec
        +int trigger_min_hits
        +float ai_timeout_sec
        +int ai_retries
        +int review_interval_sec
        +int evidence_interval_sec
        +int max_evidence_images
        +from_env()
    }

    class RobotState {
        +string status
        +float battery
        +JSON position
        +string motion
        +datetime last_update
        +to_dict()
    }

    class VoiceCommand {
        +string command
        +string target
        +int speed
        +int duration_ms
        +bool emergency
        +parse(text)
    }

    class CloudAlarm {
        +string event_id
        +string device_sn
        +JSON payload
        +int retry_count
        +int max_retries
        +send()
        +enqueue_offline()
    }

    AlarmEvent "1" --> "*" AlarmEvidence : produces
    AlarmEvent "1" --> "*" AlarmReview : triggers
    SensorFrame "1" --> "1" SensorReading : parses
    FireDetectConfig --> AlarmEvent : configures
    RobotState --> CloudAlarm : reports
    VoiceCommand --> RobotState : controls
"""
    path = write_mmd("class.mmd", content)
    mmdc_render(path, "06_数据模型类图.png", width=1600, height=1000)


# ═══════════════════════════════════════════════════════════
#  数据流图 (Flowchart)
# ═══════════════════════════════════════════════════════════
def make_dataflow():
    content = """flowchart LR
    subgraph 车端["小车端 (Jetson Orin Nano)"]
        SENSOR["传感器层<br/>9种IoT传感器<br/>温湿烟PM2.5等"]
        CAMERA["摄像头<br/>奥比中光<br/>深度相机"]
        LIDAR["激光雷达<br/>RPLIDAR A1<br/>360°扫描"]
        CHASSIS["底盘<br/>麦克纳姆轮<br/>AT32 MCU"]
        MIC["麦克风<br/>语音输入"]

        SENSOR_READER["sensor_reader<br/>串口解析<br/>6字节帧"]
        FIRE_DETECT["detect.py<br/>YOLOv5<br/>烟火检测"]
        AI_REVIEW["AI复核<br/>状态机<br/>二次确认"]
        API_SERVER["api_server.py<br/>Flask REST<br/>主控服务"]
        VOICE["voice_control<br/>ASR→LLM→TTS<br/>语音助手"]
        NAV["navigation<br/>SLAM<br/>路径规划"]
        APP_CAR["鸿蒙APP<br/>远程遥控"]

        SENSOR -->|"/dev/ttyUSB2"| SENSOR_READER
        CAMERA -->|"/dev/video0"| FIRE_DETECT
        MIC --> VOICE
        FIRE_DETECT -->|"检测结果"| AI_REVIEW
        AI_REVIEW -->|"告警决策"| API_SERVER
        SENSOR_READER -->|"环境数据"| API_SERVER
        VOICE -->|"语音命令"| API_SERVER
        NAV -->|"位姿/路径"| API_SERVER
        APP_CAR -->|"TCP :6000"| API_SERVER
        API_SERVER -->|"控制指令"| CHASSIS
        LIDAR --> NAV
    end

    subgraph 云端["云平台 (8.140.28.233)"]
        CLOUD_API["接收API<br/>gunicorn :8000<br/>Bearer Auth"]
        MYSQL[("MySQL<br/>dev_fireguard<br/>告警+证据")]
        REACT["React前端<br/>监控面板"]
        NEO4J[("Neo4j<br/>RAG知识库<br/>文档检索")]

        CLOUD_API --> MYSQL
        MYSQL --> REACT
        REACT --> NEO4J
    end

    API_SERVER -->|"HTTP POST /alarm<br/>离线outbox队列"| CLOUD_API
"""
    path = write_mmd("dataflow.mmd", content)
    mmdc_render(path, "07_数据流图.png", width=1800, height=900)


# ═══════════════════════════════════════════════════════════
#  告警状态图
# ═══════════════════════════════════════════════════════════
def make_state():
    content = """stateDiagram-v2
    [*] --> IDLE: 系统启动

    IDLE --> DETECTING: 巡检开始
    DETECTING --> IDLE: 巡检结束

    DETECTING --> TRIGGERED: 置信度>=0.70<br/>2秒窗口>=5次
    TRIGGERED --> DETECTING: 误触发<br/>auto_clear(10s)

    TRIGGERED --> AI_REVIEWING: 触发AI复核
    AI_REVIEWING --> FIRE_CONFIRMED: AI判定为火灾

    AI_REVIEWING --> NO_FIRE: AI判定非火灾
    NO_FIRE --> DETECTING: 复审间隔30s后恢复

    AI_REVIEWING --> AI_FAILED: AI复核超时(30s)<br/>重试3次后失败
    AI_FAILED --> MANUAL_PENDING: 转人工审核

    FIRE_CONFIRMED --> ALARMING: 推送告警
    ALARMING --> ALARMING: 每60s采集证据<br/>最多10张轮转

    ALARMING --> MANUAL_CONFIRM: 人工确认火情
    MANUAL_CONFIRM --> RESOLVED: 火情消除

    ALARMING --> MANUAL_DISMISS: 人工解除误报
    MANUAL_DISMISS --> IDLE: 重置状态

    RESOLVED --> [*]: 事件归档

    note right of TRIGGERED
        临界区: 状态标记ALARMED
        但上报可能失败 → 离线队列
    end note

    note right of AI_FAILED
        Known Risk:
        AI Worker无心跳监控
        需人工兜底
    end note
"""
    path = write_mmd("state.mmd", content)
    mmdc_render(path, "09_告警生命周期状态图.png", width=1400, height=900)


# ═══════════════════════════════════════════════════════════
#  传感器帧结构图 (Block Diagram)
# ═══════════════════════════════════════════════════════════
def make_frame():
    content = """block-beta
    columns 6
    block:frame:6
        columns 6
        header["0xA5"] value16["uint16 Value"] chk["Checksum"]
        space node["Node ID"] type["Type"]
    end
    space:6
    block:byte0:1
        columns 1
        b0["Byte 0\\nHeader\\n固定 0xA5"]
    end
    space
    block:byte1:1
        columns 1
        b1["Byte 1\\nNode ID\\n0x01-0xFF"]
    end
    space
    block:byte2:1
        columns 1
        b2["Byte 2\\nType\\n0x01-0x09"]
    end
    space
    block:byte34:2
        columns 2
        b3["Byte 3\\nValue[15:8]"]
        b4["Byte 4\\nValue[7:0]"]
    end
    space
    block:byte5:1
        columns 1
        b5["Byte 5\\nChecksum\\n前5字节求和%256"]
    end

    frame --> byte0
    frame --> byte1
    frame --> byte2
    frame --> byte34
    frame --> byte5
"""
    path = write_mmd("frame.mmd", content)
    mmdc_render(path, "08_传感器帧结构图.png", width=1200, height=500)


# ═══════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  FireGuard Mermaid 图表生成器")
    print("  使用 mmdc (mermaid-cli) 渲染")
    print("=" * 60)
    print()

    make_gantt()
    make_timeline()
    make_burndown()
    make_pie()
    make_er()
    make_class()
    make_dataflow()
    make_frame()
    make_state()

    print()
    print(f"所有图表已输出到: {OUTPUT_DIR}")
    for f in sorted(os.listdir(OUTPUT_DIR)):
        if f.endswith(".png"):
            size = os.path.getsize(os.path.join(OUTPUT_DIR, f))
            print(f"  {f} ({size:,} bytes)")
    print()
    print("完成！可直接插入答辩PPT。")
