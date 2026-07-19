# Hospital Guide Reliability, Face Demo, and Multilingual Voice Design

**Date:** 2026-07-19

## Context

The live hospital-guide demonstration has three visible defects: navigation failures are collapsed into the generic phrase ???????, face recognition stops after the first successful welcome, and the ASR request is configured as Chinese-only even though the deployed ASR/TTS services support multilingual input and output. The physical robot previously entered a Nav2 spin recovery while odometry/IMU feedback was invalid, so the navigation safety gate must remain fail-closed.

## Goals

1. Preserve the real navigation health gate and return its concrete rejection reason to the user.
2. Rename the two demo identities from ???/??? to ??/?? without changing their face IDs.
3. Continue scanning after a recognition success, welcome each distinct identity once per demo session, and allow recognition again after reset.
4. Use the existing ASR/TTS providers for automatic-language input and same-language output, with reliable Chinese, English, and French demo phrases.
5. Keep the internal-medicine target fixed at `(8.0, 3.0, 0.0)`.
6. Store the factory SSH password only in ignored local configuration; never commit or print it.

## Non-goals

- Removing or weakening navigation preflight checks.
- Sending a real navigation goal during development or automated tests.
- Re-enrolling faces or changing cloud face user IDs.
- Replacing the deployed ASR or TTS provider.
- Providing medical diagnosis, prescriptions, or unrestricted free-form robot motion.

## Design

### Navigation error propagation

`HospitalGuideNavigationClient.navigate_to()` will catch HTTP errors from `/api/navigate`, parse the response body as JSON, and raise a narrow navigation exception containing the server's `msg`. The conversation orchestrator will convert that exception to a safe spoken response such as ????????????????????????????? Network/protocol failures retain a conservative generic failure, but are no longer mislabeled as a service-start state.

The health gate in `navigation/ros_bridge.py` remains authoritative. The client only improves observability; it does not reinterpret a rejection as success.

### Face identity migration and continuous scanning

`face/store.py` will expose an idempotent migration that updates local SQLite display names only when the legacy names exist. It will run during hospital-demo startup before recognition begins. Duplicate-name conflicts fail visibly rather than overwriting another identity.

`HospitalGuideDemoController` will own a per-session set of recognized identity keys. The scanner remains active after the first recognition. A new identity emits a welcome event and updates public status; an already-seen identity is ignored. A queue replaces the single welcome slot so ?? and ?? can each be claimed and acknowledged without restarting the guide conversation. Reset/start clears the set and queue.

### Multilingual voice

The existing Qwen3 ASR call will omit the `language` option when `MINIMOVER_ASR_LANGUAGE` is empty or `auto`, allowing the deployed service to choose the language. Existing explicit language configuration remains supported. The PC ASR server will default the language setting to `auto` rather than `zh` and keep the current provider/fallback choices.

The hospital-guide intent layer will normalize common Chinese, English, and French symptoms, department references, confirmations, cancellations, and emergency phrases into the existing safe state machine. The reply language is selected from the current utterance, with fixed safety-critical reply templates in Chinese, English, and French. Other languages may use the existing guide LLM for informational replies, but navigation can only target a configured department ID and still requires the explicit confirmation state plus the navigation health gate.

The current TTS path receives the already-localized text. No provider replacement is required.

### Local SSH credential memory

`.env.voice` remains ignored by Git and stores `MINIMOVER_SSH_PASSWORD`. The Windows launcher will load missing values from `.env.voice` without overriding environment variables. It will never log the password. This enables subsequent Paramiko connections without interactive re-entry while respecting the repository rule against committed credentials.

## Safety and failure behavior

- Navigation health rejection always means no goal submission.
- Concurrent/active goals remain rejected.
- Unknown departments and arbitrary coordinates cannot be produced by multilingual parsing.
- Face database migration is idempotent and transactional.
- Recognition errors do not terminate the scanner loop.
- A second face welcome does not reset conversation or trigger movement.
- SSH, ASR, TTS, and LLM failures are logged without secrets and return conservative user-facing messages.

## Verification

Automated tests will cover HTTP error JSON parsing, conservative fallback errors, French/English/Chinese intent and response selection, ASR automatic-language options, same-person suppression, two-person sequencing, reset behavior, idempotent face migration, and ignored credential loading. The existing `tests` suite, Python compilation, shell syntax checks, and `git diff --check` will run after targeted tests.

Physical verification remains separate: keep the hardware emergency stop pressed, query `GET /api/nav/demo/health`, and do not issue ????? or any motion command until serial, IMU, odometry, localization, and wheel-off-ground feedback tests pass.
