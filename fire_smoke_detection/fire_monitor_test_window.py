#!/usr/bin/env python3
"""Temporary desktop window for observing the real fire detection and AI review chain."""

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
DETECTOR = ROOT / "detector.py"
DEFAULT_DEBUG_DIR = ROOT / "runtime" / "debug"


def build_detector_command(source_kind: str, source_value: str, debug_dir: Path, device: str) -> list[str]:
    source = source_value.strip()
    if source_kind == "video":
        source = str(Path(source).expanduser().resolve())
    elif not source.isdigit():
        raise ValueError("摄像头编号必须是非负整数")
    return [sys.executable, str(DETECTOR), "--source", source, "--device", device.strip() or "cpu",
            "--conf-thres", "0.7", "--no-view", "--monitor-debug-dir", str(Path(debug_dir).resolve())]


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


def format_ai_error(error):
    """Render an empty AI error field as an explicit non-error status."""
    return str(error).strip() if error else "无"


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


class MonitorTestWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("火情检测链路测试窗口")
        self.geometry("1180x780")
        self.minsize(920, 650)
        self.process = None
        self.process_log = None
        self.event_offset = 0
        self.preview_refs = {}
        self.debug_dir = DEFAULT_DEBUG_DIR
        self.source_kind = tk.StringVar(value="camera")
        self.camera = tk.StringVar(value="0")
        self.video = tk.StringVar()
        self.device = tk.StringVar(value="cpu")
        self.summary = tk.StringVar(value="尚未启动")
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(200, self._refresh)

    def _build(self):
        controls = ttk.Frame(self, padding=10)
        controls.pack(fill="x")
        ttk.Radiobutton(controls, text="真实摄像头", variable=self.source_kind, value="camera").grid(row=0, column=0, padx=4)
        ttk.Label(controls, text="编号").grid(row=0, column=1)
        ttk.Entry(controls, textvariable=self.camera, width=6).grid(row=0, column=2, padx=4)
        ttk.Radiobutton(controls, text="本地视频", variable=self.source_kind, value="video").grid(row=0, column=3, padx=(14, 4))
        ttk.Entry(controls, textvariable=self.video, width=45).grid(row=0, column=4, padx=4, sticky="ew")
        ttk.Button(controls, text="选择视频", command=self._choose_video).grid(row=0, column=5, padx=4)
        ttk.Label(controls, text="设备").grid(row=0, column=6, padx=(14, 2))
        ttk.Entry(controls, textvariable=self.device, width=7).grid(row=0, column=7)
        ttk.Button(controls, text="启动", command=self.start_detector).grid(row=0, column=8, padx=(14, 4))
        ttk.Button(controls, text="停止", command=self.stop_detector).grid(row=0, column=9, padx=4)
        controls.columnconfigure(4, weight=1)

        ttk.Label(self, textvariable=self.summary, padding=(12, 4), font=("Microsoft YaHei UI", 10, "bold")).pack(fill="x")
        previews = ttk.Panedwindow(self, orient="horizontal")
        previews.pack(fill="both", expand=True, padx=10, pady=6)
        self.live_image = self._preview_panel(previews, "实时检测画面（带框）")
        self.ai_image = self._preview_panel(previews, "实际上传 AI 的无框原图")

        status_frame = ttk.LabelFrame(self, text="链路状态", padding=8)
        status_frame.pack(fill="x", padx=10, pady=4)
        self.status_text = tk.Text(status_frame, height=5, wrap="word", state="disabled")
        self.status_text.pack(fill="x")

        log_frame = ttk.LabelFrame(self, text="链路事件", padding=8)
        log_frame.pack(fill="both", padx=10, pady=(4, 10))
        self.log = tk.Text(log_frame, height=9, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)

    def _preview_panel(self, parent, title):
        frame = ttk.LabelFrame(parent, text=title, padding=6)
        label = ttk.Label(frame, text="等待画面", anchor="center")
        label.pack(fill="both", expand=True)
        parent.add(frame, weight=1)
        return label

    def _choose_video(self):
        value = filedialog.askopenfilename(title="选择测试视频", filetypes=[("视频", "*.mp4 *.avi *.mov *.mkv"), ("全部文件", "*.*")])
        if value:
            self.video.set(value)
            self.source_kind.set("video")

    def start_detector(self):
        if self.process and self.process.poll() is None:
            messagebox.showinfo("提示", "检测进程已经在运行")
            return
        source = self.camera.get() if self.source_kind.get() == "camera" else self.video.get()
        if self.source_kind.get() == "video" and not Path(source).is_file():
            messagebox.showerror("无法启动", "请选择存在的视频文件")
            return
        try:
            command = build_detector_command(self.source_kind.get(), source, self.debug_dir, self.device.get())
        except ValueError as exc:
            messagebox.showerror("无法启动", str(exc))
            return
        shutil.rmtree(self.debug_dir, ignore_errors=True)
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.event_offset = 0
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        log_path = self.debug_dir / "detector_console.log"
        self.process_log = log_path.open("w", encoding="utf-8")
        self.process = subprocess.Popen(command, cwd=str(ROOT), creationflags=flags,
                                        stdout=self.process_log, stderr=subprocess.STDOUT)
        self.summary.set("正在启动真实检测链路……")
        self._append_log("窗口", "已启动检测子进程")

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
        self._show_image(self.ai_image, self.debug_dir / "latest_ai_upload.jpg", "ai")
        if self.process and self.process.poll() is not None:
            self.summary.set(f"检测进程已退出，退出码 {self.process.returncode}")
            self.process = None
        self.after(200, self._refresh)

    def _show_status(self, status):
        process = _nested(status, "process", "state")
        hit_count = _nested(status, "detector", "hit_count", default=0)
        required = _nested(status, "detector", "trigger_min_hits", default=5)
        event_state = _nested(status, "event", "state")
        ai_state = _nested(status, "ai", "state")
        ai_attempt = _nested(status, "ai", "attempt", default=0)
        result = _nested(status, "ai", "result", default="")
        alarm = _nested(status, "alarm", "state")
        evidence = _nested(status, "event", "evidence_path", default="")
        self.summary.set(f"进程: {process}  |  触发进度: {hit_count}/{required}  |  事件: {event_state}  |  AI: {ai_state} 第{ai_attempt}次  |  报警: {alarm}")
        detail = (f"YOLO: {_nested(status, 'detector', 'classes', default=[])}，最高置信度 {_nested(status, 'detector', 'max_confidence', default=0)}\n"
                  f"AI结果: {result or '-'}，置信度 {_nested(status, 'ai', 'confidence')}，原因 {_nested(status, 'ai', 'reason')}\n"
                  f"AI错误: {format_ai_error(_nested(status, 'ai', 'error', default=''))}\n证据路径: {evidence or '-'}")
        self._set_text(self.status_text, detail)

    def _show_image(self, label, path: Path, key: str):
        try:
            with Image.open(path) as image:
                image.thumbnail((540, 360))
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
    MonitorTestWindow().mainloop()


if __name__ == "__main__":
    main()
