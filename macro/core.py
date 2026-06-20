# -*- coding: utf-8 -*-
"""
macro/core.py — 基础设施（截图、日志、配置常量）
所有其他 macro 子模块都依赖此模块。
"""

import ctypes
import time

import cv2
import numpy as np
from colorama import Fore, Style

from engine.i18n import t
from engine.utils import (
    find_game_window,  # noqa: F401 — re-exported via macro/__init__.py
    force_foreground,
    get_client_rect,
    log_error,
    log_warning,
    safe_print,
)
from engine.utils import press_button as _press_button  # noqa: F401 — re-exported

# ==========================================
# 全局配置参数
# ==========================================

MAX_SKILL_POINTS = 999  # 技能点满值上限

POINTS_PER_CAR = 30  # 每辆 Impreza 技能树加满超级抽奖需要 30 点


# 每轮循环能够处理的车辆数 = 999 // 30 = 33 辆
def get_cars_to_process():
    from engine.runtime import load_bot_config

    config = load_bot_config()
    target = config.get("target_points", MAX_SKILL_POINTS)
    return target // POINTS_PER_CAR


# 主状态机的四个状态常量（循环顺序：刷点 -> 买车 -> 加点 -> 卖车 -> 刷点...）
STATE_BUY_CARS = "STATE_BUY_CARS"  # 阶段 2：批量购买 Subaru Impreza
STATE_UPGRADE_CARS = "STATE_UPGRADE_CARS"  # 阶段 3：逐辆消耗技能点升级技能树
STATE_TRASH_CARS = "STATE_TRASH_CARS"  # 阶段 4：移除已升级的 Impreza、保留主力车
STATE_FARM_POINTS = "STATE_FARM_POINTS"  # 阶段 1：自动跑 EventLab 刷到 999 技能点

# MSS singleton - use shared instance from utils to avoid duplicate GDI handles


def _get_mss():
    """Proxy to shared MSS singleton in utils.py"""
    from engine.utils import get_mss

    return get_mss()


# 焦点检查节流（避免每帧 1.5s 的抢焦点延迟）

_last_foreground_check = 0

_FOREGROUND_CHECK_INTERVAL = 10.0  # max check foreground window once per 10 seconds


def log_state_header(state, description):
    safe_print(f"\n{Fore.MAGENTA}{Style.BRIGHT}==================================================")
    safe_print(f"{Fore.MAGENTA}{Style.BRIGHT}{t('core.current_state', state=state)}")
    safe_print(f"{Fore.MAGENTA}{Style.BRIGHT}{t('core.task_desc', desc=description)}")
    safe_print(f"{Fore.MAGENTA}{Style.BRIGHT}=================================================={Style.RESET_ALL}")


def log_step_header(step_num, title):
    safe_print(f"\n{Fore.BLUE}{Style.BRIGHT}==================================================")
    safe_print(f"\n{Fore.BLUE}{Style.BRIGHT}{t('core.nav_step', num=step_num, title=title)}")
    safe_print(f"{Fore.BLUE}{Style.BRIGHT}=================================================={Style.RESET_ALL}")


def capture_screenshot(hwnd):
    """
    获取当前游戏窗口的截图并缩放至 1600x900。
    包含窗口最小化恢复、前台焦点检查（节流 10s）、
    GDI 句柄损坏自动重置等防御机制。
    返回: (resized_img, cx, cy, cw, ch) 或 (None, ...)
    """
    global _last_foreground_check
    cw, ch = 2560, 1440
    cx, cy = 0, 0
    if hwnd:
        try:
            # 检查窗口是否被最小化（IsIconic），如果是则恢复它
            if ctypes.windll.user32.IsIconic(hwnd):
                log_warning(t("core.window_minimized"))
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                time.sleep(2.0)  # 等待窗口恢复

            # 节流前台检查：最多每 10 秒检查一次，避免每帧 1.5s 的焦点抢夺延迟
            now = time.time()
            if now - _last_foreground_check > _FOREGROUND_CHECK_INTERVAL:
                current_fg = ctypes.windll.user32.GetForegroundWindow()
                if current_fg != hwnd:
                    force_foreground(hwnd)

                _last_foreground_check = now

            cx, cy, cw, ch = get_client_rect(hwnd)

            # 防御：窗口坐标异常（最小化时可能返回 0x0 或负坐标）
            if cw <= 0 or ch <= 0 or cx < -10000:
                err_detail = (
                    f"Region has zero or negative size: {{'top': {cy}, 'left': {cx}, 'width': {cw}, 'height': {ch}}}"
                )
                log_error(t("core.capture_fail", err=err_detail))
                return None, cx, cy, cw, ch

        except Exception as e:
            log_warning(t("core.coord_fail", err=e))

    try:
        sct = _get_mss()
        monitor = {"top": cy, "left": cx, "width": cw, "height": ch}
        screenshot = sct.grab(monitor)
        img = np.array(screenshot)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        resized = cv2.resize(img, (1600, 900), interpolation=cv2.INTER_LINEAR)
        return resized, cx, cy, cw, ch

    except Exception as e:
        # 停止信号原样抛出（尽快终止、且不当作错误打印）
        from macro.master_loop import BotStoppedError, is_stop_requested

        if isinstance(e, BotStoppedError):
            raise
        # 手动停止/teardown 期间窗口句柄失效导致的截图失败属预期 → 静默，不打 ERROR
        if not is_stop_requested():
            log_error(t("core.capture_fail", err=e))
        # GDI 句柄可能已损坏，重置 MSS 单例
        try:
            from engine.utils import reset_mss

            reset_mss()
        except OSError:
            pass  # reset_mss close failure is non-critical
        return None, cx, cy, cw, ch


def capture_raw_screenshot(hwnd):
    """
    获取原始分辨率截图（不缩放），专供 OCR 使用。
    比例 ROI 在原始图上裁剪，文字保持原始清晰度，
    不受 2560→1600 缩放导致的模糊影响。
    返回: 原始分辨率 BGR 图像，或 None
    """
    if hwnd:
        try:
            cx, cy, cw, ch = get_client_rect(hwnd)
            if cw <= 0 or ch <= 0:
                return None
        except (OSError, Exception) as e:
            log_warning(t("core.coord_fail", err=e))
            return None
    else:
        return None
    try:
        sct = _get_mss()
        monitor = {"top": cy, "left": cx, "width": cw, "height": ch}
        screenshot = sct.grab(monitor)
        img = np.array(screenshot)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    except Exception as e:
        # 停止信号原样抛出（尽快终止、且不当作错误打印）
        from macro.master_loop import BotStoppedError, is_stop_requested

        if isinstance(e, BotStoppedError):
            raise
        # 手动停止/teardown 期间的截图失败属预期 → 静默，不打 ERROR
        if not is_stop_requested():
            log_error(t("core.capture_fail", err=e))
        try:
            from engine.utils import reset_mss

            reset_mss()
        except OSError:
            pass
        return None
