#!/usr/bin/env python3
"""
轻量化红绿灯视觉识别
基于 HSV 色彩空间 + HoughCircles 圆检测，纯 OpenCV 实现
"""
import cv2
import numpy as np

class TrafficLightDetector:
    """红绿灯检测器"""

    def __init__(self):
        # HSV 色彩范围（可微调适应实际光照）
        self.color_ranges = {
            'red':    [(0, 120, 70),   (10, 255, 255)],   # 红色低阈值
            'red2':   [(170, 120, 70), (180, 255, 255)],  # 红色高阈值(HSV环绕)
            'yellow': [(20, 100, 100), (35, 255, 255)],
            'green':  [(40, 50, 50),   (90, 255, 255)],
        }

    def detect(self, frame):
        """
        检测帧中的红绿灯
        返回: (result_frame, state)
          state: 'red' | 'yellow' | 'green' | 'none'
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h, w = frame.shape[:2]

        # ROI: 取画面上半部分 1/3（交通灯通常在上方）
        hsv_roi = hsv[0:h//2, :]
        gray_roi = cv2.cvtColor(frame[0:h//2, :], cv2.COLOR_BGR2GRAY)

        # 高斯模糊降噪
        blurred = cv2.GaussianBlur(gray_roi, (9, 9), 2)

        # HoughCircles 圆检测
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=30,
            param1=50,
            param2=25,
            minRadius=8,
            maxRadius=60
        )

        detected_state = 'none'
        best = None  # (x, y, r, color)

        if circles is not None:
            circles = np.uint16(np.around(circles))

            for (cx, cy, r) in circles[0]:
                # 在圆内取 ROI 掩码
                mask = np.zeros(hsv_roi.shape[:2], dtype=np.uint8)
                cv2.circle(mask, (cx, cy), max(r - 3, 1), 255, -1)

                for color_name, ranges in self.color_ranges.items():
                    if color_name == 'red2':
                        continue  # red2 与 red 合并处理
                    lower, upper = ranges

                    if color_name == 'red':
                        # red 需要合并两个 HSV 范围
                        mask_r1 = cv2.inRange(hsv_roi, self.color_ranges['red'][0],
                                              self.color_ranges['red'][1])
                        mask_r2 = cv2.inRange(hsv_roi, self.color_ranges['red2'][0],
                                              self.color_ranges['red2'][1])
                        color_mask = cv2.bitwise_or(mask_r1, mask_r2)
                    else:
                        color_mask = cv2.inRange(hsv_roi, lower, upper)

                    # 圆内像素中该颜色占比
                    overlap = cv2.bitwise_and(mask, color_mask)
                    ratio = np.sum(overlap > 0) / (np.sum(mask > 0) + 1)

                    if ratio > 0.3:  # 超过 30% 认为匹配
                        clean_name = 'red' if color_name == 'red' else color_name
                        # 保留最大的匹配圆
                        if best is None or r > best[2]:
                            best = (cx, cy, r, clean_name)
                            detected_state = clean_name

        # 绘制结果
        result = frame.copy()
        if best:
            cx, cy, r, color = best
            colors = {'red': (0, 0, 255), 'yellow': (0, 255, 255), 'green': (0, 255, 0)}
            cv2.circle(result, (cx, cy), r, colors.get(color, (255, 255, 255)), 2)
            cv2.circle(result, (cx, cy), 2, colors.get(color, (255, 255, 255)), 3)

            text = f"{color.upper()} LIGHT"
            cv2.putText(result, text, (10, h - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, colors.get(color, (255, 255, 255)), 2)

        return result, detected_state


def main():
    import sys

    detector = TrafficLightDetector()
    source = sys.argv[1] if len(sys.argv) > 1 else "0"

    print("=" * 50)
    print("  Traffic Light Detector - 红绿灯识别")
    print(f"  Source: {source}")
    print("  Press 'q' to quit | 's' to save screenshot")
    print("=" * 50)

    if source.isdigit():
        cap = cv2.VideoCapture(int(source))
    else:
        cap = cv2.VideoCapture(source)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        result, state = detector.detect(frame)
        cv2.imshow("Traffic Light Detection", result)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            cv2.imwrite("screenshot.jpg", result)
            print("Screenshot saved: screenshot.jpg")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
