import math
import re
import shlex
import subprocess
import time

from .config import CONTAINER_NAME, CONTAINER_WS, ROS_DOMAIN_ID

_PATROL_HINT = '请在网页点击「启动导航栈」（会自动启动容器并拉起 p1）'

_cache_lock_time = 0.0
_container_cache = (False, 0.0)  # running, ts
_ready_cache = (False, 0.0)  # ready, ts


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


def _call_trigger(service):
    proc, err = _run_ros(
        'ros2 service call %s std_srvs/srv/Trigger "{}"' % service, timeout=12)
    if err:
        return err
    text = _combined_output(proc)
    if proc.returncode != 0:
        return {'success': False, 'message': _friendly_error(text or 'trigger failed')}
    return _parse_trigger_response(text)


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


def navigate_to(x, y, theta=0.0):
    if not container_running():
        return {'success': False, 'message': '容器 %s 未运行' % CONTAINER_NAME}
    cmd = (
        '%s && ros2 action send_goal /navigate_to_pose '
        'nav2_msgs/action/NavigateToPose '
        '"{pose: {header: {frame_id: map}, pose: {position: {x: %s, y: %s}, '
        'orientation: {z: %s, w: 1.0}}}}"'
    ) % (_ros_env_shell(), x, y, theta)
    subprocess.Popen(
        _docker_cmd('bash', '-lc', cmd),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {'success': True, 'message': '导航到 (%.2f, %.2f)' % (x, y)}
