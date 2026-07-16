# Real-time Hospital Guide Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Process the car's real WebSocket ASR final utterances through hospital guidance, ShortMedKG retrieval, TTS, dashboard telemetry, and confirmation-gated navigation.

**Architecture:** A Flask bridge creates one stateful guide orchestrator and exposes a local-only utterance API. The Jetson WebSocket microphone client posts each actual `final_text` to that API, speaks the returned reply through its existing TTS endpoint, and ignores legacy server chat/command messages when hospital-guide mode is enabled.

**Tech Stack:** Python 3, Flask, urllib, existing WebSocket client, ShortMedKG JSONL, existing MiniMover navigation API, unittest.

---

### Task 1: Add a tested bridge API and navigation adapter

**Files:**
- Create: `hospital_guide_bridge.py`
- Modify: `tests/test_hospital_guide_bridge.py`

- [ ] Write tests for an empty utterance rejection, a real department match with a pending confirmation, a disabled navigation confirmation that makes no navigation request, and a configured navigation confirmation that invokes the injected adapter exactly once.
- [ ] Run: `python -m unittest tests.test_hospital_guide_bridge -v`; expect import failure before implementation.
- [ ] Implement `HospitalGuideBridge`, a bounded Flask `POST /api/hospital-guide/turn` route, an HTTP navigation adapter that posts only to `/api/navigate`, and safe LLM/knowledge fallback construction.
- [ ] Run the targeted test; expect all bridge assertions to pass.
- [ ] Commit the bridge API and tests.

### Task 2: Add a tested Jetson-side final-text client

**Files:**
- Create: `voice_assistant/hospital_guide_client.py`
- Create: `tests/test_hospital_guide_client.py`

- [ ] Write tests that verify a UTF-8 `POST` is sent to `/api/hospital-guide/turn`, the reply is extracted from the success envelope, and malformed/error envelopes fail closed.
- [ ] Run the targeted test; expect import failure before implementation.
- [ ] Implement `HospitalGuideClient.process_final_text` with timeout and response validation.
- [ ] Run the targeted test; expect all assertions to pass.
- [ ] Commit the final-text client and tests.

### Task 3: Wire the bridge into the API and document live-mode configuration

**Files:**
- Modify: `api_server.py`
- Modify: `voice_assistant/README.md`
- Modify: `tests/test_hospital_guide_console.py`

- [ ] Write a route smoke test that registers both the read-only console and the bridge without duplicating dashboard routes.
- [ ] Run the affected tests and observe the missing bridge registration failure.
- [ ] Register the bridge with paths rooted at the repository and document `MINIMOVER_HOSPITAL_GUIDE_MODE=1`, LLM variables, ShortMedKG setup, and the coordinate-enablement prerequisite.
- [ ] Run all hospital-guide tests and compile the changed Python files.
- [ ] Commit API integration and documentation.

### Task 4: Deploy and minimally patch the existing Jetson microphone client

**Files on Jetson:**
- Add: `hospital_guide_bridge.py`, `voice_assistant/hospital_guide.py`, `voice_assistant/medical_knowledge.py`, `voice_assistant/hospital_guide_client.py`, `voice_assistant/hospital_guide_telemetry.py`, template and ShortMedKG fetch script
- Modify: `api_server.py`, `voice_assistant/car_client.py`, `.env.voice`

- [ ] Upload and checksum all additive files; never overwrite the dirty Jetson files wholesale.
- [ ] Download and validate the pinned ShortMedKG JSONL snapshot, then inspect its record count and SHA-256 metadata.
- [ ] Insert the bridge registration into Jetson `api_server.py` with an atomic marker-checked patch and a backup.
- [ ] Insert a hospital-mode branch into Jetson `car_client.py`: send `final_text` to the local bridge and TTS its reply; ignore `chat_reply`/`command` in hospital mode; preserve legacy behavior when disabled.
- [ ] Add only `MINIMOVER_HOSPITAL_GUIDE_MODE=1` and non-secret guide settings to `.env.voice`, keeping a backup.
- [ ] Syntax-check before restart.

### Task 5: Verify real deployment safely

**Files:** no new source files.

- [ ] Restart only the exact `api_server.py` PID and verify `/hospital-guide`, `/api/hospital-guide/status`, `/api/hospital-guide/config`, and `/api/hospital-guide/turn` validation behavior.
- [ ] Start the existing `car_client.py` under the current voice environment and confirm its log reports a real ASR `final_text` when a person speaks after the wake word.
- [ ] Confirm the dashboard moves from `IDLE` to `WAITING_CONFIRMATION` from that actual utterance, without a dashboard navigation endpoint.
- [ ] Do not enable or send physical navigation until audited map points are configured. Report this prerequisite plainly.
