import base64
import json
import time

import requests

from .crypto import aes_decrypt_image
from .models import UserFaceImage

BAIDU_API_KEY = 'NypddVrKw1QSvISLwoEtmUfT'
BAIDU_SECRET_KEY = 'VTfOhjLs9Bq0taXoJKoWdfLlJZ4NUkeR'
BAIDU_APP_ID = '119454489'
FACE_MATCH_THRESHOLD = 80


def get_baidu_token():
    url = (
        'https://aip.baidubce.com/oauth/2.0/token'
        f'?grant_type=client_credentials&client_id={BAIDU_API_KEY}&client_secret={BAIDU_SECRET_KEY}'
    )
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        return response.json().get('access_token')
    return None


def _image_path_to_base64(image_path):
    user_face = UserFaceImage.objects.filter(image=image_path).first()
    if user_face:
        file_obj = user_face.image.open()
        decrypted_data = file_obj.read()
        file_obj.close()
    else:
        with open(image_path, 'rb') as file:
            decrypted_data = aes_decrypt_image(file.read())
    return base64.b64encode(decrypted_data).decode('utf-8')


def add_face_to_baidu(image_path, user_id, user_info=None):
    token = get_baidu_token()
    if not token:
        return None

    url = f'https://aip.baidubce.com/rest/2.0/face/v3/faceset/user/add?access_token={token}'
    data = {
        'image': _image_path_to_base64(image_path),
        'image_type': 'BASE64',
        'group_id': 'user_faces',
        'user_id': str(user_id),
        'user_info': user_info or '',
    }
    response = requests.post(url, data=json.dumps(data), headers={'Content-Type': 'application/json'}, timeout=20)
    if response.status_code == 200:
        result = response.json()
        if result.get('error_code') == 0:
            return result.get('result', {}).get('face_token')
    return None


def search_face(image_base64):
    token = get_baidu_token()
    if not token:
        return None, '人脸识别服务暂不可用'

    url = f'https://aip.baidubce.com/rest/2.0/face/v3/search?access_token={token}'
    data = {
        'image': image_base64,
        'image_type': 'BASE64',
        'group_id_list': 'user_faces',
        'max_face_num': 1,
    }
    response = requests.post(url, data=json.dumps(data), headers={'Content-Type': 'application/json'}, timeout=20)
    return response.json(), None


def match_face(face_token, image_base64):
    token = get_baidu_token()
    if not token:
        return None, '人脸识别服务暂不可用'

    url = f'https://aip.baidubce.com/rest/2.0/face/v3/match?access_token={token}'
    data = [
        {'image': face_token, 'image_type': 'FACE_TOKEN', 'face_type': 'LIVE', 'quality_control': 'LOW'},
        {'image': image_base64, 'image_type': 'BASE64', 'face_type': 'LIVE', 'quality_control': 'LOW'},
    ]
    response = requests.post(url, data=json.dumps(data), headers={'Content-Type': 'application/json'}, timeout=20)
    return response.json(), None


def register_faces_for_user(user, face_images, username, email):
    success_faces = []
    for image in face_images:
        user_face = UserFaceImage(user=user, image=image)
        user_face.save()
        face_token = None
        try:
            time.sleep(0.2)
            face_token = add_face_to_baidu(
                user_face.image.path,
                user.id,
                f"{{'username': '{username}', 'email': '{email}'}}",
            )
        except Exception:
            face_token = None
        if face_token:
            user_face.face_token = face_token
            user_face.save()
            success_faces.append(user_face)
        else:
            user_face.delete()
    return success_faces
