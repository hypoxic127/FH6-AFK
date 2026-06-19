# -*- coding: utf-8 -*-
"""快速截图并标注 _wait_for_cars_text 的 ROI 区域"""

import sys, os, time, cv2

sys.path.insert(0, os.path.dirname(__file__))
from macro.core import capture_screenshot, capture_raw_screenshot
from utils import find_game_window, force_foreground

hwnd = find_game_window()
if not hwnd:
    print("未找到游戏窗口！")
    sys.exit(1)
force_foreground(hwnd)
print("3 秒后截图...")
time.sleep(3)

raw = capture_raw_screenshot(hwnd)
if raw is None:
    print("截图失败！")
    sys.exit(1)

h, w = raw.shape[:2]
print(f"分辨率: {w}x{h}")

# 当前 ROI: "Cars" 大标题 (9-13% 高度, 6-14% 宽度)
y1, y2 = int(h * 0.09), int(h * 0.13)
x1, x2 = int(w * 0.06), int(w * 0.14)

annotated = raw.copy()
# 绿框 = 当前 ROI
cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 3)
cv2.putText(annotated, f"Cars ROI (9-13%, 6-14%)", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

# 裁剪出 ROI
roi = raw[y1:y2, x1:x2]

cv2.imwrite("debug_cars_roi_annotated.png", annotated)
cv2.imwrite("debug_cars_roi_crop.png", roi)
print(f"ROI 像素坐标: ({x1},{y1})-({x2},{y2}), 尺寸: {x2 - x1}x{y2 - y1}")
print(f"已保存: debug_cars_roi_annotated.png + debug_cars_roi_crop.png")
