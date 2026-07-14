#!/bin/bash
# FireGuard one-click shutdown (reverse of start_services.sh)
GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RED='\033[0;31m'; NC='\033[0m'
CAM_CONTAINER=fireguard_cam
# 自动查找 yahboom 容器（不硬编码 ID）
YAHBOOM_CONTAINER=$(docker ps -aq -f ancestor=yahboomtechnology/ros-foxy:5.0.1 --latest 2>/dev/null | head -1)
if [ -z "$YAHBOOM_CONTAINER" ]; then
    YAHBOOM_CONTAINER=$(docker ps -aq -f ancestor=yahboomtechnology/ros-foxy:5.0.1 2>/dev/null | head -1)
fi

echo -e "${RED}========================================${NC}"
echo -e "${RED}  FireGuard Service Stopping${NC}"
echo -e "${RED}========================================${NC}"

# 1. Stop API
echo -e "  ${YELLOW}Stopping API...${NC}"
sudo systemctl stop fireguard-api 2>/dev/null
pkill -f api_server.py 2>/dev/null
echo -e "  ${GREEN}[OK] API stopped${NC}"

# 2. Stop video stream
echo -e "  ${YELLOW}Stopping video stream...${NC}"
sudo docker exec $CAM_CONTAINER pkill -f web_video_server 2>/dev/null
echo -e "  ${GREEN}[OK] video stream stopped${NC}"

# 3. Stop camera
echo -e "  ${YELLOW}Stopping camera...${NC}"
sudo docker exec $CAM_CONTAINER pkill -f astra_camera 2>/dev/null
echo -e "  ${GREEN}[OK] camera stopped${NC}"

# 4. Stop VNC
echo -e "  ${YELLOW}Stopping VNC...${NC}"
pkill vino-server 2>/dev/null
echo -e "  ${GREEN}[OK] VNC stopped${NC}"

# 5. Stop Docker containers
echo -e "  ${YELLOW}Stopping containers...${NC}"
sudo docker stop $CAM_CONTAINER 2>/dev/null && echo -e "  ${GREEN}[OK] camera container stopped${NC}" || echo -e "  ${YELLOW}[-] camera container not running${NC}"
sudo docker stop $YAHBOOM_CONTAINER 2>/dev/null && echo -e "  ${GREEN}[OK] yahboom container stopped${NC}" || echo -e "  ${YELLOW}[-] yahboom container not running${NC}"

# 6. Stop fire detection (if running)
pkill -f detector.py 2>/dev/null && echo -e "  ${GREEN}[OK] fire detection stopped${NC}" || true

# 7. Check remaining processes
REMAINING=$(ps aux 2>/dev/null | grep -E 'ros|astra|vino|web_video|api_server|detector' | grep -v grep | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo -e "  ${YELLOW}[!] $REMAINING processes remaining:${NC}"
    ps aux 2>/dev/null | grep -E 'ros|astra|vino|web_video' | grep -v grep | awk '{print "    " $11}'
else
    echo -e "  ${GREEN}[OK] no remaining processes${NC}"
fi

echo -e "\n${RED}========================================${NC}"
echo -e "${RED}  All services stopped${NC}"
echo -e "${RED}========================================${NC}"