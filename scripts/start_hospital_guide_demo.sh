#!/usr/bin/env bash
# MiniMover hospital-guide demo launcher for the Jetson.
# This script deliberately starts only real services; it never injects mock ASR,
# telemetry, medical-KB, or navigation data.
set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${MINIMOVER_ENV_FILE:-$PROJECT_DIR/.env.voice}"
ASR_HOST="${MINIMOVER_ASR_HOST:-}"
ASR_PORT="${MINIMOVER_ASR_PORT:-8765}"
CAR_URL="${MINIMOVER_CAR_URL:-http://127.0.0.1:5000}"
CAR_LOG="${MINIMOVER_HOSPITAL_GUIDE_CAR_LOG:-/tmp/minimover-hospital-guide-car.log}"
CAR_PID_FILE="${MINIMOVER_HOSPITAL_GUIDE_CAR_PID_FILE:-/tmp/minimover-hospital-guide-car.pid}"
RESTART_CLIENT=0

usage() {
    cat <<'EOF'
Usage: start_hospital_guide_demo.sh [--asr-host HOST] [--asr-port PORT] [--restart-client]

Starts the real Jetson-side hospital-guide chain:
printf '演示流程: 直接说导诊问题，例如：头疼应该挂什么科？\n'
  voice_assistant/car_client_jetson.py -> Jetson microphone -> PC ASR final_text
  hospital guide -> ShortMedKG + configured OpenAI-compatible LLM -> car TTS

No mock input or fake navigation result is generated.
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --asr-host)
            [ "$#" -ge 2 ] || { echo "[ERROR] --asr-host needs a value" >&2; exit 2; }
            ASR_HOST="$2"; shift 2 ;;
        --asr-port)
            [ "$#" -ge 2 ] || { echo "[ERROR] --asr-port needs a value" >&2; exit 2; }
            ASR_PORT="$2"; shift 2 ;;
        --restart-client)
            RESTART_CLIENT=1; shift ;;
        -h|--help)
            usage; exit 0 ;;
        *)
            echo "[ERROR] unknown argument: $1" >&2
            usage >&2
            exit 2 ;;
    esac
done

if [ ! -r "$ENV_FILE" ]; then
    echo "[ERROR] missing voice environment: $ENV_FILE" >&2
    echo "        Create it on the Jetson; do not commit credentials." >&2
    exit 1
fi

# Hospital demo navigation exclusively owns the chassis serial port. Persist
# this non-secret flag in the private runtime environment so the systemd API
# process sees it after restart without exposing or rewriting credential values.
if grep -q '^MINIMOVER_NAV_OWNS_CHASSIS=' "$ENV_FILE"; then
    sed -i 's/^MINIMOVER_NAV_OWNS_CHASSIS=.*/MINIMOVER_NAV_OWNS_CHASSIS=1/' "$ENV_FILE"
else
    printf '
MINIMOVER_NAV_OWNS_CHASSIS=1
' >> "$ENV_FILE"
fi

# Load the private environment without printing it. The API service also loads
# this file through its systemd drop-in; this is for the car client process.
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

ASR_HOST="${ASR_HOST:-${MINIMOVER_ASR_HOST:-}}"
ASR_PORT="${ASR_PORT:-${MINIMOVER_ASR_PORT:-8765}}"
CAR_URL="${CAR_URL:-${MINIMOVER_CAR_URL:-http://127.0.0.1:5000}}"

[ -n "$ASR_HOST" ] || { echo "[ERROR] ASR host is not configured; pass --asr-host HOST" >&2; exit 1; }
case "$ASR_PORT" in (*[!0-9]*|'') echo "[ERROR] invalid ASR port: $ASR_PORT" >&2; exit 1;; esac

PYTHON=""
for candidate in \
    "$PROJECT_DIR/.venv-voice-cpu/bin/python" \
    "$PROJECT_DIR/.venv-voice/bin/python" \
    /usr/bin/python3 \
    python3; do
    if [ -x "$candidate" ] 2>/dev/null || command -v "$candidate" >/dev/null 2>&1; then
        PYTHON="$candidate"
        break
    fi
done
[ -n "$PYTHON" ] || { echo "[ERROR] no usable Python 3 interpreter found" >&2; exit 1; }

printf '\n=== MiniMover 医院导诊现场演示 ===\n'
printf '项目目录: %s\n' "$PROJECT_DIR"
printf 'PC ASR:   ws://%s:%s/ws/asr\n' "$ASR_HOST" "$ASR_PORT"
printf '小车 API:  %s\n' "$CAR_URL"

if ! command -v curl >/dev/null 2>&1; then
    echo "[ERROR] curl is required for health checks" >&2
    exit 1
fi

# The service is intentionally managed by systemd so API restarts and logs are
# visible with journalctl. The installed policy allows this command without
# embedding a sudo password in the project.
if command -v systemctl >/dev/null 2>&1; then
    if ! sudo -n systemctl daemon-reload; then
        echo "[ERROR] cannot reload systemd configuration without sudo permission" >&2
        exit 1
    fi
    # Runtime files were synchronized immediately before this launcher runs.
    # A plain `start` leaves an already-running Python process on stale code.
    if ! sudo -n systemctl restart fireguard-api.service; then
        echo "[ERROR] cannot restart fireguard-api.service without sudo permission" >&2
        exit 1
    fi
    if ! sudo -n systemctl is-active --quiet fireguard-api.service; then
        echo "[ERROR] fireguard-api.service is not active" >&2
        sudo -n journalctl -u fireguard-api.service -n 30 --no-pager >&2 || true
        exit 1
    fi
    echo "[OK] API service active"
else
    echo "[ERROR] systemctl is required on the Jetson" >&2
    exit 1
fi

api_ready=0
for _ in $(seq 1 30); do
    if curl -fsS --max-time 3 "$CAR_URL/hospital-guide" >/dev/null 2>&1; then
        api_ready=1
        break
    fi
    sleep 1
done
if [ "$api_ready" -ne 1 ]; then
    echo "[ERROR] hospital-guide API is not ready: $CAR_URL/hospital-guide" >&2
    sudo -n journalctl -u fireguard-api.service -n 40 --no-pager >&2 || true
    exit 1
fi
echo "[OK] hospital-guide API ready"

if ! curl -fsS --max-time 3 "$CAR_URL/nav/patrol" >/dev/null 2>&1; then
    echo "[ERROR] existing map/patrol console is not ready: $CAR_URL/nav/patrol" >&2
    exit 1
fi
echo "[OK] map/patrol console ready"

# The PC service may still be loading its ASR model when the launcher reaches
# this gate. Retry for a bounded window, but fail closed if no real TCP
# connection succeeds; never report a fake ready state.
asr_ready=0
for _ in $(seq 1 15); do
    if timeout 3 bash -c "</dev/tcp/$ASR_HOST/$ASR_PORT" >/dev/null 2>&1; then
        asr_ready=1
        break
    fi
    sleep 1
done
if [ "$asr_ready" -ne 1 ]; then
    echo "[ERROR] PC ASR is unreachable at $ASR_HOST:$ASR_PORT" >&2
    exit 1
fi
echo "[OK] PC ASR TCP port reachable"

existing_pid=""
if [ -f "$CAR_PID_FILE" ]; then
    candidate_pid="$(cat "$CAR_PID_FILE" 2>/dev/null || true)"
    if [ -n "$candidate_pid" ] && kill -0 "$candidate_pid" 2>/dev/null; then
        existing_pid="$candidate_pid"
    fi
fi
if [ -z "$existing_pid" ]; then
    existing_pid="$(pgrep -f '[v]oice_assistant/car_client_jetson.py' | head -1 || true)"
fi

if [ "$RESTART_CLIENT" -eq 1 ] && [ -n "$existing_pid" ]; then
    process_command="$(tr '\0' ' ' < "/proc/$existing_pid/cmdline" 2>/dev/null || true)"
    case "$process_command" in
        *"voice_assistant/car_client_jetson.py"*) ;;
        *)
            echo "[ERROR] refusing to stop an unexpected process (pid=$existing_pid)" >&2
            exit 1 ;;
    esac
    echo "[INFO] restarting dedicated car client to apply synchronized code (pid=$existing_pid)"
    kill "$existing_pid"
    for _ in $(seq 1 10); do
        kill -0 "$existing_pid" 2>/dev/null || break
        sleep 1
    done
    if kill -0 "$existing_pid" 2>/dev/null; then
        echo "[ERROR] dedicated car client did not exit after restart request (pid=$existing_pid)" >&2
        exit 1
    fi
    rm -f "$CAR_PID_FILE"
    existing_pid=""
fi

if [ -n "$existing_pid" ]; then
    # This dedicated client only implements the hospital-guide demo flow.
    if [ -r "/proc/$existing_pid/environ" ]; then
        process_env="$(tr '\0' '\n' < "/proc/$existing_pid/environ" 2>/dev/null || true)"
        if ! printf '%s\n' "$process_env" | grep -qx 'MINIMOVER_HOSPITAL_GUIDE_DEMO_MODE=1'; then
            echo "[ERROR] existing car client is not in face-triggered hospital demo mode (pid=$existing_pid)" >&2
            echo "        Rerun with --restart-client." >&2
            exit 1
        fi
        if ! printf '%s\n' "$process_env" | grep -qx "MINIMOVER_ASR_HOST=$ASR_HOST"; then
            echo "[ERROR] existing car client points to a different ASR host (pid=$existing_pid)" >&2
            echo "        Stop it manually, then rerun this launcher." >&2
            exit 1
        fi
        actual_log="$(readlink "/proc/$existing_pid/fd/1" 2>/dev/null || true)"
        if [ -n "$actual_log" ] && [ -f "$actual_log" ]; then
            CAR_LOG="$actual_log"
        fi
    fi
    echo "$existing_pid" > "$CAR_PID_FILE"
    echo "[OK] car client already running (pid=$existing_pid)"
else
    cd "$PROJECT_DIR" || exit 1
    # Clear stale readiness/error lines so this launch is judged only by the
    # current client process (USB audio card numbers may change after camera restart).
    : > "$CAR_LOG"
    nohup env \
        MINIMOVER_ASR_HOST="$ASR_HOST" \
        MINIMOVER_ASR_PORT="$ASR_PORT" \
        MINIMOVER_CAR_URL="$CAR_URL" \
        MINIMOVER_HOSPITAL_GUIDE_DEMO_MODE=1 \
        MINIMOVER_CAR_SPEAKER=1 \
        "$PYTHON" -u voice_assistant/car_client_jetson.py \
        >>"$CAR_LOG" 2>&1 < /dev/null &
    car_pid=$!
    echo "$car_pid" > "$CAR_PID_FILE"
    sleep 2
    if ! kill -0 "$car_pid" 2>/dev/null; then
        echo "[ERROR] car client exited during startup; log: $CAR_LOG" >&2
        tail -n 60 "$CAR_LOG" >&2 || true
        exit 1
    fi
    echo "[OK] car client started (pid=$car_pid)"
fi

# The process may still be retrying its first WebSocket connection. Wait for a
# real microphone-open line, but report a useful log tail instead of pretending
# that audio is ready.
mic_ready=0
for _ in $(seq 1 30); do
    if grep -q 'Mic open, listening' "$CAR_LOG" 2>/dev/null; then
        mic_ready=1
        break
    fi
    sleep 1
done
if [ "$mic_ready" -eq 1 ]; then
    echo "[OK] Jetson microphone streaming to PC ASR"
else
    echo "[WARN] car client is alive but microphone-ready log has not appeared yet"
    tail -n 25 "$CAR_LOG" || true
fi

if ! bash "$PROJECT_DIR/scripts/start_hospital_rgb_camera.sh"; then
    echo "[ERROR] failed to start the real RGB camera chain" >&2
    exit 1
fi

if ! curl -fsS --max-time 5 "$CAR_URL/api/face/snapshot" >/dev/null 2>&1; then
    echo "[ERROR] face camera snapshot is unavailable; start :8080 camera/video first" >&2
    exit 1
fi
echo "[OK] face camera snapshot ready"

demo_start_payload="$(curl -fsS --max-time 8 -X POST "$CAR_URL/api/hospital-guide/demo/start")" || {
    echo "[ERROR] failed to start face-triggered hospital demo session" >&2
    exit 1
}
printf '%s' "$demo_start_payload" | grep -q '"code":0' || {
    echo "[ERROR] demo session start rejected: $demo_start_payload" >&2
    exit 1
}
echo "[OK] face scan session started"

JETSON_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
printf '\n控制台:   http://%s:5000/hospital-guide\n' "$JETSON_IP"
printf '地图选点: http://%s:5000/nav/patrol\n' "$JETSON_IP"
printf '车端日志: %s\n' "$CAR_LOG"
printf '停止车端: kill %s\n' "$(cat "$CAR_PID_FILE" 2>/dev/null || echo '?')"
printf '演示流程: 直接说导诊问题，例如：头疼应该挂什么科？\n'
printf '说明: 内科新标定目标: (8.0, 3.0, 0.0)；传感器健康检查通过前禁止释放急停；实体移动前请清空场地并由安全员监护。\n'
