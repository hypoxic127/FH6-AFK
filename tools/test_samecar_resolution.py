# -*- coding: utf-8 -*-
"""
tools/test_samecar_resolution.py — 模拟不同分辨率下 ROI 的偏差
=================================================================
将 debug/samecar*.png (1600x900) 先放大到 2560x1440 再跑 OCR，
模拟实际 capture_raw_screenshot 返回原始分辨率图像的场景。
"""

import os
import re
import sys

import cv2
import pytesseract

EXPECTED: dict[str, tuple[str, int]] = {
    "samecar.png": ("SUBARU BRZ", 12_500),
    "samecar2.png": ("PORSCHE 917 FE", 625_000),
    "samecar3.png": ("CORVETTE '19", 125_000),
    "samecar4.png": ("911 TURBO S '23", 137_500),
    "samecar5.png": ("CROWN VICTORIA", 7_500),
}

# 模拟常见游戏分辨率
RESOLUTIONS = [
    (1600, 900),  # 原始 debug 截图
    (1920, 1080),  # 1080p
    (2560, 1440),  # 1440p（用户实际分辨率）
    (3840, 2160),  # 4K
]


def read_duplicate_car_info_from_image(
    raw,
) -> tuple[str | None, int | None]:
    """复刻 wheelspin._read_duplicate_car_info 的核心逻辑。"""
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


def _normalize(s: str) -> str:
    return re.sub(r"[\s'\"']+", "", s).upper()


def main() -> None:
    debug_dir = os.path.join(os.path.dirname(__file__), "..", "debug")
    files = sorted(f for f in os.listdir(debug_dir) if re.match(r"^samecar\d*\.png$", f))
    if not files:
        print("[ERROR] No samecar*.png found in debug/")
        sys.exit(1)

    for res_w, res_h in RESOLUTIONS:
        print(f"\n{'#' * 70}")
        print(f"# Resolution: {res_w}x{res_h}")
        print(f"{'#' * 70}")
        total = 0
        passed = 0

        for fname in files:
            total += 1
            path = os.path.join(debug_dir, fname)
            raw = cv2.imread(path)
            if raw is None:
                print(f"  [ERROR] Cannot read {fname}")
                continue

            # 缩放到目标分辨率
            if (raw.shape[1], raw.shape[0]) != (res_w, res_h):
                raw = cv2.resize(raw, (res_w, res_h), interpolation=cv2.INTER_LINEAR)

            h, w = raw.shape[:2]
            car_name, sell_price = read_duplicate_car_info_from_image(raw)

            # 也显示 ROI 像素范围供排查
            name_y1, name_y2 = int(h * 0.60), int(h * 0.66)
            price_y1, price_y2 = int(h * 0.78), int(h * 0.84)
            name_x1, name_x2 = int(w * 0.36), int(w * 0.66)

            if fname in EXPECTED:
                exp_name, exp_price = EXPECTED[fname]
                name_ok = car_name is not None and _normalize(exp_name) == _normalize(car_name)
                price_ok = sell_price == exp_price
                status = "PASS" if price_ok else "FAIL"
                detail = ""
                if not name_ok:
                    detail += f" name='{car_name}'"
                if not price_ok:
                    detail += f" price={sell_price}(expect {exp_price})"
                print(
                    f"  [{status}] {fname:20s} car={car_name!r:25s} price={str(sell_price):>10s}"
                    f"  ROI name=[{name_y1}:{name_y2}, {name_x1}:{name_x2}]"
                    f"  price=[{price_y1}:{price_y2}]"
                    f"{detail}"
                )
                if price_ok:
                    passed += 1

        print(f"\n  Results: {passed}/{total} passed at {res_w}x{res_h}")


if __name__ == "__main__":
    main()
