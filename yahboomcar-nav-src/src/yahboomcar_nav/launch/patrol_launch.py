from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    spacing = LaunchConfiguration('waypoint_spacing')

    return LaunchDescription([
        DeclareLaunchArgument(
            'waypoint_spacing', default_value='0.5',
            description='Distance between auto-generated waypoints (m)'),

        Node(
            package='yahboomcar_nav',
            executable='route_patrol',
            name='route_patrol',
            output='screen',
            parameters=[{
                'waypoint_spacing': spacing,
                'loop': True,
                'frame_id': 'map',
            }],
        ),
    ])
