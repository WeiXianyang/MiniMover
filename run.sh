#!/bin/bash
# ============================================
# Rosmaster 小车启动脚本
# 用法: bash run.sh [mode]
#   mode: app    - 启动 Web 服务器 (Jetson)
#         sim    - 启动桌面 GUI 面板 (PC/X11)
#         docker - 启动 ROS2 Docker 容器
# ============================================
set -e

MODE="${1:-app}"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "====================================="
echo "  Rosmaster Car - $MODE"
echo "  Dir: $APP_DIR"
echo "====================================="

# 检测是否在 Jetson 上
if [ -f /etc/nv_tegra_release ]; then
    IS_JETSON=true
    echo "  Platform: Jetson (aarch64)"
else
    IS_JETSON=false
    echo "  Platform: PC/WSL (x86_64)"
fi

case "$MODE" in
    app)
        echo "  启动 Web 服务器 (端口 6500)..."
        cd "$APP_DIR"
        # 检查依赖
        python3 -c "import flask, gevent, cv2, serial" 2>/dev/null || {
            echo "  安装依赖..."
            pip3 install flask gevent opencv-python pyserial pyzbar RPi.GPIO 2>/dev/null || true
        }
        # 启动主程序
        python3 app.py "$@"
        ;;

    sim)
        echo "  启动桌面 GUI 控制面板..."
        cd "$APP_DIR"
        # X11 检查
        if [ -z "$DISPLAY" ]; then
            echo "  [WARN] 未检测到 X Server，需要先启动 X11 服务"
            echo "  Windows: 启动 VcXsrv/Xming"
            echo "  Linux:   export DISPLAY=:0"
        fi
        python3 app_sim_run.py 2>/dev/null || python3 app_sim.py
        ;;

    docker)
        echo "  启动 ROS2 Docker 容器..."
        if [ -f "$APP_DIR/run_docker.sh" ]; then
            bash "$APP_DIR/run_docker.sh"
        else
            echo "  run_docker.sh 未配置"
        fi
        ;;

    stop)
        echo "  终止 Rosmaster 进程..."
        bash "$APP_DIR/kill_rosmaster.sh"
        ;;

    test)
        echo "  手动控制测试模式"
        cd "$APP_DIR"
        python3 drive.py "${@:2}"
        ;;

    *)
        echo "用法: bash run.sh {app|sim|docker|stop|test}"
        echo ""
        echo "  app    - 启动 Web 服务器 (手机APP/浏览器控制)"
        echo "  sim    - 启动桌面 GUI 控制面板 (本地操控)"
        echo "  docker - 启动 ROS2 容器 (激光雷达/视觉 SLAM)"
        echo "  stop   - 终止所有 Rosmaster 进程"
        echo "  test   - 手动测试 (python3 drive.py <方向> <速度>)"
        ;;
esac
