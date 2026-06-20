# -*- coding: utf-8 -*-
"""
macro/master_loop.py — 主控状态机循环

从 macro/__init__.py 中分离出来，使 __init__.py 仅负责包导出。
"""

import sys
import time

import pytesseract
import vgamepad as vg
from colorama import Fore, Style

import engine.ocr as module_ocr
from engine.control import (
    BotStoppedError,  # noqa: F401 — re-exported for web/server.py & macro/core.py & farm/skills.py
    check_stop,
    clear_stop,  # noqa: F401 — re-exported for web/server.py
    is_stop_requested,  # noqa: F401 — re-exported for截图层 (macro/core.py, farm/skills.py)
    request_stop,  # noqa: F401 — re-exported for web/server.py
)
from engine.event_bus import get_bus
from engine.i18n import t
from engine.utils import log_error, log_info, log_success, log_warning
from farm.skills import archive_upgrade_to_file
from macro.core import (
    MAX_SKILL_POINTS,
    STATE_BUY_CARS,
    STATE_FARM_POINTS,
    STATE_TRASH_CARS,
    STATE_UPGRADE_CARS,
    _press_button,
    capture_raw_screenshot,
    capture_screenshot,
    find_game_window,
    force_foreground,
    get_cars_to_process,
    log_state_header,
)
from macro.garage import (
    _scan_and_delete_cars,
    _wait_for_anna_link,
    _wait_for_cars_text,
    _wait_for_designs_and_paints,
    navigate_to_car_in_garage,
    navigate_to_main_car,
    reset_upgrade_position,
)
from macro.navigation import (
    _scan_for_subaru_page,
    navigate_menu_to_garage,
    return_to_garage,
)
from macro.purchase import (
    action_buy_single_car,
    navigate_to_impreza_purchase_screen,
)
from macro.upgrade import action_upgrade_car_skills

# 停止原语统一由 engine/control.py 提供（见上方 import），此处仅再导出以保持现有
# `from macro.master_loop import BotStoppedError, clear_stop, request_stop, is_stop_requested` 可用。

# 同一 state 连续异常达到此次数则熔断退出，避免任何持续性错误无限 5s 空转
MAX_CONSECUTIVE_STATE_ERRORS: int = 5


def run_master_bot_loop(
    initial_state: str | None = None,
    skip_buy: bool = False,
    loop: bool = True,
) -> None:
    """
    主控制状态机。

    状态转换顺序：
      STATE_FARM_POINTS -> STATE_BUY_CARS -> STATE_UPGRADE_CARS -> STATE_TRASH_CARS -> (循环)
      当 skip_buy=True 时：
      STATE_FARM_POINTS -> STATE_UPGRADE_CARS -> STATE_TRASH_CARS -> (循环，跳过买车)

    Args:
        initial_state: 起始阶段，None 表示从 STATE_FARM_POINTS 开始
        skip_buy: 是否跳过买车阶段
        loop: True=无限循环所有阶段，False=只跑选中的阶段一次
    """

    hwnd = find_game_window()
    if not hwnd:
        log_error(t("loop.window_missing"))
        sys.exit(1)

    try:
        gamepad = vg.VX360Gamepad()
        log_success(t("loop.ctrl_connected"))
    except Exception as e:
        log_error(t("loop.ctrl_fail", err=e))
        sys.exit(1)

    current_state = initial_state if initial_state else STATE_FARM_POINTS
    loop_count = 1
    consecutive_errors = 0  # 连续异常计数（熔断用），每个 state 正常完成后归零
    try:
        while True:
            check_stop()
            log_info(t("loop.cycle", count=loop_count))
            try:
                # --- 1. 买车阶段 ---

                if current_state == STATE_BUY_CARS:
                    cars_to_process = get_cars_to_process()
                    log_state_header(STATE_BUY_CARS, t("loop.buy_desc", count=cars_to_process))
                    success = navigate_to_impreza_purchase_screen(hwnd, gamepad)
                    if not success:
                        log_error(t("loop.nav_fail"))
                        time.sleep(2.0)
                        continue

                    log_success(t("loop.nav_ok"))
                    log_info(t("loop.buying"))
                    for i in range(1, cars_to_process + 1):
                        action_buy_single_car(hwnd, gamepad, i, cars_to_process)

                    log_success(t("loop.buy_done", count=cars_to_process))

                    log_info(t("loop.press_b_back"))
                    for i in range(4):
                        log_info(t("loop.press_b_n", n=i + 1))
                        _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_B, delay=1.0)

                    log_success(t("loop.b_back_done"))

                    current_state = STATE_UPGRADE_CARS
                    log_info(t("loop.transition", src="STATE_BUY_CARS", dst="STATE_UPGRADE_CARS"))
                    if not loop:
                        log_success(t("loop.buy_single_done"))
                        return
                    time.sleep(1.0)

                # --- 2. 加点阶段 ---

                elif current_state == STATE_UPGRADE_CARS:
                    log_state_header(STATE_UPGRADE_CARS, t("loop.upgrade_desc"))
                    reset_upgrade_position()  # 每次进入加点阶段都从头扫描（删车/跳过买车后网格已变）
                    navigate_menu_to_garage(hwnd, gamepad)
                    upgraded_count = 0
                    while True:
                        upgraded_count += 1
                        log_info(t("loop.upgrade_nav", n=upgraded_count))
                        success = navigate_to_car_in_garage(hwnd, gamepad)

                        # 触发条件 1: 导航返回 False → 无更多 NEW 车，立即进入删车
                        if not success:
                            log_info(t("loop.upgrade_no_more", count=upgraded_count - 1))
                            # B × 1
                            log_info(t("general.b_x", n=1))
                            _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_B, delay=1.0)
                            # A × 1
                            log_info(t("general.a_x", n=1))
                            _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=2.0)
                            # LB 扫描 Subaru 页面
                            _scan_for_subaru_page(hwnd, gamepad)
                            # 选中主力车
                            log_info(t("general.select_main_car"))
                            navigate_to_main_car(hwnd, gamepad)
                            # 等待确认进入详情页
                            if _wait_for_designs_and_paints(hwnd):
                                time.sleep(2.0)  # 等待详情页完全渲染
                                log_info(t("general.detail_confirmed"))
                                _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_B, delay=1.0)
                            else:
                                log_warning(t("general.detail_skip"))
                            # Up × 2
                            log_info(t("general.up_x", n=2))
                            _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP, delay=0.5)
                            _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP, delay=0.5)
                            # 等待检测 'Cars' 再按 A 进入车库
                            if _wait_for_cars_text(hwnd):
                                log_info(t("general.enter_garage_cars"))
                                _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=2.0)
                            else:
                                log_warning(t("general.cars_skip"))
                            # LB scan for Subaru page
                            _scan_for_subaru_page(hwnd, gamepad)
                            break

                        log_success(t("loop.upgrade_enter", n=upgraded_count))
                        remaining_points = action_upgrade_car_skills(hwnd, gamepad)
                        archive_upgrade_to_file("Subaru Impreza", 1)
                        get_bus().emit("stats_update", {"super_wheelspins": upgraded_count})

                        # 触发条件 2: Available Points < 30 → 技能点不足，进入删车
                        if remaining_points is not None and remaining_points < 30:
                            log_info(t("loop.pts_low", pts=remaining_points))
                            # B × 2 退出技能树
                            log_info(t("general.b_x", n=2))
                            _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_B, delay=1.0)
                            _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_B, delay=1.0)
                            # Up × 1
                            log_info(t("general.up_x", n=1))
                            _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP, delay=0.5)
                            # A × 1
                            log_info(t("general.enter_garage"))
                            _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=2.0)
                            # LB 扫描 Subaru 页面标签
                            _scan_for_subaru_page(hwnd, gamepad)
                            # 选中主力车
                            log_info(t("general.select_main_car"))
                            navigate_to_main_car(hwnd, gamepad)
                            # A × 1
                            log_info(t("general.select_main_a"))
                            _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=2.0)
                            # 等待检测 'Cars' 再按 A 进入车库
                            if _wait_for_cars_text(hwnd):
                                log_info(t("general.enter_garage_cars"))
                                _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=2.0)
                            else:
                                log_warning(t("general.cars_skip"))
                            _scan_for_subaru_page(hwnd, gamepad)
                            break

                        return_to_garage(hwnd, gamepad)

                    log_success(t("loop.upgrade_done", count=upgraded_count - 1))
                    current_state = STATE_TRASH_CARS
                    log_info(t("loop.transition", src="STATE_UPGRADE_CARS", dst="STATE_TRASH_CARS"))
                    if not loop:
                        log_success(t("loop.upgrade_single_done"))
                        return
                    time.sleep(1.0)

                # --- 3. 清理车库阶段 ---

                elif current_state == STATE_TRASH_CARS:
                    log_state_header(STATE_TRASH_CARS, t("loop.trash_desc"))
                    removed_count = _scan_and_delete_cars(hwnd, gamepad)
                    log_success(t("loop.trash_done", count=removed_count))
                    # B × 2 退出车库
                    log_info(t("general.b_x", n=2))
                    _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_B, delay=1.0)
                    _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_B, delay=1.0)
                    # 等待回到自由漫游画面后再按菜单键
                    if _wait_for_anna_link(hwnd):
                        log_info(t("loop.menu_confirmed"))
                        time.sleep(2.0)  # 等待自由漫游画面完全就绪
                        _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_START, delay=2.0)
                    else:
                        log_warning(t("loop.menu_fallback"))
                        _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_START, delay=2.0)

                    current_state = STATE_FARM_POINTS
                    log_info(t("loop.transition", src="STATE_TRASH_CARS", dst="STATE_FARM_POINTS"))
                    if not loop:
                        log_success(t("loop.trash_single_done"))
                        return
                    time.sleep(1.0)

                # --- 4. 刷图阶段 ---

                elif current_state == STATE_FARM_POINTS:
                    log_state_header(STATE_FARM_POINTS, t("loop.farm_desc"))
                    log_warning(t("loop.farm_launching"))

                    verified_999 = False
                    farm_attempt = 0
                    while not verified_999:
                        farm_attempt += 1
                        try:
                            import farm.skills as module_farm_skills

                            log_info(t("loop.farm_start", n=farm_attempt))
                            module_farm_skills.main(gamepad=gamepad)
                            log_success(t("loop.farm_returned"))

                        except BotStoppedError:
                            raise
                        except Exception as e:
                            log_error(t("loop.farm_error", err=e))
                            try:
                                module_farm_skills.clear_race_state()
                            except (ImportError, AttributeError) as cleanup_err:
                                log_warning(f"Failed to clear race state: {cleanup_err}")
                            log_warning(t("loop.farm_retry"))
                            time.sleep(5.0)
                            continue

                        # === 验证技能点是否到达 999 ===
                        # 技能点只在暂停菜单 CARS 标签页可见，需要先导航过去
                        log_info(t("loop.verify_focus"))
                        try:
                            from engine.utils import reset_mss

                            reset_mss()
                        except (ImportError, OSError) as mss_err:
                            log_warning(f"Failed to reset MSS: {mss_err}")
                        force_foreground(hwnd)
                        time.sleep(3.0)

                        # farm 模块返回时已在暂停菜单，按 RB 导航到 CARS 标签页
                        log_info(t("loop.verify_nav_cars"))
                        detected_points = None
                        cars_found = False

                        from engine.state_detect import get_detector

                        _detector = get_detector()

                        for rb_press in range(8):  # 最多按 8 次 RB 遍历所有标签
                            resized_v, _, _, _, _ = capture_screenshot(hwnd)
                            if resized_v is None:
                                _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER, delay=0.8)
                                continue

                            detected_state = _detector.detect(resized_v, mode="menu")
                            if detected_state == "CARS":
                                log_success(t("loop.verify_cars_ok", state=detected_state))
                                cars_found = True
                                # 在 CARS 页读取技能点 (使用原始分辨率截图以保证 OCR 精确度)
                                raw_img = capture_raw_screenshot(hwnd)
                                if raw_img is not None:
                                    pts = module_ocr.read_skill_points(raw_img)
                                    if pts is not None:
                                        detected_points = pts
                                break

                            log_info(t("loop.verify_rb", n=rb_press + 1, state=detected_state))
                            _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER, delay=0.8)

                        if not cars_found:
                            log_warning(t("loop.verify_cars_fail"))

                        if cars_found:
                            log_info(t("loop.verify_lb_back"))
                            _press_button(gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER, delay=0.5)

                        if detected_points is not None:
                            from engine.runtime import load_bot_config

                            config = load_bot_config()
                            target_points = config.get("target_points", MAX_SKILL_POINTS)
                            log_info(t("loop.verify_pts", pts=detected_points, max=target_points))

                            # If OCR is known to sometimes miss digits (e.g. 999 read as 99), we should be careful.
                            # However, if target_points is used, it will at least stop when target_points is 500.
                            if detected_points >= target_points:
                                log_success(t("loop.verify_ok", pts=detected_points, max=target_points))
                                verified_999 = True
                            else:
                                shortfall = target_points - detected_points
                                extra_races = max(1, shortfall // 10 + 1)
                                log_warning(t("loop.verify_low", pts=detected_points, diff=shortfall))
                                log_info(t("loop.verify_extra", races=extra_races))
                                try:
                                    module_farm_skills.clear_race_state()
                                except (ImportError, AttributeError) as cleanup_err:
                                    log_warning(f"Failed to clear race state: {cleanup_err}")
                                time.sleep(2.0)
                        else:
                            log_warning(t("loop.verify_ocr_fail"))
                            verified_999 = True

                    from engine.runtime import load_bot_config

                    config = load_bot_config()
                    target_points = config.get("target_points", MAX_SKILL_POINTS)
                    log_success(t("loop.farm_done", max=target_points))

                    if skip_buy:
                        current_state = STATE_UPGRADE_CARS
                        log_info(t("loop.transition_skip_buy"))
                    else:
                        current_state = STATE_BUY_CARS
                        log_info(t("loop.transition_new_cycle"))
                    if not loop:
                        log_success(t("loop.farm_single_done"))
                        return
                    loop_count += 1
                    time.sleep(2.0)

                # 本轮 state 正常完成（未抛异常）→ 重置连续错误计数
                consecutive_errors = 0

            except BotStoppedError:
                raise
            except pytesseract.TesseractNotFoundError:
                # OCR 环境缺失属致命错误，重试无意义 → 直接终止，避免无限 5s 死循环
                log_error(t("loop.ocr_unavailable"))
                raise
            except Exception as e:
                consecutive_errors += 1
                log_error(t("loop.state_error", state=current_state, err=e))
                if consecutive_errors >= MAX_CONSECUTIVE_STATE_ERRORS:
                    log_error(t("loop.too_many_errors", n=consecutive_errors))
                    raise
                log_warning(t("loop.state_retry"))
                time.sleep(5.0)
                continue

    except BotStoppedError:
        log_warning("==================================================")
        log_warning(t("loop.user_stop"))
        log_warning("==================================================")
    except KeyboardInterrupt:
        print()
        log_warning("==================================================")
        log_warning(t("loop.kb_interrupt"))
        log_warning(t("loop.kb_releasing"))
        log_warning("==================================================")
        sys.exit(0)
    finally:
        # 无论何种原因退出（正常完成 / Web 停止 / 异常 / Ctrl-C），都释放虚拟手柄所有按键
        # 并重置 MSS——避免停止后游戏仍收到残留输入，或损坏的 GDI 句柄影响下次启动。
        # （farm 阶段已自行清理油门/手柄，此处是覆盖 BUY/UPGRADE/TRASH 阶段的安全网。）
        try:
            gamepad.reset()
            gamepad.update()
        except Exception:
            pass  # 手柄清理失败不应掩盖正在传播的退出原因
        try:
            from engine.utils import reset_mss

            reset_mss()
        except (ImportError, OSError):
            pass
        log_info(t("loop.teardown_done"))
