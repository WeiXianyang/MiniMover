#!/bin/bash
cd /home/jetson/MiniMover
export MINIMOVER_WAKE_WORD=小南
export MINIMOVER_ASR_BACKEND=funasr
export MINIMOVER_CAR_SPEAKER=1
exec /home/jetson/MiniMover/.venv-voice/bin/python -u -m voice_assistant.voice_service
