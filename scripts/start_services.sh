#!/bin/bash
# FireGuard 一键启动 (当前小车专用)
GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
CAM_CONTAINER=fireguard_cam
YAHBOOM_CONTAINER=a21066535c99

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  FireGuard 服务启动${NC}"
echo -e "${GREEN}========================================${NC}"

# 1. 修复摄像头设备
sudo modprobe -r uvcvideo 2>/dev/null
sudo modprobe uvcvideo 2>/dev/null
sleep 2
sudo ln -sf /dev/video0 /dev/camera_depth 2>/dev/null

# 1.5 修复底盘串口 (某台小车 /dev/myserial 可能指向错误的 ttyUSB)
if [ -L /dev/myserial ]; then
    ACTUAL=$(readlink /dev/myserial)
    if [ "$ACTUAL" = "/dev/ttyUSB2" ]; then
        sudo rm /dev/myserial && sudo ln -s /dev/ttyUSB1 /dev/myserial
        echo -e "  ${GREEN}✅ 修复底盘串口: /dev/myserial -> /dev/ttyUSB1${NC}"
    fi
fi

# 2. 启动 yahboom 容器 (底盘+雷达用)
sudo docker start $YAHBOOM_CONTAINER >/dev/null 2>&1
echo -e "  ${GREEN}✅ yahboom 容器已启动${NC}"

# 3. 启动特权容器 (相机+视频流用)
RUNNING=$(sudo docker ps -q -f name=$CAM_CONTAINER)
if [ -n "$RUNNING" ]; then
    echo -e "  ${GREEN}✅ 相机容器已在运行${NC}"
else
    EXIST=$(sudo docker ps -aq -f name=$CAM_CONTAINER)
    if [ -n "$EXIST" ]; then
        sudo docker start $CAM_CONTAINER >/dev/null 2>&1
        echo -e "  ${GREEN}✅ 相机容器已启动${NC}"
    else
        sudo docker run -d --network host --privileged \
            --name $CAM_CONTAINER \
            -v /dev:/dev:rw \
            icar/ros-foxy:1.0.2 \
            bash -c 'sleep infinity' >/dev/null 2>&1
        echo -e "  ${GREEN}✅ 相机容器已创建并启动${NC}"
    fi
fi

# 4. VNC
pkill vino-server 2>/dev/null
/usr/lib/vino/vino-server --display=:0 &>/dev/null &

# 5. 彩色相机 (特权容器内)
sudo docker exec -d $CAM_CONTAINER bash -c 'source /root/icar_ros2_ws/icar_ws/install/setup.bash && ros2 launch astra_camera astro_pro_plus.launch.xml > /tmp/cam.log 2>&1 &'
sleep 8
echo -e "  ${GREEN}✅ 彩色相机已启动${NC}"

# 6. ROS 2 守护进程刷新
sudo docker exec $CAM_CONTAINER bash -c 'source /root/icar_ros2_ws/icar_ws/install/setup.bash && ros2 daemon stop 2>/dev/null' 2>/dev/null
sleep 1

# 7. 视频流
sudo docker exec -d $CAM_CONTAINER bash -c 'source /root/icar_ros2_ws/icar_ws/install/setup.bash && ros2 run web_video_server web_video_server > /tmp/video.log 2>&1 &'
sleep 3
echo -e "  ${GREEN}✅ 视频流 :8080${NC}"

# 8. API 服务
pkill -f api_server.py 2>/dev/null; sleep 1
cd ~/MiniMover && python3 api_server.py > /tmp/api.log 2>&1 &
sleep 3
echo -e "  ${GREEN}✅ API :5000${NC}"

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo -e "\n${GREEN}========================================${NC}"
echo -e "  控制面板: ${YELLOW}http://$IP:5000/${NC}"
echo -e "  视频流:   http://$IP:8080/"
echo -e "  VNC:      $IP:5900"
echo -e "${GREEN}========================================${NC}"
