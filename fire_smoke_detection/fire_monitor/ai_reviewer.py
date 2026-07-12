from __future__ import annotations

import base64
import json
import math
import queue
import re
import threading
import time
import urllib.request
from typing import Callable

from .config import FireMonitorConfig
from .types import AIReviewRequest, AIReviewResult, AIResultKind
from .debug_telemetry import NullTelemetry

SYSTEM_PROMPT = """你是火灾图像复核系统。请判断图片中是否存在真实明火或烟雾。
confirmed_fire：明确可见火焰、燃烧区域，或火焰伴随烟雾。
suspected_smoke：没有明确火焰，但有具备火灾风险的明显烟雾。
no_fire：没有可靠明火或烟雾证据。灯光、夕阳、红橙色物体、蒸汽、云雾、反光和屏幕画面不能仅凭颜色判断为火情。
必须综合形状、纹理、扩散方式和环境；证据不足时返回 no_fire。
只能输出JSON，不要输出Markdown或其他文字，格式为：
{"result":"confirmed_fire|suspected_smoke|no_fire","confidence":0.0,"reason":"简短中文原因"}
"""


def build_payload(model: str, jpeg_bytes: bytes) -> bytes:
    encoded = base64.b64encode(jpeg_bytes).decode("ascii")
    payload = {"model": model, "temperature": 0, "messages": [{"role": "user", "content": [
        {"type": "text", "text": SYSTEM_PROMPT},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + encoded}},
    ]}]}
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def parse_model_content(content: str):
    text = content.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1)
    try:
        payload = json.loads(text)
        kind = AIResultKind(payload["result"])
        confidence = payload["confidence"]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid AI review JSON") from exc
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("confidence must be numeric")
    confidence = float(confidence)
    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")
    reason = " ".join(str(payload.get("reason", "")).split())[:300]
    return kind, confidence, reason


def urllib_transport(url: str, headers: dict, body: bytes, timeout: float) -> dict:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _safe_error(exc: Exception) -> str:
    text = re.sub(r"data:image/[^\s]+|Bearer\s+\S+", "[redacted]", str(exc))
    return f"{type(exc).__name__}: {text[:200]}"


class AIReviewer:
    _SENTINEL = object()

    def __init__(self, config: FireMonitorConfig, transport: Callable = urllib_transport, telemetry=None):
        self.config = config
        self.transport = transport
        self.telemetry = telemetry or NullTelemetry()
        self._requests = queue.Queue(maxsize=1)
        self._results = queue.Queue()
        self._lock = threading.Lock()
        self._busy = False
        self._closed = False
        self._worker = threading.Thread(target=self._run, name="fire-ai-reviewer", daemon=True)
        self._worker.start()

    def review_now(self, request: AIReviewRequest) -> AIReviewResult:
        if not self.config.ai_api_key:
            error = "FIRE_AI_API_KEY is not configured"
            self.telemetry.update(ai={"state": "failed", "attempt": 0, "error": error})
            self.telemetry.event("ai_failed", "Real AI key is not configured; human intervention required", attempts=0, error=error)
            return AIReviewResult(request.event_id, request.review_id, False, 0, error=error)
        body = build_payload(self.config.ai_model, request.jpeg_bytes)
        headers = {"Authorization": "Bearer " + self.config.ai_api_key, "Content-Type": "application/json"}
        attempts = 1 + self.config.ai_retries
        last_error = ""
        for attempt in range(1, attempts + 1):
            started = time.monotonic()
            self.telemetry.update(ai={"state": "requesting", "attempt": attempt, "max_attempts": attempts})
            self.telemetry.event("ai_attempt", f"Real AI request {attempt}/{attempts}", attempt=attempt, max_attempts=attempts)
            try:
                response = self.transport(self.config.ai_base_url + self.config.ai_endpoint, headers, body, self.config.ai_timeout_seconds)
                content = response["choices"][0]["message"]["content"]
                kind, confidence, reason = parse_model_content(content)
                elapsed = round(time.monotonic() - started, 3)
                self.telemetry.update(ai={"state": "completed", "attempt": attempt, "elapsed_seconds": elapsed,
                                          "result": kind.value, "confidence": confidence, "reason": reason, "error": ""})
                self.telemetry.event("ai_result", f"{kind.value} confidence={confidence:.2f}", attempt=attempt,
                                     elapsed_seconds=elapsed, result=kind.value, confidence=confidence, reason=reason)
                return AIReviewResult(request.event_id, request.review_id, True, attempt, kind, confidence, reason)
            except Exception as exc:
                last_error = _safe_error(exc)
                elapsed = round(time.monotonic() - started, 3)
                if attempt < attempts:
                    self.telemetry.event("ai_retry", f"Attempt {attempt} failed; retrying immediately", attempt=attempt,
                                         elapsed_seconds=elapsed, error=last_error)
        self.telemetry.update(ai={"state": "failed", "attempt": attempts, "error": last_error})
        self.telemetry.event("ai_failed", "All real AI requests failed; human intervention required", attempts=attempts, error=last_error)
        return AIReviewResult(request.event_id, request.review_id, False, attempts, error=last_error)

    def submit(self, request: AIReviewRequest) -> bool:
        with self._lock:
            if self._closed or self._busy:
                return False
            self._busy = True
        try:
            self._requests.put_nowait(request)
            return True
        except queue.Full:
            with self._lock:
                self._busy = False
            return False

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._busy

    def poll(self):
        results = []
        while True:
            try:
                results.append(self._results.get_nowait())
            except queue.Empty:
                return results

    def close(self, join_timeout: float = 1.0) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        try:
            self._requests.put_nowait(self._SENTINEL)
        except queue.Full:
            pass
        self._worker.join(join_timeout)

    def _run(self) -> None:
        while True:
            request = self._requests.get()
            if request is self._SENTINEL:
                return
            result = self.review_now(request)
            self._results.put(result)
            with self._lock:
                self._busy = False
