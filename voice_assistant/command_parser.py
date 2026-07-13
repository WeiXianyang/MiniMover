"""Parse the deliberately small, safety-critical voice command vocabulary."""

import re

_STOP_PHRASES = ("\u6025\u505c", "\u505c\u6b62", "\u505c\u4e0b\u6765", "\u505c\u4e0b", "\u522b\u52a8", "\u4e0d\u8981\u52a8")

_PATTERNS = (
    ("stop", _STOP_PHRASES),
    ("spin", ("转圈", "原地转", "旋转一圈", "转个圈")),
    ("backward", ("向后转", "后转", "向后走", "后退")),
    ("left", ("向左转", "左转", "往左转", "向左")),
    ("right", ("向右转", "右转", "往右转", "向右")),
)


def normalize_text(text):
    return re.sub(r"[，。！？、,.!?；;：:‘’“”\" ]", "", (text or "").strip().lower())


def parse_command(text):
    normalized = normalize_text(text)
    if not normalized:
        return None
    for command, phrases in _PATTERNS:
        if any(phrase in normalized for phrase in phrases):
            return {"cmd": command}
    return None
