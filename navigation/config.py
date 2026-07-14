import os

CONTAINER_NAME = os.environ.get('NAV_CONTAINER', 'ded7')
ROS_DOMAIN_ID = os.environ.get('NAV_ROS_DOMAIN_ID', '30')

MAP_HOST_DIR = os.environ.get(
    'NAV_MAP_DIR',
    '/home/jetson/code/yahboomcar_ws/src/yahboomcar_nav/maps',
)
DEFAULT_MAP = os.environ.get('NAV_MAP_NAME', 'loudao')

CONTAINER_WS = '/root/yahboomcar_ros2_ws/yahboomcar_ws'
PATROL_BRIDGE_BIN = (
    f'{CONTAINER_WS}/install/yahboomcar_nav/lib/yahboomcar_nav/patrol_api_bridge'
)
ROUTES_DIR = os.path.join(os.path.dirname(__file__), 'data', 'routes')
