import io
from unittest.mock import patch

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
    }):
        status = ros_bridge.demo_goal_status(tolerance=0.15)

    assert status["arrived"] is True
    assert status["distance_m"] == pytest.approx(0.1)
    assert status["tolerance_m"] == 0.15


def test_succeeded_goal_outside_tolerance_or_without_map_pose_is_not_arrived():
    _set_goal("SUCCEEDED", "Goal finished with status: SUCCEEDED")
    with patch.object(ros_bridge, "get_robot_pose", return_value={
        "valid": True,
        "frame_id": "odom",
        "x": 1.0,
        "y": 2.0,
    }):
        status = ros_bridge.demo_goal_status()

    assert status["arrived"] is False
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


def test_cancel_disabled_without_verified_environment(monkeypatch):
    monkeypatch.delenv("MINIMOVER_DEMO_CANCEL_ENABLED", raising=False)

    result = ros_bridge.cancel_demo_goal()

    assert result["success"] is False
    assert "disabled" in result["message"]


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
