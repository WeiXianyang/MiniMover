from __future__ import annotations

import base64
import json
import math
import queue
import re
import threading
import urllib.request
from typing import Callable

from .config import FireMonitorConfig
from .types import AIReviewRequest, AIReviewResult, AIResultKind

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

    def __init__(self, config: FireMonitorConfig, transport: Callable = urllib_transport):
        self.config = config
        self.transport = transport
        self._requests = queue.Queue(maxsize=1)
        self._results = queue.Queue()
        self._lock = threading.Lock()
        self._busy = False
        self._closed = False
        self._worker = threading.Thread(target=self._run, name="fire-ai-reviewer", daemon=True)
        self._worker.start()

    def review_now(self, request: AIReviewRequest) -> AIReviewResult:
        if not self.config.ai_api_key:
            return AIReviewResult(request.event_id, request.review_id, False, 0, error="FIRE_AI_API_KEY is not configured")
        body = build_payload(self.config.ai_model, request.jpeg_bytes)
        headers = {"Authorization": "Bearer " + self.config.ai_api_key, "Content-Type": "application/json"}
        attempts = 1 + self.config.ai_retries
        last_error = ""
        for attempt in range(1, attempts + 1):
            try:
                response = self.transport(self.config.ai_base_url + self.config.ai_endpoint, headers, body, self.config.ai_timeout_seconds)
                content = response["choices"][0]["message"]["content"]
                kind, confidence, reason = parse_model_content(content)
                return AIReviewResult(request.event_id, request.review_id, True, attempt, kind, confidence, reason)
            except Exception as exc:
                last_error = _safe_error(exc)
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
