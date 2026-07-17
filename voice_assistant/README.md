# MiniMover Hospital Guide Demo

This directory now contains the **only supported voice flow** for the five-minute
hospital-guide demo. It is intentionally direct: there is no wake word, generic
chat, dance, velocity command, or legacy motion-command client.

## Runtime path

```text
Jetson microphone
  -> voice_assistant/car_client_jetson.py
  -> PC voice_assistant/pc_asr_server.py (Silero VAD + DashScope ASR)
  -> POST /api/hospital-guide/turn
  -> Jetson POST /api/audio/say
```

`CaptureGate` prevents TTS playback from being uploaded as another microphone
turn. The PC relay sends only `final_text`, speech status, capture-gate status,
and monitoring telemetry. It has no wake-word or motion-command branch.

## Live start

From the development PC, run:

```powershell
$env:MINIMOVER_SSH_PASSWORD = '<Jetson SSH password>'
python scripts/start_hospital_guide_demo.py --jetson-host <Jetson IP>
Remove-Item Env:MINIMOVER_SSH_PASSWORD
```

The launcher starts/reuses PC ASR, synchronizes the dedicated Jetson runtime
files before each run, then restarts only `car_client_jetson.py` so the uploaded
source is the process actually using the microphone. It never uploads local
credential files.

The Jetson requires a private `.env.voice` with the DashScope credentials and
its local API service configuration. Keep that file out of Git.

## Demonstration check

1. Open `/hospital-guide` to observe final ASR text, guide replies, and status.
2. Say a complete guide request directly, for example: `?????`.
3. Confirm the spoken guide reply and, where a configured department point is
   available, the existing hospital-guide navigation handoff.

## Retired paths

The following legacy executable paths were removed: the generic voice service,
wake-word service, generic LLM chat client, WebSocket motion client, command
parser, and `/api/move` HTTP client. Do not recreate or launch them for this
demo. Navigation remains owned by the hospital-guide bridge and configured
hospital department markers, not by spoken velocity commands.
