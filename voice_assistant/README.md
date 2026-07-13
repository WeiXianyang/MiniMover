# MiniMover voice assistant

The service now supports this pipeline:

```text
microphone -> FunASR Paraformer 2-pass (primary)
           -> local VAD + OpenAI-compatible Whisper (explicit fallback)
           -> safe command parser -> /api/move
           -> optional LLM -> optional online TTS
```

## Supported motion commands

- `???` / `??`
- `???` / `??`
- `???` / `??`
- `??` / `????`

Unsupported speech never moves the car unless an LLM is configured; then it is
treated as a question and is sent to the LLM without granting it motion control.

## Install

On the car Linux environment:

```bash
pip3 install -r requirements-voice.txt
```

## Run

Start the existing car API first, then run the local FunASR service:

```bash
python3 -m voice_assistant.voice_service --car-url http://127.0.0.1:5000 --asr funasr
```

Use the Whisper fallback explicitly:

```bash
export MINIMOVER_ASR_BACKEND=whisper
export MINIMOVER_WHISPER_URL=https://your-openai-compatible-endpoint/v1
export MINIMOVER_API_KEY=replace-me
python3 -m voice_assistant.voice_service --asr whisper
```

Optional question answering and TTS:

```bash
export MINIMOVER_LLM_URL=https://your-openai-compatible-endpoint/v1
export MINIMOVER_LLM_MODEL=your-chat-model
export MINIMOVER_TTS_URL=https://your-openai-compatible-endpoint/v1
export MINIMOVER_TTS_VOICE=alloy
python3 -m voice_assistant.voice_service
```

Configuration variables include `MINIMOVER_CAR_URL`, `MINIMOVER_VOICE_SPEED`,
`MINIMOVER_VOICE_DURATION`, `MINIMOVER_ASR_BACKEND`, `MINIMOVER_WHISPER_URL`,
`MINIMOVER_LLM_URL`, `MINIMOVER_LLM_MODEL`, and `MINIMOVER_TTS_URL`.

## Speaker gate

Enroll the authorized speaker once (15 seconds):

```bash
python3 -m voice_assistant.speaker_verifier ~/.minimover/speaker_profile.npy
```

Start voice control with speaker verification enabled:

```bash
python3 -m voice_assistant.voice_service \
  --asr funasr \
  --speaker-profile ~/.minimover/speaker_profile.npy
```

Motion commands require a CAM++ cosine similarity of at least `0.38`.
Stop commands remain highest priority and always issue `/api/move` stop without
requiring a speaker match.

## Pending Linux audio work

The following interfaces are intentionally reserved for the next hardware pass:

- ALSA input-device enumeration and explicit device selection.
- `scipy.signal.resample_poly` for microphones whose native rate is not 16 kHz.

The current service requests 16 kHz directly through `sounddevice`; these two
Linux-specific adapters remain TODOs until the car's actual ALSA devices are
confirmed.
