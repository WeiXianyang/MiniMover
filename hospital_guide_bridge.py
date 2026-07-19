"""Runtime bridge between finalized ASR text and safe hospital guidance."""

import json
import math
import os
import threading
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError

from flask import jsonify, request as flask_request

from voice_assistant.hospital_guide import (
    HospitalGuideConfig,
    HospitalGuideOrchestrator,
    NavigationRequestError,
)
from voice_assistant.hospital_guide_telemetry import HospitalGuideTelemetry
from voice_assistant.medical_knowledge import MedicalKnowledgeBase


MAX_FINAL_TEXT_CHARS = 500


class HospitalGuideNavigationClient:
    """Narrow adapter for the existing map navigation endpoint."""

    def __init__(self, base_url="http://127.0.0.1:5000", timeout=5.0):
        self.base_url = str(base_url or "http://127.0.0.1:5000").rstrip("/")
        self.timeout = float(timeout)

    def navigate_to(self, x, y, theta=0.0):
        try:
            goal = {"x": float(x), "y": float(y), "theta": float(theta)}
        except (TypeError, ValueError) as exc:
            raise ValueError("navigation coordinates must be numeric") from exc
        if not all(math.isfinite(value) for value in goal.values()):
            raise ValueError("navigation coordinates must be finite")
        body = json.dumps(goal).encode("utf-8")
        req = request.Request(
            self.base_url + "/api/navigate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode("utf-8"))
            except (OSError, UnicodeDecodeError, ValueError):
                payload = None
            reason = payload.get("msg") if isinstance(payload, dict) else None
            raise NavigationRequestError(
                reason or "\u5bfc\u822a\u670d\u52a1\u62d2\u7edd\u4e86\u672c\u6b21\u8bf7\u6c42"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise NavigationRequestError("\u65e0\u6cd5\u8fde\u63a5\u5bfc\u822a\u670d\u52a1") from exc
        except (UnicodeDecodeError, ValueError) as exc:
            raise NavigationRequestError(
                "\u5bfc\u822a\u670d\u52a1\u8fd4\u56de\u4e86\u65e0\u6548\u54cd\u5e94"
            ) from exc
        if not isinstance(payload, dict) or payload.get("code") != 0:
            reason = payload.get("msg") if isinstance(payload, dict) else None
            raise NavigationRequestError(
                reason or "\u5bfc\u822a\u670d\u52a1\u62d2\u7edd\u4e86\u672c\u6b21\u8bf7\u6c42"
            )
        return payload


class KnowledgeOnlyGuideLlm:
    """Conservative retrieval fallback when no configured LLM is reachable."""

    def answer(self, text, context=None):
        del text
        evidence = (context or {}).get("medical_evidence") or []
        if evidence:
            return (
                "以下为医疗知识库中的一般健康教育信息，不能替代现场医护评估："
                + str(evidence[0]).strip()[:160]
                + "。如症状加重或出现紧急情况，请立即联系现场医护或前往急诊。"
            )
        return "我暂未检索到相关健康教育信息，请向现场医护或服务台咨询。"


class OpenAICompatibleGuideLlm:
    """Small OpenAI-compatible client isolated from the legacy voice client."""

    def __init__(self, base_url, api_key, model, timeout=20.0):
        self.base_url = str(base_url or "").rstrip("/")
        self.api_key = str(api_key or "")
        self.model = str(model or "")
        self.timeout = float(timeout)

    def answer(self, text, context=None):
        if not self.base_url or not self.api_key or not self.model:
            raise RuntimeError("hospital guide LLM is not configured")
        system = (
            "你是医院导诊机器人，仅用于导诊和一般健康教育。"
            "不得诊断、开处方、调整用药或保证疗效；紧急情况应建议立即联系现场医护或急诊。"
            "回答简短、清楚、适合语音播报。若根据用户意图需要推荐已配置科室，"
            "请在回答末尾附加且只附加一个标记【导诊科室:科室ID】。"
        )
        if context:
            system += "\n可信上下文：" + json.dumps(context, ensure_ascii=False)
        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": str(text)},
            ],
            "temperature": 0.2,
        }, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            self.base_url + "/chat/completions",
            data=body,
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        try:
            return str(payload["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("hospital guide LLM returned no reply") from exc


def build_hospital_guide_llm(environment=None):
    environment = environment if environment is not None else os.environ
    api_key = (
        environment.get("MINIMOVER_HOSPITAL_GUIDE_LLM_API_KEY")
        or environment.get("MINIMOVER_LLM_API_KEY")
        or environment.get("MINIMOVER_API_KEY")
        or environment.get("MINIMOVER_DASHSCOPE_API_KEY")
        or ""
    )
    base_url = environment.get("MINIMOVER_HOSPITAL_GUIDE_LLM_URL") or environment.get("MINIMOVER_LLM_URL")
    if not base_url and api_key:
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model = environment.get("MINIMOVER_HOSPITAL_GUIDE_LLM_MODEL") or environment.get("MINIMOVER_LLM_MODEL") or "qwen-plus"
    if api_key and base_url:
        return OpenAICompatibleGuideLlm(base_url, api_key, model)
    return KnowledgeOnlyGuideLlm()


class HospitalGuideBridge:
    """Serializes finalized ASR turns through one stateful guide session."""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self._lock = threading.Lock()

    def process_final_text(self, text):
        if not isinstance(text, str):
            raise ValueError("text must be a string")
        normalized = text.strip()
        if not normalized:
            raise ValueError("text is required")
        if len(normalized) > MAX_FINAL_TEXT_CHARS:
            raise ValueError("text is too long")
        with self._lock:
            return self.orchestrator.handle(normalized)

    def reset(self):
        with self._lock:
            self.orchestrator.reset()

    def set_guide_event_handler(self, handler):
        with self._lock:
            self.orchestrator._on_guide_event = handler


def register_hospital_guide_bridge(
    app,
    *,
    config_path,
    knowledge_path,
    telemetry_path,
    navigation_client=None,
    llm_client=None,
    memory_turns=6,
    retrieval_limit=3,
    reply_max_chars=180,
    on_guide_event=None,
):
    """Register the real-ASR guide endpoint and return its stateful bridge."""

    guide_config = HospitalGuideConfig.from_path(Path(config_path))
    telemetry = HospitalGuideTelemetry(Path(telemetry_path))
    orchestrator = HospitalGuideOrchestrator(
        guide_config,
        MedicalKnowledgeBase.from_jsonl(Path(knowledge_path)),
        llm_client or build_hospital_guide_llm(),
        navigation_client or HospitalGuideNavigationClient(),
        memory_turns=memory_turns,
        retrieval_limit=retrieval_limit,
        reply_max_chars=reply_max_chars,
        telemetry=telemetry,
        on_guide_event=on_guide_event,
    )
    telemetry.publish(
        history=orchestrator.history(),
        state="AWAKE",
        event_type="bridge_started",
        event_message="医院导诊实时桥接已就绪，等待真实语音最终识别文本。",
    )
    bridge = HospitalGuideBridge(orchestrator)

    @app.route("/api/hospital-guide/turn", methods=["POST"])
    def hospital_guide_turn():
        payload = flask_request.get_json(silent=True)
        text = payload.get("text") if isinstance(payload, dict) else None
        try:
            reply = bridge.process_final_text(text)
        except ValueError as exc:
            return jsonify({"code": 1, "msg": str(exc)}), 400
        return jsonify({"code": 0, "data": {"reply": reply}})

    return bridge
