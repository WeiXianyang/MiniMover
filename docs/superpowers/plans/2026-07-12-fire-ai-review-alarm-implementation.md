# Fire AI Review and Alarm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add non-blocking fire/smoke event debouncing, evidence capture, AI visual review, bounded local retention, and replaceable alarm callbacks to the existing YOLOv5 detector.

**Architecture:** The YOLO loop remains the real-time producer and calls a single-thread-owned FireEventManager. A bounded background AIReviewer performs OpenAI-compatible image requests and returns tagged results through a queue; the event manager consumes results on later frames, owns state transitions, and delegates disk writes and alarms to focused services.

**Tech Stack:** Python 3 standard library (dataclasses, enum, queue, threading, urllib, json, logging), OpenCV, NumPy, existing PyTorch/YOLOv5 runtime, unittest.

---

## File map

Create:

- fire_smoke_detection/fire_monitor/__init__.py — package exports.
- fire_smoke_detection/fire_monitor/types.py — enums and immutable records.
- fire_smoke_detection/fire_monitor/config.py — environment and optional .env loading.
- fire_smoke_detection/fire_monitor/evidence_store.py — atomic JPEG/JSON writes and ten-image rotation.
- fire_smoke_detection/fire_monitor/ai_reviewer.py — prompt, HTTP request, strict parsing, retry worker.
- fire_smoke_detection/fire_monitor/alarm_service.py — alarm protocol and local adapter.
- fire_smoke_detection/fire_monitor/event_manager.py — event state machine.
- fire_smoke_detection/tests/test_fire_config.py
- fire_smoke_detection/tests/test_evidence_store.py
- fire_smoke_detection/tests/test_ai_reviewer.py
- fire_smoke_detection/tests/test_alarm_service.py
- fire_smoke_detection/tests/test_event_manager.py
- fire_smoke_detection/tests/test_detection_bridge.py
- fire_smoke_detection/.env.example

Modify:

- fire_smoke_detection/yolov5_runtime/detect.py — initialize/close monitor and submit frames.
- fire_smoke_detection/README.md — setup, behavior, alarms, testing.
- fire_smoke_detection/requirements.txt and requirements-jetson.txt — dependency note.
- .gitignore — ignore runtime output and local .env.

No OpenAI SDK, requests, or python-dotenv is added; urllib and a small parser minimize Jetson dependency constraints.

---

### Task 1: Define monitoring types and validated configuration

**Files:** create fire_monitor/__init__.py, types.py, config.py, tests/test_fire_config.py, and .env.example.

- [ ] **Step 1: Write failing configuration tests**

Test FireMonitorConfig.from_env(ROOT) with a cleared environment. Assert defaults: base URL https://zz.cxwms.com/v1, endpoint /chat/completions, model gpt-5.4-mini, window 2, hits 5, clear 10, re-review 30, evidence 60, maximum 10, timeout 30, retries 2. Test environment overrides, .env loading without overriding an existing process variable, endpoint slash normalization, and rejection of zero/negative or nonnumeric settings.

Representative test:

    with patch.dict(os.environ, {}, clear=True):
        config = FireMonitorConfig.from_env(ROOT)
    self.assertEqual(config.trigger_min_hits, 5)
    self.assertEqual(config.max_evidence_images, 10)

Run:

    python -m unittest fire_smoke_detection.tests.test_fire_config -v

Expected: ModuleNotFoundError for fire_monitor.

- [ ] **Step 2: Add exact shared records**

In types.py define string enums EventState with IDLE, AI_REVIEWING, AI_REJECTED, ALARMED_FIRE, ALARMED_SMOKE, AI_FAILED; AIResultKind with CONFIRMED_FIRE, SUSPECTED_SMOKE, NO_FIRE. Add frozen dataclasses:

    Detection(class_name: str, confidence: float)
    AIReviewRequest(event_id: str, review_id: int, jpeg_bytes: bytes, captured_at: datetime)
    AIReviewResult(event_id: str, review_id: int, success: bool, attempts: int,
                   result: Optional[AIResultKind] = None,
                   confidence: Optional[float] = None,
                   reason: str = "", error: str = "")
    AlarmEvent(event_id: str, alarm_type: str, occurred_at: datetime,
               reason: str, confidence: Optional[float],
               evidence_path: Optional[str], local_detection_gone: bool)

Also define FIRE_CLASSES = ("fire", "smoke").

- [ ] **Step 3: Implement configuration**

config.py must implement load_dotenv(path), positive float/int parsers, and frozen FireMonitorConfig. from_env(root) loads root/.env, never overrides existing environment values, strips quotes, normalizes Base URL and endpoint, validates all numeric values, and exposes runtime_dir and evidence_dir properties.

.env.example must contain every FIRE_AI_* and timing variable with no real Key.

- [ ] **Step 4: Run tests and commit**

    python -m unittest fire_smoke_detection.tests.test_fire_config -v
    git add fire_smoke_detection/fire_monitor fire_smoke_detection/tests/test_fire_config.py fire_smoke_detection/.env.example
    git commit -m "Add fire monitor configuration and types"

Expected: all configuration tests pass.

---

### Task 2: Implement bounded atomic evidence storage

**Files:** create fire_monitor/evidence_store.py and tests/test_evidence_store.py.

- [ ] **Step 1: Write failing tests**

Use TemporaryDirectory and a 4x4 NumPy image. Cover: save creates matching JPEG/JSON; metadata includes event ID, review ID, capture type and ISO time; the eleventh save retains the latest ten managed pairs; unknown teacher-note.jpg is untouched; update_metadata recursively merges nested dictionaries; updating an already rotated path returns False and does not recreate it; no .tmp remains.

Run:

    python -m unittest fire_smoke_detection.tests.test_evidence_store -v

Expected: missing module failure.

- [ ] **Step 2: Implement EvidenceStore**

Public API:

    class EvidenceStore:
        def __init__(self, root: Path, max_images: int): ...
        def save(self, event_id, review_id, capture_type, captured_at,
                 annotated_frame, metadata) -> Path: ...
        def update_metadata(self, image_path: Path, updates: dict) -> bool: ...

Requirements:

- Make root recursively.
- JPEG encode via cv2.imencode at quality 90; fail clearly if encoding fails.
- Name managed files {event_id}_{review_id:03d}_{capture_type}_{HHMMSSffffff}.jpg; event IDs start fire_.
- Write same-directory temporary files and atomically replace both JPEG and UTF-8 JSON.
- JSON uses ensure_ascii=False and indent=2.
- Recursive dictionary merge on update.
- Rotate only fire_*.jpg files with matching JSON; unknown files are never deleted.
- Sort by parsed captured_at, then filename. Malformed managed metadata sorts oldest so it cannot block rotation.
- Delete oldest JPG/JSON pairs until max_images remains.

- [ ] **Step 3: Verify and commit**

    python -m unittest fire_smoke_detection.tests.test_evidence_store -v
    git add fire_smoke_detection/fire_monitor/evidence_store.py fire_smoke_detection/tests/test_evidence_store.py
    git commit -m "Add bounded fire evidence storage"

---

### Task 3: Implement strict AI review client and non-blocking worker

**Files:** create fire_monitor/ai_reviewer.py and tests/test_ai_reviewer.py.

- [ ] **Step 1: Write failing parser/request/retry tests**

Inject a fake transport with signature transport(url, headers, body, timeout) -> dict. Cover:

1. Valid confirmed_fire, suspected_smoke and no_fire map to enums.
2. One outer JSON Markdown code fence is accepted.
3. Invalid enum, invalid JSON, missing choices, bool confidence, NaN/infinity, and confidence outside 0..1 fail.
4. Two transport exceptions followed by success returns attempts 3; all three bodies are identical.
5. Three failures returns success False and attempts 3 with sanitized error.
6. Empty Key returns attempts 0 without transport call.
7. submit rejects a second queued/in-flight request; poll returns the correctly tagged result; close is idempotent.

Compatible fake response:

    {"choices":[{"message":{"content":
      "{\"result\":\"confirmed_fire\",\"confidence\":0.94,\"reason\":\"明确火焰\"}"}}]}

Run and expect missing module:

    python -m unittest fire_smoke_detection.tests.test_ai_reviewer -v

- [ ] **Step 2: Implement prompt, payload and strict parser**

SYSTEM_PROMPT must contain the approved three definitions, false positives (lights, sunset, red/orange objects, steam, clouds/fog, reflections, screens), shape/texture/spread/context requirement, insufficient-evidence rule, and exact JSON-only output keys.

Implement:

    build_payload(model: str, jpeg_bytes: bytes) -> bytes
    parse_model_content(content: str) -> tuple[AIResultKind, float, str]
    urllib_transport(url: str, headers: dict, body: bytes, timeout: float) -> dict

Payload uses Chat Completions user content with text plus image_url data:image/jpeg;base64,... and temperature 0. Parser removes at most one outer JSON fence, uses json.loads without keyword guessing, rejects bool confidence, requires finite 0..1, normalizes reason whitespace and truncates to 300 characters.

urllib_transport uses urllib.request.Request(method="POST") and JSON UTF-8. Never include Key, Authorization, Base64 body, or full response body in logged/returned errors.

- [ ] **Step 3: Implement AIReviewer lifecycle**

Public API:

    AIReviewer(config, transport=urllib_transport)
    review_now(request) -> AIReviewResult
    submit(request) -> bool
    poll() -> list[AIReviewResult]
    close(join_timeout=1.0) -> None

Rules: request queue maxsize 1; one daemon worker; locked busy flag; unique sentinel; URL = normalized base + endpoint; attempts = 1 + retries; same payload bytes reused; failure retries immediately; missing Key is local failure; error contains exception type and at most 200 sanitized characters; result always retains event_id/review_id; close is finite and idempotent.

- [ ] **Step 4: Verify and commit**

    python -m unittest fire_smoke_detection.tests.test_ai_reviewer -v
    git add fire_smoke_detection/fire_monitor/ai_reviewer.py fire_smoke_detection/tests/test_ai_reviewer.py
    git commit -m "Add asynchronous AI fire reviewer"

Expected: all tests pass without real network or sleeps.

---

### Task 4: Add replaceable alarm logging

**Files:** create fire_monitor/alarm_service.py and tests/test_alarm_service.py.

- [ ] **Step 1: Write failing tests**

With a temporary runtime directory, assert each method writes one UTF-8 JSONL object with confirmed_fire, suspected_smoke, or ai_unavailable; the AI failure reason says human intervention is required; duplicate (event_id, alarm_type) calls write once; different events/types remain independent.

- [ ] **Step 2: Implement protocol and adapter**

Define AlarmService Protocol with report_confirmed_fire, report_suspected_smoke, report_ai_unavailable returning bool. LoggingAlarmService creates runtime directory, maintains a locked process-local dedupe set, appends/flushes alarms.jsonl, and logs:

- 【火灾报警】AI确认发现明火
- 【烟雾报警】AI确认发现疑似火灾烟雾
- 【系统报警】AI服务失效，需人工介入

Serialize only AlarmEvent fields, never credentials or image bytes. Add configure_monitor_logger(runtime_dir) with RotatingFileHandler(maxBytes=1 MiB, backupCount=3, UTF-8) and console output; calling twice must not duplicate handlers.

- [ ] **Step 3: Verify and commit**

    python -m unittest fire_smoke_detection.tests.test_alarm_service -v
    git add fire_smoke_detection/fire_monitor/alarm_service.py fire_smoke_detection/tests/test_alarm_service.py
    git commit -m "Add fire alarm service interface"

---

### Task 5: Build the event state machine with fake-clock tests

**Files:** create fire_monitor/event_manager.py and tests/test_event_manager.py; finalize fire_monitor/__init__.py.

- [ ] **Step 1: Add test doubles**

Create FakeReviewer with requests/results/busy, non-blocking submit, poll and close; FakeEvidenceStore recording save/update calls; FakeAlarmService with fire/smoke/failed lists. Use 4x4 NumPy frames, UTC datetimes and numeric monotonic time. No real threads, network or filesystem.

- [ ] **Step 2: Write failing trigger tests**

Prove: four hits at 0.0, 0.3, 0.6, 0.9 do not trigger; fifth at 1.2 creates one event, one initial save and one AI request; times 0, 0.5, 1.0, 1.5, 2.1 do not trigger because the first expires; multiple boxes in one frame count once; irrelevant/below-threshold detections do not count.

- [ ] **Step 3: Implement frame API and event context**

Public API:

    FireEventManager(config, reviewer, evidence_store, alarm_service,
                     minimum_confidence: float, logger)
    process_frame(detections, raw_frame, annotated_frame,
                  now_monotonic: float, captured_at: datetime) -> None
    close() -> None
    state -> EventState

Use a deque for hit times. Context records event_id, state, review_id, last hit, last review capture, last evidence capture, evidence path by review ID, in-flight flag, detection-gone flag, current classes/max confidence. Event IDs include wall-clock microseconds and process counter. Only on capture action encode raw_frame JPEG for AI and save annotated_frame; ordinary frames do not copy/encode.

- [ ] **Step 4: Run trigger tests**

    python -m unittest fire_smoke_detection.tests.test_event_manager.EventManagerTriggerTests -v

Expected: pass.

- [ ] **Step 5: Write failing result-transition tests**

Cover confirmed_fire -> ALARMED_FIRE and one fire alarm; suspected_smoke -> ALARMED_SMOKE; no_fire -> AI_REJECTED without alarm; failure -> AI_FAILED and one unavailable alarm; subsequent frames do not repeat alarms; mismatched event_id/review_id is ignored.

- [ ] **Step 6: Implement tagged result consumption**

Drain reviewer.poll at the start of each frame. For a matching result, atomically update the evidence metadata with status, attempts, result/confidence/reason or error; create AlarmEvent; invoke exactly one alarm method; transition without AI confidence threshold. Warn and ignore stale tagged results.

- [ ] **Step 7: Write failing interval/reset tests**

Prove: AI_REJECTED has no review at 29.9 seconds and a fresh review image/request at 30.0 if still hit; no parallel task while busy; if a long request returns no_fire after its capture-based 30 seconds elapsed, the next still-hit frame can submit immediately; alarmed and AI_FAILED states save one periodic image at 60.0, not 59.9, without AI; AI_FAILED never re-requests in that event; no reset at 9.9 seconds, reset at 10.0; next event has new ID.

- [ ] **Step 8: Implement intervals and reset**

Use capture time, not response time, for interval anchors. Periodic save updates last evidence capture. Reset discards event and clears hit deque, preventing old hits from triggering the next event.

- [ ] **Step 9: Cover in-flight disappearance**

Tests: after ten seconds with no hit while AI is busy, later confirmed_fire still alarms with local_detection_gone=True then resets without periodic capture; no_fire resets without alarm; failure sends unavailable then resets. Implement by retaining the event until its tagged result arrives, marking detection gone, blocking new captures, and never cancelling the worker request.

- [ ] **Step 10: Verify and commit**

    python -m unittest fire_smoke_detection.tests.test_event_manager -v
    git add fire_smoke_detection/fire_monitor/event_manager.py fire_smoke_detection/fire_monitor/__init__.py fire_smoke_detection/tests/test_event_manager.py
    git commit -m "Add fire event state machine"

---

### Task 6: Integrate monitoring into the legacy YOLO loop

**Files:** modify yolov5_runtime/detect.py; create tests/test_detection_bridge.py.

- [ ] **Step 1: Write a failing pure conversion test**

Add build_fire_detections(names, rows) in a lightweight fire_monitor module rather than importing heavyweight legacy CUDA code in tests. Verify class IDs/confidences become Detection("fire", 0.81) and Detection("smoke", 0.72), while other class names are omitted.

- [ ] **Step 2: Add monitor construction**

In detect.py add sys and datetime imports, insert MODULE_ROOT = Path(__file__).resolve().parents[1] into sys.path, then import monitor components. After output setup construct config, rotating logger, AIReviewer, EvidenceStore, LoggingAlarmService and FireEventManager with minimum_confidence=opt.conf_thres. Invalid configuration prints a clear error and exits; monitoring is not silently disabled.

- [ ] **Step 3: Bridge each frame**

Before drawing boxes preserve raw_frame = im0.copy() and create fire_detections. While iterating detections append only fire/smoke records. After drawing, before imshow/video writing, call process_frame with raw frame, annotated im0, time.monotonic(), and datetime.now().astimezone(). Arrays pass by reference; manager only encodes/saves on capture actions.

Wrap loop lifecycle in try/finally so fire_manager.close and vid_writer.release run on normal completion, q, KeyboardInterrupt, or exception. Preserve existing image/video output behavior.

- [ ] **Step 4: Verify integration**

    python -m unittest fire_smoke_detection.tests.test_detection_bridge fire_smoke_detection.tests.test_detector -v
    python fire_smoke_detection/detector.py --source fire_smoke_detection/samples/result_demo.jpg --device cpu

Expected: tests pass; sample exits 0 and writes existing annotated output; one image cannot satisfy five-frame trigger and therefore needs no Key/network.

- [ ] **Step 5: Commit**

    git add fire_smoke_detection/yolov5_runtime/detect.py fire_smoke_detection/tests/test_detection_bridge.py
    git commit -m "Integrate fire monitoring with YOLO detection"

---

### Task 7: Document setup and protect runtime files

**Files:** modify .gitignore, README.md, requirements.txt, requirements-jetson.txt.

- [ ] **Step 1: Add ignore rules**

Add:

    /fire_smoke_detection/output/
    /fire_smoke_detection/runtime/
    /fire_smoke_detection/.env
    !/fire_smoke_detection/.env.example

Verify with git check-ignore that .env is ignored and .env.example is not.

- [ ] **Step 2: Update README**

Document copying .env.example to .env; all endpoint/model/timing overrides; 2-second/5-hit trigger; 30-second denied review; 60-second periodic evidence; 10-second clear; original image sent versus annotated image saved; global maximum ten; meanings of confirmed_fire, suspected_smoke, ai_unavailable; runtime evidence/log paths; local-only alarm adapter as future mobile-App boundary; Windows/Jetson commands; unit test command. Never include the actual Key.

- [ ] **Step 3: Document dependency choice**

In both requirement files state that AI HTTP uses Python urllib and adds no SDK. Do not add openai, requests, or python-dotenv.

- [ ] **Step 4: Verify and commit**

    git diff --check
    python -m unittest discover -s fire_smoke_detection/tests -v
    git add .gitignore fire_smoke_detection/README.md fire_smoke_detection/requirements.txt fire_smoke_detection/requirements-jetson.txt
    git commit -m "Document fire AI review workflow"

---

### Task 8: Full regression and acceptance verification

**Files:** modify only if verification exposes defects.

- [ ] **Step 1: Run full unit and migration suites**

    python -m unittest discover -s fire_smoke_detection/tests -v
    python fire_smoke_detection/tools/verify_migration.py

Expected: all existing and new tests pass; migration assets verify.

- [ ] **Step 2: Prove non-blocking behavior without sleeps**

Add EventManagerNonBlockingTests using a fake reviewer that remains busy while 100 later process_frame calls return. Manually inject the result afterward. Assert no second submit and continued local frame processing; avoid fragile elapsed-time thresholds.

    python -m unittest fire_smoke_detection.tests.test_event_manager.EventManagerNonBlockingTests -v

- [ ] **Step 3: Verify proxy compatibility safely**

With an untracked local .env containing the temporary classroom Key, run a one-off Python command that loads config, reads and JPEG-encodes samples/result_demo.jpg without annotations, calls AIReviewer.review_now once, and prints only enum/confidence/reason/attempts or sanitized error. It must never print Key, headers, body, or Base64. Expect a valid three-way result or a sanitized endpoint/format error; do not weaken parsing without understanding the response.

- [ ] **Step 4: Manual camera/Jetson acceptance**

Run on target:

    cd /path/to/MiniMover/fire_smoke_detection
    bash run.sh --source 0 --view-img

Verify rendering continues during review; five qualifying frames create one initial pair; no per-frame saves; AI denial re-reviews no sooner than 30 seconds; confirmation alarms once and saves no sooner than 60 seconds; removal for ten seconds resets; more than ten managed images deletes oldest pairs only; quit releases camera. If hardware is unavailable, report this check as unrun rather than claiming target verification.

- [ ] **Step 5: Repository and credential hygiene**

    git status --short
    git diff --check
    git grep -n "sk-" -- ':!fire_smoke_detection/.env' ':!docs/superpowers/specs/*' ':!docs/superpowers/plans/*'
    git ls-files fire_smoke_detection/runtime fire_smoke_detection/.env

Expected: no runtime/.env tracked, no Key in source, unrelated pre-existing untracked files untouched.

- [ ] **Step 6: Commit verification fixes only when needed**

    git add <only corrected files>
    git commit -m "Fix fire monitor verification issues"

Do not make an empty commit.

- [ ] **Step 7: Final review checkpoint**

Report modules added; exact passing commands; real API compatibility outcome; whether camera/Jetson checks ran; and the intentional remaining boundary that mobile delivery is represented only by AlarmService. Never claim completion while tests fail, and distinguish local verification from target-hardware verification.
