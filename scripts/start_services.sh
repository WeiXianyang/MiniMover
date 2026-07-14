#!/bin/bash
# FireGuard one-click startup (car-specific)
GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
CAM_CONTAINER=fireguard_cam
# 自动查找 yahboom 容器（不硬编码 ID）
YAHBOOM_CONTAINER=$(docker ps -aq -f ancestor=yahboomtechnology/ros-foxy:5.0.1 --latest 2>/dev/null | head -1)
if [ -z "$YAHBOOM_CONTAINER" ]; then
    YAHBOOM_CONTAINER=$(docker ps -aq -f ancestor=yahboomtechnology/ros-foxy:5.0.1 2>/dev/null | head -1)
fi

# Generate unique ROS_DOMAIN_ID from IP last octet (30-250)
DOMAIN_SUFFIX=$(hostname -I 2>/dev/null | awk '{print $1}' | awk -F. '{print $4}')
ROS_DOMAIN_ID=$(( 30 + DOMAIN_SUFFIX % 220 ))

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  FireGuard Service Starting${NC}"
echo -e "${GREEN}========================================${NC}"

# 1. Fix camera device
sudo modprobe -r uvcvideo 2>/dev/null
sudo modprobe uvcvideo 2>/dev/null
sleep 2
sudo ln -sf /dev/video0 /dev/camera_depth 2>/dev/null

# 1.5 Fix chassis serial - find the right ttyUSB (car_B=USB1, car_A=USB2)
for TTY in /dev/ttyUSB1 /dev/ttyUSB2; do
    if [ -c "$TTY" ]; then
        CURRENT=$(readlink /dev/myserial 2>/dev/null || echo "")
        if [ "$CURRENT" != "$TTY" ]; then
            sudo rm -f /dev/myserial && sudo ln -s "$TTY" /dev/myserial
            echo -e "  ${GREEN}[OK] /dev/myserial -> $TTY${NC}"
        fi
        break
    fi
done

# 2. Start yahboom container (chassis + lidar)
sudo docker start $YAHBOOM_CONTAINER >/dev/null 2>&1
echo -e "  ${GREEN}[OK] yahboom container started${NC}"


# 3. Start camera container
RUNNING=$(sudo docker ps -q -f name=$CAM_CONTAINER)
if [ -n "$RUNNING" ]; then
    echo -e "  ${GREEN}[OK] camera container already running${NC}"
else
    EXIST=$(sudo docker ps -aq -f name=$CAM_CONTAINER)
    if [ -n "$EXIST" ]; then
        sudo docker start $CAM_CONTAINER >/dev/null 2>&1
        echo -e "  ${GREEN}[OK] camera container started${NC}"
    else
        sudo docker run -d --network host --privileged \
            --name $CAM_CONTAINER \
            -v /dev:/dev:rw \
            icar/ros-foxy:1.0.2 \
            bash -c 'sleep infinity' >/dev/null 2>&1
        echo -e "  ${GREEN}[OK] camera container created${NC}"
    fi
fi

# 4. VNC
pkill vino-server 2>/dev/null
/usr/lib/vino/vino-server --display=:0 &>/dev/null &

# 5. Color camera (inside container)
sudo docker exec -d $CAM_CONTAINER bash -c "source /root/icar_ros2_ws/icar_ws/install/setup.bash && ROS_DOMAIN_ID=$ROS_DOMAIN_ID ros2 launch astra_camera astro_pro_plus.launch.xml > /tmp/cam.log 2>&1 &"
sleep 8
echo -e "  ${GREEN}[OK] camera started (DOMAIN=$ROS_DOMAIN_ID)${NC}"

# 6. ROS 2 daemon refresh
sudo docker exec $CAM_CONTAINER bash -c "source /root/icar_ros2_ws/icar_ws/install/setup.bash && ROS_DOMAIN_ID=$ROS_DOMAIN_ID ros2 daemon stop 2>/dev/null" 2>/dev/null
sleep 1

# 7. Video stream
sudo docker exec -d $CAM_CONTAINER bash -c "source /root/icar_ros2_ws/icar_ws/install/setup.bash && ROS_DOMAIN_ID=$ROS_DOMAIN_ID ros2 run web_video_server web_video_server > /tmp/video.log 2>&1 &"
sleep 3
echo -e "  ${GREEN}[OK] video stream :8080${NC}"

# 8. API service
API_PIDS=$(sudo ss -ltnp 'sport = :5000' 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u)
if [ -n "$API_PIDS" ]; then
    sudo kill $API_PIDS 2>/dev/null
    sleep 1
fi
cd ~/MiniMover && nohup /usr/bin/python3 api_server.py > /tmp/api.log 2>&1 &
sleep 3
echo -e "  ${GREEN}[OK] API :5000${NC}"

# 9. (可选) 火灾检测 — 默认跳过，可传入 FIRE_DETECT=1 开启
if [ "${FIRE_DETECT:-0}" = "1" ]; then
    echo -e ""
    cd ~/MiniMover && bash scripts/start_fire_detection.sh 2>/dev/null || \
        echo -e "  ${YELLOW}[SKIP] 火灾检测启动失败，可稍后手动执行 scripts/start_fire_detection.sh${NC}"
fi

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo -e "\n${GREEN}========================================${NC}"
echo -e "  Dashboard: ${YELLOW}http://$IP:5000/${NC}"
echo -e "  Video:     http://$IP:8080/"
echo -e "  VNC:       $IP:5900"
echo -e "${GREEN}========================================${NC}"