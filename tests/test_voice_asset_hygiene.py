from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOICE_ASSETS = [
    ROOT / "REASONIX_ASR_PITFALLS.md",
    ROOT / "REASONIX_TTS_ASR_PITFALLS.md",
    ROOT / "dashboard.html",
    ROOT / "launch_asr.py",
    *sorted((ROOT / "tools").glob("*.py")),
]


def test_voice_assets_do_not_contain_plaintext_credentials() -> None:
    api_key = re.compile(r"sk-ws-[A-Za-z0-9._-]{20,}")
    python_password = re.compile(r"password\s*=\s*['\"][^<{][^'\"]+['\"]", re.IGNORECASE)
    documented_password = re.compile(r"密码\s*`(?!<)[^`]+`")

    findings: list[str] = []
    for path in VOICE_ASSETS:
        text = path.read_text(encoding="utf-8")
        for pattern in (api_key, python_password, documented_password):
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT)} matches {pattern.pattern}")

    assert not findings, "Plaintext credentials found:\n" + "\n".join(findings)


def test_dashboard_does_not_render_monitor_messages_with_inner_html() -> None:
    dashboard = (ROOT / "dashboard.html").read_text(encoding="utf-8")
    assert ".innerHTML" not in dashboard


def test_voice_utility_scripts_are_import_safe() -> None:
    scripts = [ROOT / "launch_asr.py", *sorted((ROOT / "tools").glob("*.py"))]
    missing_guards: list[str] = []

    for path in scripts:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        has_guard = any(
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
            and any(isinstance(value, ast.Constant) and value.value == "__main__" for value in node.test.comparators)
            for node in tree.body
        )
        if not has_guard:
            missing_guards.append(str(path.relative_to(ROOT)))

    assert not missing_guards, "Scripts missing __main__ guards:\n" + "\n".join(missing_guards)
