#!/usr/bin/env bash
set -u

API_BASE=''
ROS_DOMAIN=''
TIMEOUT_SECONDS=2
HAS_FAILURE=0
SEEN_API_BASE=0
SEEN_ROS_DOMAIN=0
SEEN_TIMEOUT_SECONDS=0

TMP_DIR=$(mktemp -d 2>/dev/null) || {
  printf 'usage error: unable to create temporary directory\n' >&2
  exit 2
}
trap 'rm -rf "$TMP_DIR"' EXIT

usage() {
  cat <<'USAGE'
Usage: check_hospital_guide_preflight.sh --api-base http[s]://host[:port] [--ros-domain N] [--timeout-seconds N]
USAGE
}

usage_error() {
  printf 'usage error: %s\n' "$1" >&2
  usage >&2
  exit 2
}

pass() {
  printf '[PASS] %s\n' "$1"
}

fail() {
  printf '[FAIL] %s\n' "$1"
  HAS_FAILURE=1
}

unavailable() {
  printf '[UNAVAILABLE] %s\n' "$1"
  HAS_FAILURE=1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --api-base)
      [ "$#" -ge 2 ] || usage_error 'missing value for --api-base'
      [ "$SEEN_API_BASE" -eq 0 ] || usage_error 'duplicate --api-base'
      API_BASE="$2"
      SEEN_API_BASE=1
      shift 2
      ;;
    --ros-domain)
      [ "$#" -ge 2 ] || usage_error 'missing value for --ros-domain'
      [ "$SEEN_ROS_DOMAIN" -eq 0 ] || usage_error 'duplicate --ros-domain'
      ROS_DOMAIN="$2"
      SEEN_ROS_DOMAIN=1
      shift 2
      ;;
    --timeout-seconds)
      [ "$#" -ge 2 ] || usage_error 'missing value for --timeout-seconds'
      [ "$SEEN_TIMEOUT_SECONDS" -eq 0 ] || usage_error 'duplicate --timeout-seconds'
      TIMEOUT_SECONDS="$2"
      SEEN_TIMEOUT_SECONDS=1
      shift 2
      ;;
    --help)
      [ "$#" -eq 1 ] || usage_error '--help cannot be combined with other arguments'
      usage
      exit 0
      ;;
    *)
      usage_error "unknown argument: $1"
      ;;
  esac
done

[ -n "$API_BASE" ] || usage_error '--api-base is required'
while [[ "$API_BASE" == */ ]]; do
  API_BASE=${API_BASE%/}
done
[[ "$API_BASE" =~ ^https?://[^/:[:space:]]+(:[0-9]+)?$ ]] || usage_error 'invalid --api-base URL'
[ -z "$ROS_DOMAIN" ] || [[ "$ROS_DOMAIN" =~ ^[0-9]+$ ]] || usage_error 'invalid --ros-domain'
[[ "$TIMEOUT_SECONDS" =~ ^[1-9][0-9]*$ ]] || usage_error 'invalid --timeout-seconds'

if ! command -v curl >/dev/null 2>&1; then
  unavailable 'local.curl: command unavailable'
  printf '[PENDING] release_gate: safety officer, hardware emergency stop, and route clearance must be confirmed\n'
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  unavailable 'local.python3: command unavailable'
  printf '[PENDING] release_gate: safety officer, hardware emergency stop, and route clearance must be confirmed\n'
  exit 1
fi

probe_get() {
  local name="$1"
  local path="$2"
  local kind="$3"
  local body_file="$TMP_DIR/${name}.json"
  local summary
  local record
  local first
  local second
  local third

  if ! curl --silent --show-error --fail --request GET \
    --connect-timeout "$TIMEOUT_SECONDS" --max-time "$TIMEOUT_SECONDS" \
    --output "$body_file" "${API_BASE}${path}"; then
    unavailable "api.${name}: GET unavailable"
    return
  fi

  summary=$(python3 - "$kind" "$body_file" 2>/dev/null <<'PY'
import json
import re
import sys

kind, filename = sys.argv[1:]
with open(filename, encoding="utf-8") as handle:
    payload = json.load(handle)
data = payload["data"]
if not isinstance(data, dict):
    raise ValueError("data must be an object")
if kind == "stack":
    ready = data.get("patrol_ready", data.get("stack_ready"))
    if not isinstance(ready, bool):
        raise ValueError("missing readiness boolean")
    print(f"stack\t{str(ready).lower()}")
elif kind == "pose":
    valid, frame_id = data.get("valid"), data.get("frame_id")
    if (
        not isinstance(valid, bool)
        or not isinstance(frame_id, str)
        or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_/-]{0,63}", frame_id)
    ):
        raise ValueError("missing or unsafe pose safety fields")
    print(f"pose\t{str(valid).lower()}\t{frame_id}")
elif kind == "demo":
    session = data.get("session")
    phase = session.get("phase") if isinstance(session, dict) else None
    if not isinstance(phase, str) or not re.fullmatch(r"[A-Z_]{1,48}", phase):
        raise ValueError("missing or unsafe anonymous phase")
    print(f"demo\t{phase}")
else:
    raise ValueError("unsupported parser")
PY
)
  if [ "$?" -ne 0 ]; then
    unavailable "api.${name}: invalid anonymous JSON status"
    return
  fi

  IFS=$'\t' read -r first second third <<< "$summary"
  case "$kind" in
    stack)
      [ "$first" = 'stack' ] && { [ "$second" = 'true' ] || [ "$second" = 'false' ]; } || {
        unavailable "api.${name}: invalid anonymous JSON status"
        return
      }
      if [ "$second" = 'true' ]; then
        pass "api.${name}: ready=true"
      else
        fail "api.${name}: ready=false"
      fi
      ;;
    pose)
      [ "$first" = 'pose' ] && { [ "$second" = 'true' ] || [ "$second" = 'false' ]; } && [ -n "$third" ] || {
        unavailable "api.${name}: invalid anonymous JSON status"
        return
      }
      if [ "$second" = 'true' ] && [ "$third" = 'map' ]; then
        pass "api.${name}: valid=true frame_id=map"
      else
        fail "api.${name}: valid=${second} frame_id=${third}"
      fi
      ;;
    demo)
      [ "$first" = 'demo' ] && [ -n "$second" ] || {
        unavailable "api.${name}: invalid anonymous JSON status"
        return
      }
      pass "api.${name}: phase=${second}"
      ;;
  esac
}

ros_query() {
  if [ -n "$ROS_DOMAIN" ]; then
    ROS_DOMAIN_ID="$ROS_DOMAIN" ros2 "$@"
  else
    ros2 "$@"
  fi
}

probe_ros_graph() {
  local node_file="$TMP_DIR/ros_nodes.txt"
  local action_file="$TMP_DIR/ros_actions.txt"
  local topic_file="$TMP_DIR/ros_topics.txt"
  local node_count
  local visible_topics=''
  local topic

  if ! command -v ros2 >/dev/null 2>&1; then
    unavailable 'ros.graph: ros2 command unavailable'
    return
  fi

  if ros_query node list >"$node_file" 2>/dev/null; then
    node_count=$(awk 'NF { count += 1 } END { print count + 0 }' "$node_file")
    pass "ros.nodes: count=${node_count}"
  else
    unavailable 'ros.nodes: discovery unavailable'
  fi

  if ros_query action list -t >"$action_file" 2>/dev/null; then
    if grep -Eq '(^|/)navigate_to_pose([[:space:]]|$)' "$action_file"; then
      pass 'ros.navigate_to_pose: action visible'
    else
      fail 'ros.navigate_to_pose: action missing'
    fi
  else
    unavailable 'ros.navigate_to_pose: discovery unavailable'
  fi

  if ros_query topic list -t >"$topic_file" 2>/dev/null; then
    for topic in /map /amcl_pose /tf /odom /scan; do
      if awk -v expected="$topic" '$1 == expected { found = 1 } END { exit !found }' "$topic_file"; then
        if [ -n "$visible_topics" ]; then
          visible_topics="${visible_topics},${topic}"
        else
          visible_topics="$topic"
        fi
      fi
    done
    if awk '$1 == "/map" { found = 1 } END { exit !found }' "$topic_file"; then
      pass "ros.topics: visible=${visible_topics}"
    else
      fail "ros.topics: visible=${visible_topics:-none}; /map missing"
    fi
  else
    unavailable 'ros.topics: discovery unavailable'
  fi
}

probe_get nav_stack /api/nav/stack/status stack
probe_get nav_pose /api/nav/pose pose
probe_get demo_status /api/hospital-guide/demo/status demo
probe_ros_graph
printf '[PENDING] release_gate: safety officer, hardware emergency stop, and route clearance must be confirmed\n'

if [ "$HAS_FAILURE" -ne 0 ]; then
  exit 1
fi
exit 0
