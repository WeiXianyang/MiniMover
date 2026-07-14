#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FireGuard 数据模型图表生成器 (纯 Matplotlib 版)
===============================================
生成业界标准的：
  1. ER 图 (Entity-Relationship Diagram)
  2. 数据模型类图 (Data Model Class Diagram)
  3. 数据流图 (Data Flow Diagram)
  4. 传感器数据帧结构图 (Sensor Frame Diagram)
  5. 告警生命周期状态图 (Alarm Lifecycle State Diagram)

用法: python generate_data_models.py
输出: charts/ 目录下的五张高清 PNG 图片
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Arc
import matplotlib.lines as mlines
import numpy as np
import os

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "charts")
os.makedirs(OUTPUT_DIR, exist_ok=True)

plt.rcParams.update({
    "font.family": "Microsoft YaHei",
    "font.size": 9,
    "axes.unicode_minus": False,
    "figure.dpi": 150,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.2,
})

# ── 配色 ──
C = {
    "primary":   "#1a73e8",
    "danger":    "#ea4335",
    "success":   "#34a853",
    "warn":      "#fbbc04",
    "ai":        "#9334e6",
    "grid":      "#dadce0",
    "text":      "#202124",
    "text_l":    "#5f6368",
    "bg":        "#ffffff",
    "table_hdr": {"MySQL": "#ea4335", "Evidence": "#34a853", "Outbox": "#fbbc04",
                  "Car": "#1a73e8", "Detection": "#34a853", "Event": "#ea4335",
                  "AI": "#9334e6", "Alarm": "#fbbc04", "IO": "#1a73e8",
                  "Sensor": "#34a853", "Voice": "#9334e6"},
}


# ═══════════════════════════════════════════════════════════════
#  Helper: draw a titled table box
# ═══════════════════════════════════════════════════════════════
def draw_table_box(ax, x, y, w, h, title, rows, title_color="#1a73e8"):
    """Draw a professional table entity box."""
    # Shadow
    shadow = FancyBboxPatch((x+0.02, y-0.02), w, h,
                            boxstyle="round,pad=0.08", facecolor="#e8eaed",
                            edgecolor="none", zorder=1)
    ax.add_patch(shadow)

    # Main box
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                          facecolor="white", edgecolor=title_color,
                          linewidth=1.8, zorder=2)
    ax.add_patch(box)

    # Title bar
    title_h = 0.25
    title_bar = FancyBboxPatch((x, y+h-title_h), w, title_h,
                                boxstyle="round,pad=0.04",
                                facecolor=title_color, edgecolor=title_color,
                                linewidth=1, zorder=3)
    ax.add_patch(title_bar)
    ax.text(x + w/2, y + h - title_h/2, title, ha="center", va="center",
            fontsize=9, fontweight="bold", color="white", zorder=4)

    # Rows
    row_h = 0.16
    start_y = y + h - title_h - row_h
    row_color_alt = ["#ffffff", "#f8f9fa"]
    for i, (field, ftype, note) in enumerate(rows):
        ri = i % 2
        rx, ry = x, start_y - i * row_h
        is_pk = field.startswith("🔑")
        is_fk = field.startswith("🔗")
        display_field = field[2:] if is_pk or is_fk else field

        # Row bg
        row_bg = FancyBboxPatch((rx, ry), w, row_h,
                                 boxstyle="round,pad=0.02",
                                 facecolor=row_color_alt[ri],
                                 edgecolor="#e8eaed", linewidth=0.3, zorder=3)
        ax.add_patch(row_bg)

        field_color = C["text"]
        if is_pk:
            ax.text(rx + 0.05, ry + row_h/2, f"🔑{display_field}", ha="left", va="center",
                    fontsize=7.5, fontweight="bold", color="#e65100", zorder=4)
        elif is_fk:
            ax.text(rx + 0.05, ry + row_h/2, f"🔗{display_field}", ha="left", va="center",
                    fontsize=7.5, fontweight="bold", color=C["primary"], zorder=4)
        else:
            ax.text(rx + 0.05, ry + row_h/2, display_field, ha="left", va="center",
                    fontsize=7.5, color=C["text"], zorder=4)

        ax.text(rx + w*0.52, ry + row_h/2, ftype, ha="left", va="center",
                fontsize=6.8, color=C["text_l"], zorder=4)
        ax.text(rx + w*0.85, ry + row_h/2, note, ha="left", va="center",
                fontsize=6.2, color=C["text_l"], style="italic", zorder=4)

    return x, y, w, h


def draw_arrow(ax, x1, y1, x2, y2, label="", color="#5f6368", style="-", lw=1.5):
    """Draw a connection arrow between two points."""
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color, lw=lw,
                                linestyle=style, connectionstyle="arc3,rad=0"),
                zorder=10)
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx, my+0.02, label, ha="center", va="bottom",
                fontsize=7, color=color, zorder=11,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                          edgecolor="#e0e0e0", alpha=0.9))


# ═══════════════════════════════════════════════════════════════
#  1. ER 图
# ═══════════════════════════════════════════════════════════════
def draw_er():
    fig, ax = plt.subplots(figsize=(22, 12))
    ax.set_xlim(0, 22)
    ax.set_ylim(0, 12)
    ax.axis("off")
    ax.set_facecolor(C["bg"])

    # fire_alarm (center)
    fire_alarm = [
        ("🔑 id",                "BIGINT AUTO_INCREMENT",  "PK"),
        ("event_id",             "VARCHAR(64) NOT NULL",   "UNIQUE(联合)"),
        ("alarm_type",           "VARCHAR(32) NOT NULL",   "UNIQUE(联合)"),
        ("occurred_at",          "DATETIME(6) NOT NULL",   "INDEXED"),
        ("reason",               "VARCHAR(300) NULL",      "AI复核原因"),
        ("confidence",           "DECIMAL(4,3) NULL",      "0.000-1.000"),
        ("evidence_url",         "VARCHAR(500) NULL",      "证据图片 URL"),
        ("detection_classes",    "VARCHAR(200) NULL",      "逗号分隔"),
        ("max_confidence",       "DECIMAL(4,3) NULL",      "YOLO置信度"),
        ("local_detection_gone", "TINYINT(1) NULL",        "本地检测消失"),
        ("car_id",               "VARCHAR(64) NULL",       "INDEXED FK"),
        ("received_at",          "DATETIME(6) NOT NULL",   "云端入库时间"),
        ("raw_payload",          "JSON NULL",              "原始上报存档"),
    ]
    draw_table_box(ax, 8.0, 4.5, 5.5, 2.55, "fire_alarm (MySQL)", fire_alarm, C["danger"])

    # evidence (left)
    evidence = [
        ("🔑 file_path",     "VARCHAR(500)",          "相对路径"),
        ("event_id",         "VARCHAR(64) NOT NULL",  "FK→fire_alarm"),
        ("review_id",        "INT",                   "复核序号"),
        ("capture_type",     "VARCHAR(16)",           "initial|review|periodic"),
        ("captured_at",      "DATETIME(6)",           "抓拍时刻"),
        ("local_detection",  "JSON",                  "YOLO命中详情"),
        ("ai_review",        "JSON",                  "AI复核结果"),
        ("file_size",        "INT",                   "JPEG字节数"),
    ]
    draw_table_box(ax, 1.0, 5.0, 5.0, 1.75, "Evidence (文件系统)", evidence, C["success"])

    # outbox (right)
    outbox = [
        ("🔑 event_id",      "VARCHAR(64)",           "事件ID"),
        ("alarm_type",       "VARCHAR(32)",           "告警类型"),
        ("occurred_at",      "DATETIME(6)",           "发生时间"),
        ("confidence",       "DECIMAL(4,3)",          "AI置信度"),
        ("car_id",           "VARCHAR(64)",           "车辆标识"),
        ("attempts",         "INT DEFAULT 0",         "重试次数"),
        ("first_try",        "DATETIME(6)",           "首次尝试"),
        ("last_attempt",     "DATETIME(6)",           "末次尝试"),
    ]
    draw_table_box(ax, 15.5, 5.5, 5.0, 1.75, "OutboxQueue (JSONL)", outbox, C["warn"])

    # car (bottom center)
    car = [
        ("🔑 car_id",        "VARCHAR(64)",           "唯一标识"),
        ("car_ip",           "VARCHAR(45)",           "IP地址"),
        ("status",           "VARCHAR(16)",           "online|timeout|offline"),
        ("battery",          "FLOAT",                 "电压(V)"),
        ("position",         "JSON {x,y,theta}",      "位姿"),
        ("last_seen",        "DATETIME(6)",           "最后心跳"),
        ("registered_at",    "DATETIME(6)",           "注册时间"),
    ]
    draw_table_box(ax, 8.0, 1.0, 5.5, 1.6, "Car (协调器注册)", car, C["primary"])

    # Relationships
    # fire_alarm → evidence (right-bottom to left)
    draw_arrow(ax, 10.75, 5.6, 6.0, 5.87, "  1:N 产生证据", C["success"], lw=2.0)
    # fire_alarm → outbox
    draw_arrow(ax, 13.5, 6.5, 15.5, 6.37, "  1:1 失败入队", C["warn"], "--", lw=1.8)
    # car → fire_alarm
    draw_arrow(ax, 10.75, 2.6, 10.75, 4.5, "  1:N 产生告警", C["primary"], lw=2.0)

    # Legend
    legend_x, legend_y = 1.0, 1.0
    ax.add_patch(FancyBboxPatch((legend_x, legend_y), 5.5, 1.3,
                                 boxstyle="round,pad=0.1", facecolor="#f8f9fa",
                                 edgecolor=C["grid"], linewidth=1, zorder=5))
    ax.plot([legend_x+0.3, legend_x+1.1], [legend_y+1.05, legend_y+1.05], "-",
            color=C["success"], lw=2.5, zorder=6)
    ax.text(legend_x+1.2, legend_y+1.05, "实线 = 强关联", fontsize=8, va="center", color=C["text"])
    ax.plot([legend_x+0.3, legend_x+1.1], [legend_y+0.65, legend_y+0.65], "--",
            color=C["warn"], lw=2.5, zorder=6)
    ax.text(legend_x+1.2, legend_y+0.65, "虚线 = 异步队列", fontsize=8, va="center", color=C["text"])
    ax.plot([legend_x+0.3, legend_x+1.1], [legend_y+0.25, legend_y+0.25], ":",
            color=C["text_l"], lw=2.5, zorder=6)
    ax.text(legend_x+1.2, legend_y+0.25, "点线 = 文件系统", fontsize=8, va="center", color=C["text"])
    ax.text(legend_x+0.2, legend_y, " 图例", fontsize=8.5, fontweight="bold", va="bottom", color=C["text"], zorder=7)

    title = "FireGuard ER 图 — 数据库与持久化实体关系"
    ax.set_title(f"{title}\n基于 MySQL fire_alarm 表 + JSONL + 文件系统", fontsize=14,
                 fontweight="bold", color=C["text"], pad=16)

    path = os.path.join(OUTPUT_DIR, "05_ER图.png")
    fig.savefig(path, facecolor=C["bg"])
    plt.close(fig)
    print(f"✅ ER 图已保存: {path}")


# ═══════════════════════════════════════════════════════════════
#  2. 数据模型类图
# ═══════════════════════════════════════════════════════════════
def draw_class_diagram():
    fig, ax = plt.subplots(figsize=(24, 14))
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 14)
    ax.axis("off")
    ax.set_facecolor(C["bg"])

    # Detection (top-left)
    detection = [
        ("class_name",  "str",       "'fire' | 'smoke'"),
        ("confidence",  "float",     "0.0–1.0"),
    ]
    draw_table_box(ax, 1.0, 12.0, 4.8, 0.57, "Detection (YOLO检测)", detection, C["success"])

    # _Event (center-top)
    event = [
        ("🔑 event_id",  "str",      "唯一标识 fire_YYYYMMDD_..."),
        ("state",        "EventState","idle→ai_reviewing→alarmed"),
        ("review_id",    "int",      "当前复核序号"),
        ("last_hit",     "float",    "monotonic 最后命中时刻"),
        ("evidence_paths","Dict",    "review_id→路径映射"),
        ("in_flight",    "bool",     "AI请求在途"),
        ("local_detection_gone","bool","检测目标消失"),
        ("classes",      "tuple",    "命中类别"),
        ("max_confidence","float",   "YOLO最大置信度"),
    ]
    draw_table_box(ax, 9.5, 11.0, 5.5, 1.82, "_Event (状态机核心)", event, C["danger"])

    # AIReviewRequest
    ai_req = [
        ("event_id",     "str",      "事件ID"),
        ("review_id",    "int",      "递增序号"),
        ("jpeg_bytes",   "bytes",    "原始帧JPEG"),
        ("captured_at",  "datetime", "抓拍时刻"),
    ]
    draw_table_box(ax, 18.0, 12.0, 4.8, 0.9, "AIReviewRequest (AI)", ai_req, C["ai"])

    # AIReviewResult
    ai_res = [
        ("event_id",     "str",      "事件ID"),
        ("success",      "bool",     "是否成功"),
        ("attempts",     "int",      "尝试次数"),
        ("result",       "AIResultKind","confirmed_fire|smoke|no"),
        ("confidence",   "float|null","AI置信度"),
        ("reason",       "str|null", "≤300字原因"),
        ("error",        "str|null", "失败信息"),
    ]
    draw_table_box(ax, 18.0, 9.8, 4.8, 1.4, "AIReviewResult (AI)", ai_res, C["ai"])

    # AlarmEvent
    alarm = [
        ("event_id",     "str",      "事件ID"),
        ("alarm_type",   "str",      "confirmed_fire|suspected_smoke"),
        ("occurred_at",  "datetime", "发生时刻"),
        ("reason",       "str|null", "AI原因"),
        ("confidence",   "float|null","AI置信度"),
        ("evidence_path","str|null", "证据路径"),
    ]
    draw_table_box(ax, 9.5, 7.8, 5.5, 1.26, "AlarmEvent (告警数据)", alarm, C["warn"])

    # EvidencePair
    evidence = [
        ("event_id",     "str",      "事件ID"),
        ("capture_type", "str",      "initial|review|periodic"),
        ("captured_at",  "datetime", "抓拍时刻"),
        ("frame_jpeg",   "bytes",    "标注框JPEG"),
        ("metadata_json","JSON",     "元数据"),
    ]
    draw_table_box(ax, 1.0, 9.8, 4.8, 1.08, "EvidencePair (证据)", evidence, C["success"])

    # CarStatus
    car = [
        ("🔑 car_id",    "str",      "车辆标识"),
        ("car_ip",       "str",      "IP:端口"),
        ("battery",      "float",    "电压V"),
        ("position",     "{x,y,theta}","位姿"),
        ("status",       "str",      "online|timeout|offline"),
        ("collision",    "str|null", "WARNING|CRITICAL"),
    ]
    draw_table_box(ax, 1.0, 3.5, 4.8, 1.26, "CarStatus (车辆)", car, C["primary"])

    # VoiceCommand
    voice = [
        ("cmd",          "str",      "forward|backward|left|right|stop"),
        ("speed",        "int",      "0-100 (默认35)"),
        ("duration",     "float",    "秒 (默认0.8)"),
        ("verified",     "bool",     "声纹验证通过"),
        ("similarity",   "float",    "CAM++余弦相似度"),
    ]
    draw_table_box(ax, 1.0, 7.5, 4.8, 1.08, "VoiceCommand (语音)", voice, C["ai"])

    # SensorSnapshot
    sensor = [
        ("temperature",  "float",    "°C"),
        ("humidity",     "float",    "%"),
        ("smoke",        "int",      "原始值"),
        ("pm25",         "int",      "μg/m³"),
        ("co2",          "int",      "ppm"),
        ("gps",          "{lat,lon}","WGS84"),
    ]
    draw_table_box(ax, 1.0, 5.7, 4.8, 1.26, "SensorSnapshot (IoT)", sensor, C["success"])

    # Arrows — data flow between entities
    draw_arrow(ax, 5.8, 12.3, 9.5, 12.3, "N:1 命中累计", C["success"], lw=1.5)
    draw_arrow(ax, 15.0, 12.0, 18.0, 12.45, "1:1 触发复核", C["ai"], lw=1.5)
    draw_arrow(ax, 20.4, 11.5, 20.4, 11.2, "1:1 API调用", C["ai"], lw=1.5)
    draw_arrow(ax, 17.5, 10.5, 15.0, 11.5, "1:1 状态转换", C["danger"], lw=1.5)
    draw_arrow(ax, 12.0, 10.95, 12.0, 9.56, "1:1 产生告警", C["warn"], lw=1.5)
    draw_arrow(ax, 9.0, 11.0, 5.8, 10.3, "1:N 证据采集", C["success"], lw=1.5)

    title = "FireGuard 数据模型类图 — 核心数据结构与字段"
    ax.set_title(f"{title}\ntypes.py · event_manager.py · icar_sensor_driver.py", fontsize=14,
                 fontweight="bold", color=C["text"], pad=16)

    path = os.path.join(OUTPUT_DIR, "06_数据模型类图.png")
    fig.savefig(path, facecolor=C["bg"])
    plt.close(fig)
    print(f"✅ 数据模型类图已保存: {path}")


# ═══════════════════════════════════════════════════════════════
#  3. 数据流图 (DFD)
# ═══════════════════════════════════════════════════════════════
def draw_dataflow():
    fig, ax = plt.subplots(figsize=(24, 16))
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 16)
    ax.axis("off")
    ax.set_facecolor(C["bg"])

    def draw_component(x, y, w, h, label, color, icon=""):
        """Draw a system component box."""
        b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                            facecolor=color, edgecolor=color, linewidth=1.5,
                            alpha=0.12, zorder=2)
        ax.add_patch(b)
        b2 = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                             facecolor="none", edgecolor=color, linewidth=2.5,
                             zorder=3)
        ax.add_patch(b2)
        ax.text(x+w/2, y+h/2, f"{icon} {label}", ha="center", va="center",
                fontsize=9.5, fontweight="bold", color=color, zorder=4)
        return x, y, w, h

    def draw_store(x, y, w, h, label, color):
        """Draw a data store (cylinder-like)."""
        b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                            facecolor=color, edgecolor=color, linewidth=2.0,
                            alpha=0.65, zorder=2)
        ax.add_patch(b)
        ax.text(x+w/2, y+h/2, label, ha="center", va="center",
                fontsize=8.5, fontweight="bold", color="white", zorder=3)
        return x, y, w, h

    # Layer labels
    ax.text(0.3, 15.2, "物理层", fontsize=11, fontweight="bold", color=C["text"])
    ax.text(0.3, 10.8, "车端处理层 (Jetson Orin Nano)", fontsize=11, fontweight="bold", color=C["text"])
    ax.text(0.3, 5.5, "云端 & 协同层", fontsize=11, fontweight="bold", color=C["text"])

    # Separators
    for y_line in [14.8, 10.4, 5.1]:
        ax.axhline(y=y_line, color=C["grid"], linewidth=1, linestyle="--", zorder=1)

    # ── Physical Layer ──
    draw_component(1.0, 14.9, 3.5, 0.8, "深度相机", C["success"], "📷")
    draw_component(6.0, 14.9, 3.5, 0.8, "传感器模组 (9种)", C["success"], "🌡")
    draw_component(11.0, 14.9, 3.5, 0.8, "Rosmaster 底盘", C["primary"], "🚗")
    draw_component(16.0, 14.9, 3.5, 0.8, "麦克风/音箱", C["ai"], "🎤🔊")

    # ── Car Processing Layer ──
    draw_component(1.0, 10.6, 4.0, 0.9, "Flask API\n:5000", C["primary"], "🌐")
    draw_component(7.0, 10.6, 3.5, 0.9, "YOLOv5\n烟火检测", C["success"], "🔥")
    draw_component(12.0, 10.6, 4.0, 0.9, "FireEventManager\n状态机", C["danger"], "⚙")
    draw_component(17.5, 10.6, 3.0, 0.9, "AIReviewer\nGPT复核", C["ai"], "🧠")

    # Stores in car layer
    draw_store(7.0, 8.3, 3.5, 0.7, "Evidence JPEG+JSON", C["success"])
    draw_store(12.0, 8.3, 3.5, 0.7, "outbox.jsonl", C["warn"])
    draw_store(17.0, 8.3, 3.0, 0.7, "alarms.jsonl", C["warn"])

    # ── Cloud & External Layer ──
    draw_component(1.0, 5.8, 4.0, 0.9, "多车协同\nCoordinator :8888", C["primary"], "🚗🚗")
    draw_component(7.0, 5.8, 4.0, 0.9, "云端 API\n:8000", C["danger"], "☁")
    draw_store(13.0, 5.8, 3.5, 0.9, "MySQL fire_alarm", C["danger"])
    draw_component(17.5, 5.8, 3.0, 0.9, "OpenAI\nGPT Vision", C["ai"], "🔮")

    # ── User Layer ──
    draw_component(7.0, 3.5, 4.0, 0.9, "Web 前端\nReact+TS", C["warn"], "🖥")
    draw_component(13.0, 3.5, 3.5, 0.9, "语音助手\nVoiceService", C["ai"], "🎙")

    # ── Data Flow Arrows ──
    # Physical → Car
    draw_arrow(ax, 2.75, 14.9, 3.0, 11.5, "MJPEG帧", C["success"], lw=1.2)
    draw_arrow(ax, 7.75, 14.9, 8.0, 11.5, "6字节帧\n0xA5...", C["success"], lw=1.2)
    draw_arrow(ax, 13.0, 14.9, 13.5, 11.5, "运动指令", C["primary"], lw=1.2)
    draw_arrow(ax, 17.5, 11.8, 17.5, 14.9, "PCM 16kHz", C["ai"], lw=1.2)

    # Car internal
    draw_arrow(ax, 8.75, 11.05, 12.0, 11.05, "Detection[]", C["success"], lw=1.5)
    draw_arrow(ax, 14.0, 11.5, 17.5, 11.5, "AIReviewRequest", C["ai"], lw=1.5)

    # Evidence flow
    draw_arrow(ax, 12.0, 10.0, 8.75, 9.0, "标注帧+元数据", C["success"], lw=1.2)
    draw_arrow(ax, 14.0, 9.8, 14.0, 9.0, "AlarmEvent", C["warn"], lw=1.2)

    # Cloud upload
    draw_arrow(ax, 14.0, 8.3, 9.0, 6.7, "证据JPEG+告警JSON", C["warn"], lw=1.5)
    draw_arrow(ax, 9.0, 5.8, 13.0, 6.3, "INSERT\n幂等", C["danger"], lw=1.5)
    draw_arrow(ax, 11.0, 5.8, 12.0, 4.4, "Alarm[] JSON", C["warn"], lw=1.5)

    # Multi-car
    draw_arrow(ax, 3.0, 10.6, 3.0, 6.7, "GET /api/status\n每5s轮询", C["primary"], lw=1.2)
    draw_arrow(ax, 5.0, 6.2, 3.0, 11.0, "POST /api/move", C["primary"], "--", lw=1.2)

    # Voice
    draw_arrow(ax, 14.75, 4.4, 3.0, 11.0, "POST /api/move\n语音命令", C["ai"], lw=1.2)

    title = "FireGuard 数据流图 (DFD) — 组件间数据交换"
    ax.set_title(f"{title}\n物理层 → 车端处理 → 云端 & 协同", fontsize=14,
                 fontweight="bold", color=C["text"], pad=16)

    path = os.path.join(OUTPUT_DIR, "07_数据流图.png")
    fig.savefig(path, facecolor=C["bg"])
    plt.close(fig)
    print(f"✅ 数据流图已保存: {path}")


# ═══════════════════════════════════════════════════════════════
#  4. 传感器数据帧结构图
# ═══════════════════════════════════════════════════════════════
def draw_sensor_frame():
    fig, ax = plt.subplots(figsize=(22, 10))
    ax.set_xlim(0, 22)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_facecolor(C["bg"])

    # 6 bytes layout
    byte_colors = ["#ea4335", "#1a73e8", "#1a73e8", "#34a853", "#34a853", "#fbbc04"]
    byte_labels = ["0xA5", "node", "type", "value[7:0]", "value[15:8]", "checksum"]
    byte_desc = ["帧头 (固定)", "节点号", "传感器类型码", "数值低字节", "数值高字节", "校验和"]

    for i in range(6):
        x = 1.0 + i * 3.3
        y = 7.0
        w, h = 2.8, 1.2

        # Byte box
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                              facecolor=byte_colors[i], edgecolor=byte_colors[i],
                              linewidth=2, alpha=0.15, zorder=3)
        ax.add_patch(box)
        box2 = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                               facecolor="none", edgecolor=byte_colors[i],
                               linewidth=2, zorder=4)
        ax.add_patch(box2)

        ax.text(x+w/2, y+h-0.22, byte_labels[i], ha="center", va="center",
                fontsize=14, fontweight="bold", color=byte_colors[i],
                fontfamily="Consolas", zorder=5)
        ax.text(x+w/2, y+0.2, byte_desc[i], ha="center", va="center",
                fontsize=7.5, color=C["text_l"], zorder=5)

        # Offset label
        ax.text(x+w/2, y+h+0.2, f"Byte {i}", ha="center", va="bottom",
                fontsize=8, fontweight="bold", color=C["text_l"], zorder=5)

    # Arrow between bytes
    for i in range(5):
        x1 = 1.0 + i * 3.3 + 2.8
        x2 = 1.0 + (i+1) * 3.3
        draw_arrow(ax, x1+0.1, 7.6, x2-0.1, 7.6, "", C["grid"], lw=1.0)

    # checksum formula
    formula_box = FancyBboxPatch((1.0, 4.5), 18.5, 1.2, boxstyle="round,pad=0.1",
                                  facecolor="#fff8e1", edgecolor=C["warn"], linewidth=1.5, zorder=3)
    ax.add_patch(formula_box)
    ax.text(10.25, 5.1, "checksum = (0xA5 + node + type + value[7:0] + value[15:8]) & 0xFF",
            ha="center", va="center", fontsize=12, fontfamily="Consolas", fontweight="bold",
            color="#e65100", zorder=4)
    ax.text(10.25, 4.7, "校验失败 → parse() 返回 None → 丢弃该帧",
            ha="center", va="center", fontsize=9, color=C["text_l"], zorder=4)

    # Sensor type code table
    sensor_types = [
        ("0x01  temperature (°C)",  "value / 10.0",  "263 → 26.3°C"),
        ("0x02  humidity (%)",      "value / 10.0",  "550 → 55.0%"),
        ("0x03  smoke",             "raw",           "0–65535"),
        ("0x04  pm25 (μg/m³)",      "raw",           "0–65535"),
        ("0x05  pressure (hPa)",    "raw",           "0–65535"),
        ("0x06  light (lux)",       "raw",           "0–65535"),
        ("0x07  GPS latitude (°)",  "float",         "拆分"),
        ("0x08  GPS longitude (°)", "float",         "拆分"),
        ("0x09  co2 (ppm)",         "raw",           "0–65535"),
    ]
    draw_table_box(ax, 1.0, 1.8, 6.5, 1.78, "传感器类型码 → 解析公式", sensor_types, C["success"])

    # Protocol details
    ax.text(10.0, 3.6, "串口协议", fontsize=10, fontweight="bold", color=C["text"])
    details = [
        ("接口:", "/dev/ttyUSB2"),
        ("波特率:", "115200 bps"),
        ("MCU:", "AT32 (ARM Cortex-M4)"),
        ("帧长:", "固定 6 字节"),
        ("帧头:", "0xA5"),
        ("字节序:", "Little-Endian"),
        ("间隔:", "连续发送"),
    ]
    for i, (k, v) in enumerate(details):
        ax.text(10.0, 3.2 - i * 0.28, f"{k} {v}", fontsize=8.5, color=C["text"], fontfamily="Consolas")

    title = "iCar 传感器串口数据帧结构 — 6 字节二进制协议"
    ax.set_title(f"{title}\n/dev/ttyUSB2 · 115200 baud · AT32 MCU", fontsize=14,
                 fontweight="bold", color=C["text"], pad=16)

    path = os.path.join(OUTPUT_DIR, "08_传感器帧结构图.png")
    fig.savefig(path, facecolor=C["bg"])
    plt.close(fig)
    print(f"✅ 传感器帧结构图已保存: {path}")


# ═══════════════════════════════════════════════════════════════
#  5. 告警生命周期状态图
# ═══════════════════════════════════════════════════════════════
def draw_alarm_lifecycle():
    fig, ax = plt.subplots(figsize=(22, 12))
    ax.set_xlim(0, 22)
    ax.set_ylim(0, 12)
    ax.axis("off")
    ax.set_facecolor(C["bg"])

    # State nodes — positions
    states = {
        "IDLE":        (1.5, 6.0, "IDLE\n空闲等待", C["success"]),
        "REVIEWING":   (7.5, 6.0, "AI_REVIEWING\nAI 复核中", C["primary"]),
        "ALARM_FIRE":  (13.5, 8.5, "ALARMED_FIRE\n🔥 明火告警", C["danger"]),
        "ALARM_SMOKE": (13.5, 5.5, "ALARMED_SMOKE\n💨 烟雾告警", C["warn"]),
        "REJECTED":    (13.5, 3.0, "AI_REJECTED\n❌ AI 否定", C["ai"]),
        "FAILED":      (19.0, 6.0, "AI_FAILED\n⚠ AI 失效", C["text_l"]),
    }

    state_w, state_h = 3.5, 1.5
    for sid, (sx, sy, slabel, scolor) in states.items():
        box = FancyBboxPatch((sx, sy), state_w, state_h, boxstyle="round,pad=0.1",
                              facecolor=scolor, edgecolor=scolor, linewidth=2.5,
                              alpha=0.12, zorder=3)
        ax.add_patch(box)
        box2 = FancyBboxPatch((sx, sy), state_w, state_h, boxstyle="round,pad=0.1",
                               facecolor="none", edgecolor=scolor, linewidth=2.5, zorder=4)
        ax.add_patch(box2)
        ax.text(sx+state_w/2, sy+state_h/2, slabel, ha="center", va="center",
                fontsize=9.5, fontweight="bold", color=scolor, zorder=5)

    # Transition arrows
    # IDLE → REVIEWING (trigger)
    draw_arrow(ax, 5.0, 6.75, 7.5, 6.75, "2s窗口内 ≥5次命中\nYOLO置信度 ≥0.70", C["primary"], lw=2.0)

    # REVIEWING → outcomes
    review_x, review_y = 11.0, 6.75
    draw_arrow(ax, review_x, review_y, 13.5, 9.25, "confirmed_fire", C["danger"], lw=2.0)
    draw_arrow(ax, review_x, review_y-0.5, 13.5, 6.1, "suspected_smoke", C["warn"], lw=2.0)
    draw_arrow(ax, review_x, review_y-1.5, 13.5, 3.6, "no_fire", C["ai"], lw=2.0)
    draw_arrow(ax, review_x+4, review_y+0.0, 19.0, 6.75, "全部失败\n(重试2次)", C["text_l"], lw=1.5, style="--")

    # Return to IDLE
    draw_arrow(ax, 15.5, 3.0, 5.0, 6.0, "30s后重新复审", C["ai"], lw=1.5, style="--")
    draw_arrow(ax, 15.5, 9.0, 3.25, 7.2, "YOLO目标消失 >10s\n且无 in_flight 任务", C["text_l"], lw=1.5, style="--")
    draw_arrow(ax, 19.0, 5.5, 5.0, 5.5, "人工介入后复位", C["text_l"], lw=1.5, style="--")

    # Action notes
    note_style = dict(boxstyle="round,pad=0.3", facecolor="#f8f9fa", edgecolor=C["grid"], alpha=0.9)

    ax.text(7.5, 10.5,
            "AI 复核动作:\n① 抓拍原始帧 JPEG (未画框)\n② Base64 编码\n③ 调用 OpenAI GPT Vision API\n④ 30s 超时, 失败立即重试 2 次",
            ha="center", va="top", fontsize=8, color=C["text_l"], bbox=note_style, zorder=6)

    ax.text(13.5, 11.2,
            "告警状态动作:\n→ AlarmService.trigger_alarm()\n→ 本地日志 alarms.jsonl\n→ 云端 HTTP POST 上报\n→ 每 60s 采集周期证据\n→ EvidenceStore 轮转 (≤10对)",
            ha="center", va="top", fontsize=8, color=C["text_l"], bbox=note_style, zorder=6)

    # Config table
    config_items = [
        ("YOLO置信度阈值",  "0.70"),
        ("触发窗口",       "2秒 / 5次命中"),
        ("AI请求超时",     "30秒 × 3次"),
        ("AI_REJECTED间隔","30秒"),
        ("周期证据间隔",   "60秒"),
        ("最大证据数",     "10张"),
        ("事件清除条件",   "目标消失 >10s"),
    ]
    for i, (k, v) in enumerate(config_items):
        ax.text(19.5, 11.0 - i*0.3, f"{k}:", fontsize=7.5, color=C["text_l"], ha="left")
        ax.text(22.0, 11.0 - i*0.3, v, fontsize=7.5, fontweight="bold", color=C["text"], ha="right")

    title = "FireGuard 烟火检测告警生命周期状态机"
    ax.set_title(f"{title}\nFireEventManager · 6 状态 × 4 转换路径", fontsize=14,
                 fontweight="bold", color=C["text"], pad=16)

    path = os.path.join(OUTPUT_DIR, "09_告警生命周期状态图.png")
    fig.savefig(path, facecolor=C["bg"])
    plt.close(fig)
    print(f"✅ 告警生命周期状态图已保存: {path}")


# ═══════════════════════════════════════════════════════════════
#  main
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  FireGuard 数据模型图表生成器 (Matplotlib)")
    print("  ER图 · 类图 · 数据流图 · 帧结构图 · 状态图")
    print("=" * 60)
    print()

    draw_er()
    draw_class_diagram()
    draw_dataflow()
    draw_sensor_frame()
    draw_alarm_lifecycle()

    print()
    print(f"📁 所有图表已输出到: {OUTPUT_DIR}")
    for f in sorted(os.listdir(OUTPUT_DIR)):
        if f.endswith(".png"):
            fsize = os.path.getsize(os.path.join(OUTPUT_DIR, f))
            print(f"   {f} ({fsize:,} bytes)")
    print()
    print("✅ 完成！可直接插入答辩PPT。")
