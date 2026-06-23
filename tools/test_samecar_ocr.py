# -*- coding: utf-8 -*-
"""
tools/test_samecar_ocr.py — 离线验证 _read_duplicate_car_info 的 OCR 逻辑
===================================================================
直接加载 debug/samecar*.png 图片，跳过 capture_raw_screenshot，
把 _read_duplicate_car_info 的核心 ROI + OCR 流程独立跑一遍。
"""

import os
import re
import sys

import cv2
import pytesseract

# 期望结果，用于比对
EXPECTED: dict[str, tuple[str, int]] = {
    "samecar.png": ("SUBARU BRZ", 12_500),
    "samecar2.png": ("PORSCHE 917 FE", 625_000),
    "samecar3.png": ("CORVETTE '19", 125_000),
    "samecar4.png": ("911 TURBO S '23", 137_500),
    "samecar5.png": ("CROWN VICTORIA", 7_500),
}


def read_duplicate_car_info_from_image(
    raw,
) -> tuple[str | None, int | None]:
    """复刻 wheelspin._read_duplicate_car_info 的核心逻辑（不依赖 hwnd）。"""
    h, w = raw.shape[:2]

    # ── 车名 ROI ──
    car_name: str | None = None
    name_roi = raw[int(h * 0.60) : int(h * 0.66), int(w * 0.36) : int(w * 0.66)]
    if name_roi.size:
        gray = cv2.cvtColor(name_roi, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY)
        txt = pytesseract.image_to_string(thresh, config="--psm 7").strip()
        if txt:
            car_name = txt.upper()

    # ── 售价 ROI ──
    sell_price: int | None = None
    price_roi = raw[int(h * 0.78) : int(h * 0.84), int(w * 0.36) : int(w * 0.66)]
    if price_roi.size:
        gray = cv2.cvtColor(price_roi, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY)
        txt = pytesseract.image_to_string(thresh, config="--psm 7").strip()
        matches = re.findall(r"[\d,]+", txt)
        if matches:
            digits = max(matches, key=len).replace(",", "")
            try:
                v = int(digits)
                if 0 <= v <= 20_000_000:
                    sell_price = v
            except ValueError:
                pass

    return car_name, sell_price


def main() -> None:
    debug_dir = os.path.join(os.path.dirname(__file__), "..", "debug")
    files = sorted(f for f in os.listdir(debug_dir) if re.match(r"^samecar\d*\.png$", f))
    if not files:
        print("[ERROR] No samecar*.png found in debug/")
        sys.exit(1)

    total = 0
    passed = 0
    for fname in files:
        total += 1
        path = os.path.join(debug_dir, fname)
        raw = cv2.imread(path)
        if raw is None:
            print(f"[ERROR] Cannot read {fname}")
            continue
        print(f"\n{'=' * 60}")
        print(f"[TEST] {fname}  ({raw.shape[1]}x{raw.shape[0]})")

        car_name, sell_price = read_duplicate_car_info_from_image(raw)
        print(f"  OCR car_name  = {car_name!r}")
        print(f"  OCR sell_price = {sell_price!r}")

        # ── 保存 ROI debug 图片 ──
        h, w = raw.shape[:2]
        name_roi = raw[int(h * 0.60) : int(h * 0.66), int(w * 0.36) : int(w * 0.66)]
        price_roi = raw[int(h * 0.78) : int(h * 0.84), int(w * 0.36) : int(w * 0.66)]
        base = fname.replace(".png", "")
        cv2.imwrite(os.path.join(debug_dir, f"{base}_name_roi.png"), name_roi)
        cv2.imwrite(os.path.join(debug_dir, f"{base}_price_roi.png"), price_roi)
        # 也保存阈值化后的版本
        gray_name = cv2.cvtColor(name_roi, cv2.COLOR_BGR2GRAY)
        _, thresh_name = cv2.threshold(gray_name, 140, 255, cv2.THRESH_BINARY)
        cv2.imwrite(os.path.join(debug_dir, f"{base}_name_thresh.png"), thresh_name)
        gray_price = cv2.cvtColor(price_roi, cv2.COLOR_BGR2GRAY)
        _, thresh_price = cv2.threshold(gray_price, 140, 255, cv2.THRESH_BINARY)
        cv2.imwrite(os.path.join(debug_dir, f"{base}_price_thresh.png"), thresh_price)

        # ── 与期望比对 ──
        if fname in EXPECTED:
            exp_name, exp_price = EXPECTED[fname]

            # 车名仅用于日志，Tesseract 可能丢失/改变引号和空格
            # 归一化后比较：去除引号和多余空格
            def _normalize(s: str) -> str:
                return re.sub(r"[\s'\"']+", "", s).upper()

            name_ok = car_name is not None and _normalize(exp_name) == _normalize(car_name)
            price_ok = sell_price == exp_price
            if not name_ok:
                print(f"  [WARN] car_name expected '{exp_name}', got '{car_name}' (cosmetic)")
            if not price_ok:
                print(f"  [FAIL] sell_price expected {exp_price}, got {sell_price}")
            if price_ok:
                print(f"  [{'PASS' if name_ok else 'PASS (price OK, name cosmetic)'}]")
                passed += 1
        else:
            print(f"  [INFO] No expected value defined for {fname}")

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} passed")
    if passed < total:
        print("[WARN] Some tests FAILED — ROI or OCR parameters need adjustment.")
        sys.exit(1)
    else:
        print("[OK] All tests passed.")


if __name__ == "__main__":
    main()
