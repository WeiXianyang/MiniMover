#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FireGuard 项目图表生成器
========================
基于 GitHub 仓库 133 条提交记录，生成行业标准的：
  1. 甘特图 (Gantt Chart)  — 按成员分组的任务时间线
  2. 里程碑图 (Milestone Chart) — 关键节点与交付物
  3. 燃尽图 (Burndown Chart) — 理想 vs 实际进度

用法: python generate_charts.py
输出: charts/ 目录下的三张高清 PNG 图片
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from matplotlib.font_manager import FontProperties
import numpy as np
from datetime import datetime, timedelta
import os

# ── 全局配置 ──────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "charts")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 中文字体
CN_FONT = FontProperties(fname=None)
CN_FONT.set_family("Microsoft YaHei")

plt.rcParams.update({
    "font.family": "Microsoft YaHei",
    "font.size": 11,
    "axes.unicode_minus": False,
    "figure.dpi": 150,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.2,
})

# ── 全局配色 ──────────────────────────────────────────────
COLORS = {
    "primary":   "#1a73e8",
    "secondary": "#ea4335",
    "tertiary":  "#34a853",
    "quaternary":"#fbbc04",
    "member_魏贤炀": "#1a73e8",   # 蓝
    "member_张家炅": "#ea4335",   # 红
    "member_曹晋豪": "#34a853",   # 绿
    "member_朱宇帆": "#fbbc04",   # 黄
    "member_李沐宸": "#9334e6",   # 紫
    "milestone": "#ff6d01",
    "done":      "#34a853",
    "ongoing":   "#fbbc04",
    "pending":   "#dadce0",
    "ideal":     "#1a73e8",
    "actual":    "#ea4335",
    "grid":      "#e8eaed",
    "text":      "#202124",
    "text_light":"#5f6368",
    "bg":        "#ffffff",
}

# ── 时间轴配置 ────────────────────────────────────────────
START_DATE = datetime(2026, 7, 6)
END_DATE   = datetime(2026, 7, 14)


def date_to_num(d):
    """datetime → matplotlib ordinal"""
    return mdates.date2num(d)


def make_date(day):
    """7月 day 日 → datetime"""
    return datetime(2026, 7, day)


def date_label(d):
    """datetime → '7/6' 格式"""
    return f"{d.month}/{d.day}"


# ═══════════════════════════════════════════════════════════
#  任务数据（基于 GitHub 提交记录逐条追溯）
# ═══════════════════════════════════════════════════════════

TASKS = [
    # ── 魏贤炀 (A) ──
    {"member": "魏贤炀", "grade": "A", "task": "项目初始化",                       "s": 6,  "e": 6,  "color": COLORS["member_魏贤炀"]},
    {"member": "魏贤炀", "grade": "A", "task": "小车底盘代码导入 + AGENTS.md",      "s": 7,  "e": 7,  "color": COLORS["member_魏贤炀"]},
    {"member": "魏贤炀", "grade": "A", "task": "烟火检测模块迁移 (YOLOv5)",        "s": 11, "e": 11, "color": COLORS["member_魏贤炀"]},
    {"member": "魏贤炀", "grade": "A", "task": "三检测器答辩演示 (烟火+红绿灯+车牌)","s": 11, "e": 11, "color": COLORS["member_魏贤炀"]},
    {"member": "魏贤炀", "grade": "A", "task": "AI二次复核 (状态机+证据+告警)",      "s": 12, "e": 12, "color": COLORS["member_魏贤炀"]},
    {"member": "魏贤炀", "grade": "A", "task": "语音助手 (ASR+唤醒词+LLM+TTS)",     "s": 12, "e": 13, "color": COLORS["member_魏贤炀"]},
    {"member": "魏贤炀", "grade": "A", "task": "RAG知识库 + 中期答辩演讲稿",        "s": 12, "e": 12, "color": COLORS["member_魏贤炀"]},
    {"member": "魏贤炀", "grade": "A", "task": "TTS优化 (CosyVoice) + 部署修复",    "s": 13, "e": 13, "color": COLORS["member_魏贤炀"]},
    {"member": "魏贤炀", "grade": "A", "task": "PR审查合并 (×5) + 需求分析报告",    "s": 13, "e": 14, "color": COLORS["member_魏贤炀"]},

    # ── 张家炅 (A) ──
    {"member": "张家炅", "grade": "A", "task": "SLAM建图 + Nav2导航配置",          "s": 7,  "e": 9,  "color": COLORS["member_张家炅"]},
    {"member": "张家炅", "grade": "A", "task": "人脸识别 (注册+1:N+百度API)",       "s": 12, "e": 13, "color": COLORS["member_张家炅"]},
    {"member": "张家炅", "grade": "A", "task": "视频源连接测试 + 巡检闭环联调",      "s": 13, "e": 14, "color": COLORS["member_张家炅"]},

    # ── 曹晋豪 (A) ──
    {"member": "曹晋豪", "grade": "A", "task": "小车使用指南 + SLAM导航章节",        "s": 7,  "e": 7,  "color": COLORS["member_曹晋豪"]},
    {"member": "曹晋豪", "grade": "A", "task": "REST API服务器 (Flask)",           "s": 9,  "e": 9,  "color": COLORS["member_曹晋豪"]},
    {"member": "曹晋豪", "grade": "A", "task": "传感器驱动 (9种传感器串口)",          "s": 9,  "e": 9,  "color": COLORS["member_曹晋豪"]},
    {"member": "曹晋豪", "grade": "A", "task": "地图导航 (选点导航+地图API)",        "s": 11, "e": 11, "color": COLORS["member_曹晋豪"]},
    {"member": "曹晋豪", "grade": "A", "task": "多车协调器 (注册+轮询+编队+碰撞)",    "s": 12, "e": 13, "color": COLORS["member_曹晋豪"]},
    {"member": "曹晋豪", "grade": "A", "task": "启动脚本 + 音频API + 运动冻结修复",   "s": 12, "e": 13, "color": COLORS["member_曹晋豪"]},

    # ── 朱宇帆 (B) ──
    {"member": "朱宇帆", "grade": "B", "task": "Docker CI/CD 流水线 (GitHub Actions)","s": 9,  "e": 9,  "color": COLORS["member_朱宇帆"]},
    {"member": "朱宇帆", "grade": "B", "task": "鸿蒙APP (ArkTS 30+文件 + hvigor 6.x)","s": 9,  "e": 13, "color": COLORS["member_朱宇帆"]},
    {"member": "朱宇帆", "grade": "B", "task": "云平台后端 (Flask+MySQL+告警API)",    "s": 13, "e": 13, "color": COLORS["member_朱宇帆"]},
    {"member": "朱宇帆", "grade": "B", "task": "云平台前端 (React+Vite+Tailwind)",   "s": 13, "e": 13, "color": COLORS["member_朱宇帆"]},
    {"member": "朱宇帆", "grade": "B", "task": "API文档 + 需求文档 + 模块关系图",      "s": 13, "e": 14, "color": COLORS["member_朱宇帆"]},

    # ── 李沐宸 (B) ──
    {"member": "李沐宸", "grade": "B", "task": "Web前端重构 (HTML5+组件化)",         "s": 8,  "e": 9,  "color": COLORS["member_李沐宸"]},
    {"member": "李沐宸", "grade": "B", "task": "车队编队+手动控制+雷达+状态管理",       "s": 12, "e": 12, "color": COLORS["member_李沐宸"]},
    {"member": "李沐宸", "grade": "B", "task": "Web移动端适配 + TCP→HTTP迁移",       "s": 12, "e": 13, "color": COLORS["member_李沐宸"]},
    {"member": "李沐宸", "grade": "B", "task": "3D模型展示+图标系统+UI对齐",          "s": 13, "e": 13, "color": COLORS["member_李沐宸"]},
    {"member": "李沐宸", "grade": "B", "task": "页面原型规范 + 交互流程校正",          "s": 13, "e": 14, "color": COLORS["member_李沐宸"]},
]

MILESTONES = [
    {"label": "M1\n基础环境",  "date": 7,  "color": COLORS["done"]},
    {"label": "M2\n服务化开发","date": 9,  "color": COLORS["done"]},
    {"label": "M3\n核心模块",  "date": 11, "color": COLORS["done"]},
    {"label": "M4\n全面开发",  "date": 12, "color": COLORS["done"]},
    {"label": "M5\n全栈联调",  "date": 13, "color": COLORS["ongoing"]},
    {"label": "M6\n答辩交付",  "date": 14, "color": COLORS["pending"]},
]

# 燃尽图数据
BURNDOWN = [
    # day: 6,7,8,9,10,11,12,13,14
    {"day": 6,  "ideal_remaining": 100, "actual_remaining": 97},
    {"day": 7,  "ideal_remaining": 89,  "actual_remaining": 85},
    {"day": 8,  "ideal_remaining": 78,  "actual_remaining": 82},
    {"day": 9,  "ideal_remaining": 67,  "actual_remaining": 72},
    {"day": 10, "ideal_remaining": 56,  "actual_remaining": 72},
    {"day": 11, "ideal_remaining": 44,  "actual_remaining": 48},
    {"day": 12, "ideal_remaining": 33,  "actual_remaining": 28},
    {"day": 13, "ideal_remaining": 22,  "actual_remaining": 15},
    {"day": 14, "ideal_remaining": 11,  "actual_remaining": None},
]


# ═══════════════════════════════════════════════════════════
#  1. 甘特图 (Gantt Chart)
# ═══════════════════════════════════════════════════════════
def draw_gantt():
    fig, ax = plt.subplots(figsize=(18, 11))
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])

    # 按贡献度→成员排序, 每个成员内按开始时间排序
    member_order = [
        ("魏贤炀", "A"), ("张家炅", "A"), ("曹晋豪", "A"),
        ("朱宇帆", "B"), ("李沐宸", "B"),
    ]
    grade_colors = {"A": "#1a73e8", "B": "#5f6368"}

    y = 0
    y_ticks = []
    y_labels = []
    member_section_lines = []

    for mname, mgrade in member_order:
        mtasks = [t for t in TASKS if t["member"] == mname]
        # 绘制成员分隔带
        if y > 0:
            member_section_lines.append(y - 0.6)

        # 成员标签 + 贡献度
        y_ticks.append(y + (len(mtasks) - 1) / 2)
        y_labels.append(mname)

        for t in sorted(mtasks, key=lambda x: (x["s"], x["e"])):
            sdate = make_date(t["s"])
            # 结束日 +1 天，这样 bar 右边缘覆盖到结束日
            edate = make_date(t["e"]) + timedelta(days=1)
            bar = ax.barh(
                y,
                edate - sdate,
                left=sdate,
                height=0.7,
                color=t["color"],
                edgecolor="white",
                linewidth=0.5,
                alpha=0.92,
                zorder=3,
            )
            # 任务标签
            ax.text(
                sdate + timedelta(hours=6), y,
                f"  {t['task']}",
                va="center", ha="left",
                fontsize=8.2, color="white" if t["color"] not in ["#fbbc04"] else "#202124",
                zorder=4,
            )
            y -= 1
        y -= 0.4  # 成员间间距

    # ── 里程碑 ──
    for ms in MILESTONES:
        md = make_date(ms["date"])
        ax.axvline(x=md, color=ms["color"], linewidth=2.2, linestyle="--",
                   alpha=0.7, zorder=2)
        ax.text(md + timedelta(hours=2), y - 0.1,
                ms["label"].replace("\n", " "),
                fontsize=8.5, color=ms["color"], fontweight="bold",
                va="top", ha="left", zorder=5,
                bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                          edgecolor=ms["color"], alpha=0.9))

    # ── 今日线 ──
    today = datetime(2026, 7, 14)
    ax.axvline(x=today, color=COLORS["secondary"], linewidth=1.8,
               linestyle="-", alpha=0.35, zorder=2)
    ax.text(today + timedelta(hours=1), y - 0.5, "今天",
            fontsize=8, color=COLORS["secondary"], fontweight="bold")

    # ── 装饰 ──
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels, fontsize=11, fontweight="bold")
    ax.invert_yaxis()

    # X 轴: 每天一格
    ax.set_xlim(date_to_num(make_date(5)), date_to_num(make_date(15)))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    def _fmt_date(x, pos=None):
        dt = mdates.num2date(x)
        return f"{dt.month}/{dt.day}"
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_fmt_date))
    ax.tick_params(axis="x", labelsize=10, colors=COLORS["text_light"])
    ax.tick_params(axis="y", labelsize=10, colors=COLORS["text"])

    # 日期标签加星期
    weekdays = ["日", "一", "二", "三", "四", "五", "六"]
    for d in range(6, 15):
        dt = make_date(d)
        wd = weekdays[dt.weekday()]
        ax.annotate(
            f"周{wd}",
            xy=(date_to_num(dt), ax.get_ylim()[0]),
            xytext=(0, -16),
            textcoords="offset points",
            fontsize=7.5,
            color=COLORS["text_light"],
            ha="center",
            va="top",
        )

    # 网格
    ax.grid(axis="x", color=COLORS["grid"], linewidth=0.5, alpha=0.6, zorder=1)
    ax.set_axisbelow(True)

    # 标题
    ax.set_title(
        "FireGuard 项目甘特图 — 基于 133 条 GitHub 提交记录",
        fontsize=15, fontweight="bold", color=COLORS["text"], pad=18,
    )

    # 图例
    legend_handles = [
        mpatches.Patch(color=COLORS["done"], alpha=0.7, label="已完成里程碑"),
        mpatches.Patch(color=COLORS["ongoing"], alpha=0.7, label="进行中里程碑"),
        mpatches.Patch(color=COLORS["pending"], alpha=0.7, label="待完成里程碑"),
    ]
    ax.legend(handles=legend_handles, loc="lower right", fontsize=9,
              framealpha=0.9, edgecolor=COLORS["grid"])

    # 底部说明
    fig.text(0.5, 0.01,
             "数据来源: GitHub WeiXianyang/MiniMover 仓库 | 统计周期: 2026/07/06 ~ 2026/07/14",
             ha="center", fontsize=7.5, color=COLORS["text_light"])

    fig.tight_layout(rect=[0, 0.03, 1, 0.97])
    path = os.path.join(OUTPUT_DIR, "01_甘特图.png")
    fig.savefig(path, facecolor=COLORS["bg"])
    plt.close(fig)
    print(f"✅ 甘特图已保存: {path}")
    return path


# ═══════════════════════════════════════════════════════════
#  2. 里程碑图 (Milestone Chart)
# ═══════════════════════════════════════════════════════════
def draw_milestone():
    """垂直时间轴式里程碑图，每个里程碑独立一行，清晰可读"""
    fig, ax = plt.subplots(figsize=(20, 9))
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])

    milestones_detail = [
        {"label": "M1", "title": "基础环境搭建",        "date": 7,  "status": "done",
         "desc": "仓库初始化 + 小车底盘代码导入 + 底盘/摄像头/SLAM就绪\nAGENTS.md + 小车使用指南"},
        {"label": "M2", "title": "服务化与初始开发",      "date": 9,  "status": "done",
         "desc": "REST API服务器上线 + 9种传感器驱动 + Docker CI/CD流水线\n鸿蒙APP工程(hvigor6.x)初始化"},
        {"label": "M3", "title": "核心模块开发",          "date": 11, "status": "done",
         "desc": "YOLOv5烟火检测完整迁移 + 三检测器答辩演示 + 地图导航功能\n中期检查"},
        {"label": "M4", "title": "多模块全面开发",        "date": 12, "status": "done",
         "desc": "AI二次复核(状态机) + 人脸识别(注册+1:N) + 多车协调器(编队+碰撞)\nWeb车队编队+雷达+状态管理"},
        {"label": "M5", "title": "全栈联调与最终集成",    "date": 13, "status": "ongoing",
         "desc": "语音助手(ASR→LLM→TTS) + 鸿蒙APP迭代 + 云平台(后端API+前端React)\nRAG知识库 + 3D模型+图标 + 文档完善"},
        {"label": "M6", "title": "答辩交付准备",          "date": 14, "status": "pending",
         "desc": "巡检闭环联调 + 演示视频录制 + 最终答辩PPT + 需求分析报告\n测试报告·使用手册·日报(5人×10天) + 稳定镜像+回滚脚本"},
    ]

    status_colors = {"done": COLORS["done"], "ongoing": COLORS["ongoing"], "pending": COLORS["pending"]}
    status_text  = {"done": "● 已完成", "ongoing": "◎ 进行中", "pending": "○ 待完成"}
    commit_counts = [9, 7, 24, 41, 52, None]

    # 画垂直时间轴线
    x_min = date_to_num(make_date(5)) - 0.5
    x_max = date_to_num(make_date(14)) + 0.5
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(0, 7.5)

    # 垂直时间轴
    ax.vlines(x=date_to_num(make_date(6)), ymin=0.5, ymax=6.8,
              color=COLORS["grid"], linewidth=2.5, zorder=1)

    # 每个里程碑一行
    for i, ms in enumerate(milestones_detail):
        y = 6.3 - i * 1.1  # 从上到下排列
        x = make_date(ms["date"])
        color = status_colors[ms["status"]]

        # 连接线到时间轴
        ax.hlines(y=y, xmin=date_to_num(make_date(6)), xmax=date_to_num(x),
                  color=color, linewidth=2.5, alpha=0.6, zorder=2)

        # 大圆点
        ax.plot(date_to_num(x), y, "o", color=color, markersize=18, zorder=5,
                markeredgecolor="white", markeredgewidth=2.5)
        # 内圈
        ax.plot(date_to_num(x), y, "o", color="white", markersize=7, zorder=6, alpha=0.7)

        # 日期标签 (在圆点上方)
        dt = make_date(ms["date"])
        ax.text(date_to_num(x), y + 0.55, f'7/{ms["date"]}',
                ha="center", va="bottom", fontsize=11, fontweight="bold",
                color=color, zorder=5)

        # 里程碑标题 (在圆点右方)
        ax.text(date_to_num(x) + 0.25, y + 0.2,
                f'{ms["label"]}  {ms["title"]}',
                ha="left", va="bottom", fontsize=13, fontweight="bold",
                color=color, zorder=5)

        # 状态标签
        ax.text(date_to_num(x) + 0.30, y - 0.05,
                status_text[ms["status"]],
                ha="left", va="top", fontsize=9, color=color, zorder=5)

        # commits数
        if commit_counts[i]:
            ax.text(date_to_num(make_date(5)) + 0.4, y,
                    f'{commit_counts[i]} commits',
                    ha="left", va="center", fontsize=9,
                    fontweight="bold", color=COLORS["text_light"], zorder=5)

        # 描述框
        desc_text = ms["desc"]
        ax.text(date_to_num(x) + 1.2, y + 0.55,
                desc_text,
                ha="left", va="top", fontsize=9, color=COLORS["text"],
                zorder=4,
                bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa",
                          edgecolor=color, linewidth=1.2, alpha=0.9))

    # 底部日期刻度
    for d in range(6, 15):
        dt = make_date(d)
        ax.text(date_to_num(dt), 0.2, f'7/{d}', ha="center", va="top",
                fontsize=9, color=COLORS["text_light"], zorder=5)

    # 时间轴标签
    ax.text(date_to_num(make_date(6)), 0.0, "项目启动", ha="center", va="top",
            fontsize=8.5, color=COLORS["text_light"], zorder=5)
    ax.text(date_to_num(make_date(14)), 0.0, "答辩交付", ha="center", va="top",
            fontsize=8.5, fontweight="bold", color=COLORS["secondary"], zorder=5)

    ax.set_ylim(-0.2, 7.5)
    ax.axis("off")

    # 图例
    legend_y = 0.6
    legend_positions = [date_to_num(make_date(10)) + 0.5, date_to_num(make_date(11)) + 0.1, date_to_num(make_date(12)) + 0.2]
    legend_labels = ["已完成", "进行中", "待完成"]
    legend_statuses = ["done", "ongoing", "pending"]
    for pos, status, label in zip(legend_positions, legend_statuses, legend_labels):
        color = status_colors[status]
        ax.plot(pos, legend_y, "o", color=color, markersize=10, zorder=5,
                markeredgecolor="white", markeredgewidth=1.5)
        ax.text(pos + 0.3, legend_y, label, fontsize=8.5, va="center", color=COLORS["text"])

    ax.set_title(
        "FireGuard 项目里程碑 — 6 个关键节点 × 133 条提交 × 8 天开发",
        fontsize=15, fontweight="bold", color=COLORS["text"], pad=16,
    )

    fig.tight_layout()
    path = os.path.join(OUTPUT_DIR, "02_里程碑图.png")
    fig.savefig(path, facecolor=COLORS["bg"])
    plt.close(fig)
    print(f"✅ 里程碑图已保存: {path}")
    return path


# ═══════════════════════════════════════════════════════════
#  3. 燃尽图 (Burndown Chart)
# ═══════════════════════════════════════════════════════════
def draw_burndown():
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])

    days = [d["day"] for d in BURNDOWN]
    ideal = [d["ideal_remaining"] for d in BURNDOWN]
    actual_raw = [d["actual_remaining"] for d in BURNDOWN]

    # 实际剩余：最后一天 None 表示未完成，画到前一天的线
    actual_days = [d for d, a in zip(days, actual_raw) if a is not None]
    actual_vals = [a for a in actual_raw if a is not None]

    # 理想燃尽线
    ax.plot([make_date(d) for d in days], ideal,
            color=COLORS["ideal"], linewidth=2.5, linestyle="--",
            marker="s", markersize=7, markerfacecolor="white",
            markeredgecolor=COLORS["ideal"], markeredgewidth=2,
            label="理想进度 (均匀分配)", zorder=4)
    # 填充理想区域
    ax.fill_between([make_date(d) for d in days], ideal, 0,
                    color=COLORS["ideal"], alpha=0.05)

    # 实际燃尽线
    ax.plot([make_date(d) for d in actual_days], actual_vals,
            color=COLORS["actual"], linewidth=3, linestyle="-",
            marker="o", markersize=9, markerfacecolor=COLORS["actual"],
            markeredgecolor="white", markeredgewidth=1.5,
            label="实际进度 (GitHub Commits)", zorder=5)
    # 填充实际区域
    ax.fill_between([make_date(d) for d in actual_days], actual_vals, 0,
                    color=COLORS["actual"], alpha=0.08)

    # 每个数据点标注
    for i, (d, iv, av) in enumerate(zip(days, ideal, actual_raw)):
        x = make_date(d)
        # 理想值
        ax.annotate(f"{iv}%", xy=(x, iv), xytext=(5, 8),
                    textcoords="offset points", fontsize=7.5,
                    color=COLORS["ideal"], ha="left")
        # 实际值
        if av is not None:
            ax.annotate(f"{av}%", xy=(x, av), xytext=(-5, -14),
                        textcoords="offset points", fontsize=8,
                        color=COLORS["actual"], ha="right",
                        fontweight="bold")

    # 7.10 授课日标注
    dt_710 = make_date(10)
    ax.axvspan(make_date(10), make_date(11), color=COLORS["grid"],
               alpha=0.25, zorder=1)
    ax.annotate("7.10\n企业授课\n(0 commits)",
                xy=(make_date(10) + timedelta(hours=12), 72), fontsize=8.5,
                color=COLORS["secondary"], ha="center",
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#fff3e0",
                          edgecolor=COLORS["secondary"], alpha=0.8),
                zorder=6)

    # 中期检查标注
    ax.axvline(x=make_date(11), color=COLORS["milestone"], linewidth=1.5,
               linestyle=":", alpha=0.8, zorder=2)
    ax.annotate("▲ 7.11 中期检查",
                xy=(make_date(11), 50), xytext=(15, 15),
                textcoords="offset points", fontsize=9,
                color=COLORS["milestone"], fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=COLORS["milestone"], lw=1.5),
                zorder=6)

    # 最终日标注
    ax.annotate("🎯 7.14 最终答辩",
                xy=(make_date(14), 11), xytext=(-30, 20),
                textcoords="offset points", fontsize=9.5,
                color=COLORS["secondary"], fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=COLORS["secondary"], lw=1.5),
                zorder=6)

    # 坐标轴
    ax.set_xlim(date_to_num(make_date(5)) - 0.5, date_to_num(make_date(14)) + 0.5)
    ax.set_ylim(0, 108)
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    def _fmt_date2(x, pos=None):
        dt = mdates.num2date(x)
        return f"{dt.month}/{dt.day}"
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_fmt_date2))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v)}%"))
    ax.tick_params(axis="both", labelsize=10, colors=COLORS["text"])

    # 添加星期
    weekdays = ["日", "一", "二", "三", "四", "五", "六"]
    for d in range(6, 15):
        dt = make_date(d)
        wd = weekdays[dt.weekday()]
        ax.annotate(f"周{wd}", xy=(date_to_num(dt), -3),
                    xytext=(0, -10), textcoords="offset points",
                    fontsize=7, color=COLORS["text_light"], ha="center")

    ax.set_ylabel("剩余工作量 (%)", fontsize=11, color=COLORS["text"])
    ax.set_xlabel("日期", fontsize=11, color=COLORS["text"])

    # 网格
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.5, alpha=0.6, zorder=1)
    ax.grid(axis="x", color=COLORS["grid"], linewidth=0.5, alpha=0.4, zorder=1)
    ax.set_axisbelow(True)

    # 图例
    ax.legend(loc="upper right", fontsize=10, framealpha=0.9,
              edgecolor=COLORS["grid"])

    # 标题
    ax.set_title(
        "FireGuard 项目燃尽图 — 理想进度 vs 实际进度 (基于 133 条 Git 提交)",
        fontsize=14, fontweight="bold", color=COLORS["text"], pad=14,
    )

    # 注释框
    textstr = (
        f"起始工作量: 100%\n"
        f"当前剩余: 15%\n"
        f"总提交: 133 commits\n"
        f"团队: 5人\n"
        f"冲刺峰值: 52 commits/日 (7.13)"
    )
    props = dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa",
                 edgecolor=COLORS["grid"], alpha=0.9)
    ax.text(0.02, 0.95, textstr, transform=ax.transAxes,
            fontsize=8.5, color=COLORS["text"], va="top",
            bbox=props, zorder=7)

    fig.tight_layout()
    path = os.path.join(OUTPUT_DIR, "03_燃尽图.png")
    fig.savefig(path, facecolor=COLORS["bg"])
    plt.close(fig)
    print(f"✅ 燃尽图已保存: {path}")
    return path


# ═══════════════════════════════════════════════════════════
#  4. 成员贡献度饼图
# ═══════════════════════════════════════════════════════════
def draw_contribution_pie():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor(COLORS["bg"])

    # ── 左: 提交数饼图 ──
    members_commits = [
        ("魏贤炀", 59, COLORS["member_魏贤炀"]),
        ("朱宇帆", 26, COLORS["member_朱宇帆"]),
        ("曹晋豪", 20, COLORS["member_曹晋豪"]),
        ("李沐宸", 18, COLORS["member_李沐宸"]),
        ("张家炅", 4,  COLORS["member_张家炅"]),
    ]
    labels_c = [f"{m}\n{c} commits" for m, c, _ in members_commits]
    sizes_c = [c for _, c, _ in members_commits]
    colors_c = [clr for _, _, clr in members_commits]
    explode_c = (0.05, 0, 0, 0, 0)

    wedges, texts, autotexts = ax1.pie(
        sizes_c, explode=explode_c, labels=labels_c, colors=colors_c,
        autopct="%1.1f%%", startangle=140,
        textprops={"fontsize": 9},
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
    )
    for at in autotexts:
        at.set_fontsize(9)
        at.set_fontweight("bold")
    ax1.set_title("Git Commits 占比 (总计133)", fontsize=12,
                  fontweight="bold", color=COLORS["text"])

    # ── 右: 贡献分布饼图 ──
    grade_labels = [
        f"核心模块独立负责\n魏贤炀·张家炅·曹晋豪",
        f"全栈协作开发\n朱宇帆·李沐宸",
    ]
    grade_sizes = [60, 40]
    grade_colors = ["#1a73e8", "#dadce0"]

    wedges2, texts2, autotexts2 = ax2.pie(
        grade_sizes, labels=grade_labels, colors=grade_colors,
        autopct="%1.0f%%", startangle=90,
        textprops={"fontsize": 9},
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
    )
    for at in autotexts2:
        at.set_fontsize(11)
        at.set_fontweight("bold")
    ax2.set_title("贡献分布", fontsize=12,
                  fontweight="bold", color=COLORS["text"])

    fig.suptitle("FireGuard 团队贡献度分析", fontsize=14,
                 fontweight="bold", color=COLORS["text"], y=1.02)
    fig.tight_layout()

    path = os.path.join(OUTPUT_DIR, "04_贡献度饼图.png")
    fig.savefig(path, facecolor=COLORS["bg"])
    plt.close(fig)
    print(f"✅ 贡献度饼图已保存: {path}")
    return path


# ═══════════════════════════════════════════════════════════
#  main
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  FireGuard 项目图表生成器")
    print("  基于 GitHub 133 条提交记录")
    print("=" * 60)
    print()

    draw_gantt()
    draw_milestone()
    draw_burndown()
    draw_contribution_pie()

    print()
    print(f"📁 所有图表已输出到: {OUTPUT_DIR}")
    for f in sorted(os.listdir(OUTPUT_DIR)):
        fsize = os.path.getsize(os.path.join(OUTPUT_DIR, f))
        print(f"   {f} ({fsize:,} bytes)")
    print()
    print("✅ 完成！可直接插入答辩PPT。")
