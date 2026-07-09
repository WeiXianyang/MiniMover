#!/bin/bash
# FireGuard 小车服务启动脚本
echo "========================================"
echo "  FireGuard 工业巡检系统 - 服务启动"
echo "========================================"

# 1. 启动 Docker 容器
CONTAINER_ID=$(sudo docker ps -q | head -1)
if [ -z "$CONTAINER_ID" ]; then
    CONTAINER_ID=$(sudo docker ps -aq | head -1)
    if [ -n "$CONTAINER_ID" ]; then
        sudo docker start $CONTAINER_ID >/dev/null 2>&1
        echo "✅ 容器 $CONTAINER_ID 已启动"
    else
        echo "❌ 未找到容器"
        exit 1
    fi
else
    echo "✅ 容器 $CONTAINER_ID 运行中"
fi

# 2. VNC
echo "启动 VNC..."
pkill vino-server 2>/dev/null
/usr/lib/vino/vino-server --display=:0 &>/dev/null &
echo "✅ VNC :5900"

# 3. REST API
echo "启动 API..."
pkill -f api_server.py 2>/dev/null
sleep 1
cd ~/MiniMover && python3 api_server.py > /tmp/api.log 2>&1 &
echo "✅ API :5000"

IP=$(hostname -I | awk '{print $1}')
echo "========================================"
echo "  VNC:   $IP:5900"
echo "  API:   http://$IP:5000"
echo "========================================"
