# Hospital Guide Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe, live hospital-guide dashboard that displays the voice-service dialogue, retained memory, medical-knowledge activity, confirmation gate, configured department target, and navigation audit while reusing the existing map-point navigation console.

**Architecture:** The voice process will write a bounded, atomic JSON telemetry snapshot through a small `HospitalGuideTelemetry` adapter. The Flask process will expose a read-only status API and a `/hospital-guide` page that polls it; it will never provide a web endpoint that can directly send a navigation goal. The dashboard can open the existing `/nav/patrol` point-selection page and displays the configured department target only after it has been emitted by the real voice guide.

**Tech Stack:** Python 3 standard library, Flask, existing MiniMover navigation API, vanilla HTML/CSS/JavaScript, `unittest`.

---

## File Structure

- Create `voice_assistant/hospital_guide_telemetry.py`: bounded atomic runtime snapshot store shared by the voice service and Flask process.
- Modify `voice_assistant/hospital_guide.py`: publish safe, branch-specific telemetry after guide turns without changing its confirmation-gated navigation logic.
- Modify `voice_assistant/voice_service.py`: construct the telemetry store when hospital-guide mode is enabled and inject it into the orchestrator.
- Create `hospital_guide_console.py`: read-only Flask status/config routes and dashboard page constant.
- Modify `api_server.py`: register the console routes with repository-relative configuration and runtime paths.
- Modify `voice_assistant/config.py`: expose an optional telemetry-path environment setting.
- Create `tests/test_hospital_guide_telemetry.py`: exercise atomic snapshot data, event bounds, and reset behavior.
- Create `tests/test_hospital_guide_console.py`: exercise read-only Flask status/config/page behavior with a temporary runtime snapshot.
- Modify `tests/test_hospital_guide.py`: assert actual guide branches record state, knowledge count, confirmation state, and navigation outcome to telemetry.
- Modify `voice_assistant/README.md`: document launch, console URL, and map-point configuration workflow.

### Task 1: Define and test the telemetry contract

**Files:**
- Create: `tests/test_hospital_guide_telemetry.py`
- Create: `voice_assistant/hospital_guide_telemetry.py`

- [ ] **Step 1: Write the failing telemetry test**

```python
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from voice_assistant.hospital_guide_telemetry import HospitalGuideTelemetry


class HospitalGuideTelemetryTests(unittest.TestCase):
    def test_publish_writes_a_bounded_safe_snapshot(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.json"
            telemetry = HospitalGuideTelemetry(path, max_events=2)
            telemetry.publish(
                history=[{"role": "user", "content": "带我去内科"}],
                state="WAITING_CONFIRMATION",
                pending_department={"id": "internal_medicine", "name": "内科", "floor": "一层", "navigation_enabled": False},
                evidence_count=3,
                event_type="department_matched",
                event_message="已识别内科，等待用户确认。",
            )
            telemetry.publish(history=[], state="AWAKE", event_type="reply", event_message="第二条")
            telemetry.publish(history=[], state="AWAKE", event_type="reply", event_message="第三条")

            snapshot = telemetry.read()

        self.assertEqual("WAITING_CONFIRMATION", snapshot["session"]["state"])
        self.assertEqual("内科", snapshot["session"]["pending_department"]["name"])
        self.assertEqual(3, snapshot["knowledge"]["evidence_count"])
        self.assertEqual(["reply", "reply"], [item["type"] for item in snapshot["events"]])
        self.assertFalse(snapshot["navigation"]["requested"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_hospital_guide_telemetry.HospitalGuideTelemetryTests.test_publish_writes_a_bounded_safe_snapshot -v`

Expected: FAIL with `ModuleNotFoundError` because `hospital_guide_telemetry` does not exist.

- [ ] **Step 3: Implement the smallest telemetry store**

```python
class HospitalGuideTelemetry:
    def __init__(self, path, max_events=50):
        self.path = Path(path)
        self.max_events = max(1, min(int(max_events), 100))
        self._events = []
        self._navigation = {"requested": False, "status": "not_requested", "message": "尚未下发导航"}

    def publish(self, *, history, state, event_type, event_message,
                pending_department=None, evidence_count=0, navigation=None):
        if navigation is not None:
            self._navigation = dict(navigation)
        self._events.append({"type": str(event_type), "message": str(event_message), "at": _now_iso()})
        self._events = self._events[-self.max_events:]
        snapshot = {
            "schema_version": 1,
            "updated_at": _now_iso(),
            "session": {"state": str(state), "pending_department": pending_department},
            "memory": _safe_history(history),
            "knowledge": {"evidence_count": max(0, int(evidence_count))},
            "navigation": dict(self._navigation),
            "events": list(self._events),
        }
        _atomic_write_json(self.path, snapshot)
        return snapshot
```

`read()` must return a safe default snapshot when the file does not exist or contains malformed JSON. `_atomic_write_json()` must write to a sibling temporary path and replace the target via `Path.replace()` so the Flask reader cannot observe a partial file.

- [ ] **Step 4: Run the telemetry test to verify it passes**

Run: `python -m unittest tests.test_hospital_guide_telemetry -v`

Expected: PASS.

- [ ] **Step 5: Commit the telemetry increment**

```bash
git add voice_assistant/hospital_guide_telemetry.py tests/test_hospital_guide_telemetry.py
git commit -m "feat: add hospital guide telemetry store"
```

### Task 2: Publish actual guide state without weakening safety gates

**Files:**
- Modify: `tests/test_hospital_guide.py`
- Modify: `voice_assistant/hospital_guide.py`

- [ ] **Step 1: Write the failing orchestrator telemetry test**

```python
def test_department_confirmation_is_visible_before_navigation(self):
    with TemporaryDirectory() as directory:
        telemetry = HospitalGuideTelemetry(Path(directory) / "runtime.json")
        guide = HospitalGuideOrchestrator(config, knowledge_base, llm, car, telemetry=telemetry)

        guide.handle("带我去内科")
        pending = telemetry.read()
        guide.handle("好的")
        navigated = telemetry.read()

    self.assertEqual("WAITING_CONFIRMATION", pending["session"]["state"])
    self.assertEqual("内科", pending["session"]["pending_department"]["name"])
    self.assertFalse(pending["navigation"]["requested"])
    self.assertTrue(navigated["navigation"]["requested"])
    self.assertEqual("started", navigated["navigation"]["status"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_hospital_guide.HospitalGuideTests.test_department_confirmation_is_visible_before_navigation -v`

Expected: FAIL because the orchestrator has no `telemetry` constructor parameter.

- [ ] **Step 3: Add optional telemetry publishing to the orchestrator**

Update the constructor signature to accept `telemetry=None`. Add `_department_payload()`, `_publish()` and branch labels. Call `_publish()` from `_remember_and_return()` after the memory update, with state `WAITING_CONFIRMATION` only while `_pending_department_id` is set. For a confirmation attempt:

```python
navigation = {"requested": True, "status": "started", "message": "已开始带您前往内科。", "department": _department_payload(department)}
```

For disabled or failed navigation, preserve `requested: False` and use `status: "not_configured"` or `"failed"`. For emergency input, publish `event_type="emergency"` and clear the pending department before saving. Never expose coordinates in the telemetry payload and do not change the existing `navigate_to()` confirmation condition.

- [ ] **Step 4: Run focused guide tests to verify they pass**

Run: `python -m unittest tests.test_hospital_guide -v`

Expected: PASS, including existing safety and confirmation tests.

- [ ] **Step 5: Commit the guide publishing increment**

```bash
git add voice_assistant/hospital_guide.py tests/test_hospital_guide.py
git commit -m "feat: publish hospital guide session events"
```

### Task 3: Wire telemetry into the real voice-service startup

**Files:**
- Modify: `voice_assistant/config.py`
- Modify: `voice_assistant/voice_service.py`
- Modify: `tests/test_hospital_guide_telemetry.py`

- [ ] **Step 1: Write the failing config/startup test**

```python
def test_voice_config_defaults_telemetry_next_to_guide_data(self):
    with patch.dict(os.environ, {}, clear=True):
        config = VoiceConfig()
    self.assertTrue(config.hospital_guide_telemetry_path.endswith("hospital_guide_runtime.json"))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_hospital_guide_telemetry.HospitalGuideTelemetryTests.test_voice_config_defaults_telemetry_next_to_guide_data -v`

Expected: FAIL because the configuration property does not exist.

- [ ] **Step 3: Add configuration and injection**

Add `hospital_guide_telemetry_path` to `VoiceConfig`, read `MINIMOVER_HOSPITAL_GUIDE_TELEMETRY_PATH` when supplied, and otherwise default to `voice_assistant/data/hospital_guide_runtime.json`. In `voice_service.main()`, construct `HospitalGuideTelemetry(config.hospital_guide_telemetry_path)` next to the guide configuration/knowledge-base loading and pass it as `telemetry=telemetry` to `HospitalGuideOrchestrator`.

- [ ] **Step 4: Run the focused voice tests to verify they pass**

Run: `python -m unittest tests.test_hospital_guide_telemetry -v`

Expected: PASS.

- [ ] **Step 5: Commit the voice startup increment**

```bash
git add voice_assistant/config.py voice_assistant/voice_service.py tests/test_hospital_guide_telemetry.py
git commit -m "feat: wire guide telemetry into voice service"
```

### Task 4: Provide read-only Flask routes and dashboard rendering

**Files:**
- Create: `tests/test_hospital_guide_console.py`
- Create: `hospital_guide_console.py`
- Modify: `api_server.py`

- [ ] **Step 1: Write failing Flask route tests**

```python
class HospitalGuideConsoleTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.runtime_path = Path(self.directory.name) / "runtime.json"
        self.config_path = Path(self.directory.name) / "hospital.json"
        self.config_path.write_text(json.dumps({"hospital_name": "演示医院", "departments": []}), encoding="utf-8")
        self.app = Flask(__name__)
        register_hospital_guide_console(self.app, self.runtime_path, self.config_path)
        self.client = self.app.test_client()

    def test_status_returns_safe_offline_snapshot_when_voice_is_not_running(self):
        response = self.client.get("/api/hospital-guide/status")
        self.assertEqual(200, response.status_code)
        self.assertFalse(response.get_json()["data"]["service_online"])

    def test_console_is_a_read_only_page_with_existing_map_link(self):
        response = self.client.get("/hospital-guide")
        self.assertEqual(200, response.status_code)
        self.assertIn(b"\xe5\x8c\xbb\xe9\x99\xa2\xe5\xaf\xbc\xe8\xaf\x8a\xe6\x8e\xa7\xe5\x88\xb6\xe5\x8f\xb0", response.data)
        self.assertIn(b"/nav/patrol", response.data)
        self.assertNotIn(b"/api/navigate", response.data)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_hospital_guide_console -v`

Expected: FAIL with `ModuleNotFoundError` because `hospital_guide_console` does not exist.

- [ ] **Step 3: Implement the route module and register it**

Create `register_hospital_guide_console(app, runtime_path, config_path)`. It must register only:

```python
@app.route("/hospital-guide")
def hospital_guide_page():
    return HOSPITAL_GUIDE_CONSOLE_HTML

@app.route("/api/hospital-guide/status")
def hospital_guide_status():
    snapshot = HospitalGuideTelemetry(runtime_path).read()
    snapshot["service_online"] = runtime_path.exists()
    return jsonify({"code": 0, "data": snapshot})

@app.route("/api/hospital-guide/config")
def hospital_guide_config():
    return jsonify({"code": 0, "data": _public_department_config(config_path)})
```

The HTML must poll the status API every second and render: service state, the last six memory entries, pending department, event timeline, evidence count, navigation audit, configured department list, and a link to `/nav/patrol`. It must render all user/assistant text with `textContent`, not `innerHTML`, and include no POST/fetch operation that calls navigation.

In `api_server.py`, call `register_hospital_guide_console()` immediately after the navigation page registrations with absolute paths based on `os.path.dirname(os.path.abspath(__file__))`.

- [ ] **Step 4: Run Flask route tests to verify they pass**

Run: `python -m unittest tests.test_hospital_guide_console -v`

Expected: PASS.

- [ ] **Step 5: Commit the console increment**

```bash
git add hospital_guide_console.py api_server.py tests/test_hospital_guide_console.py
git commit -m "feat: add hospital guide dashboard"
```

### Task 5: Document and verify end-to-end behavior

**Files:**
- Modify: `voice_assistant/README.md`
- Modify: `.gitignore` only if `voice_assistant/data/hospital_guide_runtime.json` is not already ignored by its existing `voice_assistant/data/` rule.

- [ ] **Step 1: Write documentation for the console contract**

Add a `## 医院导诊控制台` section that lists:

```text
http://<小车IP>:5000/hospital-guide
http://<小车IP>:5000/nav/patrol
```

Explain that the page is read-only, real guide activity appears only after `MINIMOVER_HOSPITAL_GUIDE_ENABLED=1` voice service is running, no webpage action can bypass confirmation, and department navigation remains disabled until real map-selected points are saved in `hospital_guide_template.json`.

- [ ] **Step 2: Run all unit tests and static checks**

Run:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
python -m compileall -q voice_assistant scripts hospital_guide_console.py api_server.py
git diff --check
```

Expected: all unit tests pass, compilation exits `0`, and `git diff --check` returns no output.

- [ ] **Step 3: Verify console routes locally without hardware motion**

Run:

```bash
python -c "from flask import Flask; from hospital_guide_console import register_hospital_guide_console; from pathlib import Path; app=Flask(__name__); register_hospital_guide_console(app, Path('voice_assistant/data/hospital_guide_runtime.json'), Path('voice_assistant/data/hospital_guide_template.json')); c=app.test_client(); print(c.get('/hospital-guide').status_code, c.get('/api/hospital-guide/status').status_code, c.get('/api/hospital-guide/config').status_code)"
```

Expected: `200 200 200`. This command sends no motion or navigation request.

- [ ] **Step 4: Commit the documentation and final verification increment**

```bash
git add voice_assistant/README.md .gitignore
git commit -m "docs: document hospital guide console"
```

