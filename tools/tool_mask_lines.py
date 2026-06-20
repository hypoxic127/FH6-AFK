# -*- coding: utf-8 -*-
"""
Mask Line Annotation Tool
==========================
Click to place vertical/horizontal mask boundary lines on a game screenshot.

Controls:
  Left Click   = Place a vertical line (X boundary)
  Right Click  = Place a horizontal line (Y boundary)
  R            = Reset all lines
  Q / ESC      = Quit and print final values
"""

import os
import sys
import time

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import cv2
import module_macro
import numpy as np

# Global state
base_image = None
img_w, img_h = 1600, 900
v_lines = []  # vertical lines (X values)
h_lines = []  # horizontal lines (Y values)


def mouse_callback(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        v_lines.append(x)
        pct = x / img_w
        print(
            f"  [V-LINE] X = {x}px  ({pct:.4f} = {pct:.2f})  →  mask[:, :{x}] = 0  or  mask[:, :int(w*{pct:.2f})] = 0"
        )
    elif event == cv2.EVENT_RBUTTONDOWN:
        h_lines.append(y)
        pct = y / img_h
        print(
            f"  [H-LINE] Y = {y}px  ({pct:.4f} = {pct:.2f})  →  mask[:{y}, :] = 0  or  mask[:int(h*{pct:.2f}), :] = 0"
        )


def main():
    global base_image, img_w, img_h

    print("\n==================================================")
    print("   Mask Line Annotation Tool")
    print("   Left Click  = vertical line (X mask)")
    print("   Right Click = horizontal line (Y mask)")
    print("   R = reset  |  Q/ESC = quit")
    print("==================================================\n")

    hwnd = module_macro.find_game_window()
    if not hwnd:
        print("[ERROR] Game window not found!")
        sys.exit(1)
    module_macro.force_foreground(hwnd)

    print("  3 seconds...")
    time.sleep(3)

    resized, _, _, _, _ = module_macro.capture_screenshot(hwnd)
    if resized is None:
        print("[ERROR] Screenshot failed!")
        sys.exit(1)

    img_h, img_w = resized.shape[:2]
    base_image = resized.copy()
    print(f"  Image: {img_w}x{img_h}\n")

    cv2.namedWindow("Mask Line Tool", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Mask Line Tool", 1600, 900)
    cv2.setMouseCallback("Mask Line Tool", mouse_callback)

    while True:
        vis = base_image.copy()

        # Draw vertical lines (red)
        for vx in v_lines:
            cv2.line(vis, (vx, 0), (vx, img_h), (0, 0, 255), 2)
            # Shade left side
            overlay = vis.copy()
            cv2.rectangle(overlay, (0, 0), (vx, img_h), (0, 0, 100), -1)
            vis = cv2.addWeighted(overlay, 0.3, vis, 0.7, 0)
            pct = vx / img_w
            cv2.putText(vis, f"X={vx} ({pct:.2f})", (vx + 5, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # Draw horizontal lines (blue)
        for hy in h_lines:
            cv2.line(vis, (0, hy), (img_w, hy), (255, 100, 0), 2)
            # Shade top side
            overlay = vis.copy()
            cv2.rectangle(overlay, (0, 0), (img_w, hy), (100, 0, 0), -1)
            vis = cv2.addWeighted(overlay, 0.3, vis, 0.7, 0)
            pct = hy / img_h
            cv2.putText(
                vis, f"Y={hy} ({pct:.2f})", (img_w - 200, hy + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 100, 0), 2
            )

        # HUD
        cv2.putText(
            vis,
            "LClick=V-line | RClick=H-line | R=reset | Q=quit",
            (10, img_h - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
        )

        cv2.imshow("Mask Line Tool", vis)
        key = cv2.waitKey(30) & 0xFF

        if key == ord("q") or key == 27:
            break
        elif key == ord("r"):
            v_lines.clear()
            h_lines.clear()
            print("\n  [RESET] All lines cleared\n")

    cv2.destroyAllWindows()

    # Print summary
    print(f"\n{'=' * 60}")
    print("  SUMMARY — Copy to module_ocr.py find_cursor_position()")
    print(f"{'=' * 60}")
    if v_lines:
        vx = v_lines[-1]
        pct = vx / img_w
        print("\n  # Left panel mask (last V-line)")
        print(f"  mask[:, :int(img_w * {pct:.2f})] = 0    # X={vx}px")
    if h_lines:
        hy = h_lines[-1]
        pct = hy / img_h
        print("\n  # Top bar mask (last H-line)")
        print(f"  mask[:int(img_h * {pct:.2f}), :] = 0    # Y={hy}px")
    if not v_lines and not h_lines:
        print("\n  No lines placed.")
    print(f"\n{'=' * 60}")
    print("Done!")


if __name__ == "__main__":
    main()
