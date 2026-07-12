#!/usr/bin/env python3
"""生成红绿灯测试图片并验证检测器"""
import cv2
import numpy as np
import os

os.makedirs("E:/MiniMover/traffic_light/test_images", exist_ok=True)

def draw_traffic_light(img, x, y, radius, active_light, size=(200, 400)):
    """在图上画一个红绿灯"""
    h, w = size
    # 外壳
    cv2.rectangle(img, (x-30, y-10), (x+30, y+h+10), (80, 80, 80), -1)
    cv2.rectangle(img, (x-30, y-10), (x+30, y+h+10), (50, 50, 50), 2)

    positions = {'red': 60, 'yellow': h//2, 'green': h-60}
    colors = {'red': (0, 0, 200), 'yellow': (0, 200, 200), 'green': (0, 200, 0)}
    dark = (40, 40, 40)

    for name, offset in positions.items():
        cy = y + offset
        color = colors[name] if name == active_light else dark
        cv2.circle(img, (x, cy), radius, color, -1)
        cv2.circle(img, (x, cy), radius, (20, 20, 20), 1)

# 生成测试图片
bg = np.zeros((480, 640, 3), dtype=np.uint8)
bg[:] = (100, 150, 200)  # 蓝天背景

# 测试1: 红灯
img1 = bg.copy()
draw_traffic_light(img1, 320, 50, 20, 'red')
cv2.putText(img1, "RED LIGHT", (10, 450), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
cv2.imwrite("E:/MiniMover/traffic_light/test_images/red_light.jpg", img1)

# 测试2: 绿灯
img2 = bg.copy()
draw_traffic_light(img2, 320, 50, 20, 'green')
cv2.putText(img2, "GREEN LIGHT", (10, 450), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
cv2.imwrite("E:/MiniMover/traffic_light/test_images/green_light.jpg", img2)

# 测试3: 黄灯
img3 = bg.copy()
draw_traffic_light(img3, 320, 50, 20, 'yellow')
cv2.putText(img3, "YELLOW LIGHT", (10, 450), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
cv2.imwrite("E:/MiniMover/traffic_light/test_images/yellow_light.jpg", img3)

print("Test images generated: test_images/red_light.jpg, green_light.jpg, yellow_light.jpg")
