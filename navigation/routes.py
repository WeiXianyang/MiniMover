import json
import os

import cv2
import numpy as np
from flask import Blueprint, Response, jsonify, request

from . import department_markers, map_utils, ros_bridge
from . import stack_manager
from .config import ROUTES_DIR
from .patrol_page import PATROL_PAGE_HTML

nav_bp = Blueprint('navigation', __name__)


def _ok(data=None, msg='ok'):
    body = {'code': 0, 'msg': msg}
    if data is not None:
        body['data'] = data
    return jsonify(body)


def _err(msg, status=400):
    return jsonify({'code': -1, 'msg': msg}), status


@nav_bp.route('/department-markers', methods=['GET'])
def department_marker_list():
    try:
        return _ok(department_markers.list_markers())
    except department_markers.MarkerConfigError as exc:
        return _err(str(exc), 500)


@nav_bp.route('/department-markers', methods=['POST'])
def department_marker_save():
    data = request.json or {}
    try:
        marker = department_markers.save_marker(
            data.get('department'), data.get('x'), data.get('y'))
    except department_markers.MarkerConfigError as exc:
        return _err(str(exc), 500)
    except ValueError as exc:
        return _err(str(exc), 400)
    except OSError as exc:
        return _err('保存科室标注失败: %s' % exc, 500)
    return _ok(marker, '科室标注已保存')


def _parse_points(data):
    raw = data.get('points', [])
    if not raw:
        raise ValueError('points 不能为空')
    points = []
    for item in raw:
        if isinstance(item, dict):
            points.append({'x': float(item['x']), 'y': float(item['y'])})
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            points.append({'x': float(item[0]), 'y': float(item[1])})
        else:
            raise ValueError('无效的点格式: %r' % item)
    return points


@nav_bp.route('/map', methods=['GET'])
def map_info():
    try:
        return _ok(map_utils.read_map_info(request.args.get('map')))
    except Exception as exc:
        return _err('读取地图信息失败: %s' % exc, 500)


@nav_bp.route('/map/image', methods=['GET'])
def map_image():
    paths = map_utils.map_paths(request.args.get('map'))
    try:
        img = map_utils.load_pgm_gray(paths['pgm'])
        colored = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
        colored[img > 200] = [255, 255, 255]
        colored[(img >= 50) & (img <= 200)] = [200, 200, 200]
        colored[img < 50] = [30, 30, 30]
        _, jpg = cv2.imencode('.jpg', colored, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return Response(jpg.tobytes(), mimetype='image/jpeg')
    except FileNotFoundError:
        return _err('地图不存在: %s' % paths['pgm'], 404)
    except Exception as exc:
        return _err(str(exc), 500)


@nav_bp.route('/coord/pixel_to_map', methods=['POST'])
def coord_pixel_to_map():
    data = request.json or {}
    info = map_utils.read_map_info(data.get('map'))
    if 'screen_x' in data:
        x, y = map_utils.screen_to_pixel(
            float(data['screen_x']), float(data['screen_y']),
            float(data.get('display_width', info['width'])),
            float(data.get('display_height', info['height'])), info)
    else:
        x, y = map_utils.pixel_to_map(float(data['pixel_x']), float(data['pixel_y']), info)
    px, py = map_utils.map_to_pixel(x, y, info)
    return _ok({'x': x, 'y': y, 'pixel_x': px, 'pixel_y': py})


@nav_bp.route('/initial_pose', methods=['POST'])
def initial_pose():
    data = request.json or {}
    result = ros_bridge.set_initial_pose(
        data.get('x', 0), data.get('y', 0), data.get('yaw', 0))
    if not result.get('success'):
        return _err(result.get('message', '设置起点失败'))
    return _ok(result, result.get('message', 'ok'))


@nav_bp.route('/patrol/route', methods=['GET'])
def patrol_get_route():
    result = ros_bridge.get_route()
    if not result.get('success'):
        return _err(result.get('message', '读取失败'))
    return _ok(result)


@nav_bp.route('/patrol/route', methods=['POST'])
def patrol_set_route():
    try:
        points = _parse_points(request.json or {})
    except ValueError as exc:
        return _err(str(exc))
    result = ros_bridge.set_route(points)
    if not result.get('success'):
        return _err(result.get('message', '设置失败'))
    return _ok(result, result.get('message', 'ok'))


@nav_bp.route('/patrol/start', methods=['POST'])
def patrol_start():
    result = ros_bridge.start_patrol()
    if not result.get('success'):
        return _err(result.get('message', '启动失败'))
    return _ok(result, result.get('message', 'ok'))


@nav_bp.route('/patrol/stop', methods=['POST'])
def patrol_stop():
    result = ros_bridge.stop_patrol()
    if not result.get('success'):
        return _err(result.get('message', '停止失败'))
    return _ok(result, result.get('message', 'ok'))


@nav_bp.route('/patrol/clear', methods=['POST'])
def patrol_clear():
    result = ros_bridge.clear_route()
    if not result.get('success'):
        return _err(result.get('message', '清空失败'))
    return _ok(result, result.get('message', 'ok'))


@nav_bp.route('/pose', methods=['GET'])
def patrol_pose_api():
    result = dict(ros_bridge.get_robot_pose())
    result.pop('success', None)
    return _ok(result, result.get('message', 'ok'))


@nav_bp.route('/patrol/status', methods=['GET'])
def patrol_status_api():
    return _ok(ros_bridge.patrol_status())


@nav_bp.route('/patrol/loop', methods=['POST'])
def patrol_loop():
    data = request.json or {}
    result = ros_bridge.set_loop(bool(data.get('loop', True)))
    if not result.get('success'):
        return _err(result.get('message', '设置失败'))
    return _ok(result, result.get('message', 'ok'))


@nav_bp.route('/patrol/routes', methods=['GET'])
def list_saved_routes():
    os.makedirs(ROUTES_DIR, exist_ok=True)
    routes = []
    for name in sorted(os.listdir(ROUTES_DIR)):
        if name.endswith('.json'):
            routes.append({'name': name[:-5]})
    return _ok(routes)


@nav_bp.route('/patrol/routes/<name>', methods=['GET'])
def get_saved_route(name):
    path = os.path.join(ROUTES_DIR, '%s.json' % name)
    if not os.path.isfile(path):
        return _err('路线不存在', 404)
    with open(path, 'r', encoding='utf-8') as f:
        return _ok(json.load(f))


@nav_bp.route('/patrol/routes/<name>', methods=['POST'])
def save_route(name):
    os.makedirs(ROUTES_DIR, exist_ok=True)
    data = request.json or {}
    points = data.get('points')
    if not points:
        current = ros_bridge.get_route()
        points = current.get('points', [])
    payload = {
        'name': name,
        'map': data.get('map', 'loudao'),
        'initial_pose': data.get('initial_pose', {'x': 0, 'y': 0, 'yaw': 0}),
        'points': points,
        'loop': data.get('loop', True),
    }
    with open(os.path.join(ROUTES_DIR, '%s.json' % name), 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return _ok(payload, '路线已保存')


@nav_bp.route('/patrol/routes/<name>/load', methods=['POST'])
def load_saved_route(name):
    path = os.path.join(ROUTES_DIR, '%s.json' % name)
    if not os.path.isfile(path):
        return _err('路线不存在', 404)
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if (request.json or {}).get('apply_initial_pose', True) and 'initial_pose' in data:
        pose = data['initial_pose']
        ros_bridge.set_initial_pose(pose.get('x', 0), pose.get('y', 0), pose.get('yaw', 0))
    result = ros_bridge.set_route(data.get('points', []))
    if not result.get('success'):
        return _err(result.get('message', '加载失败'))
    return _ok({'route': data, 'loaded': result}, '路线已加载')


@nav_bp.route('/navigate', methods=['POST'])
def navigate():
    data = request.json or {}
    result = ros_bridge.navigate_to(data.get('x', 0), data.get('y', 0), data.get('theta', 0))
    return _ok(result, result.get('message', 'ok'))


@nav_bp.route('/stack/status', methods=['GET'])
def stack_status():
    # 只用缓存/轻量刷新，避免叠两轮 docker+ros 把 :5000 堵死
    info = ros_bridge.stack_info()
    cached = stack_manager.get_cached_status()
    info['stack_ready'] = bool(info.get('patrol_ready') or cached.get('ready'))
    info['starting'] = bool(info.get('starting') or cached.get('starting'))
    info['stopping'] = bool(info.get('stopping') or cached.get('stopping'))
    info['stack_message'] = info.get('stack_message') or cached.get('message')
    info['log_tail'] = cached.get('log_tail')
    if info.get('stack_ready'):
        info['patrol_ready'] = True
        info['starting'] = False
    if not info.get('patrol_ready'):
        if info.get('starting'):
            info['hint'] = '导航栈启动中，状态会自动刷新'
        elif info.get('stopping'):
            info['hint'] = '正在关闭导航栈…'
        elif not info.get('container_running'):
            info['hint'] = '点「启动导航栈」自动启动容器'
        else:
            info['hint'] = '点「启动导航栈」拉起 p1'
    return _ok(info)


@nav_bp.route('/stack/start', methods=['POST'])
def stack_start():
    """立即返回，后台启动（默认不等待就绪，避免点击卡住）"""
    data = request.json or {}
    wait = bool(data.get('wait_ready', False))
    timeout = int(data.get('timeout', 45))
    result = stack_manager.start_stack(wait_ready=wait, timeout=timeout)
    # 启动请求一律 200，失败信息放 msg，避免前端红字误以为「没点上」
    return _ok(result, result.get('message', 'ok'))


@nav_bp.route('/stack/stop', methods=['POST'])
def stack_stop():
    """立即返回，后台停止；不再因 docker 超时而 400"""
    result = stack_manager.stop_stack_async()
    return _ok(result, result.get('message', 'ok'))


def register_legacy_routes(app):
    @app.route('/api/map')
    def legacy_map():
        return map_info()

    @app.route('/api/map_image')
    def legacy_map_image():
        return map_image()

    @app.route('/api/navigate', methods=['POST'])
    def legacy_navigate():
        return navigate()


def register_patrol_page(app):
    @app.route('/nav/patrol')
    def patrol_test_page():
        return PATROL_PAGE_HTML
