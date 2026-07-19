import math
import re
import shlex
import subprocess
import threading
import time

from .config import CONTAINER_NAME, CONTAINER_WS, ROS_DOMAIN_ID

_PATROL_HINT = '请在网页点击「启动导航栈」（会自动启动容器并拉起 p1）'

_cache_lock_time = 0.0
_container_cache = (False, 0.0)  # running, ts
_ready_cache = (False, 0.0)  # ready, ts
_pose_cache = (None, 0.0)  # normalized pose, ts
_pose_query_lock = threading.Lock()
_POSE_CACHE_TTL = 0.8


def _docker_cmd(*args):
    return ['docker', 'exec', CONTAINER_NAME, *args]


def _ros_env_shell():
    return (
        'export ROS_DOMAIN_ID=%(domain)s && '
        'source /opt/ros/foxy/setup.bash && '
        'source %(ws)s/install/yahboomcar_patrol_interfaces/share/'
        'yahboomcar_patrol_interfaces/local_setup.bash && '
        'source %(ws)s/install/yahboomcar_nav/share/yahboomcar_nav/package.bash'
    ) % {'ws': CONTAINER_WS, 'domain': ROS_DOMAIN_ID}


def _friendly_error(msg):
    if 'service unavailable' in msg or 'waiting for service' in msg.lower():
        return '%s（%s，ROS_DOMAIN_ID=%s）' % (msg, _PATROL_HINT, ROS_DOMAIN_ID)
    if '超时' in msg or 'timeout' in msg.lower():
        return msg + '（服务忙或未就绪，请等「就绪」后再点）'
    return msg


def container_running(force=False):
    global _container_cache
    now = time.time()
    if not force and now - _container_cache[1] < 2.0:
        return _container_cache[0]
    try:
        out = subprocess.check_output(
            ['docker', 'inspect', '-f', '{{.State.Running}}', CONTAINER_NAME],
            stderr=subprocess.DEVNULL, timeout=2).decode().strip()
        val = out == 'true'
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        val = False
    _container_cache = (val, now)
    return val


def _run_ros(cmd, timeout=12):
    if not container_running():
        return None, {
            'success': False,
            'message': '容器 %s 未运行，请先点网页「启动导航栈」' % CONTAINER_NAME,
        }

    shell = '%s && %s' % (_ros_env_shell(), cmd)
    try:
        proc = subprocess.run(
            _docker_cmd('bash', '-lc', shell),
            capture_output=True, text=True, timeout=timeout)
        return proc, None
    except subprocess.TimeoutExpired:
        return None, {'success': False, 'message': 'ROS 调用超时'}
    except FileNotFoundError:
        return None, {'success': False, 'message': 'docker 命令不可用'}


def _combined_output(proc):
    return ((proc.stdout or '') + '\n' + (proc.stderr or '')).strip()


def _parse_trigger_response(text):
    match = re.search(r"success=(True|False).*?message='([^']*)'", text, re.DOTALL)
    if match:
        return {'success': match.group(1) == 'True', 'message': match.group(2)}
    if 'waiting for service' in text.lower():
        return {'success': False, 'message': _friendly_error('service unavailable')}
    return {'success': False, 'message': text or 'empty response from ros2'}


_NUMBER_RE = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'


def _invalid_pose(message, success=True):
    return {
        'success': success,
        'valid': False,
        'x': None,
        'y': None,
        'yaw': None,
        'frame_id': '',
        'source': '',
        'stamp': {'sec': 0, 'nanosec': 0},
        'message': message,
    }


def _parse_robot_pose_response(text):
    valid_match = re.search(r'valid=(True|False)', text)
    if not valid_match:
        return _invalid_pose('failed to parse pose service response', success=False)

    message_match = re.search(r"message='([^']*)'", text, re.DOTALL)
    message = message_match.group(1) if message_match else ''
    if valid_match.group(1) != 'True':
        return _invalid_pose(message or 'map-frame pose unavailable')

    position_match = re.search(
        r'position=.*?Point\(x=(%s), y=(%s),' % (_NUMBER_RE, _NUMBER_RE),
        text, re.DOTALL)
    orientation_match = re.search(
        r'orientation=.*?Quaternion\(x=(%s), y=(%s), z=(%s), w=(%s)\)'
        % (_NUMBER_RE, _NUMBER_RE, _NUMBER_RE, _NUMBER_RE),
        text, re.DOTALL)
    frame_match = re.search(r"frame_id='([^']*)'", text)
    stamp_match = re.search(r'Time\(sec=(-?\d+), nanosec=(\d+)\)', text)
    source_match = re.search(r"source='([^']*)'", text)
    if not all([position_match, orientation_match, frame_match, stamp_match, source_match]):
        return _invalid_pose('failed to parse pose service response', success=False)

    x = float(position_match.group(1))
    y = float(position_match.group(2))
    qx, qy, qz, qw = (float(value) for value in orientation_match.groups())
    yaw = math.atan2(
        2.0 * (qw * qz + qx * qy),
        1.0 - 2.0 * (qy * qy + qz * qz))
    return {
        'success': True,
        'valid': True,
        'x': x,
        'y': y,
        'yaw': yaw,
        'frame_id': frame_match.group(1),
        'source': source_match.group(1),
        'stamp': {
            'sec': int(stamp_match.group(1)),
            'nanosec': int(stamp_match.group(2)),
        },
        'message': message or 'ok',
    }


def _call_trigger(service):
    proc, err = _run_ros(
        'ros2 service call %s std_srvs/srv/Trigger "{}"' % service, timeout=12)
    if err:
        return err
    text = _combined_output(proc)
    if proc.returncode != 0:
        return {'success': False, 'message': _friendly_error(text or 'trigger failed')}
    return _parse_trigger_response(text)



def get_robot_pose(force=False):
    global _pose_cache
    # Browser pages poll both pose and demo status. Serialize the expensive
    # docker/ROS query so concurrent HTTP requests share the short-lived cache
    # instead of spawning overlapping ``docker exec ros2 service call`` jobs.
    with _pose_query_lock:
        now = time.time()
        cached, cached_at = _pose_cache
        if not force and cached is not None and now - cached_at < _POSE_CACHE_TTL:
            return cached

        proc, err = _run_ros(
            'timeout --signal=TERM --kill-after=1s 4s '
            'ros2 service call /patrol/get_robot_pose '
            'yahboomcar_patrol_interfaces/srv/GetRobotPose "{}"',
            timeout=6)
        if err:
            result = _invalid_pose(
                err.get('message', 'localization service unavailable'),
                success=False,
            )
        else:
            text = _combined_output(proc)
            if proc.returncode != 0:
                result = _invalid_pose(
                    _friendly_error(text or 'pose service failed'),
                    success=False,
                )
            else:
                result = _parse_robot_pose_response(text)
        _pose_cache = (result, time.time())
        return result


def patrol_services_ready(force=False):
    """优先用 stack_manager 缓存，避免每次 ros2 service list。"""
    global _ready_cache
    now = time.time()
    if not force and now - _ready_cache[1] < 2.0:
        return _ready_cache[0]

    # 先读 stack_manager 缓存（几乎零开销）
    try:
        from . import stack_manager
        cached = stack_manager.get_cached_status()
        if cached.get('updated_at', 0) and now - cached['updated_at'] < 5:
            val = bool(cached.get('ready'))
            _ready_cache = (val, now)
            return val
    except Exception:
        pass

    if not container_running():
        _ready_cache = (False, now)
        return False
    shell = (
        '%s && timeout 5 ros2 service list 2>/dev/null | grep -q /patrol/set_route'
        % _ros_env_shell()
    )
    try:
        proc = subprocess.run(
            _docker_cmd('bash', '-lc', shell),
            capture_output=True, timeout=7)
        val = proc.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        val = False
    _ready_cache = (val, now)
    return val


def stack_info():
    """轻量：主要返回缓存，不再每次双份 docker/ros 探测。"""
    try:
        from . import stack_manager
        cached = stack_manager.refresh_status(force=False)
        ready = bool(cached.get('ready'))
        running = bool(cached.get('container_running'))
        return {
            'container': CONTAINER_NAME,
            'container_running': running,
            'patrol_ready': ready,
            'starting': bool(cached.get('starting')),
            'stopping': bool(cached.get('stopping')),
            'ros_domain_id': ROS_DOMAIN_ID,
            'stack_message': cached.get('message'),
            'hint': None if ready else _PATROL_HINT,
        }
    except Exception:
        running = container_running()
        return {
            'container': CONTAINER_NAME,
            'container_running': running,
            'patrol_ready': False,
            'ros_domain_id': ROS_DOMAIN_ID,
            'hint': _PATROL_HINT,
        }


def _build_set_route_request(points):
    poses = []
    for pt in points:
        poses.append(
            '{header: {frame_id: map}, pose: {position: {x: %s, y: %s}, orientation: {w: 1.0}}}'
            % (float(pt['x']), float(pt['y'])))
    return '{route: {header: {frame_id: map}, poses: [%s]}}' % ', '.join(poses)


def set_route(points):
    if not patrol_services_ready(force=True):
        return {
            'success': False,
            'message': '巡逻服务未就绪，请等导航栈显示「就绪」后再上传路线',
        }
    req = _build_set_route_request(points)
    proc, err = _run_ros(
        'ros2 service call /patrol/set_route yahboomcar_patrol_interfaces/srv/SetRoute '
        + shlex.quote(req),
        timeout=15)
    if err:
        return err
    text = _combined_output(proc)
    if proc.returncode != 0:
        return {'success': False, 'message': _friendly_error(text or 'set_route failed')}

    match = re.search(
        r"success=(True|False).*?message='([^']*)'.*?point_count=(\d+)", text, re.DOTALL)
    if match:
        return {
            'success': match.group(1) == 'True',
            'message': match.group(2),
            'point_count': int(match.group(3)),
        }
    return _parse_trigger_response(text)


def get_route():
    proc, err = _run_ros(
        'ros2 service call /patrol/get_route yahboomcar_patrol_interfaces/srv/GetRoute "{}"',
        timeout=12)
    if err:
        return err
    text = _combined_output(proc)
    if proc.returncode != 0:
        return {'success': False, 'message': _friendly_error(text or 'get_route failed')}

    points = []
    for match in re.finditer(
            r'position=geometry_msgs\.msg\.Point\(x=([-\d.]+), y=([-\d.]+)', text):
        points.append({
            'x': round(float(match.group(1)), 4),
            'y': round(float(match.group(2)), 4),
        })

    success_match = re.search(r'success=(True|False)', text)
    message_match = re.search(r"message='([^']*)'", text)
    count_match = re.search(r'point_count=(\d+)', text)
    active_match = re.search(r'patrol_active=(True|False)', text)
    loop_match = re.search(r'loop=(True|False)', text)

    return {
        'success': success_match.group(1) == 'True' if success_match else False,
        'message': message_match.group(1) if message_match else '',
        'point_count': int(count_match.group(1)) if count_match else len(points),
        'patrol_active': active_match.group(1) == 'True' if active_match else False,
        'loop': loop_match.group(1) == 'True' if loop_match else True,
        'points': points,
    }


def start_patrol():
    return _call_trigger('/patrol/start')


def stop_patrol():
    return _call_trigger('/patrol/stop')


def clear_route():
    return _call_trigger('/patrol/clear')


def set_loop(enabled):
    value = 'true' if enabled else 'false'
    proc, err = _run_ros(
        'ros2 service call /patrol/set_loop std_srvs/srv/SetBool "{data: %s}"' % value,
        timeout=20)
    if err:
        return err
    text = _combined_output(proc)
    if proc.returncode != 0:
        return {'success': False, 'message': _friendly_error(text or 'set_loop failed')}
    return _parse_trigger_response(text)


def set_initial_pose(x, y, yaw=0.0):
    """发布 /initialpose。不阻塞等待 DDS 发现，避免网页「ROS 调用超时」。"""
    if not container_running():
        return {
            'success': False,
            'message': '容器 %s 未运行，请先点「启动导航栈」' % CONTAINER_NAME,
        }
    z = math.sin(float(yaw) / 2.0)
    w = math.cos(float(yaw) / 2.0)
    cov = (
        '[0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, '
        '0.06853891945200942, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, '
        '0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]'
    )
    msg = (
        '{header: {frame_id: map}, pose: {pose: {position: {x: %s, y: %s}, '
        'orientation: {z: %s, w: %s}}, covariance: %s}}'
    ) % (float(x), float(y), z, w, cov)
    # 多发几次提高 AMCL 收到概率；后台执行 + timeout，避免网页卡「ROS 调用超时」
    # （Foxy 的 ros2 topic pub 会等 DDS 发现，同步调用很容易超过 Flask 超时）
    pub = (
        'timeout 15 ros2 topic pub --times 5 '
        '/initialpose geometry_msgs/msg/PoseWithCovarianceStamped %s '
        '>/tmp/initialpose_pub.log 2>&1 || true'
    ) % shlex.quote(msg)
    shell = '%s && %s' % (_ros_env_shell(), pub)
    try:
        subprocess.Popen(
            _docker_cmd('bash', '-lc', shell),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        return {'success': False, 'message': 'docker 命令不可用'}
    return {
        'success': True,
        'message': '起点已提交 (%.2f, %.2f, yaw=%.2f)' % (float(x), float(y), float(yaw)),
        'x': float(x),
        'y': float(y),
        'yaw': float(yaw),
    }


def patrol_status():
    # 导航栈未就绪时不要硬查 topic（会超时，前端看起来像一直「未知」）
    if not patrol_services_ready():
        running = container_running()
        return {
            'status': 'idle' if running else 'container_stopped',
            'patrol_active': False,
            'point_count': 0,
            'loop': True,
            'message': '导航栈未就绪' if running else '容器未运行',
        }

    status_text = 'ready'
    proc, err = _run_ros(
        'timeout 2 ros2 topic echo --once /patrol_status std_msgs/msg/String 2>/dev/null || true',
        timeout=5)
    if proc and proc.stdout:
        match = re.search(r"data:\s*['\"]([^'\"]*)['\"]", proc.stdout)
        if match:
            status_text = match.group(1)
    active = ('navigating' in status_text.lower()) or ('waypoint' in status_text.lower())
    return {
        'status': status_text,
        'patrol_active': active,
        'point_count': 0,
        'loop': True,
    }



_DEMO_ACTIVE_GOAL_STATUSES = frozenset({'PENDING', 'ACTIVE'})
_DEMO_TERMINAL_GOAL_STATUSES = frozenset({'SUCCEEDED', 'FAILED', 'CANCELLED'})
_MIN_IMU_ACCELERATION_NORM = 0.5
_demo_goal_lock = threading.RLock()
_demo_goal = None
_demo_goal_sequence = 0


def _parse_imu_acceleration(text):
    match = re.search(
        r"linear_acceleration:\s*x:\s*(%s)\s*y:\s*(%s)\s*z:\s*(%s)"
        % (_NUMBER_RE, _NUMBER_RE, _NUMBER_RE),
        str(text or ""),
        re.DOTALL,
    )
    if not match:
        return None
    return tuple(float(match.group(index)) for index in (1, 2, 3))


def _demo_navigation_health():
    """Fail closed unless chassis, localization, odometry, and IMU are observable."""
    if not container_running(force=True):
        return {"success": False, "message": "navigation container is not running"}
    if not patrol_services_ready(force=True):
        return {"success": False, "message": "navigation stack is not ready"}

    pose = get_robot_pose(force=True)
    if not pose.get("valid") or pose.get("frame_id") != "map":
        return {"success": False, "message": "fresh map-frame localization is unavailable"}

    imu_command = (
        "serial=$(readlink -f /dev/myserial 2>/dev/null || true); "
        "if [ -z \"$serial\" ] || [ ! -c \"$serial\" ]; then "
        "echo __SERIAL_UNAVAILABLE__; exit 41; fi; "
        "timeout 4 ros2 topic echo --once /imu/data_raw sensor_msgs/msg/Imu"
    )
    imu_proc, imu_error = _run_ros(imu_command, timeout=7)
    if imu_error:
        return {"success": False, "message": imu_error.get("message", "IMU health check failed")}
    imu_output = _combined_output(imu_proc)
    if imu_proc.returncode != 0:
        if "__SERIAL_UNAVAILABLE__" in imu_output:
            return {"success": False, "message": "/dev/myserial is unavailable inside the navigation container"}
        return {"success": False, "message": "IMU data is unavailable"}

    acceleration = _parse_imu_acceleration(imu_output)
    if acceleration is None:
        return {"success": False, "message": "IMU acceleration could not be parsed"}
    gravity_norm = math.sqrt(sum(value * value for value in acceleration))
    if not math.isfinite(gravity_norm) or gravity_norm < _MIN_IMU_ACCELERATION_NORM:
        return {"success": False, "message": "IMU reports free fall or zero acceleration"}

    odom_proc, odom_error = _run_ros(
        "timeout 4 ros2 topic echo --once /odom nav_msgs/msg/Odometry", timeout=7)
    if odom_error:
        return {"success": False, "message": odom_error.get("message", "odometry health check failed")}
    if odom_proc.returncode != 0 or not _combined_output(odom_proc):
        return {"success": False, "message": "odometry feedback is unavailable"}

    return {
        "success": True,
        "message": "navigation sensor health check passed",
        "imu_acceleration_norm": gravity_norm,
    }


def _update_demo_goal_from_line(goal_id, line):
    """Apply a Nav2 CLI output transition for the currently tracked goal only."""
    text = str(line or '').strip()
    if not text:
        return
    lowered = text.lower()
    status = None
    message = text
    finished = re.search(r'goal finished with status:\s*([A-Za-z_]+)', text, re.IGNORECASE)
    if finished:
        reported = finished.group(1).upper()
        if reported == 'SUCCEEDED':
            status = 'SUCCEEDED'
        elif reported in {'CANCELED', 'CANCELLED'}:
            status = 'CANCELLED'
        else:
            status = 'FAILED'
    elif ('goal canceled' in lowered or 'goal cancelled' in lowered
          or 'canceled' in lowered or 'cancelled' in lowered):
        status = 'CANCELLED'
    elif 'goal accepted' in lowered or 'goal was accepted' in lowered:
        status = 'ACTIVE'
    elif 'goal rejected' in lowered or 'goal aborted' in lowered:
        status = 'FAILED'
    if status is None:
        return

    with _demo_goal_lock:
        goal = _demo_goal
        if not goal or goal.get('goal_id') != goal_id:
            return
        if goal.get('status') in _DEMO_TERMINAL_GOAL_STATUSES:
            return
        goal['status'] = status
        goal['message'] = message


def _finish_demo_goal_reader(goal_id, return_code=None, error=None):
    with _demo_goal_lock:
        goal = _demo_goal
        if not goal or goal.get('goal_id') != goal_id:
            return
        if goal.get('status') in _DEMO_ACTIVE_GOAL_STATUSES:
            goal['status'] = 'FAILED'
            if error:
                goal['message'] = 'Nav2 goal output reader failed: %s' % error
            else:
                goal['message'] = (
                    'Nav2 goal process exited before reporting success'
                    + ('' if return_code is None else ' (exit code %s)' % return_code)
                )
        goal.pop('_process', None)


def _read_demo_goal_output(goal_id, proc):
    """Follow the Nav2 CLI result stream without deriving completion from HTTP."""
    try:
        if proc.stdout is None:
            raise RuntimeError('Nav2 goal process has no output stream')
        for line in proc.stdout:
            _update_demo_goal_from_line(goal_id, line)
        return_code = proc.wait()
    except Exception as exc:
        _finish_demo_goal_reader(goal_id, error=str(exc))
        return
    _finish_demo_goal_reader(goal_id, return_code=return_code)


def navigate_to(x, y, theta=0.0):
    """Submit one Nav2 goal and track only the status emitted by Nav2 itself."""
    global _demo_goal, _demo_goal_sequence
    try:
        x = float(x)
        y = float(y)
        theta = float(theta)
    except (TypeError, ValueError):
        return {'success': False, 'message': 'navigation coordinates must be numeric'}
    if not all(math.isfinite(value) for value in (x, y, theta)):
        return {'success': False, 'message': 'navigation coordinates must be finite'}

    with _demo_goal_lock:
        if _demo_goal and _demo_goal.get('status') in _DEMO_ACTIVE_GOAL_STATUSES:
            return {
                'success': False,
                'message': 'a demo navigation goal is already active',
                'status': _demo_goal.get('status'),
            }

    # Sensor probes can block for several seconds. Keep them outside the goal
    # lock so status and cancel requests remain responsive during preflight.
    health = _demo_navigation_health()
    if not health.get('success'):
        return {
            'success': False,
            'message': 'navigation health check failed: %s' % health.get('message', 'unknown failure'),
        }

    with _demo_goal_lock:
        # Another request may have submitted a goal while health was checked.
        # Recheck under the lock before spawning the only Nav2 goal process.
        if _demo_goal and _demo_goal.get('status') in _DEMO_ACTIVE_GOAL_STATUSES:
            return {
                'success': False,
                'message': 'a demo navigation goal is already active',
                'status': _demo_goal.get('status'),
            }

        z = math.sin(theta / 2.0)
        w = math.cos(theta / 2.0)
        goal_yaml = (
            '{pose: {header: {frame_id: map}, pose: {position: {x: %s, y: %s}, '
            'orientation: {z: %s, w: %s}}}}'
        ) % (x, y, z, w)
        cmd = (
            '%s && ros2 action send_goal --feedback /navigate_to_pose '
            'nav2_msgs/action/NavigateToPose %s'
        ) % (_ros_env_shell(), shlex.quote(goal_yaml))
        try:
            proc = subprocess.Popen(
                _docker_cmd('bash', '-lc', cmd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except (FileNotFoundError, OSError) as exc:
            return {'success': False, 'message': 'unable to start Nav2 goal: %s' % exc}

        _demo_goal_sequence += 1
        goal_id = _demo_goal_sequence
        _demo_goal = {
            'goal_id': goal_id,
            'x': x,
            'y': y,
            'theta': theta,
            'status': 'PENDING',
            'message': 'Nav2 goal submitted; waiting for acceptance',
            '_process': proc,
        }

    threading.Thread(
        target=_read_demo_goal_output,
        args=(goal_id, proc),
        daemon=True,
    ).start()
    return {
        'success': True,
        'message': 'navigation goal submitted (%.2f, %.2f)' % (x, y),
        'status': 'PENDING',
        'target': {'x': x, 'y': y, 'theta': theta},
    }


def demo_goal_status(tolerance=0.15):
    """Trust Nav2 completion while retaining map-pose distance as diagnostics."""
    try:
        tolerance = float(tolerance)
    except (TypeError, ValueError):
        tolerance = 0.15
    if not math.isfinite(tolerance) or tolerance < 0:
        tolerance = 0.15

    with _demo_goal_lock:
        goal = dict(_demo_goal) if _demo_goal else None
    if not goal:
        return {
            'active': False,
            'arrived': False,
            'status': 'IDLE',
            'message': 'no demo navigation goal',
            'target': None,
            'pose': None,
            'distance_m': None,
            'tolerance_m': tolerance,
        }

    try:
        pose = get_robot_pose()
    except Exception as exc:
        pose = _invalid_pose('failed to read robot pose: %s' % exc, success=False)

    distance = None
    # Nav2's action result is the authority for motion completion. Its goal
    # checker already applies the configured XY/yaw tolerances and stops the
    # controller before reporting SUCCEEDED. A stricter HTTP-layer distance
    # threshold must not leave the demo stuck in NAVIGATING after the car stops.
    arrived = goal.get('status') == 'SUCCEEDED'
    if arrived and pose.get('valid') and pose.get('frame_id') == 'map':
        try:
            pose_x = float(pose.get('x'))
            pose_y = float(pose.get('y'))
            if math.isfinite(pose_x) and math.isfinite(pose_y):
                distance = math.hypot(pose_x - goal['x'], pose_y - goal['y'])
        except (TypeError, ValueError):
            pass

    return {
        'active': goal.get('status') in _DEMO_ACTIVE_GOAL_STATUSES,
        'arrived': arrived,
        'status': goal.get('status', 'FAILED'),
        'message': goal.get('message', ''),
        'target': {
            'x': goal.get('x'),
            'y': goal.get('y'),
            'theta': goal.get('theta'),
        },
        'pose': pose,
        'distance_m': distance,
        'tolerance_m': tolerance,
    }


def mark_demo_goal_cancelled(message):
    """Clear local ACTIVE/PENDING state after a verified cancel or stack stop."""
    with _demo_goal_lock:
        goal = _demo_goal
        if not goal or goal.get('status') not in _DEMO_ACTIVE_GOAL_STATUSES:
            return False
        goal['status'] = 'CANCELLED'
        goal['message'] = str(message)
        return True


def cancel_demo_goal():
    """Cancel all NavigateToPose goals through the ROS 2 action cancel service."""
    with _demo_goal_lock:
        goal = _demo_goal
        if not goal:
            return {
                'success': True,
                'status': 'IDLE',
                'message': 'no active demo navigation goal',
            }
        status = goal.get('status')
        process = goal.get('_process')
        if status not in _DEMO_ACTIVE_GOAL_STATUSES:
            return {
                'success': True,
                'status': status,
                'message': 'demo navigation goal is already terminal',
            }

    zero_uuid = ', '.join(['0'] * 16)
    request = (
        '{goal_info: {goal_id: {uuid: [%s]}, '
        'stamp: {sec: 0, nanosec: 0}}}' % zero_uuid
    )
    command = (
        'ros2 service call /navigate_to_pose/_action/cancel_goal '
        'action_msgs/srv/CancelGoal %s' % shlex.quote(request)
    )
    proc, error = _run_ros(command, timeout=8)
    if error:
        return error
    output = _combined_output(proc)
    if proc.returncode != 0 or not re.search(r'return_code\s*[:=]\s*0', output):
        return {
            'success': False,
            'message': _friendly_error(output or 'Nav2 cancel request failed'),
        }

    mark_demo_goal_cancelled('Nav2 navigation goal cancelled')
    if process is not None and hasattr(process, 'terminate'):
        try:
            process.terminate()
        except OSError:
            pass
    return {
        'success': True,
        'status': 'CANCELLED',
        'message': 'Nav2 navigation goal cancelled',
    }
