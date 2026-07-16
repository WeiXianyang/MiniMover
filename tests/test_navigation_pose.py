import math
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from navigation import ros_bridge
from navigation.routes import nav_bp


ROOT = Path(__file__).resolve().parents[1]
INTERFACES = ROOT / 'yahboomcar-nav-src' / 'src' / 'yahboomcar_patrol_interfaces'
ROUTE_PATROL = ROOT / 'yahboomcar-nav-src' / 'src' / 'yahboomcar_nav' / 'yahboomcar_nav' / 'route_patrol.py'


def test_get_robot_pose_interface_declares_map_pose_response():
    service = (INTERFACES / 'srv' / 'GetRobotPose.srv').read_text(encoding='utf-8')
    cmake = (INTERFACES / 'CMakeLists.txt').read_text(encoding='utf-8')
    package = (INTERFACES / 'package.xml').read_text(encoding='utf-8')

    assert 'bool valid' in service
    assert 'geometry_msgs/PoseStamped pose' in service
    assert 'string source' in service
    assert '"srv/GetRobotPose.srv"' in cmake
    assert 'geometry_msgs' in cmake
    assert '<depend>geometry_msgs</depend>' in package


def test_route_patrol_wires_tf_amcl_fallback_and_pose_service():
    source = ROUTE_PATROL.read_text(encoding='utf-8')

    assert 'from tf2_ros import Buffer, TransformListener' in source
    assert 'from geometry_msgs.msg import PoseWithCovarianceStamped' in source
    assert 'GetRobotPose' in source
    assert "'/amcl_pose'" in source
    assert "'/patrol/get_robot_pose'" in source
    assert "self.declare_parameter('pose_max_age', 3.0)" in source
    assert "response.source = 'tf'" in source
    assert "response.source = 'amcl_pose'" in source


def test_parse_robot_pose_response_returns_map_coordinates_and_yaw():
    payload = """response:
yahboomcar_patrol_interfaces.srv.GetRobotPose_Response(valid=True, pose=geometry_msgs.msg.PoseStamped(header=std_msgs.msg.Header(stamp=builtin_interfaces.msg.Time(sec=12, nanosec=34), frame_id='map'), pose=geometry_msgs.msg.Pose(position=geometry_msgs.msg.Point(x=1.25, y=-0.8, z=0.0), orientation=geometry_msgs.msg.Quaternion(x=0.0, y=0.0, z=0.70710678, w=0.70710678))), source='tf', message='ok')"""

    pose = ros_bridge._parse_robot_pose_response(payload)

    assert pose['valid'] is True
    assert pose['x'] == 1.25
    assert pose['y'] == -0.8
    assert math.isclose(pose['yaw'], math.pi / 2, abs_tol=1e-5)
    assert pose['frame_id'] == 'map'
    assert pose['source'] == 'tf'
    assert pose['stamp'] == {'sec': 12, 'nanosec': 34}
    assert pose['message'] == 'ok'


def test_robot_pose_returns_http_safe_invalid_shape_when_ros_reports_no_pose():
    payload = "response: GetRobotPose_Response(valid=False, pose=PoseStamped(), source='', message='map-frame pose unavailable')"

    pose = ros_bridge._parse_robot_pose_response(payload)

    assert pose == {
        'success': True,
        'valid': False,
        'x': None,
        'y': None,
        'yaw': None,
        'frame_id': '',
        'source': '',
        'stamp': {'sec': 0, 'nanosec': 0},
        'message': 'map-frame pose unavailable',
    }


def test_robot_pose_uses_short_ttl_cache():
    ros_bridge._pose_cache = (None, 0.0)
    proc = type('Proc', (), {
        'returncode': 0,
        'stdout': "response: GetRobotPose_Response(valid=False, pose=PoseStamped(), source='', message='waiting')",
        'stderr': '',
    })()
    with patch.object(ros_bridge, '_run_ros', return_value=(proc, None)) as run_ros:
        first = ros_bridge.get_robot_pose()
        second = ros_bridge.get_robot_pose()

    assert first == second
    assert run_ros.call_count == 1


def test_pose_endpoint_returns_http_200_for_invalid_localization(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(nav_bp, url_prefix='/api/nav')
    monkeypatch.setattr('navigation.routes.ros_bridge.get_robot_pose', lambda: {
        'success': True,
        'valid': False,
        'x': None,
        'y': None,
        'yaw': None,
        'frame_id': '',
        'source': '',
        'stamp': {'sec': 0, 'nanosec': 0},
        'message': 'map-frame pose unavailable',
    })

    response = app.test_client().get('/api/nav/pose')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['code'] == 0
    assert payload['data']['valid'] is False
    assert payload['data']['x'] is None


def test_patrol_page_contains_live_pose_marker_poll_and_invalid_state():
    from navigation.patrol_page import PATROL_PAGE_HTML

    assert 'id="robotPoseInfo"' in PATROL_PAGE_HTML
    assert 'marker robot' in PATROL_PAGE_HTML
    assert "fetch(API+'/api/nav/pose')" in PATROL_PAGE_HTML
    assert 'function updateRobotPose' in PATROL_PAGE_HTML
    assert "robotPose.valid && robotPose.frame_id==='map'" in PATROL_PAGE_HTML
    assert '定位等待中' in PATROL_PAGE_HTML
