#!/bin/bash
kill $(pgrep -f voice_assistant) 2>/dev/null
sleep 1
echo "START $(date)" >> /tmp/vlog
cd ~/MiniMover
source .tts.env
export MINIMOVER_WAKE_WORD=小北
export MINIMOVER_ASR_BACKEND=funasr
nohup ~/MiniMover/.venv-voice-cpu/bin/python -u -m voice_assistant.voice_service >> /tmp/vlog 2>&1 &
echo "PID=$!" >> /tmp/vlog
