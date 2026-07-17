#!/usr/bin/env bash
# Start the real RGB channel used by the five-minute hospital-guide demo.
# The demo needs only color images for face recognition; it deliberately avoids
# coupling RGB availability to the Astra depth/control USB sibling.
set -eu

CAM_CONTAINER="${MINIMOVER_CAMERA_CONTAINER:-fireguard_cam}"
CAM_ROS_DOMAIN_ID="${CAM_ROS_DOMAIN_ID:-30}"
CAM_TOPIC="/camera/color/image_raw"
CAM_INFO_TOPIC="/camera/color/camera_info"
SNAPSHOT_URL="http://127.0.0.1:8080/snapshot?topic=${CAM_TOPIC}"
ROS_SETUP="/root/icar_ros2_ws/icar_ws/install/setup.bash"
snapshot_file="/tmp/minimover-hospital-rgb-snapshot.jpg"
headers_file="/tmp/minimover-hospital-rgb-snapshot.headers"

fail() {
    echo "[ERROR] $*" >&2
    exit 1
}

command -v docker >/dev/null 2>&1 || fail "docker is required"
command -v curl >/dev/null 2>&1 || fail "curl is required"
command -v file >/dev/null 2>&1 || fail "file is required"
docker inspect "$CAM_CONTAINER" >/dev/null 2>&1 || fail "camera container not found: $CAM_CONTAINER"

# Select an actual Orbbec RGB UVC capture node. Both vendor/product checks and
# a YUYV 640x480 capability check are required so a stale /dev/video number is
# never trusted after USB re-enumeration.
video_device=""
for candidate in /dev/video*; do
    [ -e "$candidate" ] || continue
    props="$(udevadm info -q property -n "$candidate" 2>/dev/null || true)"
    printf '%s\n' "$props" | grep -qx 'ID_VENDOR_ID=2bc5' || continue
    printf '%s\n' "$props" | grep -qx 'ID_MODEL_ID=050f' || continue
    if docker exec "$CAM_CONTAINER" v4l2-ctl -d "$candidate" --list-formats-ext 2>/dev/null \
        | grep -A20 "'YUYV'" | grep -q '640x480'; then
        video_device="$candidate"
        break
    fi
done
[ -n "$video_device" ] || fail "real Orbbec RGB device 2bc5:050f with YUYV 640x480 is unavailable"
echo "[OK] real hospital RGB device: $video_device"

# Restart only the dedicated camera container. This releases stale camera file
# descriptors without touching Nav2, lidar, chassis serial, API, or microphone.
docker restart "$CAM_CONTAINER" >/dev/null
sleep 2

docker exec "$CAM_CONTAINER" test -r "$ROS_SETUP" || fail "ROS camera workspace is unavailable"

# The installed Foxy usb_cam build exits on this camera's MJPEG setting. The
# device-advertised YUYV/640x480/30 combination was verified on the real robot.
docker exec -d "$CAM_CONTAINER" bash -lc \
    "source '$ROS_SETUP' && export ROS_DOMAIN_ID='$CAM_ROS_DOMAIN_ID' && exec ros2 run usb_cam usb_cam_node_exe --ros-args -r __node:=hospital_rgb_camera -r image_raw:='$CAM_TOPIC' -r camera_info:='$CAM_INFO_TOPIC' -p video_device:='$video_device' -p framerate:=30.0 -p io_method:=mmap -p frame_id:=camera_color_optical_frame -p pixel_format:=yuyv -p color_format:=yuv422p -p image_width:=640 -p image_height:=480 -p camera_name:=hospital_rgb_camera > /tmp/hospital_rgb_camera.log 2>&1"

camera_ready=0
for attempt in $(seq 1 15); do
    sleep 1
    if docker exec "$CAM_CONTAINER" pgrep -f usb_cam_node_exe >/dev/null 2>&1; then
        camera_ready=1
        break
    fi
done
if [ "$camera_ready" -ne 1 ]; then
    docker exec "$CAM_CONTAINER" tail -n 100 /tmp/hospital_rgb_camera.log >&2 2>/dev/null || true
    fail "real RGB publisher did not stay running"
fi

docker exec -d "$CAM_CONTAINER" bash -lc \
    "source '$ROS_SETUP' && export ROS_DOMAIN_ID='$CAM_ROS_DOMAIN_ID' && exec ros2 run web_video_server web_video_server > /tmp/hospital_web_video.log 2>&1"

snapshot_ready=0
for attempt in $(seq 1 20); do
    sleep 1
    rm -f "$snapshot_file" "$headers_file"
    code="$(curl -sS --max-time 6 -D "$headers_file" -o "$snapshot_file" -w '%{http_code}' "$SNAPSHOT_URL" 2>/dev/null || true)"
    size="$(stat -c %s "$snapshot_file" 2>/dev/null || echo 0)"
    kind="$(file -b "$snapshot_file" 2>/dev/null || true)"
    echo "camera snapshot try${attempt}: HTTP ${code:-000} size=$size"
    if [ "$code" = 200 ] && [ "$size" -gt 5000 ] \
        && printf '%s\n' "$kind" | grep -q 'JPEG image data' \
        && printf '%s\n' "$kind" | grep -q '640x480'; then
        snapshot_ready=1
        break
    fi
done

if [ "$snapshot_ready" -ne 1 ]; then
    echo "--- RGB publisher log ---" >&2
    docker exec "$CAM_CONTAINER" tail -n 100 /tmp/hospital_rgb_camera.log >&2 2>/dev/null || true
    echo "--- web video log ---" >&2
    docker exec "$CAM_CONTAINER" tail -n 100 /tmp/hospital_web_video.log >&2 2>/dev/null || true
    fail "real RGB snapshot did not become a valid 640x480 JPEG"
fi

echo "[OK] real RGB snapshot ready: $size bytes"
