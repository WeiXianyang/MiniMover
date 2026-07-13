"""CloudAlarmService — 把告警上报到云端接收 API。

实现 fire_monitor AlarmService Protocol, 与 LoggingAlarmService 可组合使用。
上报链路: 上传证据图片(POST /api/v1/evidence) → POST /api/v1/fire-alarms
失败时写入本地 outbox.jsonl, 后台线程按退避策略重试(断网容错)。
上报在后台线程异步执行, 不阻塞 YOLO 检测主循环。

环境变量(沿用车端 .env 风格):
  CLOUD_API_BASE_URL    云端 API 根地址, 默认 http://8.140.28.233:8000
  CLOUD_API_TOKEN       鉴权 Bearer token
  CAR_ID                车辆标识(多车动态区分), 默认 unknown
  CLOUD_RETRY_MAX_SEC   最大重试等待秒数(指数退避上限), 默认 300
"""
from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
from pathlib import Path
from typing import Optional

import urllib.request

from .types import AlarmEvent


def _load_int(name: str, default: str) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _load_str(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


# ---------------------------------------------------------------------------
# Outbox entry helpers
# ---------------------------------------------------------------------------

def _write_outbox(outbox_path: Path, entry: dict) -> None:
    outbox_path.parent.mkdir(parents=True, exist_ok=True)
    with open(outbox_path, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
        stream.flush()


def _load_outbox(outbox_path: Path) -> list[dict]:
    if not outbox_path.is_file():
        return []
    entries = []
    for line in outbox_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except (ValueError, TypeError):
            continue
    return entries


def _clear_outbox(outbox_path: Path) -> None:
    outbox_path.unlink(missing_ok=True)


# ---- Composite (chains multiple AlarmService implementations) ----

class CompositeAlarmService:
    """把多个 AlarmService 实现串联为一条链, 每条都调用, 各自返回各自的结果。
    用第一个返回 True 的作为合成结果; 所有子 service 都会被调用。
    """

    def __init__(self, *services):
        self._services = services

    def report_confirmed_fire(self, event: AlarmEvent) -> bool:
        result = False
        for svc in self._services:
            if svc.report_confirmed_fire(event):
                result = True
        return result

    def report_suspected_smoke(self, event: AlarmEvent) -> bool:
        result = False
        for svc in self._services:
            if svc.report_suspected_smoke(event):
                result = True
        return result

    def report_ai_unavailable(self, event: AlarmEvent) -> bool:
        result = False
        for svc in self._services:
            if svc.report_ai_unavailable(event):
                result = True
        return result


# ---- CloudAlarmService ----

class CloudAlarmService:
    """上报告警到云端; 失败写 outbox 并在后台重试。"""

    _SENTINEL = object()
    _RETRY_INITIAL = 2.0   # 首次重试等待秒数
    _RETRY_CAP = 300.0     # 最大重试等待秒数
    _BACKOFF_FACTOR = 2.0  # 指数退避因子

    def __init__(self, runtime_dir: Path, logger: Optional[logging.Logger] = None):
        """
        Args:
            runtime_dir: 车端 fire_monitor runtime 目录(outbox 写在此)
            logger:     可选的 logger, 日志输出到此
        """
        self._runtime_dir = Path(runtime_dir)
        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        self._outbox_path = self._runtime_dir / "cloud_outbox.jsonl"
        self._logger = logger or logging.getLogger("cloud_alarm")

        # 从环境变量加载配置
        self._base_url = _load_str(
            "CLOUD_API_BASE_URL", "http://8.140.28.233:8000"
        ).rstrip("/")
        self._token = _load_str("CLOUD_API_TOKEN", "")
        self._car_id = _load_str("CAR_ID", "unknown")
        try:
            self._retry_cap = _load_int("CLOUD_RETRY_MAX_SEC", str(self._RETRY_CAP))
        except ValueError:
            self._retry_cap = int(self._RETRY_CAP)

        # 去重: 同一次 run 里同一 event+type 不重复入队
        self._sent: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

        # 异步上报队列(每个元素是 dict payload)
        self._queue: queue.Queue = queue.Queue()
        self._closed = False

        # 启动后台 worker
        self._worker = threading.Thread(target=self._run, name="cloud-alarm", daemon=True)
        self._worker.start()

    # ---- AlarmService Protocol ----

    def report_confirmed_fire(self, event: AlarmEvent) -> bool:
        return self._report(event, "confirmed_fire")

    def report_suspected_smoke(self, event: AlarmEvent) -> bool:
        return self._report(event, "suspected_smoke")

    def report_ai_unavailable(self, event: AlarmEvent) -> bool:
        return self._report(event, "ai_unavailable")

    # ---- internal ----

    def _report(self, event: AlarmEvent, alarm_type: str) -> bool:
        key = (event.event_id, alarm_type)
        with self._lock:
            if key in self._sent:
                return False
            self._sent.add(key)
        try:
            self._queue.put_nowait(self._build_entry(event, alarm_type))
        except queue.Full:
            # 队列满(极度异常), 写 outbox 兜底
            self._logger.error("Cloud alarm queue full; falling back to outbox")
            _write_outbox(self._outbox_path, self._build_entry(event, alarm_type))
        return True

    def _build_entry(self, event: AlarmEvent, alarm_type: str) -> dict:
        return {
            "event_id": event.event_id,
            "alarm_type": alarm_type,
            "occurred_at": event.occurred_at.isoformat(),
            "reason": event.reason,
            "confidence": event.confidence,
            "evidence_path": event.evidence_path,
            "local_detection_gone": event.local_detection_gone,
            "car_id": self._car_id,
        }

    # ---- background worker ----

    def _run(self) -> None:
        """后台线程: 处理实时队列 + outbox 重试。"""
        while True:
            # 1. 处理实时队列
            entry = self._queue.get()
            if entry is self._SENTINEL:
                self._queue.task_done()
                return
            self._process_one(entry)
            self._queue.task_done()
            # 2. 重新处理 outbox 里积压的条目
            self._retry_outbox()

    def _retry_outbox(self) -> None:
        """读 outbox, 逐条重试, 成功的剔除。"""
        entries = _load_outbox(self._outbox_path)
        if not entries:
            return
        remaining = []
        delay = self._RETRY_INITIAL
        for entry in entries:
            if self._closed:
                remaining.append(entry)
                continue
            if self._process_one(entry):
                # 成功, 不保留
                continue
            remaining.append(entry)
            time.sleep(min(delay, self._retry_cap))
            delay = min(delay * self._BACKOFF_FACTOR, self._retry_cap)
        if remaining and len(remaining) < len(entries):
            # 有成功清理, 重写 outbox
            with open(self._outbox_path, "w", encoding="utf-8") as stream:
                for entry_ in remaining:
                    stream.write(json.dumps(entry_, ensure_ascii=False) + "\n")
        if not remaining:
            _clear_outbox(self._outbox_path)

    def _process_one(self, entry: dict) -> bool:
        """上报一条告警, 返回 True=成功 False=失败。"""
        evidence_url = None
        evidence_path = entry.get("evidence_path")
        if evidence_path and Path(evidence_path).is_file():
            evidence_url = self._upload_evidence(evidence_path, entry["event_id"])
        return self._post_alarm(entry, evidence_url)

    # ---- HTTP transports ----

    def _upload_evidence(self, local_path: str, event_id: str) -> Optional[str]:
        """上传图片到云端, 返回 URL; 失败返回 None。"""
        url = f"{self._base_url}/api/v1/evidence"
        try:
            import io

            import requests
        except ImportError:
            # 无 requests 库, 用 urllib (兼容最小依赖)
            return self._upload_evidence_urllib(local_path, event_id)
        try:
            with open(local_path, "rb") as stream:
                files = {"file": (Path(local_path).name, stream, "image/jpeg")}
                data = {"event_id": event_id}
                headers = {}
                if self._token:
                    headers["Authorization"] = f"Bearer {self._token}"
                response = requests.post(url, files=files, data=data, headers=headers, timeout=30)
                response.raise_for_status()
                result = response.json()
                return result.get("url")
        except Exception as exc:
            self._logger.warning("Cloud evidence upload failed: %s", exc)
        return None

    def _upload_evidence_urllib(self, local_path: str, event_id: str) -> Optional[str]:
        """urllib 版本的上传(无 requests 依赖)。"""
        from urllib.parse import urlencode

        boundary = f"fireguard{int(time.time())}"
        name = Path(local_path).name
        body_parts = [
            f'--{boundary}',
            f'Content-Disposition: form-data; name="event_id"',
            '',
            event_id,
            f'--{boundary}',
            f'Content-Disposition: form-data; name="file"; filename="{name}"',
            'Content-Type: image/jpeg',
            '',
        ]
        body = "\r\n".join(body_parts).encode("utf-8") + b"\r\n"
        body += Path(local_path).read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            req = urllib.request.Request(
                f"{self._base_url}/api/v1/evidence", data=body, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("url")
        except Exception as exc:
            self._logger.warning("Cloud evidence upload failed: %s", exc)
        return None

    def _post_alarm(self, entry: dict, evidence_url: Optional[str]) -> bool:
        """POST 告警到云端, 返回 True=成功 False=失败。"""
        payload = dict(entry)
        payload.pop("evidence_path", None)
        if evidence_url:
            payload["evidence_url"] = evidence_url
        try:
            import requests
        except ImportError:
            return self._post_alarm_urllib(payload)
        try:
            headers = {"Content-Type": "application/json"}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
            response = requests.post(
                f"{self._base_url}/api/v1/fire-alarms",
                json=payload, headers=headers, timeout=15,
            )
            response.raise_for_status()
            return True
        except Exception as exc:
            self._logger.warning("Cloud alarm POST failed: %s", exc)
        return False

    def _post_alarm_urllib(self, payload: dict) -> bool:
        """urllib 版本的告警上报(无 requests 依赖)。"""
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            req = urllib.request.Request(
                f"{self._base_url}/api/v1/fire-alarms", data=data, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
            return True
        except Exception as exc:
            self._logger.warning("Cloud alarm POST failed: %s", exc)
        return False

    # ---- lifecycle ----

    def close(self, grace: float = 5.0) -> None:
        """关停后台 worker, 等待队列排空。"""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        try:
            self._queue.put_nowait(self._SENTINEL)
        except queue.Full:
            pass
        self._worker.join(timeout=grace)
