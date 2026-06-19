# -*- coding: utf-8 -*-
"""
FH6_AutoBot OCR crop verification script.
Loads sample screenshot and outputs cropped preview.
"""

import os
import sys
import shutil
import cv2
import numpy as np

# Ensure root directory is in path so we can import engine modules
ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)


def verify_crop() -> None:
    """Loads sample screenshot, applies skill points crop coordinates, and saves output."""
    img_path: str = os.path.join(ROOT_DIR, "tools", "sample_screenshot.png")
    img: np.ndarray | None = cv2.imread(img_path)
    if img is None:
        print(f"Error: Cannot read {img_path}")
        sys.exit(1)

    h: int
    w: int
    h, w, _ = img.shape

    # Coordinates matching engine/ocr.py
    crop_y1: int = int(h * 0.7244)
    crop_y2: int = int(h * 0.7611)
    crop_x1: int = int(w * 0.28)
    crop_x2: int = int(w * 0.307)

    roi: np.ndarray = img[crop_y1:crop_y2, crop_x1:crop_x2]
    out_crop_path: str = os.path.join(ROOT_DIR, "current_roi_cropped.png")
    cv2.imwrite(out_crop_path, roi)

    full_drawn: np.ndarray = img.copy()
    cv2.rectangle(full_drawn, (crop_x1, crop_y1), (crop_x2, crop_y2), (0, 0, 255), 2)
    out_full_path: str = os.path.join(ROOT_DIR, "current_roi_full.png")
    cv2.imwrite(out_full_path, full_drawn)

    print(f"Saved {out_crop_path} and {out_full_path}")

    # Copy to artifacts for UI preview
    artifact_dir: str = r"C:\Users\12449\.gemini\antigravity-ide\brain\64e14276-33a0-44f5-a128-6b39d4a92517"
    if os.path.exists(artifact_dir):
        try:
            shutil.copy(out_crop_path, os.path.join(artifact_dir, "current_roi_cropped.png"))
            shutil.copy(out_full_path, os.path.join(artifact_dir, "current_roi_full.png"))
            print("Copied preview images to artifact directory.")
        except OSError as e:
            print(f"Warning: Failed to copy to artifacts: {e}")


if __name__ == "__main__":
    verify_crop()
