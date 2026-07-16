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

    def __init__(self, config, knowledge_base, llm_client, car_client, memory_turns=6, retrieval_limit=3, reply_max_chars=180):
        self._config = config
        self._knowledge_base = knowledge_base
        self._llm_client = llm_client
        self._car_client = car_client
        self._memory = ConversationMemory(memory_turns)
        self._retrieval_limit = max(1, min(int(retrieval_limit), 5))
        self._reply_max_chars = max(60, min(int(reply_max_chars), 300))
        self._pending_department_id = None

    def remember(self, user_text, assistant_text):
        self._memory.add_turn(user_text, assistant_text)

    def history(self):
        return self._memory.history()

    def reset(self):
        self._memory.clear()
        self._pending_department_id = None

    def handle(self, text):
        text = str(text or "").strip()
        if not text:
            return "请再说一遍您的导诊需求。"
        if _contains(text, EMERGENCY_HINTS):
            self._pending_department_id = None
            return self._remember_and_return(text, "您描述的情况可能需要紧急处理，请立即联系现场医护人员或前往急诊，不要等待普通门诊。")
        if _contains(text, REJECTION_HINTS):
            self._pending_department_id = None
            return self._remember_and_return(text, "好的，已取消带路请求。如需导诊，请随时告诉我。")
        if self._pending_department_id and _contains(text, CONFIRMATION_HINTS):
            return self._start_pending_navigation(text)

        department = self._config.find_department(text)
        if department:
            self._pending_department_id = department.department_id
            reply = "%s在%s。%s需要我带您去%s吗？" % (
                department.name, department.floor, department.directions, department.name,
            )
            return self._remember_and_return(text, reply)

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
                reply = "%s需要我带您去%s吗？" % (reply.rstrip("。"), self._config.department(department_id).name)
        return self._remember_and_return(text, reply)

    def _start_pending_navigation(self, text):
        department = self._config.department(self._pending_department_id)
        if not department.navigation_enabled:
            return self._remember_and_return(text, "该科室点位尚未配置，请咨询服务台。")
        try:
            self._car_client.navigate_to(department.x, department.y, department.theta)
        except Exception:
            return self._remember_and_return(text, "导航未启动，请联系工作人员或稍后重试。")
        self._pending_department_id = None
        return self._remember_and_return(text, "已开始带您前往%s。%s" % (department.name, department.directions))

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

    def _remember_and_return(self, user_text, reply):
        self.remember(user_text, reply)
        return reply


def _contains(text, labels):
    return any(label in text for label in labels)


def _strip_department_marker(reply):
    match = DEPARTMENT_MARKER.search(reply)
    department_id = match.group(1) if match else None
    return DEPARTMENT_MARKER.sub("", reply).strip(), department_id
