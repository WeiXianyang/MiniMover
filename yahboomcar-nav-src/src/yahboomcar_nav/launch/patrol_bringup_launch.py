import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory('yahboomcar_nav')
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')

    use_sim_time = LaunchConfiguration('use_sim_time')
    map_yaml_path = LaunchConfiguration('map')
    nav2_param_path = LaunchConfiguration('params_file')
    waypoint_spacing = LaunchConfiguration('waypoint_spacing')
    robot_type = LaunchConfiguration('robot_type')
    rplidar_type = LaunchConfiguration('rplidar_type')

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument(
            'map',
            default_value=os.path.join(pkg_dir, 'maps', 'loudao.yaml'),
            description='Map yaml file'),
        DeclareLaunchArgument(
            'params_file',
            default_value=os.path.join(pkg_dir, 'params', 'dwa_nav_params.yaml')),
        DeclareLaunchArgument('waypoint_spacing', default_value='0.5'),
        DeclareLaunchArgument('robot_type', default_value='x3'),
        DeclareLaunchArgument('rplidar_type', default_value='a1'),

        # 传感器 + 底盘 (原 n1)，显式传入机器人类型和雷达类型
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_dir, 'launch', 'laser_bringup_launch.py')),
            launch_arguments={
                'robot_type': robot_type,
                'rplidar_type': rplidar_type,
            }.items(),
        ),

        # Nav2 自动导航 (原 n3)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(nav2_bringup_dir, 'launch', 'bringup_launch.py')),
            launch_arguments={
                'map': map_yaml_path,
                'use_sim_time': use_sim_time,
                'params_file': nav2_param_path,
            }.items(),
        ),

        # 巡逻节点
        Node(
            package='yahboomcar_nav',
            executable='route_patrol',
            name='route_patrol',
            output='screen',
            parameters=[{
                'waypoint_spacing': waypoint_spacing,
                'loop': True,
                'frame_id': 'map',
            }],
        ),

        # 自动发布初始位姿，让 map 坐标系出现（可在 RViz 里重新标定）
        Node(
            package='yahboomcar_nav',
            executable='initial_pose_setter',
            name='initial_pose_setter',
            output='screen',
            parameters=[{'x': 0.0, 'y': 0.0, 'yaw': 0.0, 'start_delay': 8.0, 'retry_interval': 3.0, 'max_retries': 10}],
        ),
    ])
