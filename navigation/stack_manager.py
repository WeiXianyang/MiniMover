"""p1 导航栈启动/停止管理：后台执行 + 状态缓存，避免堵塞 Flask。"""
import json
import subprocess
import threading
import time

from .config import CONTAINER_NAME, ROS_DOMAIN_ID

NAV_STACK_SCRIPT = '/root/yahboomcar_ros2_ws/yahboomcar_ws/scripts/nav_stack.sh'
LOGFILE_IN_CONTAINER = '/tmp/p1_stack.log'
ROBOT_TYPE = 'x3'
RPLIDAR_TYPE = 'a1'

_lock = threading.Lock()
_cache = {
    'container_running': False,
    'ready': False,
    'starting': False,
    'stopping': False,
    'message': '尚未查询',
    'log_tail': '',
    'updated_at': 0.0,
    'last_error': '',
}
_worker = None


def _docker(args, timeout=15):
    return subprocess.run(
        ['docker'] + args,
        capture_output=True, text=True, timeout=timeout)


def _script_shell(script_cmd):
    return (
        'export ROS_DOMAIN_ID=%s ROBOT_TYPE=%s RPLIDAR_TYPE=%s && bash %s %s'
        % (ROS_DOMAIN_ID, ROBOT_TYPE, RPLIDAR_TYPE, NAV_STACK_SCRIPT, script_cmd)
    )


def _docker_exec(script_cmd, timeout=20, detached=False):
    args = ['exec']
    if detached:
        args.append('-d')
    args.extend([CONTAINER_NAME, 'bash', '-lc', _script_shell(script_cmd)])
    return _docker(args, timeout=timeout)


def ensure_container_running_check_only():
    try:
        out = subprocess.check_output(
            ['docker', 'inspect', '-f', '{{.State.Running}}', CONTAINER_NAME],
            stderr=subprocess.DEVNULL, timeout=2).decode().strip()
        return out == 'true', None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False, None


def ensure_container_running():
    running, _ = ensure_container_running_check_only()
    if running:
        return True, '容器已在运行'
    try:
        proc = _docker(['start', CONTAINER_NAME], timeout=40)
        if proc.returncode == 0:
            time.sleep(2)
            return True, '容器已自动启动'
        err = (proc.stderr or proc.stdout or '').strip()
        if 'No such container' in err or 'no such container' in err.lower():
            return False, '找不到容器 %s' % CONTAINER_NAME
        return False, err or '容器启动失败'
    except subprocess.TimeoutExpired:
        return False, 'docker start 超时'
    except FileNotFoundError:
        return False, 'docker 命令不可用'


def _parse_json_output(proc):
    text = (proc.stdout or proc.stderr or '').strip()
    if not text:
        return {'success': False, 'message': '无输出'}
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith('{'):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {'success': proc.returncode == 0, 'message': text}


def _read_log_tail(n=20):
    try:
        proc = _docker(
            ['exec', CONTAINER_NAME, 'bash', '-lc',
             'tail -n %d %s 2>/dev/null || true' % (n, LOGFILE_IN_CONTAINER)],
            timeout=5)
        return (proc.stdout or '').strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ''


def _update_cache(**kwargs):
    with _lock:
        _cache.update(kwargs)
        _cache['updated_at'] = time.time()


def get_cached_status():
    with _lock:
        return dict(_cache)


def refresh_status(force=False):
    """轻量刷新缓存；强制或超过 2 秒才真正 docker 查询。"""
    with _lock:
        age = time.time() - _cache['updated_at']
        if not force and age < 2.0 and _cache['updated_at'] > 0:
            return dict(_cache)
        stopping = _cache['stopping']
        starting = _cache['starting']

    running, _ = ensure_container_running_check_only()
    if not running:
        _update_cache(
            container_running=False, ready=False,
            starting=False if not starting else starting,
            message='容器未运行', log_tail='')
        return get_cached_status()

    try:
        proc = _docker_exec('status', timeout=8, detached=False)
        data = _parse_json_output(proc)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        _update_cache(container_running=True, message='状态查询超时')
        return get_cached_status()

    ready = bool(data.get('ready'))
    launching = bool(data.get('starting'))
    msg = data.get('message') or ''
    log_tail = data.get('log_tail') or ''
    # 后台 start 过程中保持 starting=true，直到就绪或明确失败
    if starting and not ready and launching:
        show_starting = True
    elif starting and not ready and not launching and log_tail:
        show_starting = False
        msg = '启动失败: ' + (log_tail[-160:] if log_tail else msg)
    elif starting and ready:
        show_starting = False
        msg = '巡逻服务就绪'
    else:
        show_starting = launching and not ready

    _update_cache(
        container_running=True,
        ready=ready,
        starting=show_starting and not stopping,
        message=msg,
        log_tail=log_tail,
        last_error='' if ready else (_cache.get('last_error') or ''),
    )
    return get_cached_status()


def _bg_start():
    try:
        _update_cache(starting=True, stopping=False, message='正在启动容器…', ready=False)
        ok, msg = ensure_container_running()
        if not ok:
            _update_cache(starting=False, message=msg, last_error=msg)
            return
        _update_cache(container_running=True, message='容器已就绪，正在拉起 p1…')
        try:
            proc = _docker_exec('start', timeout=20, detached=False)
            result = _parse_json_output(proc)
        except subprocess.TimeoutExpired:
            result = {'success': True, 'starting': True, 'message': '启动命令已提交'}
            try:
                _docker_exec('start', timeout=5, detached=True)
            except Exception:
                pass

        if not result.get('success') and not result.get('ready') and not result.get('starting'):
            log_tail = _read_log_tail()
            _update_cache(
                starting=False, ready=False,
                message=result.get('message') or '启动失败',
                log_tail=log_tail, last_error=result.get('message', ''))
            return

        # 轮询就绪，最多 ~50 秒，但不堵 HTTP
        for _ in range(25):
            if get_cached_status().get('stopping'):
                break
            time.sleep(2)
            st = refresh_status(force=True)
            if st.get('ready'):
                _update_cache(starting=False, ready=True, message='导航栈已就绪')
                return
            if not st.get('starting') and not st.get('ready'):
                # 进程可能挂了
                log_tail = st.get('log_tail') or _read_log_tail()
                if log_tail and 'None' not in log_tail:  # keep waiting if just env print
                    pass
                if log_tail and ('Error' in log_tail or 'Traceback' in log_tail
                                 or 'failed' in log_tail.lower()):
                    _update_cache(
                        starting=False, ready=False,
                        message='导航栈启动失败', log_tail=log_tail,
                        last_error=log_tail[-200:])
                    return
        log_tail = _read_log_tail()
        st = refresh_status(force=True)
        if st.get('ready'):
            _update_cache(starting=False, ready=True, message='导航栈已就绪')
        else:
            _update_cache(
                starting=False,
                message='启动超时，请查看日志或再点一次启动',
                log_tail=log_tail,
                last_error=log_tail[-200:] if log_tail else 'timeout')
    except Exception as exc:
        _update_cache(starting=False, message='启动异常: %s' % exc, last_error=str(exc))


def _bg_stop():
    try:
        _update_cache(stopping=True, starting=False, message='正在停止导航栈…')
        running, _ = ensure_container_running_check_only()
        if not running:
            _update_cache(
                stopping=False, ready=False, starting=False,
                container_running=False, message='容器未运行，已是停止状态')
            return
        try:
            proc = _docker_exec('stop', timeout=25, detached=False)
            result = _parse_json_output(proc)
            msg = result.get('message') or '导航栈已停止'
            ok = bool(result.get('success', True))
        except subprocess.TimeoutExpired:
            # 超时也再杀一轮
            try:
                _docker_exec('stop', timeout=5, detached=True)
            except Exception:
                pass
            ok, msg = True, '停止命令已提交（超时，可能仍在清理）'
        _update_cache(
            stopping=False, ready=False, starting=False,
            message=msg if ok else (msg or '停止失败'),
            last_error='' if ok else msg)
        refresh_status(force=True)
    except Exception as exc:
        _update_cache(stopping=False, message='停止异常: %s' % exc, last_error=str(exc))


def start_stack_async():
    """立即返回，真正启动在后台线程。"""
    with _lock:
        if _cache.get('starting'):
            return {
                'success': True, 'accepted': True,
                'message': '已在启动中，请稍候看状态',
                'starting': True, 'patrol_ready': False,
            }
        if _cache.get('ready'):
            # 再确认一次
            pass

    # 快速查一次
    st = refresh_status(force=True)
    if st.get('ready'):
        return {
            'success': True, 'accepted': True,
            'message': '导航栈已在运行',
            'starting': False, 'patrol_ready': True, 'ready': True,
        }

    t = threading.Thread(target=_bg_start, daemon=True)
    t.start()
    _update_cache(starting=True, message='已接受启动请求，后台拉起中…')
    return {
        'success': True, 'accepted': True,
        'message': '已开始启动，请等待状态变为「就绪」（约 15 秒）',
        'starting': True, 'patrol_ready': False,
    }


def stop_stack_async():
    """立即返回，停止在后台进行；不因 docker 超时而 400。"""
    with _lock:
        if _cache.get('stopping'):
            return {
                'success': True, 'accepted': True,
                'message': '正在停止中…', 'patrol_ready': False,
            }

    t = threading.Thread(target=_bg_stop, daemon=True)
    t.start()
    _update_cache(stopping=True, starting=False, message='已接受停止请求…')
    return {
        'success': True, 'accepted': True,
        'message': '正在关闭导航栈…',
        'patrol_ready': False, 'starting': False,
    }


# ---- 兼容旧调用 ----
def start_stack(wait_ready=False, timeout=45):
    result = start_stack_async()
    if not wait_ready:
        return result
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(1)
        st = refresh_status(force=True)
        if st.get('ready'):
            return {
                'success': True, 'patrol_ready': True, 'ready': True,
                'message': '导航栈已就绪', 'starting': False,
            }
        if not st.get('starting') and not st.get('ready') and st.get('last_error'):
            return {
                'success': False, 'patrol_ready': False,
                'message': st.get('message') or '启动失败',
                'log_tail': st.get('log_tail'),
            }
    st = get_cached_status()
    return {
        'success': bool(st.get('ready')),
        'patrol_ready': bool(st.get('ready')),
        'starting': bool(st.get('starting')),
        'message': st.get('message') or '等待超时',
        'log_tail': st.get('log_tail'),
    }


def stop_stack():
    return stop_stack_async()


def stack_status_quick():
    return refresh_status(force=False)
