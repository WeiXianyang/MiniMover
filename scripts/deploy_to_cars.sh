#!/bin/bash
# deploy_to_cars.sh — 将 API 服务文件部署到新车
# Usage:
#   ./deploy_to_cars.sh 10.227.111.206          # 单台
#   ./deploy_to_cars.sh 10.227.111.206 10.227.111.207  # 多台
#
# 前提: 已在 ~/.ssh/config 或 ssh-agent 中配置好免密登录

set -e

GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RED='\033[0;31m'; NC='\033[0m'
USER="jetson"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"  # MiniMover 根目录

# 需要部署的文件 (相对于 MiniMover 根目录)
FILES=(
  "api_server.py"
  "sensors/icar_sensor_driver.py"
  "scripts/start_services.sh"
)

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  FireGuard API 部署工具${NC}"
echo -e "${GREEN}========================================${NC}"

if [ $# -eq 0 ]; then
    echo -e "${RED}Usage: $0 <car_ip> [car_ip ...]${NC}"
    echo -e "  Example: $0 10.227.111.206"
    echo -e "  Example: $0 10.227.111.206 10.227.111.207"
    exit 1
fi

deploy_to_car() {
    local IP=$1
    echo -e "\n${YELLOW}[$IP] 开始部署...${NC}"

    # 1. SSH 可达性检查
    if ! ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "$USER@$IP" "hostname -I" > /dev/null 2>&1; then
        echo -e "  ${RED}[$IP] SSH 连接失败，跳过${NC}"
        return 1
    fi
    echo -e "  ${GREEN}[$IP] SSH 连接成功${NC}"

    # 2. 创建目录
    ssh "$USER@$IP" "mkdir -p ~/MiniMover/sensors ~/MiniMover/scripts"
    echo -e "  ${GREEN}[$IP] 目录已创建${NC}"

    # 3. 推送文件
    for FILE in "${FILES[@]}"; do
        SRC="$LOCAL_DIR/$FILE"
        DST="$USER@$IP:~/MiniMover/$FILE"
        if [ -f "$SRC" ]; then
            scp -o StrictHostKeyChecking=no "$SRC" "$DST" > /dev/null 2>&1
            echo -e "  ${GREEN}[$IP] $FILE 已推送${NC}"
        else
            echo -e "  ${YELLOW}[$IP] 本地缺少 $FILE，跳过${NC}"
        fi
    done

    # 4. 设置执行权限
    ssh "$USER@$IP" "chmod +x ~/MiniMover/scripts/start_services.sh" 2>/dev/null

    # 5. 安装 Python 依赖
    echo -e "  ${YELLOW}[$IP] 安装 Python 依赖...${NC}"
    ssh "$USER@$IP" "pip3 install flask flask-cors pyserial 2>/dev/null || pip install flask flask-cors pyserial 2>/dev/null" || true

    # 6. 检查现有服务，提示启动方式
    echo -e "  ${GREEN}[$IP] 部署完成！${NC}"
    echo -e "  启动方式:"
    echo -e "    ssh $USER@$IP 'cd ~/MiniMover && python3 api_server.py &'"
    echo -e "    或: ssh $USER@$IP 'bash ~/MiniMover/scripts/start_services.sh'"
}

FAILED=0
for IP in "$@"; do
    deploy_to_car "$IP" || ((FAILED++))
done

echo -e "\n${GREEN}========================================${NC}"
echo -e "  部署统计: 总 $# 台, 成功 $(( $# - FAILED )) 台, 失败 $FAILED 台"
echo -e "${GREEN}========================================${NC}"

# 完成后提示注册到调度中心
echo -e "\n${YELLOW}部署完成后，如果调度中心正在运行，注册新车:${NC}"
echo -e "  curl -X POST http://localhost:8888/api/register_batch \\"
echo -e '    -H "Content-Type: application/json" -d \'
echo -e '    '\''{"cars": {"car_C": {"ip":"<新车IP>", "port":5000}, ...}}'\'
echo -e ""
echo -e "  或在 Dashboard  http://localhost:8888/dashboard  手动注册"