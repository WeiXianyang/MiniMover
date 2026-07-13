#!/usr/bin/env python3
"""本地摄像头 1:N 身份识别（不连接小车）。

用法：
  cd 人脸识别
  pip install opencv-python
  python manage.py migrate   # 首次运行
  python identify_camera.py

按键：
  空格 - 识别当前画面中的人是谁
  q    - 退出
"""
import base64
import os
import sys

import cv2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'face_recognition.settings')

import django

django.setup()

from face_auth.baidu_face import FACE_MATCH_THRESHOLD, identify_person
from face_auth.crypto import aes_decrypt_text
from face_auth.models import UserProfile


def lookup_user(user_id):
    try:
        user = UserProfile.objects.get(id=user_id)
    except UserProfile.DoesNotExist:
        return None
    try:
        email = aes_decrypt_text(user.email)
    except Exception:
        email = user.email
    return {'username': user.username, 'email': email}


def frame_to_base64(frame):
    ok, encoded = cv2.imencode('.jpg', frame)
    if not ok:
        return None
    return base64.b64encode(encoded.tobytes()).decode('utf-8')


def draw_overlay(frame, lines, color=(0, 220, 0)):
    y = 30
    for line in lines:
        cv2.putText(frame, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        y += 28


def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print('无法打开摄像头，请检查设备或权限。')
        return 1

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    status_lines = [
        '按空格识别，按 q 退出',
        f'匹配阈值: {FACE_MATCH_THRESHOLD}',
    ]
    print('本地 1:N 人脸识别已启动。按空格识别，按 q 退出。')

    while True:
        ok, frame = cap.read()
        if not ok:
            print('读取摄像头失败')
            break

        display = frame.copy()
        draw_overlay(display, status_lines)
        cv2.imshow('Face 1:N Identify', display)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), 27):
            break
        if key != ord(' '):
            continue

        status_lines = ['正在识别...']
        image_base64 = frame_to_base64(frame)
        if not image_base64:
            status_lines = ['图片编码失败']
            continue

        result = identify_person(image_base64)
        if not result.get('ok'):
            status_lines = [
                '识别失败',
                result.get('msg', '未知错误'),
            ]
            if result.get('score') is not None:
                status_lines.append(f"score={result['score']:.1f}")
            print('\n'.join(status_lines))
            continue

        user = lookup_user(result['user_id'])
        if user:
            status_lines = [
                f"你是: {user['username']}",
                f"相似度: {result['score']:.1f}",
            ]
            print(f"识别成功 -> {user['username']} ({result['score']:.1f})")
        else:
            status_lines = [
                '百度云已匹配，但本地无用户记录',
                f"user_id={result['user_id']}",
                f"score={result['score']:.1f}",
            ]
            print('\n'.join(status_lines))

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
