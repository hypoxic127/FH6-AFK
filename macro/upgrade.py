# -*- coding: utf-8 -*-
"""
macro/upgrade.py — 车辆加点宏
"""

import time

import cv2
import numpy as np
import pytesseract
import vgamepad as vg

import engine.ocr as module_ocr
from engine.i18n import t
from engine.utils import log_info, log_success, log_warning
from macro.core import capture_raw_screenshot, capture_screenshot

# Available Points 多帧共识帧数：低分辨率（如 1600×900，ROI 仅 ~56×27）下抗间歇性单帧误读
_AP_CONSENSUS_FRAMES = 3


def action_upgrade_car_skills(hwnd, gamepad, min_points=30):
    """
    全自动车辆熟练度加点手柄宏：
    1. 输入一次 A，等待 10 秒（进入车辆详情/历史）
    2. 输入 B（退回）
    3. 输入 D-pad Down 1 次
    4. 输入 A（进入技能树）
    5. 输入 D-pad Down 7 次
    6. 等待 1 秒
    7. 输入 A（选择超级轮盘）
    8. 输入 D-pad Right 1 次
    9. 输入 A（确认）
    10. 重复多次 (D-pad Up 1 次 + A)
    11. 输入 D-pad Left 1 次
    12. 输入 B × 2（退出技能树）
    确保已进入技能树升级界面
    """
    log_info(t("upgrade.start"))
    # 宏按键延迟设置，确保 UI 渲染稳定

    def press(button, count=1, delay=0.8):
        for k in range(count):
            gamepad.press_button(button=button)
            gamepad.update()
            time.sleep(0.15)
            gamepad.release_button(button=button)
            gamepad.update()
            time.sleep(delay)

    # 1. B × 1

    log_info(t("upgrade.wait_stable"))
    time.sleep(2.0)
    log_info("  -> [1] B × 1...")
    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_B, delay=1.0)
    # 2. Up × 1

    log_info("  -> [2] Up × 1...")
    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP, delay=0.8)
    # 3.  A

    log_info("  -> [3]  A ...")
    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.2)
    # 4. 输入 D-pad Down 7次

    log_info(t("upgrade.step_down7"))
    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN, count=7, delay=0.8)
    # 5.  A

    log_info("  -> [5]  A ...")
    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.2)

    # === 触发条件 2: 扫描 Available Points（多帧共识，低分辨率下抗间歇误读）===
    available_points = -1
    try:
        candidates: list[tuple[int, float]] = []  # 跨帧累积的 (值, 置信度)
        last_w = last_h = 0
        for frame_idx in range(_AP_CONSENSUS_FRAMES):
            time.sleep(1.0 if frame_idx == 0 else 0.2)  # 首帧等 UI 刷新，后续帧短间隔取多样性
            raw_img = capture_raw_screenshot(hwnd)
            if raw_img is None:
                continue
            h, w = raw_img.shape[:2]
            last_w, last_h = w, h

            # ROI: 数字区域 (h85-88%, w35-38.5%)
            roi = raw_img[int(h * 0.85) : int(h * 0.88), int(w * 0.35) : int(w * 0.385)]
            if roi.size == 0:
                continue

            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            # 4 条针对黄色 AP 文字的二值化管线
            pipelines = []
            _, t150 = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
            pipelines.append(("gray_t150", t150))
            _, t160 = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY)
            pipelines.append(("gray_t160", t160))
            _, t_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            pipelines.append(("gray_otsu", t_otsu))
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            yellow_mask = cv2.inRange(hsv, np.array([15, 40, 100]), np.array([45, 255, 255]))
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            yellow_mask = cv2.morphologyEx(yellow_mask, cv2.MORPH_CLOSE, kernel)
            yellow_mask = cv2.dilate(yellow_mask, kernel, iterations=1)  # 增粗抗锯齿细笔画
            pipelines.append(("hsv_yellow", yellow_mask))

            # 调试输出（仅首帧；读取实时全局值，确保 --debug 运行时也能生效）
            if module_ocr.DEBUG_WRITE_FILES and frame_idx == 0:
                cv2.imwrite("debug_ap_roi_raw.png", roi)
                cv2.imwrite("debug_ap_roi_gray_t150.png", t150)
                cv2.imwrite("debug_ap_roi_yellow_mask.png", yellow_mask)

            # 每管线：补边 + 3×CUBIC 放大 + 反相 → 置信度 OCR（候选跨帧累积）
            # 注：实测在 56×27 的小 ROI 上 3×CUBIC 优于 4×LINEAR（后者会让灰度管线误读 549→349/949）
            for _label, binary_img in pipelines:
                padded = cv2.copyMakeBorder(binary_img, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=0)
                up = cv2.resize(padded, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
                up_inv = cv2.bitwise_not(up)
                candidates.extend(module_ocr._ocr_digits_with_conf(up_inv, 7))

        # 范围校验(0..999) + 置信度加权投票（跨帧 × 4 管线候选汇总）
        voted = module_ocr._vote_skill_points(candidates)
        if voted is not None:
            available_points = voted
            log_info(t("upgrade.ap_result", pts=available_points, raw=[v for v, _ in candidates], w=last_w, h=last_h))
        else:
            log_warning(t("upgrade.ap_no_digit"))

        if available_points >= 0 and available_points < min_points:
            log_warning(t("upgrade.ap_low", pts=available_points, min=min_points))
            return available_points
    except Exception as e:
        log_warning(t("upgrade.ap_error", err=e))

    def _check_cannot_afford(step_name):
        """检测 'Cannot Afford Perk' 弹窗并按 A 关闭"""
        time.sleep(0.5)
        resized, _, _, _, _ = capture_screenshot(hwnd)
        if resized is None:
            return False
        h_img, w_img = resized.shape[:2]
        # 弹窗区域: h27-83%, w26-82%
        roi = resized[int(h_img * 0.27) : int(h_img * 0.83), int(w_img * 0.26) : int(w_img * 0.82)]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        text = pytesseract.image_to_string(thresh, config="--psm 6").strip().lower()
        if "cannot" in text and "afford" in text:
            log_warning(t("upgrade.cannot_afford", step=step_name, text=text[:50]))
            press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.0)
            return True
        return False

    # 6.  A

    log_info("  -> [6]  A ...")
    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.2)
    if _check_cannot_afford("步骤6"):
        log_warning(t("upgrade.afford_fail"))
        return available_points
    # 7. 输入 D-pad Right 1次

    log_info(t("upgrade.step_right"))
    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT, delay=0.8)
    # 8.  A

    log_info("  -> [8]  A ...")
    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.2)
    if _check_cannot_afford("步骤8"):
        log_warning(t("upgrade.afford_fail"))
        return available_points
    # 9. 重复多次 (D-pad Up 1次 + A)

    afford_failed = False
    for j in range(3):
        log_info(t("upgrade.loop_up", n=j + 1))
        press(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP, delay=0.8)
        log_info(t("upgrade.loop_a", n=j + 1))
        press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.2)
        if _check_cannot_afford(f"循环{j + 1}"):
            afford_failed = True
            break

    # 10. 输入 D-pad Left 1次

    log_info(t("upgrade.step_left"))
    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT, delay=0.8)
    # 11.  A

    log_info("  -> [11]  A ...")
    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.5)
    if afford_failed:
        _check_cannot_afford("步骤11")

    # 12. 输入 B × 2（退出技能树）
    log_info("  -> [12] B × 2...")
    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_B, count=2, delay=1.0)

    log_success(t("upgrade.done"))
    return available_points  # 返回剩余点数
