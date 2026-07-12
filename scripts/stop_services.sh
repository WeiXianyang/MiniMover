#!/bin/bash
# FireGuard one-click shutdown (reverse of start_services.sh)
GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RED='\033[0;31m'; NC='\033[0m'
CAM_CONTAINER=fireguard_cam
YAHBOOM_CONTAINER=a21066535c99

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

# 6. Check remaining processes
REMAINING=$(ps aux | grep -E 'ros|astra|vino|web_video|api_server' | grep -v grep | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo -e "  ${YELLOW}[!] $REMAINING processes remaining:${NC}"
    ps aux | grep -E 'ros|astra|vino|web_video' | grep -v grep | awk '{print "    " $11}'
else
    echo -e "  ${GREEN}[OK] no remaining processes${NC}"
fi

echo -e "\n${RED}========================================${NC}"
echo -e "${RED}  All services stopped${NC}"
echo -e "${RED}========================================${NC}"