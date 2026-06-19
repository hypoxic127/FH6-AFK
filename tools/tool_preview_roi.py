# -*- coding: utf-8 -*-
"""
Non-interactive ROI Annotation & OCR Preprocessing Preview Tool.
Loads a screenshot, draws the skill points crop zone, processes it, and saves debug images.
"""

import argparse
import sys
import os
import cv2
import numpy as np

# Ensure root directory is in path so we can import engine modules
ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)


def main() -> None:
    """Parses command-line args, crops the image, applies OCR preprocessing, and saves outputs."""
    parser = argparse.ArgumentParser(description="Test and annotate skill points ROI.")
    parser.add_argument("image_path", help="Path to the screenshot to analyze")
    args = parser.parse_args()

    img: np.ndarray | None = cv2.imread(args.image_path)
    if img is None:
        print(f"Error: Could not read image {args.image_path}")
        sys.exit(1)

    h: int
    w: int
    h, w, _ = img.shape
    print(f"Loaded image: {args.image_path} with shape {w}x{h}")

    # ROI logic from engine/ocr.py
    crop_y1: int = int(h * 0.7244)
    crop_y2: int = int(h * 0.7611)
    crop_x1: int = int(w * 0.28)
    crop_x2: int = int(w * 0.307)

    print(f"ROI Coordinates: Y={crop_y1}:{crop_y2}, X={crop_x1}:{crop_x2}")

    # Extract ROI
    roi: np.ndarray = img[crop_y1:crop_y2, crop_x1:crop_x2]

    if roi.size == 0:
        print("Error: ROI is empty!")
        sys.exit(1)

    # Draw rectangle on original image (a copy to avoid modifying original)
    annotated: np.ndarray = img.copy()
    cv2.rectangle(annotated, (crop_x1, crop_y1), (crop_x2, crop_y2), (0, 0, 255), 2)

    # Save the results in root directory
    out_annotated_path: str = os.path.join(ROOT_DIR, "debug_annotated_full.png")
    out_crop_path: str = os.path.join(ROOT_DIR, "debug_roi_cropped.png")
    cv2.imwrite(out_annotated_path, annotated)
    cv2.imwrite(out_crop_path, roi)

    print(f"Saved '{out_annotated_path}' and '{out_crop_path}'.")
    print("Please check the debug_roi_cropped.png to see if the skill points are perfectly within the boundaries.")

    # Apply OCR preprocessing to preview
    gray: np.ndarray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh_fixed = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)
    border: float = (
        thresh_fixed[0, :].mean() + thresh_fixed[-1, :].mean() + thresh_fixed[:, 0].mean() + thresh_fixed[:, -1].mean()
    ) / 4
    if border < 128:
        thresh_fixed = cv2.bitwise_not(thresh_fixed)

    cleaned: np.ndarray = thresh_fixed.copy()
    roi_h: int
    roi_w: int
    roi_h, roi_w = cleaned.shape
    scan_limit: int = max(1, int(roi_w * 0.15))
    for col in range(scan_limit):
        black_ratio: float = np.sum(cleaned[:, col] == 0) / roi_h
        if black_ratio > 0.70:
            cleaned[:, col] = 255

    padded: np.ndarray = cv2.copyMakeBorder(cleaned, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=[255, 255, 255])
    upscaled: np.ndarray = cv2.resize(padded, None, fx=4, fy=4, interpolation=cv2.INTER_LINEAR)

    out_preprocessed_path: str = os.path.join(ROOT_DIR, "debug_roi_preprocessed.png")
    cv2.imwrite(out_preprocessed_path, upscaled)
    print(f"Saved '{out_preprocessed_path}' to preview the OCR input.")


if __name__ == "__main__":
    main()
