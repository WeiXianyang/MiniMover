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

# 3. Check model file and recover from Git LFS pointer if needed
MODEL_FILE="fire_smoke_detection/model/best.pt"
MODEL_EXPECTED_SHA256="d1eae6859229ac1f5699c60f9445fa054dafc6a2cc59f00fc30ea6379dc3247e"
if [ ! -f "$MODEL_FILE" ]; then
    echo "  [ERROR] Model not found: $MODEL_FILE"
    echo "  Run: git lfs pull --include='$MODEL_FILE'"
    exit 1
fi

# Check for Git LFS pointer (136-byte pointer file instead of real model)
LFS_HEADER=$(head -c 50 "$MODEL_FILE" 2>/dev/null)
if echo "$LFS_HEADER" | grep -q "git-lfs.github.com"; then
    echo "  [WARN] Model file is a Git LFS pointer (size=$(stat -c%s "$MODEL_FILE" 2>/dev/null || echo '?') bytes)"
    echo "  [INFO] Attempting git lfs pull to download real model..."
    if command -v git &>/dev/null && git lfs version &>/dev/null; then
        git lfs pull --include="$MODEL_FILE" 2>&1
        if [ $? -ne 0 ] || head -c 50 "$MODEL_FILE" 2>/dev/null | grep -q "git-lfs.github.com"; then
            echo "  [ERROR] git lfs pull failed or file is still a pointer."
            echo "  Manual fix: cd $(pwd) && git lfs pull --include='$MODEL_FILE'"
            exit 1
        fi
        echo "  [OK] Model downloaded via git lfs pull"
    else
        echo "  [ERROR] git-lfs not available on this system."
        echo "  Install: sudo apt install git-lfs  (or copy model manually)"
        exit 1
    fi
fi

# Verify SHA256 if possible
if command -v sha256sum &>/dev/null; then
    ACTUAL_SHA=$(sha256sum "$MODEL_FILE" | cut -d' ' -f1)
    if [ "$ACTUAL_SHA" != "$MODEL_EXPECTED_SHA256" ]; then
        echo "  [ERROR] Model SHA256 mismatch!"
        echo "    Expected: $MODEL_EXPECTED_SHA256"
        echo "    Actual:   $ACTUAL_SHA"
        exit 1
    fi
    echo "  [OK] SHA256 verified"
fi
echo "  [OK] Model: $MODEL_FILE ($(stat -c%s "$MODEL_FILE" 2>/dev/null || echo '?') bytes)"

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