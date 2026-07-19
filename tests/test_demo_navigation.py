import io
from unittest.mock import Mock, patch

import pytest
from flask import Flask

from navigation import ros_bridge
from navigation.routes import nav_bp


@pytest.fixture(autouse=True)
def reset_demo_goal_state():
    with ros_bridge._demo_goal_lock:
        ros_bridge._demo_goal = None
        ros_bridge._demo_goal_sequence = 0
    yield
    with ros_bridge._demo_goal_lock:
        ros_bridge._demo_goal = None
        ros_bridge._demo_goal_sequence = 0


def _set_goal(status, message="Nav2 status"):
    with ros_bridge._demo_goal_lock:
        ros_bridge._demo_goal = {
            "goal_id": 1,
            "x": 1.0,
            "y": 2.0,
            "theta": 0.0,
            "status": status,
            "message": message,
        }


def test_arrival_requires_succeeded_and_map_tolerance():
    _set_goal("SUCCEEDED", "Goal finished with status: SUCCEEDED")
    with patch.object(ros_bridge, "get_robot_pose", return_value={
        "valid": True,
        "frame_id": "map",
        "x": 1.10,
        "y": 2.0,
        "yaw": 0.0,
    }) as get_pose:
        status = ros_bridge.demo_goal_status(tolerance=0.15)

    assert status["arrived"] is True
    assert status["distance_m"] == pytest.approx(0.1)
    assert status["tolerance_m"] == 0.15
    get_pose.assert_called_once_with()


def test_nav2_succeeded_is_arrived_even_outside_local_pose_tolerance():
    _set_goal("SUCCEEDED", "Goal finished with status: SUCCEEDED")
    with patch.object(ros_bridge, "get_robot_pose", return_value={
        "valid": True,
        "frame_id": "map",
        "x": 1.30,
        "y": 2.0,
    }):
        status = ros_bridge.demo_goal_status(tolerance=0.15)

    assert status["arrived"] is True
    assert status["distance_m"] == pytest.approx(0.30)
    assert status["tolerance_m"] == 0.15


def test_nav2_succeeded_is_arrived_when_pose_is_temporarily_unavailable():
    _set_goal("SUCCEEDED", "Goal finished with status: SUCCEEDED")
    with patch.object(ros_bridge, "get_robot_pose", return_value={
        "valid": False,
        "frame_id": "",
        "message": "pose service failed",
    }):
        status = ros_bridge.demo_goal_status()

    assert status["arrived"] is True
    assert status["distance_m"] is None


def test_active_goal_never_claims_arrived():
    _set_goal("ACTIVE", "Goal accepted")
    with patch.object(ros_bridge, "get_robot_pose", return_value={
        "valid": True,
        "frame_id": "map",
        "x": 1.0,
        "y": 2.0,
    }):
        status = ros_bridge.demo_goal_status()

    assert status["active"] is True
    assert status["arrived"] is False


def test_goal_output_is_the_only_source_of_active_and_success_states():
    _set_goal("PENDING", "Goal submitted; waiting for Nav2 acceptance")

    ros_bridge._update_demo_goal_from_line(1, "Goal accepted with ID: abc")
    with ros_bridge._demo_goal_lock:
        assert ros_bridge._demo_goal["status"] == "ACTIVE"

    ros_bridge._update_demo_goal_from_line(
        1, "Goal finished with status: SUCCEEDED")
    with ros_bridge._demo_goal_lock:
        assert ros_bridge._demo_goal["status"] == "SUCCEEDED"


def test_navigate_starts_one_pending_goal_with_feedback_and_rejects_a_second_goal():
    class RecordingThread:
        instances = []

        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon
            self.started = False
            self.__class__.instances.append(self)

        def start(self):
            self.started = True

    process = type("Process", (), {"stdout": io.StringIO("")})()
    with patch.object(ros_bridge, "container_running", return_value=True), \
            patch.object(ros_bridge, "_demo_navigation_health", return_value={"success": True}), \
            patch.object(ros_bridge.subprocess, "Popen", return_value=process) as popen, \
            patch.object(ros_bridge.threading, "Thread", RecordingThread):
        first = ros_bridge.navigate_to(1.0, 2.0, 0.0)
        second = ros_bridge.navigate_to(3.0, 4.0, 0.0)

    assert first["success"] is True
    assert first["status"] == "PENDING"
    assert second["success"] is False
    assert "already active" in second["message"]
    assert popen.call_count == 1
    command = popen.call_args.args[0][-1]
    assert "ros2 action send_goal" in command
    assert "--feedback" in command
    assert RecordingThread.instances[0].started is True


def test_navigate_fails_closed_when_chassis_health_is_bad():
    with patch.object(ros_bridge, "container_running", return_value=True), \
            patch.object(ros_bridge, "_demo_navigation_health", return_value={
                "success": False,
                "message": "IMU acceleration is unavailable",
            }), \
            patch.object(ros_bridge.subprocess, "Popen") as popen:
        result = ros_bridge.navigate_to(1.0, 2.0, 0.0)

    assert result["success"] is False
    assert "IMU" in result["message"]
    popen.assert_not_called()


def test_navigate_rechecks_active_goal_after_health_check():
    def health_check_with_competing_goal():
        _set_goal("ACTIVE", "concurrent goal")
        return {"success": True}

    with patch.object(ros_bridge, "_demo_navigation_health", side_effect=health_check_with_competing_goal), \
            patch.object(ros_bridge.subprocess, "Popen") as popen:
        result = ros_bridge.navigate_to(1.0, 2.0, 0.0)

    assert result["success"] is False
    assert "already active" in result["message"]
    popen.assert_not_called()


def test_demo_navigation_health_passes_with_serial_imu_and_odom_feedback():
    imu = type("Result", (), {
        "returncode": 0,
        "stdout": "linear_acceleration:\n  x: 0.1\n  y: -0.2\n  z: 9.7\n",
        "stderr": "",
    })()
    odom = type("Result", (), {
        "returncode": 0,
        "stdout": "header:\n  frame_id: odom\nchild_frame_id: base_footprint\n",
        "stderr": "",
    })()
    with patch.object(ros_bridge, "container_running", return_value=True) as container_running, \
            patch.object(ros_bridge, "patrol_services_ready", return_value=True), \
            patch.object(ros_bridge, "get_robot_pose", return_value={
                "valid": True, "frame_id": "map", "x": 0.0, "y": 0.0,
            }) as get_robot_pose, \
            patch.object(ros_bridge, "_run_ros", side_effect=[(imu, None), (odom, None)]):
        result = ros_bridge._demo_navigation_health()

    assert result["success"] is True
    assert result["imu_acceleration_norm"] == pytest.approx(9.7026, rel=1e-3)
    container_running.assert_called_once_with(force=True)
    get_robot_pose.assert_called_once_with(force=True)


def test_demo_navigation_health_rejects_missing_chassis_serial():
    serial_missing = type("Result", (), {
        "returncode": 41,
        "stdout": "__SERIAL_UNAVAILABLE__\n",
        "stderr": "",
    })()
    with patch.object(ros_bridge, "container_running", return_value=True), \
            patch.object(ros_bridge, "patrol_services_ready", return_value=True), \
            patch.object(ros_bridge, "get_robot_pose", return_value={
                "valid": True, "frame_id": "map", "x": 0.0, "y": 0.0,
            }), \
            patch.object(ros_bridge, "_run_ros", return_value=(serial_missing, None)):
        result = ros_bridge._demo_navigation_health()

    assert result["success"] is False
    assert "/dev/myserial" in result["message"]


def test_demo_navigation_health_rejects_imu_timeout():
    with patch.object(ros_bridge, "container_running", return_value=True), \
            patch.object(ros_bridge, "patrol_services_ready", return_value=True), \
            patch.object(ros_bridge, "get_robot_pose", return_value={
                "valid": True, "frame_id": "map", "x": 0.0, "y": 0.0,
            }), \
            patch.object(ros_bridge, "_run_ros", return_value=(None, {
                "success": False, "message": "ROS query timed out",
            })):
        result = ros_bridge._demo_navigation_health()

    assert result["success"] is False
    assert "timed out" in result["message"]


def test_demo_navigation_health_rejects_odom_timeout():
    imu = type("Result", (), {
        "returncode": 0,
        "stdout": "linear_acceleration:\n  x: 0.0\n  y: 0.0\n  z: 9.8\n",
        "stderr": "",
    })()
    with patch.object(ros_bridge, "container_running", return_value=True), \
            patch.object(ros_bridge, "patrol_services_ready", return_value=True), \
            patch.object(ros_bridge, "get_robot_pose", return_value={
                "valid": True, "frame_id": "map", "x": 0.0, "y": 0.0,
            }), \
            patch.object(ros_bridge, "_run_ros", side_effect=[
                (imu, None),
                (None, {"success": False, "message": "ROS query timed out"}),
            ]):
        result = ros_bridge._demo_navigation_health()

    assert result["success"] is False
    assert "timed out" in result["message"]


def test_demo_navigation_health_rejects_free_fall_imu():
    imu = type("Result", (), {
        "returncode": 0,
        "stdout": "linear_acceleration:\n  x: 0.0\n  y: 0.0\n  z: 0.1\n",
        "stderr": "",
    })()
    with patch.object(ros_bridge, "container_running", return_value=True), \
            patch.object(ros_bridge, "patrol_services_ready", return_value=True), \
            patch.object(ros_bridge, "get_robot_pose", return_value={
                "valid": True, "frame_id": "map", "x": 0.0, "y": 0.0,
            }), \
            patch.object(ros_bridge, "_run_ros", return_value=(imu, None)):
        result = ros_bridge._demo_navigation_health()

    assert result["success"] is False
    assert "free fall" in result["message"].lower()


def test_cancel_active_goal_uses_nav2_cancel_service_and_clears_state():
    goal_process = Mock()
    _set_goal("ACTIVE", "Goal accepted")
    with ros_bridge._demo_goal_lock:
        ros_bridge._demo_goal["_process"] = goal_process
    response = type("Result", (), {
        "returncode": 0,
        "stdout": "return_code=0, goals_canceling=[goal_info]",
        "stderr": "",
    })()
    with patch.object(ros_bridge, "_run_ros", return_value=(response, None)) as run_ros:
        result = ros_bridge.cancel_demo_goal()

    assert result["success"] is True
    assert result["status"] == "CANCELLED"
    command = run_ros.call_args.args[0]
    assert "/navigate_to_pose/_action/cancel_goal" in command
    assert "action_msgs/srv/CancelGoal" in command
    goal_process.terminate.assert_called_once_with()
    assert ros_bridge.demo_goal_status()["status"] == "CANCELLED"


def test_cancel_is_idempotent_when_no_goal_is_active():
    result = ros_bridge.cancel_demo_goal()

    assert result["success"] is True
    assert result["status"] == "IDLE"


def test_demo_goal_status_and_cancel_routes_are_http_safe(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(nav_bp, url_prefix="/api/nav")
    monkeypatch.setattr(ros_bridge, "demo_goal_status", lambda: {
        "active": False,
        "arrived": False,
        "status": "IDLE",
        "message": "no demo navigation goal",
    })
    monkeypatch.setattr(ros_bridge, "cancel_demo_goal", lambda: {
        "success": False,
        "message": "demo cancel is disabled until verified on the real vehicle",
    })

    client = app.test_client()
    status_response = client.get("/api/nav/demo/goal-status")
    cancel_response = client.post("/api/nav/demo/cancel")

    assert status_response.status_code == 200
    assert status_response.get_json()["data"]["status"] == "IDLE"
    assert cancel_response.status_code == 409
    assert cancel_response.get_json()["code"] == -1


def test_navigate_endpoint_rejects_a_goal_that_was_not_submitted(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(nav_bp, url_prefix="/api/nav")
    monkeypatch.setattr(ros_bridge, "navigate_to", lambda *args: {
        "success": False,
        "message": "container is not running",
    })

    response = app.test_client().post(
        "/api/nav/navigate", json={"x": 1.0, "y": 2.0, "theta": 0.0})

    assert response.status_code == 409
    assert response.get_json()["code"] == -1

def test_demo_navigation_health_route_is_read_only_status_surface(monkeypatch):
    monkeypatch.setattr(ros_bridge, "_demo_navigation_health", lambda: {
        "success": False,
        "message": "/dev/myserial is unavailable inside the navigation container",
    })
    app = Flask(__name__)
    app.register_blueprint(nav_bp, url_prefix="/api/nav")

    response = app.test_client().get("/api/nav/demo/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["code"] == 0
    assert payload["data"]["success"] is False
    assert "/dev/myserial" in payload["data"]["message"]


def test_navigation_defaults_to_dedicated_demo_container(monkeypatch):
    import importlib
    from navigation import config

    monkeypatch.delenv("NAV_CONTAINER", raising=False)
    reloaded = importlib.reload(config)

    assert reloaded.CONTAINER_NAME == "minimover_nav"


def test_stack_stop_clears_stale_active_demo_goal(monkeypatch):
    from navigation import routes

    _set_goal("ACTIVE", "Goal accepted")
    monkeypatch.setattr(routes.stack_manager, "stop_stack_async", lambda: {
        "success": True, "accepted": True, "message": "stopping",
    })
    app = Flask(__name__)
    app.register_blueprint(nav_bp, url_prefix="/api/nav")

    response = app.test_client().post("/api/nav/stack/stop", json={})

    assert response.status_code == 200
    assert ros_bridge.demo_goal_status()["status"] == "CANCELLED"
