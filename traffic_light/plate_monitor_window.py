#!/usr/bin/env python3
"""Tkinter monitor window for the license plate detection chain."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parent
DETECTOR = ROOT / "plate_detector.py"
DEFAULT_DEBUG_DIR = ROOT / "runtime" / "debug_plate"
CAR_SOURCE_OPTIONS = {
    "car_A（192.168.137.23）": "car_A",
    "car_B（192.168.43.8）": "car_B",
}
CAR_ALIASES = frozenset(CAR_SOURCE_OPTIONS.values())


def build_detector_command(source_kind: str, source_value: str, debug_dir: Path,
                           confidence: float = 0.7, skip_frames: int = 5,
                           detect_width: int = 640) -> list[str]:
    source = source_value.strip()
    if source_kind == "video":
        source = str(Path(source).expanduser().resolve())
    elif source_kind == "camera":
        if not source.isdigit():
            raise ValueError("摄像头编号必须是非负整数")
    elif source_kind == "car":
        if source not in CAR_ALIASES:
            raise ValueError(f"未知的小车摄像头: {source}")
    else:
        raise ValueError(f"未知的视频源类型: {source_kind}")
    return [
        sys.executable, str(DETECTOR), source,
        "--monitor-debug-dir", str(Path(debug_dir).resolve()),
        "--no-view",
        "--confidence", str(confidence),
        "--skip-frames", str(skip_frames),
        "--detect-width", str(detect_width),
    ]


def read_debug_snapshot(debug_dir: Path, event_offset: int):
    status = {}
    status_path = Path(debug_dir) / "status.json"
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    events = []
    events_path = Path(debug_dir) / "events.jsonl"
    try:
        with events_path.open("r", encoding="utf-8") as stream:
            stream.seek(event_offset)
            for line in stream:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            event_offset = stream.tell()
    except OSError:
        pass
    return status, events, event_offset


def stop_process_tree(process, platform: str | None = None):
    """Stop a detector and every descendant that may own the camera."""
    if process is None or process.poll() is not None:
        return
    current_platform = sys.platform if platform is None else platform
    if current_platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        return

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _nested(payload, *keys, default="-"):
    value = payload
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


class PlateMonitorWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("车牌检测链路测试窗口")
        self.geometry("1180x780")
        self.minsize(920, 650)
        self.process = None
        self.process_log = None
        self.event_offset = 0
        self.preview_refs = {}
        self.debug_dir = DEFAULT_DEBUG_DIR
        self.source_kind = tk.StringVar(value="car")
        self.car = tk.StringVar(value=next(iter(CAR_SOURCE_OPTIONS)))
        self.camera = tk.StringVar(value="0")
        self.video = tk.StringVar()
        self.confidence = tk.DoubleVar(value=0.7)
        self.skip_frames = tk.IntVar(value=5)
        self.detect_width = tk.IntVar(value=640)
        self.summary = tk.StringVar(value="尚未启动")
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(200, self._refresh)

    def _build(self):
        controls = ttk.Frame(self, padding=10)
        controls.pack(fill="x")
        ttk.Radiobutton(controls, text="小车摄像头", variable=self.source_kind, value="car").grid(row=0, column=0, padx=4, sticky="w")
        ttk.Combobox(
            controls,
            textvariable=self.car,
            values=tuple(CAR_SOURCE_OPTIONS),
            width=28,
            state="readonly",
        ).grid(row=0, column=1, columnspan=2, padx=4, sticky="w")

        ttk.Radiobutton(controls, text="电脑摄像头", variable=self.source_kind, value="camera").grid(row=0, column=3, padx=(14, 4))
        ttk.Label(controls, text="编号").grid(row=0, column=4)
        ttk.Entry(controls, textvariable=self.camera, width=6).grid(row=0, column=5, padx=4, sticky="w")

        ttk.Radiobutton(controls, text="本地视频", variable=self.source_kind, value="video").grid(row=1, column=0, padx=4, pady=(8, 0), sticky="w")
        ttk.Entry(controls, textvariable=self.video, width=58).grid(row=1, column=1, columnspan=5, padx=4, pady=(8, 0), sticky="ew")
        ttk.Button(controls, text="选择视频", command=self._choose_video).grid(row=1, column=6, padx=4, pady=(8, 0))

        ttk.Label(controls, text="置信度阈值").grid(row=2, column=0, padx=4, pady=(8, 0), sticky="w")
        ttk.Scale(controls, from_=0.3, to=0.95, variable=self.confidence, orient="horizontal", length=160).grid(row=2, column=1, columnspan=2, padx=4, pady=(8, 0), sticky="w")
        ttk.Label(controls, text="跳帧").grid(row=2, column=3, padx=4, pady=(8, 0), sticky="w")
        ttk.Spinbox(controls, from_=1, to=20, textvariable=self.skip_frames, width=4).grid(row=2, column=4, padx=4, pady=(8, 0), sticky="w")
        ttk.Label(controls, text="检测宽度").grid(row=3, column=3, padx=4, pady=(4, 0), sticky="w")
        ttk.Spinbox(controls, from_=320, to=1280, increment=80, textvariable=self.detect_width, width=5).grid(row=3, column=4, padx=4, pady=(4, 0), sticky="w")
        ttk.Button(controls, text="启动检测", command=self.start_detector).grid(row=2, column=5, padx=(14, 4), pady=(8, 0), sticky="e")
        ttk.Button(controls, text="停止并释放", command=self.stop_detector).grid(row=2, column=6, padx=4, pady=(8, 0))
        controls.columnconfigure(2, weight=1)
        controls.columnconfigure(5, weight=1)

        ttk.Label(self, textvariable=self.summary, padding=(12, 4), font=("Microsoft YaHei UI", 10, "bold")).pack(fill="x")

        # Single preview panel for license plate detection
        preview_frame = ttk.LabelFrame(self, text="实时检测画面（带框）", padding=6)
        preview_frame.pack(fill="both", expand=True, padx=10, pady=6)
        self.live_image = ttk.Label(preview_frame, text="等待画面", anchor="center")
        self.live_image.pack(fill="both", expand=True)

        status_frame = ttk.LabelFrame(self, text="检测状态", padding=8)
        status_frame.pack(fill="x", padx=10, pady=4)
        self.status_text = tk.Text(status_frame, height=5, wrap="word", state="disabled")
        self.status_text.pack(fill="x")

        log_frame = ttk.LabelFrame(self, text="检测事件", padding=8)
        log_frame.pack(fill="both", padx=10, pady=(4, 10))
        self.log = tk.Text(log_frame, height=9, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)

    def _choose_video(self):
        value = filedialog.askopenfilename(title="选择测试视频", filetypes=[("视频", "*.mp4 *.avi *.mov *.mkv"), ("全部文件", "*.*")])
        if value:
            self.video.set(value)
            self.source_kind.set("video")

    def start_detector(self):
        if self.process and self.process.poll() is None:
            messagebox.showinfo("提示", "检测进程已经在运行")
            return
        source_kind = self.source_kind.get()
        if source_kind == "car":
            source = CAR_SOURCE_OPTIONS.get(self.car.get(), "")
        elif source_kind == "camera":
            source = self.camera.get()
        else:
            source = self.video.get()
        if source_kind == "video" and not Path(source).is_file():
            messagebox.showerror("无法启动", "请选择存在的视频文件")
            return
        try:
            command = build_detector_command(
                source_kind, source, self.debug_dir,
                confidence=self.confidence.get(),
                skip_frames=self.skip_frames.get(),
                detect_width=self.detect_width.get(),
            )
        except ValueError as exc:
            messagebox.showerror("无法启动", str(exc))
            return
        shutil.rmtree(self.debug_dir, ignore_errors=True)
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.event_offset = 0
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        log_path = self.debug_dir / "detector_console.log"
        self.process_log = log_path.open("w", encoding="utf-8")
        self.process = subprocess.Popen(command, cwd=str(REPOSITORY_ROOT), creationflags=flags,
                                        stdout=self.process_log, stderr=subprocess.STDOUT)
        self.summary.set("正在启动车牌检测链路……")
        self._append_log("窗口", f"已启动检测子进程；视频源: {source}，置信度阈值: {self.confidence.get():.2f}")

    def stop_detector(self):
        process = self.process
        self.process = None
        if process and process.poll() is None:
            stop_process_tree(process)
            self._append_log("窗口", "检测进程树已停止，摄像头已释放")
        if self.process_log:
            self.process_log.close()
            self.process_log = None
        self.summary.set("已停止，摄像头已释放")

    def _refresh(self):
        status, events, self.event_offset = read_debug_snapshot(self.debug_dir, self.event_offset)
        for event in events:
            stamp = str(event.get("time", ""))[11:19]
            self._append_log(f"{stamp} {event.get('stage', '-')}", event.get("detail", ""))
        if status:
            self._show_status(status)
        self._show_image(self.live_image, self.debug_dir / "latest_frame.jpg", "live")
        if self.process and self.process.poll() is not None:
            self.summary.set(f"检测进程已退出，退出码 {self.process.returncode}")
            self.process = None
        self.after(200, self._refresh)

    def _show_status(self, status):
        process = _nested(status, "process", "state")
        hit_count = _nested(status, "detector", "hit_count", default=0)
        latest_plates = _nested(status, "detector", "latest_plates", default="")
        detector_type = _nested(status, "detector", "type", default="HyperLPR")
        source = _nested(status, "source", default="-")
        self.summary.set(f"进程: {process}  |  检测器: {detector_type}  |  累计命中: {hit_count}  |  最新车牌: {latest_plates or '-'}")
        detail = (
            f"视频源: {source}\n"
            f"检测器类型: {detector_type}\n"
            f"累计命中次数: {hit_count}\n"
            f"最新识别车牌: {latest_plates or '-'}\n"
            f"进程状态: {process}"
        )
        self._set_text(self.status_text, detail)

    def _show_image(self, label, path: Path, key: str):
        try:
            with Image.open(path) as image:
                image.thumbnail((800, 480))
                photo = ImageTk.PhotoImage(image.copy())
            label.configure(image=photo, text="")
            self.preview_refs[key] = photo
        except (OSError, ValueError):
            pass

    def _append_log(self, stage, detail):
        self.log.configure(state="normal")
        self.log.insert("end", f"{stage:<22} {detail}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    @staticmethod
    def _set_text(widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _close(self):
        self.stop_detector()
        self.destroy()


def main():
    PlateMonitorWindow().mainloop()


if __name__ == "__main__":
    main()
