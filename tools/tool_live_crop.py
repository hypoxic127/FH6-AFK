# -*- coding: utf-8 -*-
"""
FH6_AutoBot live OCR crop verification script.
Captures the live game window, crops the skill points ROI, and saves preview.
"""

import os
import shutil
import sys

import cv2
import numpy as np

# Ensure root directory is in path so we can import engine modules
ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from engine.utils import find_game_window, get_client_rect, get_mss  # noqa: E402


def capture_live() -> None:
    """Captures live game window, applies skill points crop coordinates, and saves outputs."""
    hwnd = find_game_window()
    if not hwnd:
        print("Error: Cannot find Forza Horizon 6 window.")
        sys.exit(1)

    left: int
    top: int
    w: int
    h: int
    left, top, w, h = get_client_rect(hwnd)
    if w <= 0 or h <= 0:
        print("Error: Invalid game window size.")
        sys.exit(1)

    print(f"Window found: left={left}, top={top}, width={w}, height={h}")

    monitor = {"top": top, "left": left, "width": w, "height": h}
    sct = get_mss()
    screenshot: np.ndarray = np.array(sct.grab(monitor))

    # mss grabs in BGRA format
    img: np.ndarray = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)

    crop_y1: int = int(h * 0.7244)
    crop_y2: int = int(h * 0.7611)
    crop_x1: int = int(w * 0.28)
    crop_x2: int = int(w * 0.307)

    roi: np.ndarray = img[crop_y1:crop_y2, crop_x1:crop_x2]
    out_crop_path: str = os.path.join(ROOT_DIR, "live_roi_cropped.png")
    cv2.imwrite(out_crop_path, roi)

    full_drawn: np.ndarray = img.copy()
    cv2.rectangle(full_drawn, (crop_x1, crop_y1), (crop_x2, crop_y2), (0, 0, 255), 2)
    out_full_path: str = os.path.join(ROOT_DIR, "live_roi_full.png")
    cv2.imwrite(out_full_path, full_drawn)

    print(f"Saved {out_crop_path} and {out_full_path}")

    # Copy to artifacts for UI preview
    artifact_dir: str = r"C:\Users\12449\.gemini\antigravity-ide\brain\64e14276-33a0-44f5-a128-6b39d4a92517"
    if os.path.exists(artifact_dir):
        try:
            shutil.copy(out_crop_path, os.path.join(artifact_dir, "live_roi_cropped.png"))
            shutil.copy(out_full_path, os.path.join(artifact_dir, "live_roi_full.png"))
            print("Copied live preview images to artifact directory.")
        except OSError as e:
            print(f"Warning: Failed to copy to artifacts: {e}")


if __name__ == "__main__":
    capture_live()
