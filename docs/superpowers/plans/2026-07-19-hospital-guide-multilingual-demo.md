# Hospital Guide Reliability and Multilingual Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the hospital-guide demo report real navigation safety failures, recognize ?? and ?? once each per session, and understand/respond in the speaker's language using the existing ASR/TTS services.

**Architecture:** Keep navigation fail-closed and improve only error propagation. Extend the existing demo controller with per-session identity deduplication and queued welcomes, and extend the current guide state machine with localized phrases/templates. Configure the existing ASR for automatic language selection while preserving explicit language overrides.

**Tech Stack:** Python 3, Flask, urllib, SQLite, threading, DashScope ASR/TTS, pytest/unittest.

---

### Task 1: Persist ignored SSH launcher credentials safely

**Files:**
- Modify: `scripts/start_hospital_guide_demo.py`
- Test: `tests/test_hospital_guide_demo_launcher.py`
- Local-only: `.env.voice` (ignored, never staged)

- [ ] Add a failing test that creates a temporary `.env.voice`, verifies `MINIMOVER_SSH_PASSWORD` is loaded when absent, verifies an existing environment value wins, and verifies no secret is printed.
- [ ] Run `python -m pytest -q tests/test_hospital_guide_demo_launcher.py` and confirm the new test fails.
- [ ] Add a small dotenv parser for the launcher's required local keys and load it before argument/password resolution.
- [ ] Re-run the launcher test and confirm it passes.

### Task 2: Propagate navigation health rejection reasons

**Files:**
- Modify: `hospital_guide_bridge.py`
- Modify: `voice_assistant/hospital_guide.py`
- Test: `tests/test_hospital_guide_bridge.py`
- Test: `tests/test_hospital_guide.py`

- [ ] Add a failing client test using a local HTTP error response whose JSON is `{"code": 1, "msg": "?????????"}` and assert the raised error preserves that reason.
- [ ] Add a failing orchestrator test that confirms the reply says the safety check failed and the vehicle will not move, without claiming navigation started.
- [ ] Run the two targeted test files and confirm the new tests fail.
- [ ] Implement a typed navigation rejection, JSON parsing for `urllib.error.HTTPError`, bounded/sanitized error text, and localized conservative failure replies.
- [ ] Re-run the targeted tests and confirm they pass.

### Task 3: Rename demo identities and continue scanning distinct people

**Files:**
- Modify: `face/store.py`
- Modify: `hospital_guide_demo.py`
- Modify: `scripts/start_hospital_guide_demo.py` runtime upload list if a new helper is introduced
- Test: `tests/test_face_store.py`
- Test: `tests/test_hospital_guide_demo.py`

- [ ] Add failing SQLite tests for the idempotent migrations `??? -> ??` and `??? -> ??`, including a duplicate-target conflict.
- [ ] Add failing controller tests for ?? then ??, repeated ?? suppression, queued welcome claims, and reset allowing ?? again.
- [ ] Run the two targeted test files and confirm failure.
- [ ] Implement a transactional display-name migration in `face/store.py` without modifying face IDs.
- [ ] Replace the single welcome slot with a per-session queue and identity set; keep the scanner running outside the initial `SCANNING` phase while the session remains current.
- [ ] Re-run targeted tests and confirm they pass.

### Task 4: Enable automatic-language ASR with existing provider

**Files:**
- Modify: `voice_assistant/asr_backends.py`
- Modify: `voice_assistant/pc_asr_server.py`
- Test: `tests/test_asr_backends.py`
- Test: `tests/test_audio_turn_safety.py`

- [ ] Add a failing test asserting `language="auto"` and `language=""` omit the Qwen3 `language` ASR option, while `language="fr"` remains explicit.
- [ ] Add a source/config test asserting the PC ASR default is `auto`, not `zh`.
- [ ] Run targeted ASR tests and confirm failure.
- [ ] Normalize `auto` to an omitted provider option and change the PC server default without changing provider/model selection.
- [ ] Re-run targeted tests and confirm they pass.

### Task 5: Add same-language hospital-guide intents and replies

**Files:**
- Modify: `voice_assistant/hospital_guide.py`
- Modify: `voice_assistant/data/hospital_guide_template.json`
- Modify: `hospital_guide_bridge.py` if language metadata must be exposed
- Test: `tests/test_hospital_guide.py`
- Test: `tests/test_hospital_guide_bridge.py`

- [ ] Add failing tests for `J'ai mal ? la t?te`, `Where is internal medicine?`, French/English confirmation and cancellation, and same-language navigation rejection replies.
- [ ] Add failing tests proving foreign-language text cannot inject a department ID or coordinates and cannot bypass confirmation.
- [ ] Run targeted guide tests and confirm failure.
- [ ] Add deterministic language detection for Chinese/English/French demo utterances, localized intent hints, department aliases, and fixed safety templates while preserving the configured department whitelist.
- [ ] Re-run targeted tests and confirm they pass.

### Task 6: Full verification and safe deployment preparation

**Files:**
- Modify as needed only for defects exposed by verification.
- Update: `docs/runbooks/five-minute-hospital-guide-demo.md`

- [ ] Run `python -m pytest -q tests`.
- [ ] Run `python -m compileall hospital_guide_bridge.py hospital_guide_demo.py face voice_assistant navigation scripts`.
- [ ] Run Bash syntax checks for changed shell scripts with the available Bash runtime.
- [ ] Run `git diff --check` and inspect `git status --short` to exclude unrelated RAG files and `.env.voice`.
- [ ] With hardware emergency stop still pressed, deploy runtime files and perform only read-only checks, including `GET /api/nav/demo/health`.
- [ ] Do not perform physical navigation until the separate serial/IMU/odometry/localization and wheel-off-ground feedback checklist passes.
