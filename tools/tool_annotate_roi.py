# -*- coding: utf-8 -*-
"""
Interactive ROI Annotation Tool v3
===================================
Drag to draw boxes on game screenshot.
Outputs both full-screen % and CARD_CROP % coordinates.
NEW: Press O to OCR the last drawn box region.

Controls:
  Drag     = draw box
  O        = OCR the last box (opens preview window)
  R        = reset all boxes
  S        = re-screenshot (refresh from game)
  Q / ESC  = quit
"""

import os
import sys
import time

# Fix encoding before any output
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np
import pytesseract

from engine import ocr as module_ocr
from engine.utils import find_game_window
from macro.core import capture_screenshot, force_foreground

# Global state
drawing: bool = False
start_x: int = 0
start_y: int = 0
current_rect: tuple[int, int, int, int] | None = None
all_rects: list[tuple[int, int, int, int]] = []
base_image: np.ndarray | None = None
img_w: int = 1600
img_h: int = 900
cursor_cx: int = 0
cursor_cy: int = 0
has_cursor: bool = False
CROP_W: int = module_ocr.CARD_CROP_W
CROP_H: int = module_ocr.CARD_CROP_H

WINDOW_NAME = "ROI Annotation Tool v3"


def mouse_callback(event: int, x: int, y: int, flags: int, param: object) -> None:
    """Handle mouse events for drawing rectangles."""
    global drawing, start_x, start_y, current_rect

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        start_x, start_y = x, y
        current_rect = None
    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        current_rect = (start_x, start_y, x, y)
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        if abs(x - start_x) > 5 and abs(y - start_y) > 5:
            rx1 = min(start_x, x)
            ry1 = min(start_y, y)
            rx2 = max(start_x, x)
            ry2 = max(start_y, y)
            rect = (rx1, ry1, rx2, ry2)
            all_rects.append(rect)
            print_rect_info(rect, len(all_rects))
        current_rect = None


def print_rect_info(rect: tuple[int, int, int, int], idx: int) -> None:
    """Print coordinate info for a drawn rectangle."""
    rx1, ry1, rx2, ry2 = rect
    rw = rx2 - rx1
    rh = ry2 - ry1

    # === Full-screen percentage (relative to 1600x900) ===
    fs_x1 = rx1 / img_w
    fs_y1 = ry1 / img_h
    fs_x2 = rx2 / img_w
    fs_y2 = ry2 / img_h

    print(f"\n{'=' * 60}")
    print(f"  [BOX #{idx}]  Pixels: ({rx1},{ry1}) -> ({rx2},{ry2})  [{rw}x{rh}]")
    print(f"{'=' * 60}")

    # Full-screen %
    print("\n  --- FULL SCREEN % (for raw_img / resized) ---")
    print(f"  Height: {fs_y1:.4f} -> {fs_y2:.4f}   (h*{fs_y1:.4f} : h*{fs_y2:.4f})")
    print(f"  Width:  {fs_x1:.4f} -> {fs_x2:.4f}   (w*{fs_x1:.4f} : w*{fs_x2:.4f})")
    print(f"  Code:  roi = image[int(h*{fs_y1:.4f}):int(h*{fs_y2:.4f}), int(w*{fs_x1:.4f}):int(w*{fs_x2:.4f})]")

    # CARD_CROP % (only if cursor was detected)
    if has_cursor:
        card_x1 = max(0, cursor_cx - CROP_W // 2)
        card_y1 = max(0, cursor_cy - CROP_H // 2)
        card_w = CROP_W
        card_h = CROP_H

        pct_x1 = (rx1 - card_x1) / card_w
        pct_y1 = (ry1 - card_y1) / card_h
        pct_x2 = (rx2 - card_x1) / card_w
        pct_y2 = (ry2 - card_y1) / card_h

        print(f"\n  --- CARD_CROP % (cursor={cursor_cx},{cursor_cy}) ---")
        print(f"  Height: {pct_y1:.4f} -> {pct_y2:.4f}   (card_h*{pct_y1:.4f} : card_h*{pct_y2:.4f})")
        print(f"  Width:  {pct_x1:.4f} -> {pct_x2:.4f}   (card_w*{pct_x1:.4f} : card_w*{pct_x2:.4f})")
        print(
            f"  Code:  roi = card[int(card_h*{pct_y1:.4f}):int(card_h*{pct_y2:.4f}), "
            f"int(card_w*{pct_x1:.4f}):int(card_w*{pct_x2:.4f})]"
        )

    print(f"{'=' * 60}")


def ocr_last_rect() -> None:
    """Run OCR on the last drawn rectangle and show preview."""
    if base_image is None or not all_rects:
        print("  [WARN] No box drawn yet. Drag to draw a box first.")
        return

    rx1, ry1, rx2, ry2 = all_rects[-1]
    roi = base_image[ry1:ry2, rx1:rx2]

    if roi.size == 0:
        print("  [WARN] Empty ROI")
        return

    # --- Method 1: _ocr_card_text pipeline (inv binary) ---
    text_inv = module_ocr._ocr_card_text(roi, debug_label="BOX_INV")

    # --- Method 2: Direct grayscale Otsu (for light text on dark bg) ---
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    padded = cv2.copyMakeBorder(otsu, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    upscaled = cv2.resize(padded, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    try:
        text_otsu = pytesseract.image_to_string(upscaled).strip().lower()
    except Exception:
        text_otsu = ""

    # --- Method 3: Inverted Otsu (black text detection) ---
    _, otsu_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    padded_inv = cv2.copyMakeBorder(otsu_inv, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    upscaled_inv = cv2.resize(padded_inv, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    try:
        text_otsu_inv = pytesseract.image_to_string(upscaled_inv).strip().lower()
    except Exception:
        text_otsu_inv = ""

    # --- Method 4 & 5: Skill Point (PSM 7 + whitelist) ---
    text_sp_otsu = ""
    text_sp_fixed = ""
    try:
        custom_config = r"--psm 7 -c tessedit_char_whitelist=0123456789/"
        ch, cw = gray.shape
        scan_limit = max(1, int(cw * 0.15))

        def _process_sp(thresh_img):
            border = (
                thresh_img[0, :].mean() + thresh_img[-1, :].mean() + thresh_img[:, 0].mean() + thresh_img[:, -1].mean()
            ) / 4
            polarity = cv2.bitwise_not(thresh_img) if border < 128 else thresh_img
            cleaned = polarity.copy()
            for col in range(scan_limit):
                if np.sum(cleaned[:, col] == 0) / ch > 0.70:
                    cleaned[:, col] = 255
            padded = cv2.copyMakeBorder(cleaned, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
            return cv2.resize(padded, None, fx=4, fy=4, interpolation=cv2.INTER_LINEAR)

        # 4.1 Otsu
        up_otsu = _process_sp(otsu)
        text_sp_otsu = pytesseract.image_to_string(up_otsu, config=custom_config).strip()

        # 4.2 Fixed 120 (cyan background)
        _, thresh_fixed = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)
        up_fixed = _process_sp(thresh_fixed)
        text_sp_fixed = pytesseract.image_to_string(up_fixed, config=custom_config).strip()

    except Exception as e:
        text_sp_otsu = f"ERROR: {e}"
        text_sp_fixed = f"ERROR: {e}"

    rw, rh = rx2 - rx1, ry2 - ry1
    print(f"\n{'=' * 60}")
    print(f"  [OCR PREVIEW] Box #{len(all_rects)} ({rw}x{rh})")
    print(f"{'=' * 60}")
    print(f'  Method 1 (inv binary 127): "{text_inv}"')
    print(f'  Method 2 (Otsu direct):    "{text_otsu}"')
    print(f'  Method 3 (Otsu inverted):  "{text_otsu_inv}"')
    print(f'  Method 4 (SP - Otsu):      "{text_sp_otsu}"')
    print(f'  Method 5 (SP - Fixed 120): "{text_sp_fixed}"')

    # match_impreza_22b on best text
    for label, txt in [("inv_binary", text_inv), ("otsu", text_otsu), ("otsu_inv", text_otsu_inv)]:
        is_match, matched = module_ocr.match_impreza_22b(txt)
        status = "MATCH" if is_match else "miss"
        print(f"  22B [{label}]: {status} kw={matched}")

    print(f"{'=' * 60}")

    # Show preview window with 4x zoom
    zoom = cv2.resize(roi, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST)
    cv2.imshow("OCR Preview (4x)", zoom)

    # Also show the processed images
    thresh_vis = cv2.resize(otsu, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
    thresh_inv_vis = cv2.resize(otsu_inv, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)

    # Stack horizontally if same height
    if thresh_vis.shape[0] == thresh_inv_vis.shape[0]:
        combined = np.hstack([thresh_vis, thresh_inv_vis])
        cv2.imshow("Threshold: Otsu | Otsu_Inv", combined)
    else:
        cv2.imshow("Threshold Otsu", thresh_vis)
        cv2.imshow("Threshold Otsu Inv", thresh_inv_vis)


def take_screenshot(hwnd: int) -> np.ndarray | None:
    """Capture fresh screenshot from game."""
    global base_image, cursor_cx, cursor_cy, has_cursor, img_w, img_h

    resized, _, _, _, _ = capture_screenshot(hwnd)
    if resized is None:
        print("  [ERROR] Screenshot failed!")
        return None

    img_h, img_w = resized.shape[:2]
    print(f"  Image: {img_w}x{img_h}")

    cursor_pos = module_ocr.find_cursor_position(resized)
    if cursor_pos:
        cursor_cx, cursor_cy = cursor_pos
        has_cursor = True
        print(f"  Cursor: ({cursor_cx}, {cursor_cy})")
    else:
        has_cursor = False
        print("  [INFO] No cursor detected (CARD_CROP % disabled)")

    base_image = resized.copy()
    return resized


def main() -> None:
    """Main entry point for the ROI annotation tool."""
    global all_rects, current_rect

    print(f"\n{'=' * 50}")
    print("   ROI Annotation Tool v3")
    print("   Drag=draw  O=OCR  R=reset  S=refresh  Q=quit")
    print(f"{'=' * 50}\n")

    hwnd = find_game_window()
    if not hwnd:
        print("[ERROR] Game window not found!")
        sys.exit(1)
    force_foreground(hwnd)

    print("  Capturing in 3 seconds...")
    time.sleep(3)

    if take_screenshot(hwnd) is None:
        sys.exit(1)

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, 1600, 900)
    cv2.setMouseCallback(WINDOW_NAME, mouse_callback)

    colors = [
        (0, 255, 255),
        (255, 0, 255),
        (0, 165, 255),
        (255, 255, 0),
        (0, 255, 0),
        (0, 0, 255),
    ]

    while True:
        vis = base_image.copy()

        # Draw CARD_CROP boundary if cursor detected
        if has_cursor:
            cx1 = max(0, cursor_cx - CROP_W // 2)
            cy1 = max(0, cursor_cy - CROP_H // 2)
            cx2 = min(img_w, cursor_cx + CROP_W // 2)
            cy2 = min(img_h, cursor_cy + CROP_H // 2)
            # Dashed border
            for i in range(cx1, cx2, 10):
                cv2.line(vis, (i, cy1), (min(i + 5, cx2), cy1), (128, 128, 128), 1)
                cv2.line(vis, (i, cy2), (min(i + 5, cx2), cy2), (128, 128, 128), 1)
            for i in range(cy1, cy2, 10):
                cv2.line(vis, (cx1, i), (cx1, min(i + 5, cy2)), (128, 128, 128), 1)
                cv2.line(vis, (cx2, i), (cx2, min(i + 5, cy2)), (128, 128, 128), 1)
            # Cross marker at cursor center
            cv2.drawMarker(vis, (cursor_cx, cursor_cy), (0, 255, 0), cv2.MARKER_CROSS, 20, 1)

        # Draw saved rects
        for i, (rx1, ry1, rx2, ry2) in enumerate(all_rects):
            color = colors[i % len(colors)]
            cv2.rectangle(vis, (rx1, ry1), (rx2, ry2), color, 2)
            cv2.putText(
                vis,
                f"#{i + 1}",
                (rx1 + 3, ry1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
            )

        # Draw current drag rectangle
        if current_rect:
            sx, sy, ex, ey = current_rect
            cv2.rectangle(vis, (sx, sy), (ex, ey), (0, 255, 0), 1)
            dw, dh = abs(ex - sx), abs(ey - sy)
            cv2.putText(
                vis,
                f"{dw}x{dh}",
                (min(sx, ex) + 5, min(sy, ey) - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 255, 0),
                1,
            )

        # HUD
        cv2.putText(
            vis,
            "Drag=draw | O=OCR | R=reset | S=refresh | Q=quit",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
        )
        if has_cursor:
            cv2.putText(
                vis,
                f"Cursor: ({cursor_cx},{cursor_cy})  Card: {CROP_W}x{CROP_H}",
                (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 0),
                1,
            )

        cv2.imshow(WINDOW_NAME, vis)
        key = cv2.waitKey(30) & 0xFF

        if key == ord("q") or key == 27:
            break
        elif key == ord("r"):
            all_rects.clear()
            for win in ["OCR Preview (4x)", "Threshold: Otsu | Otsu_Inv", "Threshold Otsu", "Threshold Otsu Inv"]:
                try:
                    cv2.destroyWindow(win)
                except cv2.error:
                    pass
            print("\n  [RESET] All boxes cleared")
        elif key == ord("o"):
            ocr_last_rect()
        elif key == ord("s"):
            print("\n  [REFRESH] Re-capturing in 3 seconds...")
            force_foreground(hwnd)
            time.sleep(3)
            all_rects.clear()
            take_screenshot(hwnd)
            print("  Screenshot refreshed!")

    cv2.destroyAllWindows()
    print("\nDone!")


if __name__ == "__main__":
    main()
