import argparse
import sys

import cv2
import numpy as np


def main():
    parser = argparse.ArgumentParser(description="Test and annotate skill points ROI.")
    parser.add_argument("image_path", help="Path to the original 2560x1440 screenshot")
    args = parser.parse_args()

    img = cv2.imread(args.image_path)
    if img is None:
        print(f"Error: Could not read image {args.image_path}")
        sys.exit(1)

    h, w, _ = img.shape
    print(f"Loaded image: {args.image_path} with shape {w}x{h}")

    # ROI logic from engine/ocr.py
    crop_y1 = int(h * 0.7244)
    crop_y2 = int(h * 0.7611)
    crop_x1 = int(w * 0.2756)
    crop_x2 = int(w * 0.3044)

    print(f"ROI Coordinates: Y={crop_y1}:{crop_y2}, X={crop_x1}:{crop_x2}")

    # Extract ROI
    roi = img[crop_y1:crop_y2, crop_x1:crop_x2]

    if roi.size == 0:
        print("Error: ROI is empty!")
        sys.exit(1)

    # Draw rectangle on original image (a copy to avoid modifying original)
    annotated = img.copy()
    cv2.rectangle(annotated, (crop_x1, crop_y1), (crop_x2, crop_y2), (0, 0, 255), 2)

    # Save the results
    cv2.imwrite("debug_annotated_full.png", annotated)
    cv2.imwrite("debug_roi_cropped.png", roi)

    print("Saved 'debug_annotated_full.png' and 'debug_roi_cropped.png'.")
    print("Please check the debug_roi_cropped.png to see if the 999 skill points are perfectly within the boundaries.")

    # Apply OCR preprocessing to preview
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh_fixed = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)
    border = (
        thresh_fixed[0, :].mean() + thresh_fixed[-1, :].mean() + thresh_fixed[:, 0].mean() + thresh_fixed[:, -1].mean()
    ) / 4
    if border < 128:
        thresh_fixed = cv2.bitwise_not(thresh_fixed)

    cleaned = thresh_fixed.copy()
    roi_h, roi_w = cleaned.shape
    scan_limit = max(1, int(roi_w * 0.15))
    for col in range(scan_limit):
        black_ratio = np.sum(cleaned[:, col] == 0) / roi_h
        if black_ratio > 0.70:
            cleaned[:, col] = 255

    padded = cv2.copyMakeBorder(cleaned, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=[255, 255, 255])
    upscaled = cv2.resize(padded, None, fx=4, fy=4, interpolation=cv2.INTER_LINEAR)
    cv2.imwrite("debug_roi_preprocessed.png", upscaled)
    print("Saved 'debug_roi_preprocessed.png' to preview the OCR input.")


if __name__ == "__main__":
    main()
