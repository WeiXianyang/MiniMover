# Hospital Guide Voice Robot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a demo-only hospital-guide voice flow with bounded multi-turn memory, local medical-knowledge retrieval, safe department routing, and explicit-confirmation navigation over the existing map-point API.

**Architecture:** Add pure-Python medical knowledge, hospital configuration, and conversation orchestration modules beneath `voice_assistant/`. The existing `VoiceService` preserves motion-command priority and delegates only unsupported text to the guide orchestrator; the orchestrator uses configured department IDs—not LLM-generated coordinates—to authorize `CarClient.navigate_to`.

**Tech Stack:** Python 3.8 standard library, unittest, existing OpenAI-compatible HTTP client, existing `/api/navigate` endpoint, JSON/JSONL files.

---

## File structure

| Path | Responsibility |
| --- | --- |
| `voice_assistant/medical_knowledge.py` | Dependency-free JSONL loader and Chinese character n-gram retrieval. |
| `voice_assistant/hospital_guide.py` | Validated department configuration, bounded memory, emergency/confirmation handling, and LLM orchestration. |
| `voice_assistant/data/hospital_guide_template.json` | Demo departments and placeholders for verified map points; navigation is disabled until a point is verified. |
| `voice_assistant/config.py` | Environment-backed hospital-guide configuration. |
| `voice_assistant/llm_client.py` | Structured chat-message support while retaining the old `answer` interface. |
| `voice_assistant/car_client.py` | Validated call to the existing `/api/navigate` endpoint. |
| `voice_assistant/voice_service.py` | Delegates non-motion text to the hospital guide and exposes memory reset. |
| `voice_assistant/wake_word.py` | Resets guide state at a new wake session and wake-window expiry. |
| `scripts/fetch_shortmedkg.py` | Explicit, pinned, non-runtime download of the medical JSONL corpus and provenance metadata. |
| `tests/test_hospital_guide.py` | Pure-Python behavior tests for retrieval, memory, routing, safety, and voice integration. |
| `voice_assistant/README.md` | Hospital-guide setup, point mapping, constraints, and demo commands. |

### Task 1: Add failing tests for the new hospital-guide contracts

**Files:**
- Create: `tests/test_hospital_guide.py`
- Test: `tests/test_hospital_guide.py`

- [ ] **Step 1: Write the failing test module**

```python
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from voice_assistant.hospital_guide import HospitalGuideConfig, HospitalGuideOrchestrator
from voice_assistant.medical_knowledge import MedicalKnowledgeBase


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class HospitalGuideTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.config_path = root / "hospital.json"
        write_json(self.config_path, {
            "hospital_name": "测试医院",
            "departments": [{
                "id": "internal_medicine",
                "name": "内科",
                "aliases": ["内科", "呼吸内科"],
                "floor": "二层",
                "directions": "到二层内科候诊区。",
                "navigation": {"enabled": True, "x": 1.2, "y": -3.4, "theta": 0.0},
            }],
        })
        self.kb_path = root / "knowledge.jsonl"
        self.kb_path.write_text(
            '{"text":"胸痛或呼吸不适需要根据症状就诊。"}\n'
            '{"text":"儿科为儿童提供门诊服务。"}\n', encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_retrieval_returns_limited_relevant_text(self):
        knowledge = MedicalKnowledgeBase.from_jsonl(self.kb_path)
        results = knowledge.search("胸痛", limit=1)
        self.assertEqual(results, ["胸痛或呼吸不适需要根据症状就诊。"])

    def test_memory_is_bounded_and_resettable(self):
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(self.config_path),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), Mock(), Mock(), memory_turns=1,
        )
        guide.remember("第一问", "第一答")
        guide.remember("第二问", "第二答")
        self.assertEqual(guide.history(), [
            {"role": "user", "content": "第二问"},
            {"role": "assistant", "content": "第二答"},
        ])
        guide.reset()
        self.assertEqual(guide.history(), [])

    def test_navigation_requires_a_pending_department_and_confirmation(self):
        car = Mock()
        llm = Mock()
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(self.config_path),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), llm, car,
        )
        guide.handle("带我去内科")
        car.navigate_to.assert_not_called()
        guide.handle("好的")
        car.navigate_to.assert_called_once_with(1.2, -3.4, 0.0)

    def test_rejection_clears_pending_navigation(self):
        car = Mock()
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(self.config_path),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), Mock(), car,
        )
        guide.handle("带我去内科")
        guide.handle("不用了")
        guide.handle("好的")
        car.navigate_to.assert_not_called()

    def test_emergency_message_never_starts_navigation_automatically(self):
        car = Mock()
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(self.config_path),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), Mock(), car,
        )
        answer = guide.handle("我胸痛而且晕倒了")
        self.assertIn("急诊", answer)
        car.navigate_to.assert_not_called()
```

- [ ] **Step 2: Run the new tests to verify RED**

Run: `python -m unittest tests.test_hospital_guide -v`

Expected: import failure because `voice_assistant.hospital_guide` and `voice_assistant.medical_knowledge` do not yet exist.

- [ ] **Step 3: Do not add production code in this task**

The expected failure demonstrates that the tests target the missing public contract rather than existing behavior.

- [ ] **Step 4: Commit the red-test checkpoint**

```bash
git add tests/test_hospital_guide.py
git commit -m "test: define hospital guide behavior"
```

### Task 2: Implement validated hospital configuration, memory, and local retrieval

**Files:**
- Create: `voice_assistant/medical_knowledge.py`
- Create: `voice_assistant/hospital_guide.py`
- Create: `voice_assistant/data/hospital_guide_template.json`
- Modify: `tests/test_hospital_guide.py`
- Test: `tests/test_hospital_guide.py`

- [ ] **Step 1: Extend the red tests for invalid configuration and disabled point safety**

```python
    def test_invalid_or_disabled_navigation_is_rejected(self):
        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        payload["departments"][0]["navigation"]["enabled"] = False
        write_json(self.config_path, payload)
        config = HospitalGuideConfig.from_path(self.config_path)
        self.assertFalse(config.department("internal_medicine").navigation_enabled)

        payload["departments"].append(dict(payload["departments"][0]))
        write_json(self.config_path, payload)
        with self.assertRaises(ValueError):
            HospitalGuideConfig.from_path(self.config_path)
```

- [ ] **Step 2: Run the focused test to verify RED**

Run: `python -m unittest tests.test_hospital_guide.HospitalGuideTests.test_invalid_or_disabled_navigation_is_rejected -v`

Expected: `AttributeError` or `ValueError` mismatch because the configuration class is still missing the safety contract.

- [ ] **Step 3: Implement the minimal retrieval and configuration API**

```python
# voice_assistant/medical_knowledge.py
class MedicalKnowledgeBase:
    @classmethod
    def from_jsonl(cls, path):
        # Return an empty database for a missing path; skip invalid lines.
        ...

    def search(self, query, limit=3):
        # Score Chinese character 2-4 grams by overlap and return unique text.
        ...

# voice_assistant/hospital_guide.py
class HospitalGuideConfig:
    @classmethod
    def from_path(cls, path):
        # Reject duplicate IDs, blank labels, missing directions, non-finite coordinates.
        ...

    def department(self, department_id):
        ...

class ConversationMemory:
    def add_turn(self, user_text, assistant_text):
        ...

    def clear(self):
        ...
```

Create a template with eight department records. Every `navigation.enabled` value must be `false`, and every coordinate must be `0.0`, so an unconfigured checkout cannot move the robot.

- [ ] **Step 4: Run all hospital-guide tests to verify GREEN**

Run: `python -m unittest tests.test_hospital_guide -v`

Expected: retrieval, memory, valid configuration, duplicate-ID rejection, and disabled-navigation checks pass; routing tests remain red until Task 3.

- [ ] **Step 5: Commit the foundation**

```bash
git add voice_assistant/medical_knowledge.py voice_assistant/hospital_guide.py voice_assistant/data/hospital_guide_template.json tests/test_hospital_guide.py
git commit -m "feat: add hospital guide knowledge foundation"
```

### Task 3: Implement safe LLM orchestration and confirmed navigation

**Files:**
- Modify: `voice_assistant/hospital_guide.py`
- Modify: `voice_assistant/car_client.py`
- Modify: `tests/test_hospital_guide.py`
- Test: `tests/test_hospital_guide.py`

- [ ] **Step 1: Add failing tests for the exact navigation request and LLM context**

```python
from unittest.mock import patch
from voice_assistant.car_client import CarClient

    def test_llm_receives_limited_history_and_evidence(self):
        llm = Mock()
        llm.answer.return_value = "建议到内科进一步咨询。"
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(self.config_path),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), llm, Mock(), memory_turns=1,
        )
        guide.handle("我胸痛")
        kwargs = llm.answer.call_args.kwargs
        self.assertIn("medical_evidence", kwargs["context"])
        self.assertLessEqual(len(kwargs["context"]["history"]), 2)
        self.assertIn("不诊断", kwargs["context"]["system_rules"])

    @patch("voice_assistant.car_client.request.urlopen")
    def test_car_client_posts_validated_navigation_payload(self, urlopen):
        response = Mock()
        response.read.return_value = b'{"code": 0}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        urlopen.return_value = response
        CarClient("http://127.0.0.1:6500").navigate_to(1.2, -3.4, 0.0)
        payload = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload, {"x": 1.2, "y": -3.4, "theta": 0.0})
```

- [ ] **Step 2: Run the focused tests to verify RED**

Run: `python -m unittest tests.test_hospital_guide.HospitalGuideTests.test_llm_receives_limited_history_and_evidence tests.test_hospital_guide.HospitalGuideTests.test_car_client_posts_validated_navigation_payload -v`

Expected: LLM context does not exist and `CarClient.navigate_to` is undefined.

- [ ] **Step 3: Implement confirmation-gated orchestration and navigation**

```python
# HospitalGuideOrchestrator.handle(text)
if self._is_emergency(text):
    self._pending_department_id = None
    return self._remember_and_return(text, self._emergency_reply())
if self._is_rejection(text):
    self._pending_department_id = None
    return self._remember_and_return(text, "好的，已取消带路请求。")
if self._pending_department_id and self._is_confirmation(text):
    department = self._config.department(self._pending_department_id)
    if not department.navigation_enabled:
        return self._remember_and_return(text, "该科室点位尚未配置，请咨询服务台。")
    self._car_client.navigate_to(department.x, department.y, department.theta)
    self._pending_department_id = None
    return self._remember_and_return(text, "已开始带您前往%s。%s" % (department.name, department.directions))
```

For a direct configured department request, set the pending ID and ask for confirmation without navigation. For general text, retrieve at most `retrieval_limit` evidence entries, call `llm.answer(text, context={...})`, remove an optional `【导诊科室:<configured-id>】` marker from speech text, and set pending navigation only when the marker names a configured department. Never parse coordinates from LLM output.

Implement `CarClient.navigate_to` with `math.isfinite` validation, a JSON POST to `/api/navigate`, and the same nonzero `code` error behavior as `execute`.

- [ ] **Step 4: Run the complete hospital-guide suite to verify GREEN**

Run: `python -m unittest tests.test_hospital_guide -v`

Expected: all routing, rejection, emergency, LLM-context, and navigation-payload tests pass.

- [ ] **Step 5: Commit the safe routing slice**

```bash
git add voice_assistant/hospital_guide.py voice_assistant/car_client.py tests/test_hospital_guide.py
git commit -m "feat: route confirmed hospital guide navigation"
```

### Task 4: Integrate the guide with the existing voice lifecycle and LLM client

**Files:**
- Modify: `voice_assistant/config.py`
- Modify: `voice_assistant/llm_client.py`
- Modify: `voice_assistant/voice_service.py`
- Modify: `voice_assistant/wake_word.py`
- Modify: `tests/test_hospital_guide.py`
- Modify: `tests/test_voice_command.py`
- Test: `tests/test_hospital_guide.py`
- Test: `tests/test_voice_command.py`

- [ ] **Step 1: Add failing integration tests**

```python
from voice_assistant.voice_service import VoiceService

    def test_voice_service_uses_guide_for_non_motion_text(self):
        guide = Mock()
        guide.handle.return_value = "请到内科候诊区。"
        tts = Mock()
        service = VoiceService(Mock(), Mock(), hospital_guide=guide, tts_backend=tts)
        service.handle_final({"text": "我胸痛"})
        guide.handle.assert_called_once_with("我胸痛")
        tts.speak.assert_called_once_with("请到内科候诊区。")

    def test_voice_service_reset_clears_guide_memory(self):
        guide = Mock()
        service = VoiceService(Mock(), Mock(), hospital_guide=guide)
        service.reset_conversation()
        guide.reset.assert_called_once_with()
```

In `tests/test_voice_command.py`, add a wake-word test that creates a mock `VoiceService`, invokes a new wake session and an idle expiry, and asserts `reset_conversation()` is called for both boundaries.

- [ ] **Step 2: Run the focused integration tests to verify RED**

Run: `python -m unittest tests.test_hospital_guide tests.test_voice_command -v`

Expected: `VoiceService` lacks the `hospital_guide` parameter and `reset_conversation` method.

- [ ] **Step 3: Implement the integration**

Add configuration defaults rooted at `voice_assistant/data/`:

```python
self.hospital_guide_enabled = os.getenv("MINIMOVER_HOSPITAL_GUIDE_ENABLED", "1").lower() not in {"0", "false", "no", "off"}
self.hospital_guide_path = os.getenv("MINIMOVER_HOSPITAL_GUIDE_PATH", default_guide_path)
self.medical_kb_path = os.getenv("MINIMOVER_MEDICAL_KB_PATH", default_kb_path)
self.medical_memory_turns = max(1, min(_int("MINIMOVER_MEDICAL_MEMORY_TURNS", 6), 12))
self.medical_retrieval_limit = max(1, min(_int("MINIMOVER_MEDICAL_RETRIEVAL_LIMIT", 3), 5))
self.medical_reply_max_chars = max(60, min(_int("MINIMOVER_MEDICAL_REPLY_MAX_CHARS", 180), 300))
```

Extend `LlmClient.answer` to preserve its current signature and compose the hospital-guide system rules and bounded `history`/`medical_evidence` context into OpenAI messages. In `main()`, construct the guide only when enabled and its JSON configuration loads; log a configuration error without crashing the movement service.

`VoiceService.handle_final` must check movement commands first, then delegate non-motion text to `hospital_guide.handle(text)` when present, speak the nonempty answer, and otherwise retain the legacy LLM fallback. `VoiceService.reset_conversation` delegates to `hospital_guide.reset`.

`WakeWordVoiceService` calls `reset_conversation` immediately when it transitions from IDLE to AWAKE and when the wake window expires. It must not call reset for every utterance in the same session.

- [ ] **Step 4: Run the voice and hospital-guide test suites to verify GREEN**

Run: `python -m unittest discover -s tests -p 'test_*.py' -v`

Expected: all pre-existing voice tests and all new hospital-guide tests pass.

- [ ] **Step 5: Commit the integration**

```bash
git add voice_assistant/config.py voice_assistant/llm_client.py voice_assistant/voice_service.py voice_assistant/wake_word.py tests/test_hospital_guide.py tests/test_voice_command.py
git commit -m "feat: integrate hospital guide into voice service"
```

### Task 5: Add the explicit knowledge import command and operator documentation

**Files:**
- Create: `scripts/fetch_shortmedkg.py`
- Modify: `.gitignore`
- Modify: `voice_assistant/README.md`
- Modify: `docs/superpowers/specs/2026-07-16-hospital-guide-voice-design.md`
- Test: `tests/test_hospital_guide.py`

- [ ] **Step 1: Add a failing importer integrity test**

```python
from scripts.fetch_shortmedkg import verify_sha256

    def test_sha256_verification_rejects_corrupt_download(self):
        path = Path(self.temp_dir.name) / "corpus.jsonl"
        path.write_text('{"text":"示例"}\n', encoding="utf-8")
        self.assertFalse(verify_sha256(path, "0" * 64))
```

- [ ] **Step 2: Run the importer test to verify RED**

Run: `python -m unittest tests.test_hospital_guide.HospitalGuideTests.test_sha256_verification_rejects_corrupt_download -v`

Expected: import failure because `scripts.fetch_shortmedkg` does not exist.

- [ ] **Step 3: Implement the pinned importer and documentation**

The importer must use `urllib.request`, write downloads to a sibling temporary file, calculate SHA-256, atomically replace the destination only after a nonempty JSONL response is received, and write a sidecar metadata JSON with source URL, commit, retrieval timestamp, byte count, and digest. It must accept `--output` and `--timeout`; it must never read or print API keys.

Add `/voice_assistant/data/shortmedkg/` to `.gitignore`, while retaining the template JSON under version control. Document the exact commands below and require the operator to set all department `navigation.enabled` flags and coordinates before navigating:

```bash
python scripts/fetch_shortmedkg.py
export MINIMOVER_HOSPITAL_GUIDE_ENABLED=1
export MINIMOVER_HOSPITAL_GUIDE_PATH="$PWD/voice_assistant/data/hospital_guide_template.json"
python -m voice_assistant.voice_service
```

Update the design doc’s configuration contract to include `navigation.enabled` as the explicit point-verification gate.

- [ ] **Step 4: Run the complete unit suite and static compilation**

Run: `python -m unittest discover -s tests -p 'test_*.py' -v && python -m compileall -q voice_assistant scripts`

Expected: all tests pass and compilation returns exit code 0.

- [ ] **Step 5: Commit the operator-facing slice**

```bash
git add scripts/fetch_shortmedkg.py .gitignore voice_assistant/README.md docs/superpowers/specs/2026-07-16-hospital-guide-voice-design.md tests/test_hospital_guide.py
git commit -m "docs: add hospital guide setup instructions"
```

## Final verification

- [ ] Run `git diff --check` and confirm no whitespace errors.
- [ ] Run `python -m unittest discover -s tests -p 'test_*.py' -v` and read the complete output.
- [ ] Run `python -m compileall -q voice_assistant scripts` and confirm exit code 0.
- [ ] Inspect `git status --short --branch`; it must contain no uncommitted feature changes.
- [ ] Confirm that no data corpus, API key, conversation transcript, or generated metadata is staged.
