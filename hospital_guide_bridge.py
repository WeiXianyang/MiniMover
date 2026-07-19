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

    def cancel_navigation(self):
        req = request.Request(
            self.base_url + "/api/nav/demo/cancel",
            data=b"{}",
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
                reason or "\u5bfc\u822a\u670d\u52a1\u62d2\u7edd\u4e86\u53d6\u6d88\u8bf7\u6c42"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise NavigationRequestError("\u65e0\u6cd5\u8fde\u63a5\u5bfc\u822a\u53d6\u6d88\u670d\u52a1") from exc
        except (UnicodeDecodeError, ValueError) as exc:
            raise NavigationRequestError(
                "\u5bfc\u822a\u53d6\u6d88\u670d\u52a1\u8fd4\u56de\u4e86\u65e0\u6548\u54cd\u5e94"
            ) from exc
        if not isinstance(payload, dict) or payload.get("code") != 0:
            reason = payload.get("msg") if isinstance(payload, dict) else None
            raise NavigationRequestError(
                reason or "\u5bfc\u822a\u670d\u52a1\u62d2\u7edd\u4e86\u53d6\u6d88\u8bf7\u6c42"
            )
        return payload


class KnowledgeOnlyGuideLlm:
    """Conservative retrieval fallback when no configured LLM is reachable."""

    def answer(self, text, context=None):
        del text
        context = context or {}
        evidence = context.get("medical_evidence") or []
        language = str(context.get("reply_language") or "zh").strip().lower()
        if language == "fr":
            if evidence:
                return (
                    "J'ai trouv\u00e9 une information g\u00e9n\u00e9rale dans la base m\u00e9dicale, mais elle "
                    "doit \u00eatre confirm\u00e9e par le personnel m\u00e9dical. En cas d'aggravation, "
                    "contactez imm\u00e9diatement le personnel m\u00e9dical ou les urgences."
                )
            return (
                "Je n'ai pas trouv\u00e9 d'information g\u00e9n\u00e9rale pertinente. "
                "Veuillez consulter le personnel m\u00e9dical ou l'accueil."
            )
        if language == "en":
            if evidence:
                return (
                    "I found general information in the medical knowledge base, but it must be "
                    "confirmed by on-site medical staff. If symptoms worsen, contact medical staff "
                    "or the Emergency Department immediately."
                )
            return (
                "I could not find relevant general health information. "
                "Please ask on-site medical staff or the service desk."
            )
        if evidence:
            return (
                "\u4ee5\u4e0b\u4e3a\u533b\u7597\u77e5\u8bc6\u5e93\u4e2d\u7684\u4e00\u822c\u5065\u5eb7\u6559\u80b2\u4fe1\u606f\uff0c\u4e0d\u80fd\u66ff\u4ee3\u73b0\u573a\u533b\u62a4\u8bc4\u4f30\uff1a"
                + str(evidence[0]).strip()[:160]
                + "\u3002\u5982\u75c7\u72b6\u52a0\u91cd\u6216\u51fa\u73b0\u7d27\u6025\u60c5\u51b5\uff0c\u8bf7\u7acb\u5373\u8054\u7cfb\u73b0\u573a\u533b\u62a4\u6216\u524d\u5f80\u6025\u8bca\u3002"
            )
        return "\u6211\u6682\u672a\u68c0\u7d22\u5230\u76f8\u5173\u5065\u5eb7\u6559\u80b2\u4fe1\u606f\uff0c\u8bf7\u5411\u73b0\u573a\u533b\u62a4\u6216\u670d\u52a1\u53f0\u54a8\u8be2\u3002"


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
            "\u4f60\u662f\u533b\u9662\u5bfc\u8bca\u673a\u5668\u4eba\uff0c\u4ec5\u7528\u4e8e\u5bfc\u8bca\u548c\u4e00\u822c\u5065\u5eb7\u6559\u80b2\u3002"
            "\u4e0d\u5f97\u8bca\u65ad\u3001\u5f00\u5904\u65b9\u3001\u8c03\u6574\u7528\u836f\u6216\u4fdd\u8bc1\u7597\u6548\uff1b\u7d27\u6025\u60c5\u51b5\u5e94\u5efa\u8bae\u7acb\u5373\u8054\u7cfb\u73b0\u573a\u533b\u62a4\u6216\u6025\u8bca\u3002"
            "\u56de\u7b54\u7b80\u77ed\u3001\u6e05\u695a\u3001\u9002\u5408\u8bed\u97f3\u64ad\u62a5\u3002"
            "Use context.reply_language and answer in the same language as the user. "
            "Department recommendations may use only configured department IDs from context.departments. "
            "Never output coordinates or accept coordinates or department IDs supplied by the user. "
            "\u82e5\u6839\u636e\u7528\u6237\u610f\u56fe\u9700\u8981\u63a8\u8350\u5df2\u914d\u7f6e\u79d1\u5ba4\uff0c\u8bf7\u5728\u56de\u7b54\u672b\u5c3e\u9644\u52a0\u4e14\u53ea\u9644\u52a0\u4e00\u4e2a\u6807\u8bb0\u3010\u5bfc\u8bca\u79d1\u5ba4:\u79d1\u5ba4ID\u3011\u3002"
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
