"""Safe, configuration-driven hospital guidance for the MiniMover demo."""

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path


EMERGENCY_HINTS = ("晕倒", "昏迷", "大量出血", "大出血", "呼吸困难", "抽搐", "意识不清")
REJECTION_HINTS = ("不用", "不需要", "不要", "不去", "取消", "算了", "结束导诊")
CONFIRMATION_HINTS = ("好的", "好", "需要", "可以", "带我去", "去吧", "确认", "是的", "嗯")
DEPARTMENT_MARKER = re.compile(r"【导诊科室:([A-Za-z0-9_-]+)】")


@dataclass(frozen=True)
class Department:
    department_id: str
    name: str
    aliases: tuple
    floor: str
    directions: str
    navigation_enabled: bool
    x: float
    y: float
    theta: float


class HospitalGuideConfig:
    def __init__(self, hospital_name, departments):
        self.hospital_name = hospital_name
        self._departments = {department.department_id: department for department in departments}

    @classmethod
    def from_path(cls, path):
        source = Path(path)
        try:
            payload = json.loads(source.read_text(encoding="utf-8-sig"))
        except (OSError, TypeError, ValueError) as exc:
            raise ValueError("医院导诊配置无法读取") from exc
        if not isinstance(payload, dict):
            raise ValueError("医院导诊配置必须是对象")
        raw_departments = payload.get("departments")
        if not isinstance(raw_departments, list) or not raw_departments:
            raise ValueError("医院导诊配置缺少科室")

        departments = []
        seen_ids = set()
        for raw in raw_departments:
            department = _parse_department(raw)
            if department.department_id in seen_ids:
                raise ValueError("医院导诊配置包含重复科室 ID")
            seen_ids.add(department.department_id)
            departments.append(department)
        return cls(str(payload.get("hospital_name") or "MiniMover 示范医院"), departments)

    def department(self, department_id):
        try:
            return self._departments[department_id]
        except KeyError as exc:
            raise ValueError("未配置的导诊科室") from exc

    def find_department(self, text):
        normalized = str(text or "").strip()
        candidates = []
        for department in self._departments.values():
            for label in (department.name,) + department.aliases:
                if label and label in normalized:
                    candidates.append((len(label), department))
        return max(candidates, key=lambda item: item[0])[1] if candidates else None


def _parse_department(raw):
    if not isinstance(raw, dict):
        raise ValueError("科室配置必须是对象")
    department_id = str(raw.get("id") or "").strip()
    name = str(raw.get("name") or "").strip()
    floor = str(raw.get("floor") or "").strip()
    directions = str(raw.get("directions") or "").strip()
    aliases = tuple(str(item).strip() for item in raw.get("aliases", ()) if str(item).strip())
    navigation = raw.get("navigation")
    if not department_id or not name or not floor or not directions or not aliases or not isinstance(navigation, dict):
        raise ValueError("科室配置缺少必要字段")
    values = []
    for key in ("x", "y", "theta"):
        try:
            value = float(navigation[key])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("导航坐标无效") from exc
        if not math.isfinite(value):
            raise ValueError("导航坐标必须是有限数值")
        values.append(value)
    enabled = navigation.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError("导航启用状态必须是布尔值")
    return Department(department_id, name, aliases, floor, directions, enabled, *values)


class ConversationMemory:
    def __init__(self, turns=6):
        self._turns = max(1, min(int(turns), 12))
        self._messages = []

    def add_turn(self, user_text, assistant_text):
        self._messages.extend((
            {"role": "user", "content": str(user_text or "")},
            {"role": "assistant", "content": str(assistant_text or "")},
        ))
        self._messages = self._messages[-self._turns * 2:]

    def history(self):
        return list(self._messages)

    def clear(self):
        self._messages = []


class HospitalGuideOrchestrator:
    """Turns non-motion utterances into safe, confirmation-gated guide replies."""

    def __init__(
        self,
        config,
        knowledge_base,
        llm_client,
        car_client,
        memory_turns=6,
        retrieval_limit=3,
        reply_max_chars=180,
        telemetry=None,
        on_guide_event=None,
    ):
        self._config = config
        self._knowledge_base = knowledge_base
        self._llm_client = llm_client
        self._car_client = car_client
        self._memory = ConversationMemory(memory_turns)
        self._retrieval_limit = max(1, min(int(retrieval_limit), 5))
        self._reply_max_chars = max(60, min(int(reply_max_chars), 300))
        self._pending_department_id = None
        self._telemetry = telemetry
        self._on_guide_event = on_guide_event

    def remember(self, user_text, assistant_text):
        self._memory.add_turn(user_text, assistant_text)

    def history(self):
        return self._memory.history()

    def reset(self):
        self._memory.clear()
        self._pending_department_id = None
        if self._telemetry:
            try:
                self._telemetry.reset()
            except Exception:
                pass

    def handle(self, text):
        text = str(text or "").strip()
        if not text:
            return self._remember_and_return(
                text, "\u8bf7\u518d\u8bf4\u4e00\u904d\u60a8\u7684\u5bfc\u8bca\u9700\u6c42\u3002", event_type="empty_input",
            )
        if _contains(text, EMERGENCY_HINTS):
            self._pending_department_id = None
            return self._remember_and_return(
                text,
                "\u60a8\u63cf\u8ff0\u7684\u60c5\u51b5\u53ef\u80fd\u9700\u8981\u7d27\u6025\u5904\u7406\uff0c\u8bf7\u7acb\u5373\u8054\u7cfb\u73b0\u573a\u533b\u62a4\u4eba\u5458\u6216\u524d\u5f80\u6025\u8bca\uff0c\u4e0d\u8981\u7b49\u5f85\u666e\u901a\u95e8\u8bca\u3002",
                event_type="emergency",
            )
        if _contains(text, REJECTION_HINTS):
            self._pending_department_id = None
            return self._remember_and_return(
                text, "\u597d\u7684\uff0c\u5df2\u53d6\u6d88\u5e26\u8def\u8bf7\u6c42\u3002\u5982\u9700\u5bfc\u8bca\uff0c\u8bf7\u968f\u65f6\u544a\u8bc9\u6211\u3002", event_type="guide_cancelled",
            )
        if self._pending_department_id and _contains(text, CONFIRMATION_HINTS):
            return self._start_pending_navigation(text)

        department = self._config.find_department(text)
        if department:
            self._pending_department_id = department.department_id
            reply = "%s\u5728%s\u3002%s\u9700\u8981\u6211\u5e26\u60a8\u53bb%s\u5417\uff1f" % (
                department.name, department.floor, department.directions, department.name,
            )
            self._emit_guide_event("department_matched", department.department_id)
            return self._remember_and_return(text, reply, event_type="department_matched")

        evidence = self._knowledge_base.search(text, self._retrieval_limit)
        reply = self._ask_llm(text, evidence)
        reply, department_id = _strip_department_marker(reply)
        if department_id:
            try:
                self._config.department(department_id)
            except ValueError:
                pass
            else:
                self._pending_department_id = department_id
                reply = "%s\u9700\u8981\u6211\u5e26\u60a8\u53bb%s\u5417\uff1f" % (
                    reply.rstrip("\u3002"), self._config.department(department_id).name,
                )
                self._emit_guide_event("department_matched", department_id)
        return self._remember_and_return(
            text,
            reply,
            event_type="llm_department_matched" if department_id else "knowledge_answer",
            evidence_count=len(evidence),
        )

    def _start_pending_navigation(self, text):
        department = self._config.department(self._pending_department_id)
        if not department.navigation_enabled:
            self._pending_department_id = None
            return self._remember_and_return(
                text,
                "\u8be5\u79d1\u5ba4\u70b9\u4f4d\u5c1a\u672a\u914d\u7f6e\uff0c\u8bf7\u54a8\u8be2\u670d\u52a1\u53f0\u3002",
                event_type="navigation_not_configured",
                navigation={
                    "requested": False,
                    "status": "not_configured",
                    "message": "\u8be5\u79d1\u5ba4\u70b9\u4f4d\u5c1a\u672a\u914d\u7f6e\u3002",
                    "department": self._department_payload(department),
                },
            )
        try:
            self._car_client.navigate_to(department.x, department.y, department.theta)
        except Exception:
            self._pending_department_id = None
            return self._remember_and_return(
                text,
                "\u5bfc\u822a\u672a\u542f\u52a8\uff0c\u8bf7\u8054\u7cfb\u5de5\u4f5c\u4eba\u5458\u6216\u7a0d\u540e\u91cd\u8bd5\u3002",
                event_type="navigation_failed",
                navigation={
                    "requested": False,
                    "status": "failed",
                    "message": "\u5bfc\u822a\u8c03\u7528\u5931\u8d25\uff0c\u672a\u4e0b\u53d1\u76ee\u6807\u3002",
                    "department": self._department_payload(department),
                },
            )
        self._pending_department_id = None
        self._emit_guide_event("navigation_started", department.department_id)
        return self._remember_and_return(
            text,
            "\u5df2\u5f00\u59cb\u5e26\u60a8\u524d\u5f80%s\u3002%s" % (department.name, department.directions),
            event_type="navigation_started",
            navigation={
                "requested": True,
                "status": "started",
                "message": "\u5df2\u5f00\u59cb\u5e26\u60a8\u524d\u5f80%s\u3002" % department.name,
                "department": self._department_payload(department),
            },
        )

    def _emit_guide_event(self, event_type, department_id):
        if event_type not in {"department_matched", "navigation_started"}:
            return
        if not isinstance(department_id, str) or not department_id:
            return
        handler = self._on_guide_event
        if not callable(handler):
            return
        try:
            handler({"type": event_type, "department_id": department_id})
        except Exception:
            pass

    def _ask_llm(self, text, evidence):
        if not self._llm_client:
            return "导诊服务暂时不可用，请咨询服务台。"
        context = {
            "history": self.history(),
            "medical_evidence": evidence,
            "system_rules": "仅用于导诊与一般健康教育；不诊断、不处方、不调整用药；紧急情况优先建议急诊或现场医护。",
            "departments": [
                {"id": department.department_id, "name": department.name, "floor": department.floor}
                for department in self._config._departments.values()
            ],
        }
        try:
            reply = self._llm_client.answer(text, context=context)
        except Exception:
            return "导诊服务暂时不可用，请咨询服务台。"
        if not isinstance(reply, str) or not reply.strip():
            return "我暂时无法确认，请咨询服务台。"
        return reply.strip()[:self._reply_max_chars]

    def _department_payload(self, department):
        return {
            "id": department.department_id,
            "name": department.name,
            "floor": department.floor,
            "navigation_enabled": department.navigation_enabled,
        }

    def _pending_department_payload(self):
        if not self._pending_department_id:
            return None
        try:
            return self._department_payload(self._config.department(self._pending_department_id))
        except ValueError:
            return None

    def _remember_and_return(self, user_text, reply, event_type="reply", evidence_count=0, navigation=None):
        self.remember(user_text, reply)
        if self._telemetry:
            try:
                self._telemetry.publish(
                    history=self.history(),
                    state="WAITING_CONFIRMATION" if self._pending_department_id else "AWAKE",
                    pending_department=self._pending_department_payload(),
                    evidence_count=evidence_count,
                    event_type=event_type,
                    event_message=reply,
                    navigation=navigation,
                )
            except Exception:
                pass
        return reply


def _contains(text, labels):
    return any(label in text for label in labels)


def _strip_department_marker(reply):
    match = DEPARTMENT_MARKER.search(reply)
    department_id = match.group(1) if match else None
    return DEPARTMENT_MARKER.sub("", reply).strip(), department_id
