"""百度云人脸 1:N 识别（不依赖 Django）。"""
import base64
import json
import time

import requests

BAIDU_API_KEY = 'NypddVrKw1QSvISLwoEtmUfT'
BAIDU_SECRET_KEY = 'VTfOhjLs9Bq0taXoJKoWdfLlJZ4NUkeR'
BAIDU_APP_ID = '119454489'
FACE_GROUP_ID = 'user_faces'
FACE_MATCH_THRESHOLD = 80

_token_cache = {'token': None, 'expires_at': 0.0}


def get_baidu_token():
    now = time.time()
    if _token_cache['token'] and now < _token_cache['expires_at']:
        return _token_cache['token']

    url = (
        'https://aip.baidubce.com/oauth/2.0/token'
        f'?grant_type=client_credentials&client_id={BAIDU_API_KEY}'
        f'&client_secret={BAIDU_SECRET_KEY}'
    )
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        token = response.json().get('access_token')
        if token:
            _token_cache['token'] = token
            _token_cache['expires_at'] = now + 25 * 24 * 3600
        return token
    return None


def add_face(image_bytes, user_id, user_info=''):
    """录入人脸到百度云人脸库。成功返回 face_token。"""
    token = get_baidu_token()
    if not token:
        return None

    url = f'https://aip.baidubce.com/rest/2.0/face/v3/faceset/user/add?access_token={token}'
    data = {
        'image': base64.b64encode(image_bytes).decode('utf-8'),
        'image_type': 'BASE64',
        'group_id': FACE_GROUP_ID,
        'user_id': str(user_id),
        'user_info': user_info or '',
    }
    response = requests.post(
        url, data=json.dumps(data),
        headers={'Content-Type': 'application/json'}, timeout=20,
    )
    if response.status_code == 200:
        result = response.json()
        if result.get('error_code') == 0:
            return result.get('result', {}).get('face_token')
    return None


def match_face(face_token, image_bytes):
    token = get_baidu_token()
    if not token:
        return None, '人脸识别服务暂不可用'

    url = f'https://aip.baidubce.com/rest/2.0/face/v3/match?access_token={token}'
    data = [
        {'image': face_token, 'image_type': 'FACE_TOKEN', 'face_type': 'LIVE', 'quality_control': 'LOW'},
        {
            'image': base64.b64encode(image_bytes).decode('utf-8'),
            'image_type': 'BASE64',
            'face_type': 'LIVE',
            'quality_control': 'LOW',
        },
    ]
    response = requests.post(
        url, data=json.dumps(data),
        headers={'Content-Type': 'application/json'}, timeout=20,
    )
    return response.json(), None


def search_face(image_bytes, max_user_num=3, match_threshold=None):
    token = get_baidu_token()
    if not token:
        return None, '人脸识别服务暂不可用'

    url = f'https://aip.baidubce.com/rest/2.0/face/v3/search?access_token={token}'
    data = {
        'image': base64.b64encode(image_bytes).decode('utf-8'),
        'image_type': 'BASE64',
        'group_id_list': FACE_GROUP_ID,
        'max_user_num': max_user_num,
        'match_threshold': match_threshold if match_threshold is not None else FACE_MATCH_THRESHOLD,
        'quality_control': 'LOW',
        'face_sort_type': 0,
    }
    response = requests.post(
        url, data=json.dumps(data),
        headers={'Content-Type': 'application/json'}, timeout=20,
    )
    return response.json(), None


def identify_person(image_bytes, max_user_num=3, match_threshold=None):
    """1:N 人脸搜索，返回眼前这个人是谁。"""
    threshold = match_threshold if match_threshold is not None else FACE_MATCH_THRESHOLD
    result, error = search_face(image_bytes, max_user_num=max_user_num, match_threshold=threshold)
    if error:
        return {'ok': False, 'msg': error}
    if result.get('error_code') != 0:
        return {
            'ok': False,
            'msg': result.get('error_msg', '识别失败'),
            'error_code': result.get('error_code'),
        }

    search_result = result.get('result', {})
    user_list = search_result.get('user_list', [])
    if not user_list:
        return {'ok': False, 'msg': '未找到匹配用户', 'error_code': 222207}

    top_user = user_list[0]
    score = float(top_user.get('score', 0))
    if score < threshold:
        return {
            'ok': False,
            'msg': f'相似度不足（{score:.1f} < {threshold}），无法确认身份',
            'score': score,
            'confidence': round(score / 100.0, 4),
            'candidates': user_list,
        }

    return {
        'ok': True,
        'user_id': top_user.get('user_id'),
        'group_id': top_user.get('group_id'),
        'user_info': top_user.get('user_info', ''),
        'score': score,
        'confidence': round(score / 100.0, 4),
        'face_token': search_result.get('face_token'),
        'candidates': user_list,
    }
