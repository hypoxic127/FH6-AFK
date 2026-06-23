# -*- coding: utf-8 -*-
"""
macro/wheelspin.py — 自动 Super Wheelspin 抽奖
================================================
在 STATE_TRASH_CARS 之后运行：从自由漫游出发，导航到
MY HORIZON → Super Wheelspin，把累积的超级抽奖全部抽完，
并对 "Car Already Owned" 重复车按售价阈值智能卖出/保留。

进/出口契约（master_loop 方案 B）：
  入口 = 自由漫游；本模块按 START 打开菜单并导航。
  出口 = 退回自由漫游（B×N + _wait_for_anna_link 确认）；
         随后由 master_loop 尾巴补一次 START 交还 FARM。

导航路径（依据 debug/Wheelspin.png）：
  START → RB×2(MY HORIZON 第 3 标签) → DPAD Left(Return Home→Super Wheelspin 磁贴) → A
"""

import re

import cv2
import pytesseract
import vgamepad as vg

import engine.ocr as module_ocr
from engine.control import check_stop, interruptible_sleep
from engine.i18n import t
from engine.runtime import load_bot_config
from engine.state_detect import get_detector
from engine.utils import log_error, log_info, log_success, log_warning
from engine.utils import press_button as _press_button
from farm.skills import archive_wheelspin_to_file
from macro.core import capture_raw_screenshot, capture_screenshot
from macro.garage import _wait_for_anna_link

# 手柄按钮常量别名
_A = vg.XUSB_BUTTON.XUSB_GAMEPAD_A
_B = vg.XUSB_BUTTON.XUSB_GAMEPAD_B
_RB = vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER
_START = vg.XUSB_BUTTON.XUSB_GAMEPAD_START
_DOWN = vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN
_LEFT = vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT

_SAFETY_CAP = 200  # 绝对上限，防 OCR 异常导致无限循环

# StateDetector.detect(mode="menu") 在主菜单返回的激活标签名（用于确认菜单已打开）
_MENU_TABS = {"CAMPAIGN", "CARS", "MY HORIZON", "ONLINE", "CREATIVE HUB", "STORE"}

_SKIP_POLL_INTERVAL = 0.15  # 快速轮询 Skip 提示的间隔（秒）
_SKIP_POLL_TIMEOUT = 8.0  # 等待 Skip 出现的最长时间（秒）


# ===================================================================
#  导航
# ===================================================================


def navigate_to_wheelspin(hwnd, gamepad) -> bool:
    """从自由漫游导航到 Super Wheelspin 抽奖界面。

    Returns:
        True = 已进入抽奖（动画/结果页）；False = 导航失败。
    """
    log_info(t("wheelspin.nav_start"))
    detector = get_detector()

    # Step 1: 自由漫游 → START 打开菜单，等菜单标签栏出现（用 state_detect 识别激活标签）
    _press_button(gamepad, _START, delay=2.0)
    for _ in range(8):
        resized, _, _, _, _ = capture_screenshot(hwnd)
        if resized is not None and detector.detect(resized, mode="menu") in _MENU_TABS:
            break
        if interruptible_sleep(1.0):
            check_stop()

    # Step 2: 按 RB 循环到 MY HORIZON —— 直接用 state_detect 的标签检测确认激活标签
    # （detect(mode="menu") 在 MY HORIZON 页返回 "MY HORIZON"；ROI 高度正确，不再依赖偏高的 _ocr_detect_menu_tab）
    horizon_ok = False
    for attempt in range(1, 8):  # 最多 7 次 RB 覆盖全部 6 个标签
        resized, _, _, _, _ = capture_screenshot(hwnd)
        if resized is not None and detector.detect(resized, mode="menu") == "MY HORIZON":
            log_success(t("wheelspin.nav_horizon_ok", n=attempt))
            horizon_ok = True
            break
        _press_button(gamepad, _RB, delay=0.8)
        if interruptible_sleep(0.4):
            check_stop()
    if not horizon_ok:
        log_warning(t("wheelspin.nav_horizon_fail"))

    # Step 3: Left 选中 Super Wheelspin 磁贴 → A 进入
    _press_button(gamepad, _LEFT, delay=0.6)
    _press_button(gamepad, _A, delay=2.0)

    # Step 4: 确认已进入抽奖（动画的 SUPER wheelspin 徽标或结果页底栏）
    for _ in range(6):
        resized, _, _, _, _ = capture_screenshot(hwnd)
        if resized is not None and (detector.check_wheelspin_ui(resized) or detector.check_spin_again(resized)):
            log_success(t("wheelspin.nav_ok"))
            return True
        if interruptible_sleep(0.8):
            check_stop()

    log_warning(t("wheelspin.nav_fail"))
    return False


# ===================================================================
#  Skip 动画检测
# ===================================================================


def _wait_and_skip_animation(hwnd, gamepad, detector, timeout: float = _SKIP_POLL_TIMEOUT) -> None:
    """快速轮询左下角 'Ⓐ Skip' 提示，出现后立即按 A 跳过动画。"""
    elapsed = 0.0
    while elapsed < timeout:
        check_stop()
        resized, _, _, _, _ = capture_screenshot(hwnd)
        if resized is not None and detector.check_skip_visible(resized):
            log_info(t("wheelspin.skip_detected"))
            _press_button(gamepad, _A, delay=0)
            return
        if interruptible_sleep(_SKIP_POLL_INTERVAL):
            check_stop()
        elapsed += _SKIP_POLL_INTERVAL

    log_warning(t("wheelspin.skip_timeout"))
    _press_button(gamepad, _A, delay=0)


# ===================================================================
#  OCR 读取
# ===================================================================


def _read_spins_remaining(hwnd) -> int | None:
    """从结果页读取 Spins Remaining 当前值。"""
    raw = capture_raw_screenshot(hwnd)
    if raw is None:
        return None
    h, w = raw.shape[:2]
    roi = raw[int(h * 0.6189) : int(h * 0.6744), int(w * 0.1031) : int(w * 0.1806)]
    if roi.size == 0:
        return None
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY)
    text = pytesseract.image_to_string(thresh, config="--psm 7 -c tessedit_char_whitelist=0123456789").strip()
    m = re.search(r"\d+", text)
    if not m:
        return None
    try:
        v = int(m.group())
    except ValueError:
        return None
    return v if 0 <= v <= 999 else None


def _read_duplicate_car_info(hwnd) -> tuple[str | None, int | None]:
    """读取 'Car Already Owned' 弹窗的车名与售价。任一为 None 表示该项 OCR 失败。"""
    raw = capture_raw_screenshot(hwnd)
    if raw is None:
        return None, None
    h, w = raw.shape[:2]

    # 车名（橙字）h60-66%, w36-66%
    car_name: str | None = None
    name_roi = raw[int(h * 0.60) : int(h * 0.66), int(w * 0.36) : int(w * 0.66)]
    if name_roi.size:
        gray = cv2.cvtColor(name_roi, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY)
        txt = pytesseract.image_to_string(thresh, config="--psm 7").strip()
        if txt:
            car_name = txt.upper()

    # 售价 "Sell for @ 12,500" h78-84%, w36-66%
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


# ===================================================================
#  结果检测（轮询）
# ===================================================================


def _detect_spin_result(hwnd, detector, timeout: float = 15.0) -> str:
    """按 0.5s 轮询检测抽奖结果页的底栏。"""
    elapsed = 0.0
    poll = 0
    while elapsed < timeout:
        check_stop()
        resized, _, _, _, _ = capture_screenshot(hwnd)
        if resized is not None:
            # 只需要看底栏，因为此时不会有弹窗（还没按 A 领奖）
            if detector.check_spin_again(resized):
                return "spin_again"
            if detector.check_collect_prize(resized):
                return "no_more_spins"
        poll += 1
        if poll % 5 == 0:
            log_info(t("wheelspin.waiting_result"))
        if interruptible_sleep(0.5):
            check_stop()
        elapsed += 0.5

    if module_ocr.DEBUG_WRITE_FILES:
        _dump_debug(hwnd, "spin_timeout")
    return "timeout"


def _dump_debug(hwnd, label: str) -> None:
    try:
        import os
        import time

        from engine.runtime import get_data_dir

        raw = capture_raw_screenshot(hwnd)
        if raw is None:
            return
        out_dir = os.path.join(get_data_dir(), "debug")
        os.makedirs(out_dir, exist_ok=True)
        cv2.imwrite(os.path.join(out_dir, f"wheelspin_{label}_{int(time.time())}.png"), raw)
    except Exception:
        pass


# ===================================================================
#  重复车辆处理
# ===================================================================


def _handle_duplicate_car(hwnd, gamepad, sell_threshold: int) -> dict:
    """处理 'Car Already Owned' 弹窗：按售价阈值决定卖出或保留。"""
    interruptible_sleep(1.0)  # 等弹窗动画完全展开后再 OCR
    car_name, sell_price = _read_duplicate_car_info(hwnd)
    log_info(
        t(
            "wheelspin.dup_found",
            car=car_name or "?",
            price=sell_price if sell_price is not None else "?",
        )
    )

    if sell_price is None:
        action = "sell"
        log_warning(t("wheelspin.dup_ocr_fail"))
    elif sell_price < sell_threshold:
        action = "sell"
    else:
        action = "keep"

    if action == "sell":
        log_info(
            t(
                "wheelspin.dup_sell",
                car=car_name or "?",
                price=sell_price if sell_price is not None else "?",
                threshold=sell_threshold,
            )
        )
        # 默认高亮 Add to Garage → 向下按两次移到 Sell for CR → 按 A 卖出
        _press_button(gamepad, _DOWN, delay=0.3)
        _press_button(gamepad, _DOWN, delay=0.3)
        _press_button(gamepad, _A, delay=1.5)
    else:
        log_info(
            t(
                "wheelspin.dup_keep",
                car=car_name or "?",
                price=sell_price if sell_price is not None else "?",
                threshold=sell_threshold,
            )
        )
        # 默认高亮 Add to Garage，直接按 A 添加到车库
        _press_button(gamepad, _A, delay=1.5)

    return {"car_name": car_name, "sell_price": sell_price, "action": action}


# ===================================================================
#  主流程
# ===================================================================


def perform_wheelspin(hwnd, gamepad, max_spins: int, sell_threshold: int = 250_000) -> int:
    """执行连续抽奖。Returns: 完成抽奖的次数。"""
    detector = get_detector()

    if not navigate_to_wheelspin(hwnd, gamepad):
        log_error(t("wheelspin.nav_fail"))
        return 0

    spin_count = 0
    target = max_spins or 999

    log_info(t("wheelspin.first_spin"))

    while True:
        check_stop()

        # 1. 此时必然是动画阶段（第一抽是刚进界面自动启动的，后续抽奖是处理完弹窗后自动启动的）
        # 等待出现 Skip 提示，并按 A 跳过动画
        _wait_and_skip_animation(hwnd, gamepad, detector)

        # 2. 动画跳过后，等待结果页稳定显示（出现 'Spin Again' 或 'Collect Prize'）
        result = _detect_spin_result(hwnd, detector, timeout=15.0)

        if result == "timeout":
            log_warning(t("wheelspin.no_result"))
            break

        spin_count += 1
        log_info(t("wheelspin.spin_n", n=spin_count))

        remaining = _read_spins_remaining(hwnd)
        if remaining is not None:
            log_info(t("wheelspin.remaining", n=remaining))

        # 3. 在结果页按 A (Collect Prize)。这会触发重复车弹窗，或（如果没有重复车）自动开始下一轮抽奖！
        _press_button(gamepad, _A, delay=0)

        # 等待 1 秒再开始识别，避免画面过渡时的残影或过度帧导致误判
        if interruptible_sleep(1.0):
            check_stop()

        # 4. 轮询接下来的画面：处理可能出现的 0~3 次弹窗
        duplicate_infos = []
        elapsed = 0.0

        while elapsed < 15.0:
            check_stop()
            resized, _, _, _, _ = capture_screenshot(hwnd)
            if resized is not None:
                # 如果出现弹窗，优先处理
                if detector.check_car_already_owned(resized):
                    info = _handle_duplicate_car(hwnd, gamepad, sell_threshold)
                    duplicate_infos.append(info)
                    elapsed = 0.0  # 处理完一个弹窗，重置轮询时间，等待下一个弹窗或动画启动
                    continue

                # 如果看到了下一轮的 Skip 提示，明确表示下一轮已经启动了，跳出轮询
                if result == "spin_again" and detector.check_skip_visible(resized):
                    break

                # 如果一直没出弹窗：过了 3~4 秒说明游戏肯定已经启动下一轮（或者结束退出）了
                if elapsed > 4.0:
                    break

            if interruptible_sleep(0.2):
                check_stop()
            elapsed += 0.2

        # 5. 本轮弹窗处理完毕，归档数据
        last_info = duplicate_infos[-1] if duplicate_infos else None
        archive_wheelspin_to_file(spin_count, target, duplicate_info=last_info)

        # 6. 检查退出条件
        if result == "no_more_spins":
            log_info(t("wheelspin.no_more"))
            break
        if max_spins > 0 and spin_count >= max_spins:
            log_info(t("wheelspin.limit_reached", n=max_spins))
            break
        if spin_count >= _SAFETY_CAP:
            log_warning(t("wheelspin.safety_stop"))
            break

        # 此时程序会自动进入下一轮的 while True 开头，执行 _wait_and_skip_animation() 来跳过新启动的动画。

    # ── 退出 ──
    log_info(t("wheelspin.exit"))
    # 直接按 B 连打退回自由漫游
    for _ in range(3):
        _press_button(gamepad, _B, delay=1.2)
        if _wait_for_anna_link(hwnd, max_wait=3):
            break

    log_success(t("wheelspin.done", count=spin_count))
    return spin_count
