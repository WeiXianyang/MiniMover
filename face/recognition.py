"""Reusable face-recognition service without HTTP or TTS side effects."""

from . import baidu, store
from .identity_utils import resolve_display_name


def _build_success(identified, local_user=None):
    identity = resolve_display_name(
        identified,
        local_username=local_user['username'] if local_user else None,
    )
    score = float(identified['score'])
    confidence = identified.get('confidence')
    if confidence is None:
        confidence = round(score / 100.0, 4)
    return {
        'ok': True,
        'msg': '识别成功',
        'identity': identity,
        'score': score,
        'confidence': confidence,
        'user': {
            'id': identified['user_id'],
            'username': identity,
            'email': local_user.get('email') if local_user else None,
            'score': score,
            'confidence': confidence,
            'user_info': identified.get('user_info', ''),
            'source': 'local_db' if local_user else 'baidu_cloud',
        },
        'candidates': identified.get('candidates', []),
    }


def identify_from_bytes(image_bytes):
    """Identify one image and preserve the existing face API payload contract."""
    identified = baidu.identify_person(image_bytes)
    if not identified.get('ok'):
        payload = {
            'ok': False,
            'msg': identified.get('msg', '识别失败'),
        }
        if identified.get('error_code') is not None:
            payload['error_code'] = identified['error_code']
        if identified.get('score') is not None:
            payload['score'] = identified['score']
            payload['confidence'] = identified.get(
                'confidence', round(float(identified['score']) / 100.0, 4)
            )
        if identified.get('candidates'):
            payload['candidates'] = identified['candidates']
        status = 404 if identified.get('error_code') == 222207 else 400
        return payload, status

    try:
        local_user = store.get_user_by_id(identified['user_id'])
    except Exception:
        local_user = None
    return _build_success(identified, local_user), 200
