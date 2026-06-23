# -*- coding: utf-8 -*-
"""
tools/capture_ocr_debug.py — 直接截取游戏画面并保存全屏图

用法（游戏窗口化/无边框）：
    python tools/capture_ocr_debug.py

输出目录：debug/（文件名带时间戳，多次运行不覆盖）
"""

import datetime
import os
import sys
import time

import cv2
import numpy as np

# 允许从项目根直接运行（python tools/capture_ocr_debug.py）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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

    hwnd = find_game_window()
    if not hwnd:
        print("[ERR] 未找到游戏窗口（确认 FH6 已运行、英文标题、窗口化/无边框）")
        return 1

    print("\n[INFO] 倒计时 2 秒后截图，请迅速切回游戏...")
    time.sleep(2)

    img = grab_client(hwnd)
    if img is None:
        return 1
    h, w = img.shape[:2]
    ts = datetime.datetime.now().strftime("%H%M%S")

    # 1) 全屏图（关键：用来核对两处 ROI 在你这台分辨率下是否对齐 / 数字是否在框内）
    save(f"capture_full_{ts}.png", img)
    print(f"[INFO] 客户区分辨率: {w}x{h}")

    print(f"\n完成。全屏截图已保存至 {DEBUG_DIR}/ 目录下。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
