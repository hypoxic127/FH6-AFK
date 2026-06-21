# -*- coding: utf-8 -*-
"""
tools/capture_ocr_debug.py — 直接截取游戏画面并保存 OCR 调试图（不依赖 bot 流程）

游戏运行中，切到要排查的界面后直接运行本脚本，即可立刻抓图，无需让 bot 跑到对应阶段。
专为排查「技能点(CARS) / Available Points(加点技能树)」识别准备：保存全屏图 + 两处 ROI 裁剪
+ 关键二值化中间图，并打印当前 OCR 识别结果，便于核对 ROI 是否对齐、是否裁断。

用法（游戏窗口化/无边框，英文 UI）：
    python tools/capture_ocr_debug.py            # 抓当前画面：全屏 + 两处 ROI
    - 排查 Available Points：切到「加点技能树」界面再运行，看 capture_ap_*.png
    - 排查 CARS 技能点：切到暂停菜单 CARS 标签页再运行，看 capture_skillpoints_roi_*.png

输出目录：debug/（文件名带时间戳，多次运行不覆盖）
"""

import datetime
import os
import sys

import cv2
import numpy as np

# 允许从项目根直接运行（python tools/capture_ocr_debug.py）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine.ocr as module_ocr  # noqa: E402
from engine.utils import find_game_window, get_client_rect, get_mss, reset_mss  # noqa: E402

DEBUG_DIR = "debug"


def grab_client(hwnd) -> np.ndarray | None:
    """抓取游戏窗口客户区的原始分辨率 BGR 图。"""
    cx, cy, cw, ch = get_client_rect(hwnd)
    if cw <= 0 or ch <= 0:
        print(f"[ERR] 客户区尺寸异常: {cw}x{ch}（窗口最小化或被遮挡？）")
        return None
    reset_mss()  # 确保新进程拿到干净的 GDI 句柄
    sct = get_mss()
    shot = sct.grab({"top": cy, "left": cx, "width": cw, "height": ch})
    return cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)


def save(name: str, img: np.ndarray) -> None:
    path = os.path.join(DEBUG_DIR, name)
    cv2.imwrite(path, img)
    print(f"[OK] {path}  ({img.shape[1]}x{img.shape[0]})")


def main() -> int:
    os.makedirs(DEBUG_DIR, exist_ok=True)
    module_ocr.setup_tesseract()  # 配置 Tesseract 路径，使下方 OCR 可用

    hwnd = find_game_window()
    if not hwnd:
        print("[ERR] 未找到游戏窗口（确认 FH6 已运行、英文标题、窗口化/无边框）")
        return 1

    img = grab_client(hwnd)
    if img is None:
        return 1
    h, w = img.shape[:2]
    ts = datetime.datetime.now().strftime("%H%M%S")

    # 1) 全屏图（关键：用来核对两处 ROI 在你这台分辨率下是否对齐 / 数字是否在框内）
    save(f"capture_full_{ts}.png", img)
    print(f"[INFO] 客户区分辨率: {w}x{h}")

    # 2) CARS 技能点 ROI（默认比例，右边界 0.313）
    sk = img[int(h * 0.7244) : int(h * 0.7611), int(w * 0.28) : int(w * 0.313)]
    if sk.size:
        save(f"capture_skillpoints_roi_{ts}.png", sk)
    print(f"[OCR] read_skill_points(整图) -> {module_ocr.read_skill_points(img)}")

    # 3) Available Points ROI（加点技能树界面，y 0.85-0.88 / x 0.35-0.385）
    ap = img[int(h * 0.85) : int(h * 0.88), int(w * 0.35) : int(w * 0.385)]
    if ap.size:
        save(f"capture_ap_roi_{ts}.png", ap)
        gray = cv2.cvtColor(ap, cv2.COLOR_BGR2GRAY)
        _, t150 = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        save(f"capture_ap_t150_{ts}.png", t150)
        hsv = cv2.cvtColor(ap, cv2.COLOR_BGR2HSV)
        yellow = cv2.inRange(hsv, np.array([15, 40, 100]), np.array([45, 255, 255]))
        save(f"capture_ap_yellow_{ts}.png", yellow)

        import pytesseract

        up = cv2.resize(cv2.bitwise_not(t150), None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        txt = pytesseract.image_to_string(up, config="--psm 7 -c tessedit_char_whitelist=0123456789").strip()
        print(f"[OCR] Available Points(t150/PSM7) -> '{txt}'")
    else:
        print("[WARN] Available Points ROI 为空（分辨率异常？）")

    print("\n完成。排查 Available Points 请把 debug/ 下的 capture_full_*.png 与 capture_ap_*.png 发我。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
