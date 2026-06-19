# -*- coding: utf-8 -*-
"""
macro/navigation.py — 菜单导航、视觉刹车、返回车库
"""

import time

import cv2
import pytesseract
import vgamepad as vg

import engine.ocr as module_ocr
from engine.i18n import t
from engine.utils import log_info, log_success, log_warning, safe_print
from engine.utils import press_button as _press_button
from macro.core import capture_raw_screenshot, capture_screenshot


def _scan_for_subaru_page(hwnd, gamepad, max_presses=15):
    """按 LB 翻页直到 OCR 检测到 Subaru 品牌标签。返回 True/False。"""

    def _detect_selected_brand(hwnd):
        """检测品牌标签栏选中的标签文字（委托给 module_ocr 统一实现）"""
        raw_img = capture_raw_screenshot(hwnd)
        return module_ocr.detect_selected_brand_tab(raw_img)

    current_brand = _detect_selected_brand(hwnd)
    if current_brand and "subaru" in current_brand:
        log_success(f"    Subaru page detected on current screen! (OCR: '{current_brand}')")
        return True

    for lb_i in range(1, max_presses + 1):
        _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER, delay=1.0)
        current_brand = _detect_selected_brand(hwnd)
        if current_brand and "subaru" in current_brand:
            log_success(f"    Subaru page detected! (LB x {lb_i}, OCR: '{current_brand}')")
            return True
        if lb_i % 3 == 0:
            log_info(t("nav.lb_brand", n=lb_i, brand=current_brand))

    log_warning(f"  Subaru page not found after {max_presses} LB presses")
    return False


def _ocr_detect_menu_tab(hwnd):
    """OCR 标签栏检测：返回匹配到的菜单关键词数量和文本。"""
    resized, _, _, _, _ = capture_screenshot(hwnd)
    if resized is None:
        return 0, ""
    h, w = resized.shape[:2]
    roi = resized[int(h * 0.14) : int(h * 0.18), int(w * 0.09) : int(w * 0.57)]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    text = pytesseract.image_to_string(thresh).strip().lower()
    keywords = [
        "campaign",
        "drive",
        "collection",
        "festival",
        "settings",
        "buy",
        "cars",
        "horizon",
        "online",
        "creative",
        "store",
    ]
    matched = sum(1 for kw in keywords if kw in text)
    return matched, text


def _ocr_wait_for_car_select(hwnd, max_poll=15):
    """OCR 轮询等待车库 'Car Select' 文字出现。"""
    log_info(t("nav.poll_car_select"))
    for poll_i in range(1, max_poll + 1):
        time.sleep(1.0)
        raw_poll = capture_raw_screenshot(hwnd)
        if raw_poll is None:
            continue
        h_p, w_p = raw_poll.shape[:2]
        top_roi = raw_poll[int(h_p * 0.09) : int(h_p * 0.13), int(w_p * 0.06) : int(w_p * 0.16)]
        gray_top = cv2.cvtColor(top_roi, cv2.COLOR_BGR2GRAY)
        _, thresh_top = cv2.threshold(gray_top, 200, 255, cv2.THRESH_BINARY)
        text_top = pytesseract.image_to_string(thresh_top, config="--psm 7").strip().lower()
        if "car" in text_top and "selec" in text_top:
            log_success(t("nav.car_select_ok", text=text_top, sec=poll_i))
            return True
        if poll_i % 3 == 0:
            log_info(t("nav.car_select_wait", n=poll_i, text=text_top))
    log_warning(t("nav.car_select_timeout", sec=max_poll))
    return False


def navigate_menu_to_garage(hwnd, gamepad):
    """从主菜单导航进入车库：RB×2→A×2→等待→RB×2→Down×2→A→Down×7→A→等待→LB扫Subaru。"""
    log_info(t("nav.menu_to_garage"))

    log_info(t("nav.step", n=1, total=10, desc="RB × 2 -> MY HORIZON"))
    _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER, delay=0.8)
    _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER, delay=0.8)

    log_info(t("nav.step", n=2, total=10, desc="A × 2 Return Home + Yes"))
    _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.0)
    _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.0)

    log_info(t("nav.step", n=3, total=10, desc="Wait for Return Home"))
    detected = False
    for attempt in range(30):
        time.sleep(1.0)
        matched, text = _ocr_detect_menu_tab(hwnd)
        if matched >= 1:
            log_success(t("nav.menu_loaded", n=attempt + 1))
            detected = True
            break
        if (attempt + 1) % 3 == 0:
            log_info(t("nav.menu_wait", n=attempt + 1, text=text[:80]))
    if not detected:
        log_warning(t("nav.campaign_timeout"))

    log_info(t("nav.step", n=4, total=10, desc="RB × 2 -> Cars"))
    _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER, delay=0.8)
    _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER, delay=0.8)

    log_info(t("nav.step", n=5, total=10, desc="Down × 2"))
    _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN, delay=0.5)
    _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN, delay=0.5)

    log_info(t("nav.step", n=6, total=10, desc="A × 1 confirm"))
    _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=2.0)

    log_info(t("nav.step", n=7, total=10, desc="Down × 7"))
    for _ in range(7):
        _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN, delay=0.5)

    log_info(t("nav.step", n=8, total=10, desc="A × 1 enter garage"))
    _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=2.0)

    log_info(t("nav.step", n=9, total=10, desc="Wait for garage"))
    _ocr_wait_for_car_select(hwnd)

    log_info(t("nav.step", n=10, total=10, desc="LB -> Subaru"))
    _scan_for_subaru_page(hwnd, gamepad)

    log_success(t("nav.menu_to_garage_done"))


def safe_exit_to_menu(hwnd, gamepad):
    """OCR 视觉刹车：循环按 B 退回，OCR 检测标签栏关键词 >= 2 个即确认到达主菜单。"""
    log_info(t("nav.safe_exit"))

    for loop_idx in range(1, 9):
        resized, _, _, _, _ = capture_screenshot(hwnd)
        if resized is not None:
            try:
                h, w = resized.shape[:2]
                roi = resized[int(h * 0.14) : int(h * 0.18), int(w * 0.09) : int(w * 0.57)]
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
                text = pytesseract.image_to_string(thresh).strip().lower()
                menu_keywords = [
                    "campaign",
                    "cars",
                    "horizon",
                    "online",
                    "creative",
                    "store",
                    "buy",
                    "sell",
                    "garage",
                    "character",
                    "customizable",
                ]
                matched_count = sum(1 for kw in menu_keywords if kw in text)
                if matched_count >= 2:
                    log_success(t("nav.brake_ok", count=matched_count))
                    safe_print(t("nav.brake_done"))
                    return True
                log_info(t("nav.brake_progress", n=loop_idx, text=text[:60], count=matched_count))
            except Exception as e:
                log_warning(t("nav.brake_error", err=e))

        log_warning(t("nav.brake_b"))
        _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_B, delay=0)
        time.sleep(2.0)

    raise TimeoutError(t("nav.brake_timeout"))


def return_to_garage(hwnd, gamepad):
    """完整返回车库流程：视觉刹车→Down→A→Down×7→A→等待→LB扫Subaru。"""
    log_info(t("nav.return_garage"))

    try:
        safe_exit_to_menu(hwnd, gamepad)
    except TimeoutError as e:
        log_warning(f"Return to garage exit menu timeout: {e}")
        # Continue to try garage return sequence even if visual confirmation fails
    log_info(t("nav.wait_stable"))
    time.sleep(1.0)

    log_info(t("nav.down_1"))
    _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN, delay=0.5)

    log_info(t("nav.a_confirm"))
    _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=2.0)

    log_info(t("nav.down_7"))
    for _ in range(7):
        _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN, delay=0.5)

    log_info(t("nav.a_enter_garage"))
    _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=2.0)

    _ocr_wait_for_car_select(hwnd)

    log_info(t("nav.lb_subaru"))
    _scan_for_subaru_page(hwnd, gamepad)

    log_success(" return_to_garage() complete!")
