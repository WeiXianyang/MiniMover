#!/bin/bash
cd /home/jetson/MiniMover
source /home/jetson/MiniMover/.tts.env
export MINIMOVER_WAKE_WORD=小北
export MINIMOVER_ASR_BACKEND=funasr
export MINIMOVER_CAR_SPEAKER=1
exec /home/jetson/MiniMover/.venv-voice-cpu/bin/python -u -m voice_assistant.voice_service
