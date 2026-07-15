#!/bin/bash
# ded7 容器内：一键启动/停止 p1 导航巡逻栈（单例，防重复 launch）
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-30}
# 与交互式 p1（ros_aliases.sh）保持一致；网页启动没有登录 shell，必须显式设置
export ROBOT_TYPE=${ROBOT_TYPE:-x3}
export RPLIDAR_TYPE=${RPLIDAR_TYPE:-a1}
WS=/root/yahboomcar_ros2_ws/yahboomcar_ws
PIDFILE=/tmp/p1_stack.pid
LOCKFILE=/tmp/p1_stack.lock
LOGFILE=/tmp/p1_stack.log

# 若存在别名脚本则加载（补充环境，不含交互 alias 也没关系）
if [ -f "$WS/ros_aliases.sh" ]; then
    # shellcheck disable=SC1090
    source "$WS/ros_aliases.sh"
fi

source /opt/ros/foxy/setup.bash
source "$WS/install/yahboomcar_patrol_interfaces/share/yahboomcar_patrol_interfaces/local_setup.bash"
source "$WS/install/yahboomcar_nav/share/yahboomcar_nav/package.bash"

# 再次确保（ros_aliases 可能被覆盖环境）
export ROBOT_TYPE=${ROBOT_TYPE:-x3}
export RPLIDAR_TYPE=${RPLIDAR_TYPE:-a1}
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-30}

cmd="${1:-status}"

_stack_ready() {
    ros2 service list 2>/dev/null | grep -q /patrol/set_route
}

_launch_running() {
    pgrep -f 'patrol_bringup_launch.py' >/dev/null 2>&1
}

_launch_pid() {
    pgrep -f 'patrol_bringup_launch.py' 2>/dev/null | head -1
}

_kill_stack() {
    if _stack_ready; then
        ros2 service call /patrol/stop std_srvs/srv/Trigger "{}" >/dev/null 2>&1 || true
        sleep 0.5
    fi
    if [ -f "$PIDFILE" ]; then
        oldpid=$(cat "$PIDFILE" 2>/dev/null)
        if [ -n "$oldpid" ]; then
            kill -TERM "$oldpid" 2>/dev/null || true
            sleep 0.5
            kill -9 "$oldpid" 2>/dev/null || true
        fi
        rm -f "$PIDFILE"
    fi
    pkill -f patrol_bringup_launch.py 2>/dev/null || true
    pkill -f route_patrol 2>/dev/null || true
    pkill -f initial_pose_setter 2>/dev/null || true
    pkill -f component_container 2>/dev/null || true
    pkill -f nav2_container 2>/dev/null || true
    pkill -f laser_bringup_launch 2>/dev/null || true
    pkill -f Mcnamu_driver 2>/dev/null || true
    pkill -f patrol_api_bridge 2>/dev/null || true
    sleep 1
}

case "$cmd" in
start)
    if _stack_ready; then
        pid=$(_launch_pid)
        [ -n "$pid" ] && echo "$pid" > "$PIDFILE"
        echo '{"success":true,"message":"导航栈已在运行","already_running":true,"ready":true,"starting":false,"pid":'"${pid:-0}"'}'
        exit 0
    fi
    if _launch_running; then
        pid=$(_launch_pid)
        echo "$pid" > "$PIDFILE"
        echo '{"success":true,"message":"导航栈正在启动中，请等待约 10-15 秒","already_running":true,"ready":false,"starting":true,"pid":'"$pid"'}'
        exit 0
    fi
    exec 9>"$LOCKFILE"
    if ! flock -n 9; then
        echo '{"success":true,"message":"导航栈正在启动中（另一任务进行中）","already_running":true,"ready":false,"starting":true}'
        exit 0
    fi
    rm -f "$PIDFILE"
    # setsid：脱离 docker exec 会话，避免宿主机 docker exec 结束后把 launch 杀掉
    : > "$LOGFILE"
    setsid bash -c "source /opt/ros/foxy/setup.bash; \
      source '$WS/install/yahboomcar_patrol_interfaces/share/yahboomcar_patrol_interfaces/local_setup.bash'; \
      source '$WS/install/yahboomcar_nav/share/yahboomcar_nav/package.bash'; \
      export ROS_DOMAIN_ID='$ROS_DOMAIN_ID'; \
      export ROBOT_TYPE='$ROBOT_TYPE'; \
      export RPLIDAR_TYPE='$RPLIDAR_TYPE'; \
      exec ros2 launch yahboomcar_nav patrol_bringup_launch.py \
        robot_type:=$ROBOT_TYPE rplidar_type:=$RPLIDAR_TYPE" \
      > "$LOGFILE" 2>&1 < /dev/null &
    echo $! > "$PIDFILE"
    sleep 1
    if ! _launch_running && [ ! -s "$LOGFILE" ]; then
        echo '{"success":false,"message":"导航栈进程未能拉起，请查看 /tmp/p1_stack.log","ready":false,"starting":false}'
        exit 1
    fi
    if ! _launch_running; then
        # 进程秒退：把日志最后几行带给前端
        tailmsg=$(tail -c 400 "$LOGFILE" 2>/dev/null | tr '\n' ' ' | sed 's/"/\\"/g')
        echo '{"success":false,"message":"导航栈启动后立即退出: '"${tailmsg:-见日志}"'","ready":false,"starting":false,"log":"'"$LOGFILE"'"}'
        exit 1
    fi
    echo '{"success":true,"message":"导航栈已启动，约需 10-15 秒就绪","pid":'"$(cat $PIDFILE)"',"log":"'"$LOGFILE"'","ready":false,"starting":true}'
    ;;
stop)
    _kill_stack
    if _stack_ready || _launch_running; then
        pkill -9 -f patrol_bringup_launch.py 2>/dev/null || true
        pkill -9 -f route_patrol 2>/dev/null || true
        pkill -9 -f component_container 2>/dev/null || true
        pkill -9 -f nav2_container 2>/dev/null || true
        sleep 1
    fi
    rm -f "$PIDFILE" "$LOCKFILE"
    if _stack_ready; then
        echo '{"success":false,"message":"部分进程可能未完全停止，请重试"}'
        exit 1
    fi
    echo '{"success":true,"message":"导航栈已停止","ready":false,"starting":false}'
    ;;
status)
    if _stack_ready; then
        pid=$(_launch_pid)
        echo '{"success":true,"ready":true,"starting":false,"message":"巡逻服务就绪","pid":'"${pid:-0}"'}'
    elif _launch_running; then
        pid=$(_launch_pid)
        echo '{"success":true,"ready":false,"starting":true,"message":"导航栈启动中","pid":'"$pid"'}'
    else
        err=''
        if [ -f "$LOGFILE" ] && [ -s "$LOGFILE" ]; then
            err=$(tail -c 300 "$LOGFILE" 2>/dev/null | tr '\n' ' ' | sed 's/"/\\"/g')
        fi
        if [ -n "$err" ]; then
            echo '{"success":true,"ready":false,"starting":false,"message":"巡逻服务未就绪（进程未运行）","log_tail":"'"$err"'"}'
        else
            echo '{"success":true,"ready":false,"starting":false,"message":"巡逻服务未就绪"}'
        fi
    fi
    ;;
*)
    echo '{"success":false,"message":"用法: nav_stack.sh start|stop|status"}'
    exit 1
    ;;
esac
