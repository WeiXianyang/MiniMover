#!/bin/bash
# Fire Detection — one-click start for fire/smoke YOLOv5 detection
# Reads local ROS web_video_server camera stream, writes telemetry to
#   fire_smoke_detection/runtime/debug/status.json
# which api_server.py reads via /api/detection/status
#
# Dashboard http://<car_ip>:5000/ shows detection status automatically
#
# Usage:
#   bash scripts/start_fire_detection.sh              # CPU mode
#   bash scripts/start_fire_detection.sh --device 0    # GPU mode (Jetson)
#
# Logs: tail -f /tmp/fire_detection.log

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR" || exit 1

DEBUG_DIR="fire_smoke_detection/runtime/debug"
LOG_FILE="/tmp/fire_detection.log"
PID_FILE="/tmp/fire_detection.pid"
EXTRA_ARGS=("$@")
if [ ${#EXTRA_ARGS[@]} -eq 0 ]; then
    EXTRA_ARGS=("--device" "cpu")
fi

echo "========================================"
echo "  Fire Detection Service Starting"
echo "========================================"

# 1. Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "  [WARN] Already running (PID=$OLD_PID)"
        echo "  Stop first: pkill -f detector.py"
        exit 1
    fi
fi

# 2. Create debug directory
mkdir -p "$DEBUG_DIR"
echo "  [OK] Debug dir: $SCRIPT_DIR/$DEBUG_DIR"

# 3. Check model file
MODEL_FILE="fire_smoke_detection/model/best.pt"
if [ ! -f "$MODEL_FILE" ]; then
    echo "  [ERROR] Model not found: $MODEL_FILE"
    exit 1
fi
echo "  [OK] Model: $MODEL_FILE"

# 4. Start detection process
ROS_STREAM="http://localhost:8080/stream?topic=/camera/color/image_raw"
echo "  [OK] Starting detection (CPU mode)..."
nohup python3 fire_smoke_detection/detector.py \
    --source "$ROS_STREAM" \
    "${EXTRA_ARGS[@]}" \
    --no-view \
    --monitor-debug-dir "$DEBUG_DIR" \
    > "$LOG_FILE" 2>&1 &
DET_PID=$!
echo "$DET_PID" > "$PID_FILE"

# 5. Confirm startup
sleep 3
if kill -0 "$DET_PID" 2>/dev/null; then
    echo "  [OK] Fire detection started (PID=$DET_PID)"
else
    echo "  [ERROR] Process crashed, check: tail -f $LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi

echo ""
echo "========================================"
echo "  Logs:  tail -f $LOG_FILE"
echo "  Stop:  pkill -f detector.py"
echo "========================================"