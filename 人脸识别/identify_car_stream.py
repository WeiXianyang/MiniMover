#!/usr/bin/env python3
"""从小车视频流做 1:N 身份识别（人脸库在百度云，无需在小车注册）。

前提：小车已启动相机与视频服务（见项目根目录 scripts/start_services.sh）。

用法：
  cd 人脸识别
  pip install opencv-python
  python identify_car_stream.py --car-ip 192.168.137.23
  python identify_car_stream.py --url http://192.168.137.23:8080/stream?topic=/camera/color/image_raw
  python identify_car_stream.py --car-ip 192.168.137.23 --auto 3

按键：
  空格 - 识别当前画面
  a      - 开启/关闭自动识别（默认每 3 秒）
  q      - 退出
"""
import argparse
import base64
import os
import sys
import time

import cv2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'face_recognition.settings')

import django

django.setup()

from face_auth.baidu_face import FACE_MATCH_THRESHOLD, identify_person
from face_auth.crypto import aes_decrypt_text
from face_auth.identity_utils import overlay_display_name, overlay_error_lines, resolve_display_name
from face_auth.models import UserProfile


def build_stream_url(car_ip, source):
    if source == 'ros':
        return f'http://{car_ip}:8080/stream?topic=/camera/color/image_raw'
    if source == 'api':
        return f'http://{car_ip}:5000/video_feed'
    raise ValueError(f'未知视频源: {source}')


def lookup_local_username(user_id):
    try:
        user = UserProfile.objects.get(id=user_id)
        return user.username
    except UserProfile.DoesNotExist:
        return None


def frame_to_base64(frame):
    ok, encoded = cv2.imencode('.jpg', frame)
    if not ok:
        return None
    return base64.b64encode(encoded.tobytes()).decode('utf-8')


def draw_overlay(frame, lines, color=(0, 220, 0)):
    y = 28
    for line in lines:
        cv2.putText(frame, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
        y += 26


def open_stream(url):
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        cap = cv2.VideoCapture(url)
    return cap


def run_identify(frame):
    image_base64 = frame_to_base64(frame)
    if not image_base64:
        return False, ['Encode failed'], (255, 80, 80)

    result = identify_person(image_base64)
    if not result.get('ok'):
        lines = overlay_error_lines(result.get('msg'), score=result.get('score'))
        print(f"[识别失败] {result.get('msg')}")
        return False, lines, (80, 80, 255)

    local_name = lookup_local_username(result['user_id'])
    display_name = overlay_display_name(result, local_username=local_name)
    lines = [
        f'Match: {display_name}',
        f'Score: {result["score"]:.1f}',
        f'user_id: {result["user_id"]}',
    ]
    full_name = resolve_display_name(result, local_username=local_name)
    print(f"[识别] {full_name} score={result['score']:.1f}")
    return True, lines, (0, 220, 0)


def parse_args():
    parser = argparse.ArgumentParser(description='小车视频流 1:N 身份识别')
    parser.add_argument('--car-ip', help='小车 IP，例如 192.168.137.23')
    parser.add_argument('--url', help='直接指定 MJPEG/视频流 URL')
    parser.add_argument(
        '--source',
        choices=['ros', 'api'],
        default='ros',
        help='视频源：ros=8080 彩色流(推荐)，api=5000/video_feed',
    )
    parser.add_argument('--auto', type=float, default=0, help='自动识别间隔秒数，例如 3')
    return parser.parse_args()


def main():
    args = parse_args()
    if args.url:
        stream_url = args.url
    elif args.car_ip:
        stream_url = build_stream_url(args.car_ip, args.source)
    else:
        print('请指定 --car-ip 或 --url')
        return 1

    print('连接小车视频流:', stream_url)
    print('空格=识别  a=自动识别开关  q=退出')
    cap = open_stream(stream_url)
    if not cap.isOpened():
        print('无法打开视频流，请检查：')
        print('  1. 小车是否已执行 bash ~/MiniMover/scripts/start_services.sh')
        print('  2. PC 与小车是否同一网段，IP 是否正确')
        print('  3. 浏览器能否打开该 URL')
        return 1

    status_lines = [
        'Car stream connected',
        'SPACE=identify  A=auto  Q=quit',
        f'Threshold: {FACE_MATCH_THRESHOLD}',
    ]
    auto_interval = max(args.auto, 0)
    auto_enabled = auto_interval > 0
    last_identify_at = 0.0
    fail_streak = 0

    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            fail_streak += 1
            if fail_streak >= 30:
                print('读帧失败，尝试重连...')
                cap.release()
                time.sleep(1)
                cap = open_stream(stream_url)
                fail_streak = 0
            time.sleep(0.05)
            continue
        fail_streak = 0

        display = frame.copy()
        draw_overlay(display, status_lines)
        cv2.imshow('Car Face 1:N', display)

        now = time.time()
        key = cv2.waitKey(1) & 0xFF
        should_identify = key == ord(' ')
        if key == ord('a'):
            auto_enabled = not auto_enabled
            status_lines = [
                f"Auto: {'ON' if auto_enabled else 'OFF'}",
                f'Interval: {auto_interval or 3:.0f}s',
            ]
        if auto_enabled and auto_interval > 0 and now - last_identify_at >= auto_interval:
            should_identify = True

        if should_identify:
            last_identify_at = now
            status_lines = ['Identifying...']
            _, status_lines, color = run_identify(frame)
            draw_overlay(display, status_lines, color=color)
            cv2.imshow('Car Face 1:N', display)
            cv2.waitKey(1)

        if key in (ord('q'), 27):
            break

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
