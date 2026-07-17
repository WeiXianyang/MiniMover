# Five-Minute Hospital Guide Demo Consolidation Plan

**Date:** 2026-07-17

## Goal

Run one reliable hospital-guide demonstration path. The supported voice flow is:

```text
Jetson microphone
-> car_client_jetson.py
-> PC pc_asr_server.py (Silero VAD + DashScope ASR)
-> /api/hospital-guide/turn
-> /api/audio/say
```

Hospital department navigation, when configured by the existing hospital-guide
bridge and department marker data, remains a hospital-guide handoff. There is
no spoken velocity or generic robot-control path.

## Required runtime boundaries

- No wake word or startup greeting.
- Every substantive ASR result is emitted as `final_text`.
- `CaptureGate` suppresses microphone upload while TTS is playing and clears
  partial VAD state at both boundaries.
- `audio_turn_safety.py` remains the source of truth for streamed WAV duration.
- The PC relay retains VAD, DashScope ASR, ASR status, and monitoring telemetry.
- The Jetson client only calls the hospital-guide API and TTS API.

## Retired components

The old generic voice/motion mode is removed: wake-word handling, generic chat,
spoken movement commands, dance, `/api/move`, the old general voice service,
and its launch helpers. These paths must not be reintroduced for this demo.

## Deployment synchronization

`scripts/start_hospital_guide_demo.py` synchronizes the dedicated Jetson runtime
on each launch before it starts the demo:

1. `scripts/start_hospital_guide_demo.sh`
2. `voice_assistant/car_client_jetson.py`
3. `voice_assistant/audio_turn_safety.py`
4. `voice_assistant/hospital_guide_client.py`

It then invokes the Jetson launcher with `--restart-client`. That flag checks
that the existing process is exactly `car_client_jetson.py`, stops only that
microphone client, and starts the synchronized source. It does not stop the API
service, navigation stack, or arbitrary processes. Credentials remain in the
Jetson-only `.env.voice` and are not copied by the launcher.

## Verification checklist

- [x] PC ASR has no wake-word, command parsing, generic chat, or movement branch.
- [x] Jetson client has only final-text hospital-guide and TTS handling.
- [x] Legacy executable voice/motion modules are removed.
- [x] Dedicated launcher syncs and restarts the microphone client safely.
- [ ] Reach the Jetson over SSH and execute the synchronized live launcher.
- [ ] Speak a direct guide request and verify final ASR text, guide reply, and
      configured department handoff in the live console.

## Local verification commands

```powershell
python -m pytest `
  tests/test_audio_turn_safety.py `
  tests/test_hospital_guide.py `
  tests/test_hospital_guide_bridge.py `
  tests/test_hospital_guide_client.py `
  tests/test_hospital_guide_console.py `
  tests/test_hospital_guide_demo_launcher.py `
  tests/test_hospital_guide_telemetry.py `
  -q

python -m py_compile `
  api_server.py `
  hospital_guide_bridge.py `
  audio/icar_audio.py `
  voice_assistant/pc_asr_server.py `
  voice_assistant/car_client_jetson.py `
  voice_assistant/audio_turn_safety.py `
  scripts/start_hospital_guide_demo.py

git diff --check
```
