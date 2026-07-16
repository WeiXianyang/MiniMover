"""人脸识别 Flask 蓝图：注册页 + 1:N 识别 + 注册/登录。"""
import threading
import time
from pathlib import Path

from flask import Blueprint, Response, jsonify, request, send_file

from . import store
from .recognition import identify_from_bytes
from audio.icar_audio import play_say

face_bp = Blueprint('face', __name__)
PAGE_PATH = Path(__file__).resolve().parent / 'page.html'


def register_face_routes(app):
    store.init_db()
    app.register_blueprint(face_bp)


@face_bp.route('/face')
def face_page():
    return send_file(PAGE_PATH, mimetype='text/html')


@face_bp.route('/api/face/snapshot')
def face_snapshot():
    """代理小车 ROS 相机一帧，供 /face 网页在非 HTTPS 下拍照（不依赖本机 getUserMedia）。"""
    import urllib.request
    url = 'http://127.0.0.1:8080/snapshot?topic=/camera/color/image_raw'
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = resp.read()
        if not data or len(data) < 500:
            return jsonify({'ok': False, 'msg': '相机未就绪（:8080 无图像）'}), 503
        return Response(data, mimetype='image/jpeg')
    except Exception as exc:
        return jsonify({'ok': False, 'msg': f'无法读取相机: {exc}'}), 503


def _read_image_file(file_storage):
    return file_storage.read()



@face_bp.route('/api/face/recognize', methods=['POST'])
@face_bp.route('/api/face_recognition', methods=['POST'])
def face_recognize():
    """1:N 身份识别：上传现场人脸照片，返回是谁 + 置信度。"""
    image = request.files.get('image') or request.files.get('face_image')
    if not image:
        return jsonify({'ok': False, 'msg': '请上传图片字段 image'}), 400
    try:
        payload, status = identify_from_bytes(_read_image_file(image))
        # 识别成功时触发 TTS 让小车说话
        if status == 200 and payload.get('ok'):
            identity = payload.get('identity', '未知用户')
            threading.Thread(
                target=play_say,
                args=(f'你好，{identity}',),
                daemon=True,
            ).start()
        return jsonify(payload), status
    except Exception as exc:
        return jsonify({'ok': False, 'msg': f'识别过程出错: {exc}'}), 500


@face_bp.route('/api/face/register', methods=['POST'])
@face_bp.route('/api/register', methods=['POST'])
def face_register():
    """注册用户并录入人脸（至少 3 张），同步到百度云。"""
    username = (request.form.get('username') or '').strip()
    password = request.form.get('password') or ''
    email = (request.form.get('email') or '').strip()
    phone = (request.form.get('phone') or '').strip()
    face_images = request.files.getlist('face_images')

    if not all([username, password, email, phone]):
        return jsonify({'ok': False, 'msg': '用户名、密码、邮箱和手机号不能为空'}), 400
    if store.get_user_by_username(username):
        return jsonify({'ok': False, 'msg': '用户名已存在'}), 400
    if len(face_images) < 3:
        return jsonify({'ok': False, 'msg': '请上传至少三张人脸图片'}), 400

    try:
        user_id = store.create_user(username, password, email, phone)
    except Exception as exc:
        return jsonify({'ok': False, 'msg': f'创建用户失败: {exc}'}), 500

    user_info = str({'username': username, 'email': email})
    success = 0
    first_token = None
    for image in face_images:
        image_bytes = _read_image_file(image)
        if not image_bytes:
            continue
        time.sleep(0.2)
        face_token = baidu.add_face(image_bytes, user_id, user_info)
        if face_token:
            store.save_face_image(user_id, username, image_bytes, face_token)
            success += 1
            if not first_token:
                first_token = face_token
        else:
            # 即便同步失败也本地留一份，方便排查；但最终以百度成功为准
            pass

    if success == 0:
        store.delete_user(user_id)
        return jsonify({'ok': False, 'msg': '人脸图片未能成功同步到百度云，请重试'}), 500

    if first_token:
        store.set_user_face_token(user_id, first_token)

    return jsonify({
        'ok': True,
        'msg': '注册成功',
        'user': {'id': user_id, 'username': username, 'faces': success},
    }), 201


@face_bp.route('/api/face/login', methods=['POST'])
@face_bp.route('/api/login', methods=['POST'])
def face_login():
    username = (request.form.get('username') or request.form.get('name') or '').strip()
    password = request.form.get('password') or ''
    face_image = request.files.get('face_image') or request.files.get('image')

    if not username or not password:
        return jsonify({'ok': False, 'msg': '用户名和密码不能为空'}), 400

    user = store.get_user_by_username(username)
    if not user or not store.verify_password(user, password):
        return jsonify({'ok': False, 'msg': '用户名或密码错误'}), 401

    if face_image:
        if not user.get('face_token'):
            return jsonify({'ok': False, 'msg': '用户人脸信息未录入，无法校验'}), 400
        image_bytes = _read_image_file(face_image)
        result, error = baidu.match_face(user['face_token'], image_bytes)
        if error:
            return jsonify({'ok': False, 'msg': error}), 503
        if result.get('error_code') != 0:
            return jsonify({
                'ok': False,
                'msg': f"人脸校验失败: {result.get('error_msg')}",
            }), 401
        score = float(result['result']['score'])
        if score < baidu.FACE_MATCH_THRESHOLD:
            return jsonify({
                'ok': False,
                'msg': '人脸校验未通过，请重新拍照',
                'score': score,
                'confidence': round(score / 100.0, 4),
                'reason': 'face_mismatch',
            }), 401
        return jsonify({
            'ok': True,
            'msg': '登录成功',
            'name': user['username'],
            'score': score,
            'confidence': round(score / 100.0, 4),
        })

    return jsonify({'ok': True, 'msg': '登录成功', 'name': user['username']})
