"""Safe, configuration-driven hospital guidance for the MiniMover demo."""

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


EMERGENCY_HINTS = {
    "zh": ("\u6655\u5012", "\u660f\u8ff7", "\u5927\u91cf\u51fa\u8840", "\u5927\u51fa\u8840", "\u547c\u5438\u56f0\u96be", "\u62bd\u6410", "\u610f\u8bc6\u4e0d\u6e05"),
    "en": ("fainted", "unconscious", "heavy bleeding", "difficulty breathing", "seizure"),
    "fr": ("\u00e9vanoui", "inconscient", "saignement abondant", "difficult\u00e9 \u00e0 respirer", "convulsions"),
}
REJECTION_HINTS = {
    "zh": ("\u4e0d\u7528", "\u4e0d\u9700\u8981", "\u4e0d\u8981", "\u4e0d\u53bb", "\u53d6\u6d88", "\u7b97\u4e86", "\u7ed3\u675f\u5bfc\u8bca"),
    "en": ("cancel navigation", "cancel", "never mind", "no thanks", "don't take me", "do not take me", "stop navigation"),
    "fr": ("annulez la navigation", "annuler", "non merci", "pas besoin", "ne m'emmenez pas", "arr\u00eatez la navigation"),
}
CONFIRMATION_HINTS = {
    "zh": ("\u597d\u7684", "\u597d", "\u9700\u8981", "\u53ef\u4ee5", "\u5e26\u6211\u53bb", "\u53bb\u5427", "\u786e\u8ba4", "\u662f\u7684", "\u55ef"),
    "en": ("yes", "okay", "ok", "take me", "guide me", "please do", "confirm", "let's go"),
    "fr": ("oui", "d'accord", "emmenez-moi", "emmenez moi", "conduisez-moi", "allez-y", "je confirme"),
}
FRENCH_LANGUAGE_HINTS = (
    "j'ai", "j ai", "mal a la tete", "ou se trouve", "emmenez-moi", "emmenez moi",
    "service de medecine", "medecine interne", "annulez", "oui", "non merci",
)
DEPARTMENT_DISPLAY_NAMES = {
    "emergency": {"en": "Emergency Department", "fr": "le service des urgences"},
    "internal_medicine": {"en": "Internal Medicine", "fr": "le service de m\u00e9decine interne"},
    "surgery": {"en": "Surgery", "fr": "le service de chirurgie"},
    "pediatrics": {"en": "Pediatrics", "fr": "le service de p\u00e9diatrie"},
    "obstetrics_gynecology": {"en": "Obstetrics and Gynecology", "fr": "le service de gyn\u00e9cologie-obst\u00e9trique"},
    "pharmacy": {"en": "Pharmacy", "fr": "la pharmacie"},
    "laboratory": {"en": "Laboratory", "fr": "le laboratoire"},
    "imaging": {"en": "Medical Imaging", "fr": "le service d'imagerie m\u00e9dicale"},
}
FLOOR_DISPLAY_NAMES = {
    "\u4e00\u5c42": {"en": "first floor", "fr": "rez-de-chauss\u00e9e"},
    "\u4e8c\u5c42": {"en": "second floor", "fr": "deuxi\u00e8me \u00e9tage"},
    "\u4e09\u5c42": {"en": "third floor", "fr": "troisi\u00e8me \u00e9tage"},
}
DEPARTMENT_MARKER = re.compile(r"\u3010\u5bfc\u8bca\u79d1\u5ba4:([A-Za-z0-9_-]+)\u3011")

class NavigationRequestError(RuntimeError):
    """A safe user-facing reason that prevented goal submission."""

    def __init__(self, reason="\u5bfc\u822a\u670d\u52a1\u6682\u65f6\u4e0d\u53ef\u7528"):
        cleaned = " ".join(str(reason or "").split()).strip()
        self.reason = (cleaned or "\u5bfc\u822a\u670d\u52a1\u6682\u65f6\u4e0d\u53ef\u7528")[:160]
        super().__init__(self.reason)



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
        normalized = _normalize_text(text)
        candidates = []
        for department in self._departments.values():
            for label in (department.name,) + department.aliases:
                normalized_label = _normalize_text(label)
                if normalized_label and normalized_label in normalized:
                    candidates.append((len(normalized_label), department))
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
        self._active_navigation_department_id = None
        self._telemetry = telemetry
        self._on_guide_event = on_guide_event

    def remember(self, user_text, assistant_text):
        self._memory.add_turn(user_text, assistant_text)

    def history(self):
        return self._memory.history()

    def reset(self):
        self._memory.clear()
        self._pending_department_id = None
        self._active_navigation_department_id = None
        if self._telemetry:
            try:
                self._telemetry.reset()
            except Exception:
                pass

    def handle(self, text):
        text = str(text or "").strip()
        language = _detect_language(text)
        if not text:
            return self._remember_and_return(
                text, _localized_message("empty_input", language), event_type="empty_input",
            )
        if _contains(text, EMERGENCY_HINTS[language]):
            self._pending_department_id = None
            return self._remember_and_return(
                text,
                _localized_message("emergency", language),
                event_type="emergency",
            )
        if _contains(text, REJECTION_HINTS[language]):
            self._pending_department_id = None
            if self._active_navigation_department_id:
                active_department = self._config.department(self._active_navigation_department_id)
                try:
                    self._car_client.cancel_navigation()
                except NavigationRequestError as exc:
                    reason = exc.reason.rstrip("\u3002.!\uff01?\uff1f")
                    reply = _navigation_cancel_rejection_reply(reason, language)
                    return self._remember_and_return(
                        text,
                        reply,
                        event_type="navigation_cancel_failed",
                        navigation={
                            "requested": False,
                            "status": "cancel_failed",
                            "message": reply,
                            "department": self._department_payload(active_department),
                        },
                    )
                except Exception:
                    reply = _localized_message("navigation_cancel_failed", language)
                    return self._remember_and_return(
                        text,
                        reply,
                        event_type="navigation_cancel_failed",
                        navigation={
                            "requested": False,
                            "status": "cancel_failed",
                            "message": reply,
                            "department": self._department_payload(active_department),
                        },
                    )
                self._active_navigation_department_id = None
                reply = _localized_message("cancelled", language)
                return self._remember_and_return(
                    text,
                    reply,
                    event_type="navigation_cancelled",
                    navigation={
                        "requested": False,
                        "status": "cancelled",
                        "message": reply,
                        "department": self._department_payload(active_department),
                    },
                )
            return self._remember_and_return(
                text, _localized_message("cancelled", language), event_type="guide_cancelled",
            )
        if self._pending_department_id and _contains(text, CONFIRMATION_HINTS[language]):
            return self._start_pending_navigation(text, language)
        if self._active_navigation_department_id and _contains(text, CONFIRMATION_HINTS[language]):
            active_department = self._config.department(self._active_navigation_department_id)
            mentioned_department = self._config.find_department(text)
            if mentioned_department is None or mentioned_department.department_id == active_department.department_id:
                reply = _navigation_already_started_reply(active_department, language)
                return self._remember_and_return(
                    text,
                    reply,
                    event_type="navigation_already_started",
                    navigation={
                        "requested": False,
                        "status": "already_started",
                        "message": reply,
                        "department": self._department_payload(active_department),
                    },
                )

        department = self._config.find_department(text)
        if department:
            self._pending_department_id = department.department_id
            reply = _department_confirmation_reply(department, language)
            self._emit_guide_event("department_matched", department.department_id)
            return self._remember_and_return(text, reply, event_type="department_matched")

        evidence = self._knowledge_base.search(text, self._retrieval_limit)
        reply = self._ask_llm(text, evidence, language)
        reply, department_id = _strip_department_marker(reply)
        if department_id:
            try:
                department = self._config.department(department_id)
            except ValueError:
                department_id = None
            else:
                self._pending_department_id = department_id
                reply = _append_department_confirmation(reply, department, language)
                self._emit_guide_event("department_matched", department_id)
        return self._remember_and_return(
            text,
            reply,
            event_type="llm_department_matched" if department_id else "knowledge_answer",
            evidence_count=len(evidence),
        )

    def _start_pending_navigation(self, text, language):
        department = self._config.department(self._pending_department_id)
        if not department.navigation_enabled:
            self._pending_department_id = None
            reply = _localized_message("navigation_not_configured", language)
            return self._remember_and_return(
                text,
                reply,
                event_type="navigation_not_configured",
                navigation={
                    "requested": False,
                    "status": "not_configured",
                    "message": reply,
                    "department": self._department_payload(department),
                },
            )
        try:
            self._car_client.navigate_to(department.x, department.y, department.theta)
        except NavigationRequestError as exc:
            self._pending_department_id = None
            reason = exc.reason.rstrip("\u3002.!\uff01?\uff1f")
            reply = _navigation_rejection_reply(reason, language)
            return self._remember_and_return(
                text,
                reply,
                event_type="navigation_failed",
                navigation={
                    "requested": False,
                    "status": "failed",
                    "message": reply,
                    "department": self._department_payload(department),
                },
            )
        except Exception:
            self._pending_department_id = None
            reply = _localized_message("navigation_failed", language)
            return self._remember_and_return(
                text,
                reply,
                event_type="navigation_failed",
                navigation={
                    "requested": False,
                    "status": "failed",
                    "message": reply,
                    "department": self._department_payload(department),
                },
            )
        self._pending_department_id = None
        self._active_navigation_department_id = department.department_id
        self._emit_guide_event("navigation_started", department.department_id)
        reply = _navigation_started_reply(department, language)
        return self._remember_and_return(
            text,
            reply,
            event_type="navigation_started",
            navigation={
                "requested": True,
                "status": "started",
                "message": reply,
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

    def _ask_llm(self, text, evidence, language):
        if not self._llm_client:
            return _localized_message("guide_unavailable", language)
        context = {
            "history": self.history(),
            "medical_evidence": evidence,
            "reply_language": language,
            "system_rules": _localized_system_rules(language),
            "departments": [
                {"id": department.department_id, "name": department.name, "floor": department.floor}
                for department in self._config._departments.values()
            ],
        }
        try:
            reply = self._llm_client.answer(text, context=context)
        except Exception:
            return _localized_message("guide_unavailable", language)
        if not isinstance(reply, str) or not reply.strip():
            return _localized_message("guide_uncertain", language)
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


def _normalize_text(text):
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    normalized = normalized.replace("\u2019", "'").replace("\u2018", "'")
    return " ".join(normalized.casefold().split())


def _fold_accents(text):
    return "".join(
        char for char in unicodedata.normalize("NFKD", _normalize_text(text))
        if not unicodedata.combining(char)
    )


def _detect_language(text):
    normalized = _normalize_text(text)
    if re.search(r"[\u3400-\u9fff]", normalized):
        return "zh"
    folded = _fold_accents(normalized)
    if re.search(r"[\u00e0\u00e2\u00e6\u00e7\u00e9\u00e8\u00ea\u00eb\u00ee\u00ef\u00f4\u0153\u00f9\u00fb\u00fc\u00ff]", normalized):
        return "fr"
    if any(hint in folded for hint in FRENCH_LANGUAGE_HINTS):
        return "fr"
    if re.search(r"[a-z]", normalized):
        return "en"
    return "zh"


def _contains(text, labels):
    normalized = _normalize_text(text)
    folded = _fold_accents(normalized)
    return any(
        _normalize_text(label) in normalized or _fold_accents(label) in folded
        for label in labels
        if str(label or "").strip()
    )


def _department_name(department, language):
    if language == "zh":
        return department.name
    return DEPARTMENT_DISPLAY_NAMES.get(department.department_id, {}).get(
        language, department.name,
    )


def _floor_name(department, language):
    if language == "zh":
        return department.floor
    return FLOOR_DISPLAY_NAMES.get(department.floor, {}).get(language, department.floor)


def _capitalize_sentence(value):
    value = str(value or "")
    return value[:1].upper() + value[1:]


def _french_destination(department):
    name = _department_name(department, "fr")
    if name.startswith("le "):
        return "au " + name[3:]
    if name.startswith("la "):
        return "\u00e0 la " + name[3:]
    if name.startswith("l'"):
        return "\u00e0 " + name
    if name.startswith("les "):
        return "aux " + name[4:]
    return "\u00e0 " + name


def _department_confirmation_reply(department, language):
    if language == "fr":
        return "%s se trouve au %s. Voulez-vous que je vous y accompagne ?" % (
            _capitalize_sentence(_department_name(department, language)),
            _floor_name(department, language),
        )
    if language == "en":
        return "%s is on the %s. Would you like me to guide you there?" % (
            _department_name(department, language), _floor_name(department, language),
        )
    return "%s\u5728%s\u3002%s\u9700\u8981\u6211\u5e26\u60a8\u53bb%s\u5417\uff1f" % (
        department.name, department.floor, department.directions, department.name,
    )


def _append_department_confirmation(reply, department, language):
    cleaned = str(reply or "").rstrip(" \u3002.!\uff01?\uff1f")
    if language == "fr":
        return "%s. Voulez-vous que je vous accompagne jusqu'%s ?" % (
            cleaned, _french_destination(department),
        )
    if language == "en":
        return "%s. Would you like me to guide you to %s?" % (
            cleaned, _department_name(department, language),
        )
    return "%s\u3002\u9700\u8981\u6211\u5e26\u60a8\u53bb%s\u5417\uff1f" % (cleaned, department.name)


def _navigation_started_reply(department, language):
    if language == "fr":
        return "Je commence \u00e0 vous guider vers %s." % _department_name(department, language)
    if language == "en":
        return "I have started guiding you to %s." % _department_name(department, language)
    return "\u5df2\u5f00\u59cb\u5e26\u60a8\u524d\u5f80%s\u3002%s" % (department.name, department.directions)


def _navigation_already_started_reply(department, language):
    if language == "fr":
        return "Je vous guide d\u00e9j\u00e0 vers %s." % _department_name(department, language)
    if language == "en":
        return "I am already guiding you to %s." % _department_name(department, language)
    return "\u6b63\u5728\u5e26\u60a8\u524d\u5f80%s\u3002%s" % (department.name, department.directions)


def _navigation_rejection_reply(reason, language):
    if language == "fr":
        return (
            "Le contr\u00f4le de s\u00e9curit\u00e9 de la navigation a \u00e9chou\u00e9 : %s. "
            "Le v\u00e9hicule ne bougera pas. Veuillez contacter le personnel."
        ) % reason
    if language == "en":
        return (
            "The navigation safety check failed: %s. The vehicle will not move. "
            "Please contact a staff member."
        ) % reason
    return "\u5bfc\u822a\u5b89\u5168\u68c0\u67e5\u672a\u901a\u8fc7\uff1a%s\u3002\u8f66\u8f86\u4e0d\u4f1a\u79fb\u52a8\uff0c\u8bf7\u8054\u7cfb\u5de5\u4f5c\u4eba\u5458\u3002" % reason


def _navigation_cancel_rejection_reply(reason, language):
    if language == "fr":
        return (
            "Je ne peux pas confirmer l'annulation de la navigation : %s. "
            "Utilisez imm\u00e9diatement l'arr\u00eat d'urgence et contactez le personnel."
        ) % reason
    if language == "en":
        return (
            "I could not confirm navigation cancellation: %s. "
            "Use the hardware emergency stop immediately and contact a staff member."
        ) % reason
    return "\u65e0\u6cd5\u786e\u8ba4\u5bfc\u822a\u5df2\u53d6\u6d88\uff1a%s\u3002\u8bf7\u7acb\u5373\u4f7f\u7528\u786c\u4ef6\u6025\u505c\uff0c\u5e76\u8054\u7cfb\u5de5\u4f5c\u4eba\u5458\u3002" % reason


def _localized_message(key, language):
    messages = {
        "empty_input": {
            "zh": "\u8bf7\u518d\u8bf4\u4e00\u904d\u60a8\u7684\u5bfc\u8bca\u9700\u6c42\u3002",
            "en": "Please repeat your hospital guidance request.",
            "fr": "Veuillez r\u00e9p\u00e9ter votre demande d'orientation dans l'h\u00f4pital.",
        },
        "emergency": {
            "zh": "\u60a8\u63cf\u8ff0\u7684\u60c5\u51b5\u53ef\u80fd\u9700\u8981\u7d27\u6025\u5904\u7406\uff0c\u8bf7\u7acb\u5373\u8054\u7cfb\u73b0\u573a\u533b\u62a4\u4eba\u5458\u6216\u524d\u5f80\u6025\u8bca\uff0c\u4e0d\u8981\u7b49\u5f85\u666e\u901a\u95e8\u8bca\u3002",
            "en": "This may require urgent care. Contact on-site medical staff or go to the Emergency Department immediately.",
            "fr": "Cette situation peut n\u00e9cessiter des soins urgents. Contactez imm\u00e9diatement le personnel m\u00e9dical ou rendez-vous aux urgences.",
        },
        "cancelled": {
            "zh": "\u597d\u7684\uff0c\u5df2\u53d6\u6d88\u5e26\u8def\u8bf7\u6c42\u3002\u5982\u9700\u5bfc\u8bca\uff0c\u8bf7\u968f\u65f6\u544a\u8bc9\u6211\u3002",
            "en": "Okay, the guidance request has been cancelled. Ask me again whenever you need directions.",
            "fr": "D'accord, la demande d'accompagnement est annul\u00e9e. Demandez-moi de nouveau si vous avez besoin d'aide.",
        },
        "navigation_not_configured": {
            "zh": "\u8be5\u79d1\u5ba4\u70b9\u4f4d\u5c1a\u672a\u914d\u7f6e\uff0c\u8bf7\u54a8\u8be2\u670d\u52a1\u53f0\u3002",
            "en": "Navigation to that department is not configured. Please ask the service desk.",
            "fr": "La navigation vers ce service n'est pas configur\u00e9e. Veuillez vous adresser \u00e0 l'accueil.",
        },
        "navigation_failed": {
            "zh": "\u5bfc\u822a\u8bf7\u6c42\u5931\u8d25\uff0c\u8f66\u8f86\u4e0d\u4f1a\u79fb\u52a8\uff0c\u8bf7\u8054\u7cfb\u5de5\u4f5c\u4eba\u5458\u6216\u7a0d\u540e\u91cd\u8bd5\u3002",
            "en": "The navigation request failed. The vehicle will not move. Please contact a staff member.",
            "fr": "La demande de navigation a \u00e9chou\u00e9. Le v\u00e9hicule ne bougera pas. Veuillez contacter le personnel.",
        },
        "navigation_cancel_failed": {
            "zh": "\u65e0\u6cd5\u786e\u8ba4\u5bfc\u822a\u5df2\u53d6\u6d88\u3002\u8bf7\u7acb\u5373\u4f7f\u7528\u786c\u4ef6\u6025\u505c\uff0c\u5e76\u8054\u7cfb\u5de5\u4f5c\u4eba\u5458\u3002",
            "en": "I could not confirm navigation cancellation. Use the hardware emergency stop immediately and contact a staff member.",
            "fr": "Je ne peux pas confirmer l'annulation de la navigation. Utilisez imm\u00e9diatement l'arr\u00eat d'urgence et contactez le personnel.",
        },
        "guide_unavailable": {
            "zh": "\u5bfc\u8bca\u670d\u52a1\u6682\u65f6\u4e0d\u53ef\u7528\uff0c\u8bf7\u54a8\u8be2\u670d\u52a1\u53f0\u3002",
            "en": "The guidance service is temporarily unavailable. Please ask the service desk.",
            "fr": "Le service d'orientation est temporairement indisponible. Veuillez vous adresser \u00e0 l'accueil.",
        },
        "guide_uncertain": {
            "zh": "\u6211\u6682\u65f6\u65e0\u6cd5\u786e\u8ba4\uff0c\u8bf7\u54a8\u8be2\u670d\u52a1\u53f0\u3002",
            "en": "I cannot confirm that right now. Please ask the service desk.",
            "fr": "Je ne peux pas le confirmer pour le moment. Veuillez vous adresser \u00e0 l'accueil.",
        },
    }
    return messages[key].get(language, messages[key]["zh"])


def _localized_system_rules(language):
    if language == "fr":
        return "Orientation et information g\u00e9n\u00e9rale uniquement; aucun diagnostic, aucune prescription ni modification de traitement; en urgence, recommander le personnel m\u00e9dical ou les urgences."
    if language == "en":
        return "Hospital guidance and general health education only; no diagnosis, prescriptions, or medication changes; emergencies must be referred to on-site staff or the Emergency Department."
    return "\u4ec5\u7528\u4e8e\u5bfc\u8bca\u4e0e\u4e00\u822c\u5065\u5eb7\u6559\u80b2\uff1b\u4e0d\u8bca\u65ad\u3001\u4e0d\u5904\u65b9\u3001\u4e0d\u8c03\u6574\u7528\u836f\uff1b\u7d27\u6025\u60c5\u51b5\u4f18\u5148\u5efa\u8bae\u6025\u8bca\u6216\u73b0\u573a\u533b\u62a4\u3002"


def _strip_department_marker(reply):
    match = DEPARTMENT_MARKER.search(reply)
    department_id = match.group(1) if match else None
    return DEPARTMENT_MARKER.sub("", reply).strip(), department_id
