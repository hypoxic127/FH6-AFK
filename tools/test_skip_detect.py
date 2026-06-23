# -*- coding: utf-8 -*-
"""
tools/test_skip_detect.py — 测试左下角 "Ⓐ Skip" 检测方案
============================================================
精确 ROI 校准后的测试。

Ⓐ Skip 在 1600x900 下的位置:
  - 绿色 Ⓐ 按钮: h92-94.5%, w4.3-5.7%
  - 白色 "Skip" 文字: h92-94.5%, w5.8-8%
  - 整体 ROI: h91-95%, w3-10%
"""

import os
import sys
import time

import cv2
import numpy as np
import pytesseract


def check_skip_visible_ocr(resized: np.ndarray) -> bool:
    """OCR 方案：读取左下角 ROI 检测 'skip' 关键字。"""
    h, w = resized.shape[:2]
    roi = resized[int(h * 0.91) : int(h * 0.96), int(w * 0.03) : int(w * 0.10)]
    if roi.size == 0:
        return False
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    text = pytesseract.image_to_string(thresh, config="--psm 7").strip().lower()
    return "skip" in text


def check_skip_visible_pixel(resized: np.ndarray) -> bool:
    """纯像素方案：绿色 Ⓐ 按钮 + 白色文字像素占比双重校验。

    Skip 区域很小（只有 4 个字母），用简短文字的像素特征区分：
    1) 绿色 Ⓐ 按钮存在（HSV 绿色像素）
    2) 白色文字区域像素占比在合理范围内
    3) 文字区域宽度有限（Skip 比 Select/Collect Prize 短很多）
    """
    h, w = resized.shape[:2]

    # 绿色 Ⓐ 按钮: h92-94.5%, w4-6%
    btn_roi = resized[int(h * 0.92) : int(h * 0.945), int(w * 0.04) : int(w * 0.06)]
    if btn_roi.size == 0:
        return False
    hsv = cv2.cvtColor(btn_roi, cv2.COLOR_BGR2HSV)
    green_mask = cv2.inRange(hsv, np.array([40, 50, 50]), np.array([80, 255, 255]))
    green_ratio = float(cv2.countNonZero(green_mask)) / green_mask.size
    if green_ratio < 0.10:
        return False

    # 白色文字: h92-94.5%, w5.8-8%（Skip 文字区域）
    text_roi = resized[int(h * 0.92) : int(h * 0.945), int(w * 0.058) : int(w * 0.08)]
    if text_roi.size == 0:
        return False
    gray = cv2.cvtColor(text_roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    white_ratio = float(np.sum(thresh == 255)) / thresh.size
    if white_ratio < 0.05:
        return False

    # 排除 "Select" / "Collect Prize" 等更长文字：
    # 检查 w8-12% 区域是否也有白色文字 → 如果有，说明文字更长，不是 Skip
    extra_roi = resized[int(h * 0.92) : int(h * 0.945), int(w * 0.08) : int(w * 0.12)]
    if extra_roi.size:
        extra_gray = cv2.cvtColor(extra_roi, cv2.COLOR_BGR2GRAY)
        _, extra_thresh = cv2.threshold(extra_gray, 200, 255, cv2.THRESH_BINARY)
        extra_white = float(np.sum(extra_thresh == 255)) / extra_thresh.size
        if extra_white > 0.05:
            return False  # 文字太长，是 Select/Collect Prize

    return True


def check_skip_visible_hybrid(resized: np.ndarray) -> bool:
    """混合方案：像素预检（<1ms）+ OCR 确认（~150ms）。"""
    if not check_skip_visible_pixel(resized):
        return False
    return check_skip_visible_ocr(resized)


def main() -> None:
    debug_dir = os.path.join(os.path.dirname(__file__), "..", "debug")
    test_files = [
        ("skip.png", True),
        ("Wheelspin.png", False),
        ("Wheelspinend.png", False),
        ("samecar.png", False),
        ("samecar2.png", False),
        ("samecar3.png", False),
        ("samecar4.png", False),
        ("samecar5.png", False),
        ("wheelspinpage.png", False),
    ]

    all_pass = True
    for fname, expected in test_files:
        path = os.path.join(debug_dir, fname)
        if not os.path.exists(path):
            print(f"[SKIP] {fname} not found")
            continue
        img = cv2.imread(path)
        if img is None:
            print(f"[ERR] Cannot read {fname}")
            continue
        if img.shape[:2] != (900, 1600):
            img = cv2.resize(img, (1600, 900))

        t0 = time.perf_counter()
        r_ocr = check_skip_visible_ocr(img)
        t_ocr = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        r_pixel = check_skip_visible_pixel(img)
        t_pixel = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        r_hybrid = check_skip_visible_hybrid(img)
        t_hybrid = (time.perf_counter() - t0) * 1000

        s_ocr = "PASS" if r_ocr == expected else "FAIL"
        s_pixel = "PASS" if r_pixel == expected else "FAIL"
        s_hybrid = "PASS" if r_hybrid == expected else "FAIL"

        if s_ocr != "PASS" or s_pixel != "PASS" or s_hybrid != "PASS":
            all_pass = False

        print(f"\n{fname:25s} (expect={expected})")
        print(f"  OCR:    {s_ocr:4s}  result={r_ocr!s:5s}  {t_ocr:6.1f}ms")
        print(f"  Pixel:  {s_pixel:4s}  result={r_pixel!s:5s}  {t_pixel:6.1f}ms")
        print(f"  Hybrid: {s_hybrid:4s}  result={r_hybrid!s:5s}  {t_hybrid:6.1f}ms")

    print(f"\n{'=' * 50}")
    if all_pass:
        print("[OK] All tests passed.")
    else:
        print("[WARN] Some tests FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
