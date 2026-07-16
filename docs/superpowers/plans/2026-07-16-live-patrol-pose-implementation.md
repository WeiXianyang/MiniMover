# Live Patrol Pose Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the patrol console render the robot's current map-frame position and heading without changing navigation, obstacle avoidance, or chassis control.

**Architecture:** The active `route_patrol` ROS 2 node will expose a small `GetRobotPose` service backed by `map -> base_footprint` TF and a fresh `/amcl_pose` fallback. The Flask navigation bridge will invoke that service through the existing container command path, normalize it into a stable HTTP response, and cache it briefly. The patrol page will poll that read-only HTTP endpoint and draw a blue directional marker only for a valid `map` pose.

**Tech Stack:** ROS 2 Foxy (`rclpy`, `tf2_ros`, AMCL), custom ROS service interfaces (`rosidl`), Python/Flask, browser JavaScript/CSS, `unittest`/pytest.

---

## File Structure

- Create: `yahboomcar-nav-src/src/yahboomcar_patrol_interfaces/srv/GetRobotPose.srv` — ROS service response contract carrying validity, `PoseStamped`, source, and diagnostics.
- Modify: `yahboomcar-nav-src/src/yahboomcar_patrol_interfaces/CMakeLists.txt` — generate the new service with `geometry_msgs` support.
- Modify: `yahboomcar-nav-src/src/yahboomcar_patrol_interfaces/package.xml` — declare the geometry message dependency.
- Modify: `yahboomcar-nav-src/src/yahboomcar_nav/yahboomcar_nav/route_patrol.py` — cache AMCL, resolve map-frame TF, and serve `/patrol/get_robot_pose`.
- Modify: `navigation/ros_bridge.py` — invoke and parse the ROS service response, calculate yaw, and cache output for the page.
- Modify: `navigation/routes.py` — provide the safe read-only `/api/nav/pose` API.
- Modify: `navigation/patrol_page.py` — add live pose panel, marker rendering, polling, and unavailable-state presentation.
- Create: `tests/test_navigation_pose.py` — regression coverage for ROS bridge parser/cache, Flask response, and static patrol-page integration points.

### Task 1: Define and generate the ROS pose service

**Files:**
- Create: `yahboomcar-nav-src/src/yahboomcar_patrol_interfaces/srv/GetRobotPose.srv`
- Modify: `yahboomcar-nav-src/src/yahboomcar_patrol_interfaces/CMakeLists.txt`
- Modify: `yahboomcar-nav-src/src/yahboomcar_patrol_interfaces/package.xml`
- Test: `tests/test_navigation_pose.py`

- [ ] **Step 1: Write the contract-presence test**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTERFACES = ROOT / 'yahboomcar-nav-src/src/yahboomcar_patrol_interfaces'


def test_get_robot_pose_interface_declares_map_pose_response():
    service = (INTERFACES / 'srv/GetRobotPose.srv').read_text(encoding='utf-8')
    cmake = (INTERFACES / 'CMakeLists.txt').read_text(encoding='utf-8')
    package = (INTERFACES / 'package.xml').read_text(encoding='utf-8')

    assert 'bool valid' in service
    assert 'geometry_msgs/PoseStamped pose' in service
    assert 'string source' in service
    assert '"srv/GetRobotPose.srv"' in cmake
    assert 'geometry_msgs' in cmake
    assert '<depend>geometry_msgs</depend>' in package
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_navigation_pose.py::test_get_robot_pose_interface_declares_map_pose_response -q`

Expected: FAIL because `GetRobotPose.srv` does not exist.

- [ ] **Step 3: Add the service and generation dependencies**

Create `yahboomcar-nav-src/src/yahboomcar_patrol_interfaces/srv/GetRobotPose.srv` with:

```srv
---
bool valid
geometry_msgs/PoseStamped pose
string source
string message
```

Update `CMakeLists.txt` to find `geometry_msgs` and generate all three interfaces:

```cmake
find_package(geometry_msgs REQUIRED)
# ...
rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/SetRoute.srv"
  "srv/GetRoute.srv"
  "srv/GetRobotPose.srv"
  DEPENDENCIES geometry_msgs nav_msgs
)
```

Add `<depend>geometry_msgs</depend>` alongside the existing `nav_msgs` dependency in `package.xml`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_navigation_pose.py::test_get_robot_pose_interface_declares_map_pose_response -q`

Expected: PASS.

- [ ] **Step 5: Commit the interface increment**

```powershell
git add tests/test_navigation_pose.py yahboomcar-nav-src/src/yahboomcar_patrol_interfaces
git commit -m "feat: add patrol robot pose service"
```

### Task 2: Make `route_patrol` provide a fresh map-frame pose

**Files:**
- Modify: `yahboomcar-nav-src/src/yahboomcar_nav/yahboomcar_nav/route_patrol.py`
- Test: `tests/test_navigation_pose.py`

- [ ] **Step 1: Write a static wiring test for the node contract**

```python
def test_route_patrol_wires_tf_amcl_fallback_and_pose_service():
    source = (ROOT / 'yahboomcar-nav-src/src/yahboomcar_nav/yahboomcar_nav/route_patrol.py').read_text(encoding='utf-8')

    assert 'from tf2_ros import Buffer, TransformListener' in source
    assert 'from geometry_msgs.msg import PoseWithCovarianceStamped' in source
    assert 'GetRobotPose' in source
    assert "'/amcl_pose'" in source
    assert "'/patrol/get_robot_pose'" in source
    assert "self.declare_parameter('pose_max_age', 3.0)" in source
    assert "source = 'tf'" in source
    assert "source = 'amcl_pose'" in source
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_navigation_pose.py::test_route_patrol_wires_tf_amcl_fallback_and_pose_service -q`

Expected: FAIL because the node has no pose service or TF/AMCL subscription.

- [ ] **Step 3: Add the minimum pose provider to `RoutePatrol`**

1. Extend imports to include `PoseWithCovarianceStamped`, `GetRobotPose`, `Buffer`, `TransformListener`, and `TransformException`.
2. In `__init__`, declare and read `pose_max_age` (default `3.0`); create `Buffer()` and `TransformListener(self.tf_buffer, self)`; initialize `self._last_amcl_pose = None` and `self._last_amcl_received_at = None`.
3. Subscribe to `/amcl_pose` with `PoseWithCovarianceStamped` and have `_amcl_pose_cb` store the received message and `self.get_clock().now()`.
4. Create `GetRobotPose` service `/patrol/get_robot_pose` bound to `_get_robot_pose_cb`.
5. Add `_pose_is_fresh(received_at)` that compares `now - received_at` against `pose_max_age`.
6. In `_get_robot_pose_cb`, first call `self.tf_buffer.lookup_transform(self.frame_id, 'base_footprint', rclpy.time.Time())`. If it succeeds, set `response.valid = True`, copy transform translation and rotation into `response.pose`, set `header.frame_id = self.frame_id`, stamp it with `now`, and set `source = 'tf'`, `message = 'ok'`.
7. If TF raises `TransformException`, and a cached AMCL message exists, has `header.frame_id == self.frame_id`, and is fresh, copy its header and pose into the response with `source = 'amcl_pose'`, `message = 'TF unavailable; using fresh AMCL pose'`.
8. Otherwise set `response.valid = False`, `response.source = ''`, `response.message = 'map-frame pose unavailable'`; do not manufacture a pose from `/odom` or `/odom_raw`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_navigation_pose.py::test_route_patrol_wires_tf_amcl_fallback_and_pose_service -q`

Expected: PASS.

- [ ] **Step 5: Commit the ROS node increment**

```powershell
git add tests/test_navigation_pose.py yahboomcar-nav-src/src/yahboomcar_nav/yahboomcar_nav/route_patrol.py
git commit -m "feat: expose live patrol pose from navigation"
```

### Task 3: Normalize and cache the host-side ROS pose call

**Files:**
- Modify: `navigation/ros_bridge.py`
- Test: `tests/test_navigation_pose.py`

- [ ] **Step 1: Write parser and cache tests**

```python
from unittest.mock import patch
from navigation import ros_bridge


def test_parse_robot_pose_response_returns_map_coordinates_and_yaw():
    payload = """response:\nyahboomcar_patrol_interfaces.srv.GetRobotPose_Response(valid=True, pose=geometry_msgs.msg.PoseStamped(header=std_msgs.msg.Header(stamp=builtin_interfaces.msg.Time(sec=12, nanosec=34), frame_id='map'), pose=geometry_msgs.msg.Pose(position=geometry_msgs.msg.Point(x=1.25, y=-0.8, z=0.0), orientation=geometry_msgs.msg.Quaternion(x=0.0, y=0.0, z=0.70710678, w=0.70710678))), source='tf', message='ok')"""

    pose = ros_bridge._parse_robot_pose_response(payload)

    assert pose['valid'] is True
    assert pose['x'] == 1.25
    assert pose['y'] == -0.8
    assert abs(pose['yaw'] - 1.5707963) < 1e-5
    assert pose['frame_id'] == 'map'
    assert pose['source'] == 'tf'
    assert pose['stamp'] == {'sec': 12, 'nanosec': 34}


def test_robot_pose_returns_http_safe_invalid_shape_when_ros_reports_no_pose():
    payload = "response: GetRobotPose_Response(valid=False, pose=PoseStamped(), source='', message='map-frame pose unavailable')"

    pose = ros_bridge._parse_robot_pose_response(payload)

    assert pose == {
        'success': True, 'valid': False, 'x': None, 'y': None, 'yaw': None,
        'frame_id': '', 'source': '', 'stamp': {'sec': 0, 'nanosec': 0},
        'message': 'map-frame pose unavailable',
    }


def test_robot_pose_uses_short_ttl_cache(monkeypatch):
    ros_bridge._pose_cache = (None, 0.0)
    ros_bridge._container_cache = (True, 0.0)
    proc = type('Proc', (), {'returncode': 0, 'stdout': "response: GetRobotPose_Response(valid=False, pose=PoseStamped(), source='', message='waiting')", 'stderr': ''})()
    with patch.object(ros_bridge, '_run_ros', return_value=(proc, None)) as run_ros:
        first = ros_bridge.get_robot_pose()
        second = ros_bridge.get_robot_pose()

    assert first == second
    assert run_ros.call_count == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_navigation_pose.py -q -k "robot_pose_response or robot_pose_uses_short_ttl_cache"`

Expected: FAIL because parser, cache, and `get_robot_pose()` are not defined.

- [ ] **Step 3: Implement the bridge without topic echo**

1. Add `_pose_cache = (None, 0.0)` and a short constant such as `_POSE_CACHE_TTL = 0.8` near the other bridge caches.
2. Add `_invalid_pose(message, success=True)` returning exactly the stable fields used in the test: `success`, `valid`, `x`, `y`, `yaw`, `frame_id`, `source`, `stamp`, `message`.
3. Add `_parse_robot_pose_response(text)` that recognizes `valid=True|False`, extracts `x`, `y`, quaternion `z/w` (also `x/y` for a general yaw formula), `frame_id`, `sec`, `nanosec`, `source`, and `message` from the ROS Python response representation. For a valid pose compute `yaw = atan2(2*(w*z+x*y), 1-2*(y*y+z*z))`. For an explicit invalid service result return a `success=True`, `valid=False` result; malformed output returns `success=False`, `valid=False` and a diagnostic message.
4. Add `get_robot_pose(force=False)`. Return `_pose_cache[0]` while it is younger than `_POSE_CACHE_TTL`; otherwise call:

```python
_run_ros(
    'ros2 service call /patrol/get_robot_pose '
    'yahboomcar_patrol_interfaces/srv/GetRobotPose "{}"',
    timeout=5,
)
```

5. On command/container failures use `_invalid_pose(error_message, success=False)`. On nonzero ROS exit use `_invalid_pose(_friendly_error(output), success=False)`. Cache every returned normalized result so a burst of browser requests does not run duplicate Docker/ROS commands.
6. Do not use `ros2 topic echo --once`; Foxy does not support it.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_navigation_pose.py -q -k "robot_pose_response or robot_pose_uses_short_ttl_cache"`

Expected: PASS.

- [ ] **Step 5: Commit the bridge increment**

```powershell
git add tests/test_navigation_pose.py navigation/ros_bridge.py
git commit -m "feat: bridge live patrol pose to web API"
```

### Task 4: Publish the safe Flask response and render it in the patrol console

**Files:**
- Modify: `navigation/routes.py`
- Modify: `navigation/patrol_page.py`
- Modify: `tests/test_navigation_pose.py`

- [ ] **Step 1: Write Flask and page integration tests**

```python
from flask import Flask
from navigation.routes import nav_bp


def test_pose_endpoint_returns_http_200_for_invalid_localization(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(nav_bp, url_prefix='/api/nav')
    monkeypatch.setattr('navigation.routes.ros_bridge.get_robot_pose', lambda: {
        'success': True, 'valid': False, 'x': None, 'y': None, 'yaw': None,
        'frame_id': '', 'source': '', 'stamp': {'sec': 0, 'nanosec': 0},
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
    assert "pose.valid && pose.frame_id==='map'" in PATROL_PAGE_HTML
    assert '定位等待中' in PATROL_PAGE_HTML
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_navigation_pose.py -q -k "pose_endpoint or patrol_page_contains_live_pose"`

Expected: FAIL because the route, marker, polling function, and unavailable state do not exist.

- [ ] **Step 3: Implement the Flask route and page behavior**

1. Add this route in `navigation/routes.py` next to the other patrol read endpoints:

```python
@nav_bp.route('/pose', methods=['GET'])
def patrol_pose_api():
    result = ros_bridge.get_robot_pose()
    if not result.get('success'):
        result = dict(result)
        result.pop('success', None)
        return _ok(result, result.get('message', '定位服务不可用'))
    result = dict(result)
    result.pop('success', None)
    return _ok(result, result.get('message', 'ok'))
```

This keeps HTTP 200 both for no current localization and temporary bridge failure, allowing the console to distinguish `data.valid` from transport status.

2. Add `.marker.robot` styles that form a blue arrow using a rotated, absolutely positioned element. Do not change `.marker.route` or `.marker.start`.
3. Add a `robotPose` object with `valid`, `x`, `y`, `yaw`, `frame_id`, `source`, `stamp`, and `message` fields. Update `redraw()` to append a `marker robot` only when `robotPose.valid && robotPose.frame_id==='map'`. Convert map coordinates with the same `origin`, `resolution`, and inverted map Y calculation used for routes. Rotate the marker with `rotate(${-robotPose.yaw * 180 / Math.PI}deg)` so ROS's counter-clockwise map yaw renders correctly in the screen coordinate system.
4. Add the `<div id="robotPoseInfo">定位等待中</div>` panel below the start panel. Format valid data as `(<x>, <y>) · yaw=<degrees>° · <source> · <stamp>`, and show `定位等待中：<message>` whenever the result is invalid, non-map-frame, or a fetch/API error. Hide the marker in every unavailable case by setting `robotPose.valid = false` and calling `redraw()`.
5. Add `updateRobotPose()` to request `/api/nav/pose`, take `j.data`, update UI/marker, and handle failures. Call it in `tick()` on every cycle; set the successful pose polling interval to 1 second rather than coupling it to stack status polling. Keep all patrol controls unchanged.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_navigation_pose.py -q -k "pose_endpoint or patrol_page_contains_live_pose"`

Expected: PASS.

- [ ] **Step 5: Commit the web increment**

```powershell
git add tests/test_navigation_pose.py navigation/routes.py navigation/patrol_page.py
git commit -m "feat: show live robot pose on patrol map"
```

### Task 5: Verify Python behavior, changed files, and ROS build compatibility

**Files:**
- Verify: `tests/test_navigation_pose.py`
- Verify: all files changed by Tasks 1–4

- [ ] **Step 1: Run the feature regression suite**

Run: `python -m pytest tests/test_navigation_pose.py -q`

Expected: PASS with all pose-service, node-wiring, bridge, API, and page tests green.

- [ ] **Step 2: Run the nearby existing console suite**

Run: `python -m pytest tests/test_hospital_guide_console.py tests/test_hospital_guide.py -q`

Expected: PASS, demonstrating the Flask app's unrelated console behavior remains intact.

- [ ] **Step 3: Inspect the final change set**

Run:

```powershell
git diff --check
git status --short
git log --oneline --decorate -4
```

Expected: no whitespace errors; only the intended pose-service files and commits are present.

- [ ] **Step 4: Build and exercise on the Jetson after source deployment**

Copy the changed `yahboomcar-nav-src` files into the vehicle's navigation workspace, then inside its navigation container run:

```bash
cd /root/yahboomcar_ros2_ws/yahboomcar_ws
source /opt/ros/foxy/setup.bash
colcon build --packages-select yahboomcar_patrol_interfaces yahboomcar_nav --symlink-install
source install/setup.bash
ros2 service call /patrol/get_robot_pose yahboomcar_patrol_interfaces/srv/GetRobotPose '{}'
```

Expected: the build succeeds; when localization is available the service returns `valid=True` with `frame_id='map'` and source `tf` or `amcl_pose`; otherwise it returns `valid=False` without odometry coordinates.

- [ ] **Step 5: Perform end-to-end visual validation**

1. Start the navigation stack from `/nav/patrol`.
2. Confirm `GET /api/nav/pose` returns the stable payload shape and HTTP 200.
3. Move the localized robot or start a patrol.
4. Compare the blue webpage arrow with RViz's RobotModel: its map position and heading must agree.
5. Stop localization or navigation and confirm the blue arrow disappears while the page says `定位等待中`; route and start markers must remain visible.

- [ ] **Step 6: Commit final verification/doc state if any tracked files changed**

```powershell
git status --short
# If only committed feature files remain, no additional commit is necessary.
```
