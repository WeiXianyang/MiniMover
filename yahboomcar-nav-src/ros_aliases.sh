# ROS 导航/巡逻别名 (ded7 容器内使用)

if [ -f /root/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash ]; then
    source /root/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash
fi

export ROBOT_TYPE=${ROBOT_TYPE:-x3}
export RPLIDAR_TYPE=${RPLIDAR_TYPE:-a1}

alias work='cd /root/yahboomcar_ros2_ws/yahboomcar_ws/src/yahboomcar_bringup/yahboomcar_bringup'
alias home='cd /root/yahboomcar_ros2_ws'
alias b='cd /root/yahboomcar_ros2_ws/yahboomcar_ws'
alias nav='cd /root/yahboomcar_ros2_ws/yahboomcar_ws/src/yahboomcar_nav/params'
alias map='cd /root/yahboomcar_ros2_ws/yahboomcar_ws/src/yahboomcar_nav/maps/'

alias n1='ros2 launch yahboomcar_nav laser_bringup_launch.py'
alias n2='ros2 launch yahboomcar_nav display_nav_launch.py'
alias n3='ros2 launch yahboomcar_nav navigation_dwa_launch.py'
alias n4='ros2 launch yahboomcar_nav navigation_teb_launch.py'

# 巡逻: p1 必须先启动并保持运行，p2 才能看到地图和雷达
alias p1='ros2 launch yahboomcar_nav patrol_bringup_launch.py'
alias p2='ros2 launch yahboomcar_nav display_nav_launch.py'
alias pstart='ros2 service call /patrol/start std_srvs/srv/Trigger'
alias pstop='ros2 service call /patrol/stop std_srvs/srv/Trigger'
alias pclear='ros2 service call /patrol/clear std_srvs/srv/Trigger'
alias pundo='ros2 service call /patrol/undo std_srvs/srv/Trigger'
alias pinit='ros2 topic pub --once /initialpose geometry_msgs/msg/PoseWithCovarianceStamped "{header: {frame_id: map}, pose: {pose: {position: {x: 0.0, y: 0.0, z: 0.0}, orientation: {w: 1.0}}, covariance: [0.25,0,0,0,0,0, 0,0.25,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0.06853891945200942]}}"'
alias pstat='echo "=== topics ===" && ros2 topic list 2>/dev/null | grep -E "^/map$|^/scan$|^/amcl_pose$" || echo "p1 未运行?"'
alias pstatus='ros2 topic echo /patrol_status --once 2>/dev/null || echo "无 patrol_status (p1 未运行?)"'
alias pcheck='echo "=== map info ===" && ros2 topic info /map 2>/dev/null; echo "=== map size ===" && ros2 topic echo /map --once 2>/dev/null | grep -E "width|height|frame_id" | head -5; echo "=== tf map->odom ===" && timeout 3 ros2 run tf2_ros tf2_echo map odom 2>&1 | head -8'

alias m1='ros2 launch yahboomcar_nav map_gmapping_launch.py'
alias m2='ros2 launch yahboomcar_nav display_map_launch.py'
alias m3='ros2 run yahboomcar_ctrl yahboom_keyboard'
alias m4='ros2 launch yahboomcar_nav save_map_launch.py'

alias r='ros2 launch yahboomcar_bringup yahboomcar_bringup_X3_launch.py'
alias l='ros2 run yahboomcar_bringup calibrate_linear_X3'
alias w='ros2 run yahboomcar_bringup calibrate_angular_X3'
alias c='ros2 run rqt_reconfigure rqt_reconfigure'
alias o='ros2 topic echo /odom'
