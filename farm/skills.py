# -*- coding: utf-8 -*-
"""
FH6_AutoBot EventLab 自动跑图模块 (module_farm_skills.py)
=========================================================
本模块负责"刷技能点"阶段的全部逻辑：

  从暂停菜单出发，自动导航进入 EventLab -> 选择收藏蓝图赛事
  -> 选车 -> 开始比赛 -> 全程按住 RT 加速 -> 检测终点 -> 重启/退出

核心设计 - 视觉状态机 (Visual State Machine)：
  使用 StateDetector (OCR + 亮度分析) 对每帧截图进行状态检测，
  识别当前处于游戏的哪个 UI 状态（菜单标签 / EventLab / 赛道 / 结算画面），
  然后根据状态执行对应的手柄操作。

额外功能:
  - OCR 读取技能点数字，支持断点续跑 (race_state.json)
  - 安全超时（12 小时上限）
  - Rate Event 弹窗自动关闭

架构说明 (P0-3 重构):
  原 main() 中 480 行的 while True 循环已拆分为 FarmStateMachine 类，
  每个状态处理逻辑独立为 <40 行的方法，提高可读性与可维护性。
"""

import datetime
import json
import math
import os
import time

import cv2
import numpy as np
import pytesseract
import vgamepad as vg
from colorama import Fore, Style

import engine.ocr as module_ocr
from engine.i18n import t
from engine.ocr import DEBUG_WRITE_FILES
from engine.state_detect import get_detector
from engine.utils import (
    find_game_window,
    force_foreground,
    get_client_rect,
    get_mss,
    log_error,
    log_info,
    log_success,
    log_warning,
    press_button,
    safe_print,
)

# ==========================================
# 辅助函数（无状态）
# ==========================================


def get_matches_needed(current_points: int) -> int:
    """根据当前技能点和用户配置计算还需要跑多少场比赛。

    从 data/bot_config.json 读取 points_per_match（单局点数）和
    target_points（目标点数），支持不同蓝图的自定义。
    """
    from engine.runtime import load_bot_config

    config = load_bot_config()
    max_points = config["target_points"]
    points_per_match = max(1, config["points_per_match"])  # 防止除零
    matches_needed = math.ceil((max_points - current_points) / points_per_match)
    # 限制单次任务最大场次，防止极端情况下的超长跑图
    matches_needed = min(max(0, matches_needed), 120)
    return matches_needed


def _get_archive_path() -> str:
    """返回比赛归档文件路径 (data/play_archive.jsonl)。"""
    from engine.runtime import get_data_dir

    return os.path.join(get_data_dir(), "play_archive.jsonl")


def _get_race_state_path() -> str:
    """返回比赛状态文件路径 (data/race_state.json)。"""
    from engine.runtime import get_data_dir

    return os.path.join(get_data_dir(), "race_state.json")


# 保留常量以兼容测试 — 指向新路径
RACE_STATE_FILE = _get_race_state_path()


def archive_match_to_file(match_num: int, remaining_matches: int) -> None:
    """将比赛完成记录以 JSONL 格式追加到 data/play_archive.jsonl。

    每行一条 JSON 记录，便于程序回读分析。
    """
    archive_path = _get_archive_path()
    record = {
        "ts": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "type": "race",
        "match": match_num,
        "remaining": remaining_matches,
        "status": "success",
    }

    try:
        with open(archive_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        log_success(t("farm.archived", path=archive_path))
        from engine.event_bus import get_bus

        get_bus().emit("match_archived", record)
    except IOError as e:
        log_error(t("farm.archive_fail", err=e))


def archive_upgrade_to_file(car_name: str = "Impreza", wheelspins: int = 1) -> None:
    """将车辆升级记录（获得超级轮盘）以 JSONL 格式追加到 data/play_archive.jsonl。"""
    archive_path = _get_archive_path()
    record = {
        "ts": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "type": "upgrade",
        "car": car_name,
        "wheelspins": wheelspins,
    }

    try:
        with open(archive_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        log_success(f"Archived upgrade event: {car_name} (+{wheelspins} Super Wheelspin)")
        from engine.event_bus import get_bus

        get_bus().emit("match_archived", record)  # 触发事件广播以更新前端统计
    except IOError as e:
        log_error(t("farm.archive_fail", err=e))


# ==========================================
# 比赛状态持久化（断点续跑）
# ==========================================


def save_race_state(matches_needed: int, matches_completed: int) -> None:
    """保存比赛进度到 data/race_state.json，支持断点续跑。"""
    state_path = _get_race_state_path()
    state = {
        "matches_needed": matches_needed,
        "matches_completed": matches_completed,
        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        log_info(t("farm.state_saved", remain=matches_needed, done=matches_completed))
    except IOError as e:
        log_error(f"Failed to save race state: {e}")


def load_race_state() -> tuple[int, int, str] | None:
    """加载已保存的比赛进度，用于断点续跑。"""
    state_path = _get_race_state_path()
    if not os.path.exists(state_path):
        return None
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)

        matches_needed = state.get("matches_needed", 0)
        matches_completed = state.get("matches_completed", 0)
        last_updated = str(state.get("last_updated", "unknown"))

        # 类型与范围校验 (SEC-3)
        if not isinstance(matches_needed, int) or matches_needed < 0:
            matches_needed = 0
        if not isinstance(matches_completed, int) or matches_completed < 0:
            matches_completed = 0

        if matches_needed > 0:
            return matches_needed, matches_completed, last_updated
        return None
    except (IOError, json.JSONDecodeError) as e:
        log_error(f"Failed to load race state: {e}")
        return None


def clear_race_state() -> None:
    """所有比赛完成后清除状态文件。"""
    state_path = _get_race_state_path()
    try:
        if os.path.exists(state_path):
            os.remove(state_path)
            log_success(t("farm.state_cleared", path=state_path))
    except OSError as e:
        log_error(t("farm.state_clear_fail", err=e))


# ==========================================
# FarmStateMachine — 视觉状态机（P0-3 重构）
# ==========================================


class FarmStateMachine:
    """
    EventLab 自动跑图视觉状态机。

    将原 main() 中 480 行的 while-True 循环拆分为独立方法：
      - tick()                  → 单帧主入口
      - _handle_rate_popup()    → Rate Event 弹窗检测
      - _handle_racing()        → 比赛中（持续 RT + 检测终点）
      - _handle_race_end()      → 比赛结束结算
      - _handle_waiting_next()  → 等待 Next 结算画面
      - _handle_waiting_gameplay() → 等待回到自由漫游
      - _handle_startup_guard() → 启动安全守卫
      - _handle_outside_race_end() → 脚本重启时比赛结束检测
      - _handle_menu_state()    → 菜单状态机分发
    """

    def __init__(self, gamepad: vg.VX360Gamepad, hwnd: int | None, detector, sct) -> None:
        """初始化状态机。

        Args:
            gamepad: 虚拟手柄实例
            hwnd: 游戏窗口句柄
            detector: StateDetector 实例
            sct: MSS 截图实例
        """
        self.gamepad = gamepad
        self.hwnd = hwnd
        self.detector = detector
        self.sct = sct

        # 状态标志
        self.is_racing: bool = False
        self.entering_race: bool = False
        self.waiting_for_next: bool = False
        self.waiting_for_gameplay: bool = False
        self._wait_next_start: float = 0.0  # 进入 waiting_for_next 的时间戳
        self.points_scanned: bool = False
        self.ocr_fail_count: int = 0

        # 计数器
        self.matches_needed: int = 0
        self.matches_completed: int = 0
        self.unknown_consecutive_count: int = 0

        # 时间控制
        self.racing_print_timer: float = 0
        self.rect_update_timer: float = 0

        # 缓存的窗口客户区坐标
        self.cw: int = 2560
        self.ch: int = 1440
        self.cx: int = 0
        self.cy: int = 0

        # 标记是否应退出循环
        self.should_exit: bool = False

    def load_saved_state(self) -> None:
        """尝试加载已保存的比赛进度（仅恢复完成场次，技能点重新扫描）。"""
        saved_state = load_race_state()
        if saved_state is not None:
            _, self.matches_completed, last_updated = saved_state
            # 不设置 points_scanned = True，确保启动后先去 CARS 扫描最新技能点
            safe_print(f"\n{Fore.CYAN}{Style.BRIGHT}==========================================")
            safe_print(t("farm.resume_title"))
            safe_print(t("farm.resume_completed", count=self.matches_completed))
            safe_print(t("farm.resume_updated", time=last_updated))
            safe_print(t("farm.resume_scan"))
            safe_print("==========================================\n")

    def _update_client_rect(self) -> None:
        """每 2 秒刷新一次窗口客户区坐标（避免每帧调用）。"""
        now = time.time()
        if now - self.rect_update_timer > 2.0:
            if self.hwnd:
                try:
                    self.cx, self.cy, self.cw, self.ch = get_client_rect(self.hwnd)
                except OSError as e:
                    log_warning(t("farm.client_rect_fail", err=e))
            self.rect_update_timer = now

    def _capture_frame(self) -> tuple[np.ndarray | None, np.ndarray | None]:
        """截取游戏画面并缩放。

        Returns:
            (resized_1600x900, original_img) 或 (None, None)
        """
        try:
            # Defense: skip grab if window coords are invalid (minimized/hidden)
            if self.cw <= 0 or self.ch <= 0:
                log_warning(t("farm.invalid_region", w=self.cw, h=self.ch))
                return None, None
            monitor = {"top": self.cy, "left": self.cx, "width": self.cw, "height": self.ch}
            screenshot = self.sct.grab(monitor)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            resized = cv2.resize(img, (1600, 900), interpolation=cv2.INTER_AREA)
            return resized, img
        except Exception as e:
            log_error(t("farm.capture_fail", err=e))
            # Auto-recovery: reset MSS instance and re-foreground the window
            # BitBlt failure corrupts the GDI DC; a fresh MSS instance fixes it
            try:
                from engine.utils import reset_mss

                reset_mss()
                self.sct = get_mss()
                log_info(t("farm.capture_retry"))
                # Re-foreground the game window (BitBlt often fails when window lost focus)
                if self.hwnd:
                    force_foreground(self.hwnd)
            except Exception as reset_err:
                log_warning(t("farm.capture_reset_fail", err=reset_err))
            return None, None

    # ===================================================================
    #  弹窗检测
    # ===================================================================

    def _handle_rate_popup(self, resized: np.ndarray) -> bool:
        """检测并关闭 Rate Event 弹窗。返回 True 表示已处理。"""
        try:
            h_frame = resized.shape[0]
            banner_roi = resized[0 : int(h_frame * 0.15), :]
            hsv_banner = cv2.cvtColor(banner_roi, cv2.COLOR_BGR2HSV)
            ygmask = cv2.inRange(hsv_banner, np.array([25, 150, 200]), np.array([45, 255, 255]))
            yg_pixels = cv2.countNonZero(ygmask)
            if yg_pixels > 5000:
                gray_banner = cv2.cvtColor(banner_roi, cv2.COLOR_BGR2GRAY)
                _, thresh_banner = cv2.threshold(gray_banner, 100, 255, cv2.THRESH_BINARY_INV)
                banner_text = pytesseract.image_to_string(thresh_banner).strip().lower()
                if "rate" in banner_text or "event" in banner_text:
                    log_success(t("farm.rate_popup", count=yg_pixels))
                    press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.0)
                    return True
        except (cv2.error, pytesseract.TesseractError) as e:
            log_warning(t("farm.rate_popup_error", err=e))
        return False

    # ===================================================================
    #  比赛状态处理
    # ===================================================================

    def _handle_racing(self, resized: np.ndarray) -> None:
        """比赛中：持续按住 RT + 扫描 RACE_END。"""
        self.gamepad.right_trigger(value=255)
        self.gamepad.update()

        if time.time() - self.racing_print_timer > 2.0:
            log_info(t("farm.racing_rt"))
            self.racing_print_timer = time.time()

        racing_state = self.detector.detect(resized, mode="racing")
        if racing_state == "RACE_END":
            self._handle_race_end()

        time.sleep(0.1)

    def _handle_race_end(self) -> None:
        """比赛结束：释放 RT、更新计数器、决定重启或退出。"""
        self.gamepad.right_trigger(value=0)
        self.gamepad.update()
        time.sleep(0.5)

        self.matches_completed += 1
        remaining_matches = max(0, self.matches_needed - 1)
        archive_match_to_file(self.matches_completed, remaining_matches)

        safe_print(f"\n{Fore.GREEN}{Style.BRIGHT}==========================================")
        safe_print(t("farm.match_done_title"))
        safe_print(t("farm.match_done_num", count=self.matches_completed))
        safe_print(t("farm.match_done_orig", count=self.matches_needed))
        safe_print(t("farm.match_done_remain", count=remaining_matches))
        safe_print("==========================================\n")

        self.matches_needed = remaining_matches
        save_race_state(self.matches_needed, self.matches_completed)

        if remaining_matches > 0:
            log_success(t("farm.restart_race", remain=remaining_matches))
            press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_X, delay=0)
            time.sleep(1.0)
            press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=0)
            self.is_racing = False
            self.entering_race = True  # 防止过渡画面误识别为菜单标签（如 STORE）触发 RB
            time.sleep(3.0)
        else:
            log_success(t("farm.all_done", count=self.matches_completed))
            press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=0)
            self.is_racing = False
            self.waiting_for_next = True
            self._wait_next_start = time.time()
            log_info(t("farm.wait_next"))

    _WAIT_NEXT_TIMEOUT: float = 20.0  # 超时阈值（秒）
    _WAIT_NEXT_RETRY_INTERVAL: float = 5.0  # 超时后重试按 A 间隔
    _WAIT_NEXT_FORCE_EXIT: float = 60.0  # 强制退出阈值

    def _handle_waiting_next(self, resized: np.ndarray) -> None:
        """Wait for the 'What's Next' screen after reward animation.

        Includes timeout + fallback:
        - Detects NEXT_SCREEN → press B to exit.
        - Detects PLAYING (free-roam) → press START to open menu directly.
        - After 20s timeout → press A every 5s to advance reward animation.
        - After 60s → force exit to waiting_for_gameplay.
        """
        elapsed = time.time() - self._wait_next_start
        next_state = self.detector.detect(resized, mode="racing")

        # 正常路径：检测到 NEXT_SCREEN
        if next_state == "NEXT_SCREEN":
            log_success(t("farm.next_found"))
            press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_B, delay=0)
            self.waiting_for_next = False
            self.waiting_for_gameplay = True
            log_info(t("farm.wait_gameplay"))
            return

        # Fallback：已经回到自由漫游（跳过了 Next 画面）
        if next_state == "PLAYING":
            log_warning(t("farm.wait_next_skip_playing"))
            press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_START, delay=0)
            self.waiting_for_next = False
            self.waiting_for_gameplay = False
            time.sleep(2.5)
            # 走后续菜单状态机逻辑
            if self.matches_needed <= 0:
                clear_race_state()
                safe_print(f"\n{Fore.GREEN}{Style.BRIGHT}==========================================")
                safe_print(f"{Fore.GREEN}{Style.BRIGHT}{t('farm.goal_reached_title')}")
                safe_print(f"{Fore.GREEN}{Style.BRIGHT}{t('farm.goal_reached_desc')}")
                safe_print(t("farm.goal_reached_menu"))
                safe_print(f"{Fore.GREEN}{Style.BRIGHT}==========================================\n")
                self.should_exit = True
            return

        # 超时强制退出（60s）：放弃等待，直接进入 gameplay 检测
        if elapsed > self._WAIT_NEXT_FORCE_EXIT:
            log_warning(t("farm.wait_next_force_exit", sec=int(elapsed)))
            press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_B, delay=0)
            self.waiting_for_next = False
            self.waiting_for_gameplay = True
            return

        # 超时重试（20s 后每 5s 按一次 A 推进奖励动画）
        if elapsed > self._WAIT_NEXT_TIMEOUT:
            interval_count = int((elapsed - self._WAIT_NEXT_TIMEOUT) / self._WAIT_NEXT_RETRY_INTERVAL)
            expected_time = self._WAIT_NEXT_TIMEOUT + interval_count * self._WAIT_NEXT_RETRY_INTERVAL
            # 每个 interval 触发一次 A 按键（容差 0.3s）
            if abs(elapsed - expected_time) < 0.3:
                log_warning(t("farm.wait_next_timeout_retry", sec=int(elapsed)))
                press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_B, delay=0)

        time.sleep(0.2)

    def _handle_waiting_gameplay(self, resized: np.ndarray) -> None:
        """等待回到自由漫游，按 START 打开暂停菜单。"""
        play_state = self.detector.detect(resized, mode="racing")
        if play_state == "PLAYING":
            log_success(t("farm.gameplay_found"))
            press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_START, delay=0)
            self.waiting_for_gameplay = False
            time.sleep(2.5)

            if self.matches_needed <= 0:
                clear_race_state()
                safe_print(f"\n{Fore.GREEN}{Style.BRIGHT}==========================================")
                safe_print(f"{Fore.GREEN}{Style.BRIGHT}{t('farm.goal_reached_title')}")
                safe_print(f"{Fore.GREEN}{Style.BRIGHT}{t('farm.goal_reached_desc')}")
                safe_print(t("farm.goal_reached_menu"))
                safe_print(f"{Fore.GREEN}{Style.BRIGHT}==========================================\n")
                self.should_exit = True
        time.sleep(0.2)

    # ===================================================================
    #  启动守卫和恢复逻辑
    # ===================================================================

    def _handle_startup_guard(self, resized: np.ndarray) -> bool:
        """如果启动时在自由漫游画面，自动按 START 打开菜单。返回 True 表示已处理。"""
        if not self.points_scanned and not self.is_racing and not self.waiting_for_gameplay:
            startup_state = self.detector.detect(resized, mode="racing")
            if startup_state == "PLAYING":
                log_success(t("farm.startup_guard"))
                press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_START, delay=2.5)
                return True
        return False

    def _handle_outside_race_end(self, resized: np.ndarray) -> bool:
        """检测非比赛模式下的 RACE_END（脚本重启恢复场景）。返回 True 表示已处理。"""
        if self.points_scanned and not self.is_racing and not self.waiting_for_next and not self.waiting_for_gameplay:
            outside_state = self.detector.detect(resized, mode="racing")
            if outside_state == "RACE_END":
                log_success(t("farm.outside_race_end"))
                self.matches_completed += 1
                remaining_matches = max(0, self.matches_needed - 1)
                archive_match_to_file(self.matches_completed, remaining_matches)

                safe_print(f"\n{Fore.GREEN}{Style.BRIGHT}==========================================")
                safe_print(t("farm.match_done_title"))
                safe_print(t("farm.match_done_num", count=self.matches_completed))
                safe_print(t("farm.match_done_orig", count=self.matches_needed))
                safe_print(t("farm.match_done_remain", count=remaining_matches))
                safe_print("==========================================\n")

                self.matches_needed = remaining_matches
                save_race_state(self.matches_needed, self.matches_completed)

                if remaining_matches > 0:
                    log_success(t("farm.restart_race", remain=remaining_matches))
                    press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_X, delay=1.0)
                    press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=0)
                    self.entering_race = True  # 防止过渡画面误识别为菜单标签
                    time.sleep(3.0)
                else:
                    log_success(t("farm.all_done", count=self.matches_completed))
                    press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=0)
                    self.waiting_for_next = True
                    self._wait_next_start = time.time()
                    log_info(t("farm.wait_next"))
                return True
        return False

    # ===================================================================
    #  菜单状态处理
    # ===================================================================

    def _handle_menu_state(self, state: str, img: np.ndarray) -> None:
        """根据 StateDetector 返回的菜单状态执行对应操作。

        Args:
            state: 检测到的状态字符串
            img: 原始分辨率截图（供 OCR 使用）
        """
        if state != "UNKNOWN":
            self.unknown_consecutive_count = 0
            if self.waiting_for_gameplay:
                log_success(t("farm.reenter_menu"))
                self.waiting_for_gameplay = False

        # 安全守卫：初始 OCR 扫描前不允许进入子菜单
        if not self.points_scanned:
            if state in ["EVENTLAB_MENU", "EVENTS_SUBMENU", "FAVORITES_LIST", "RACE_READY", "CAR_SELECT", "PRE_RACE"]:
                log_warning(t("farm.safety_guard", state=state))
                press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_B, delay=1.5)
                return

        if state == "CARS" and not self.entering_race:
            self._on_cars_tab(img)
        elif state in ["CAMPAIGN", "MY HORIZON", "ONLINE", "STORE"] and not self.entering_race:
            self._on_other_tab(state)
        elif state in ["CREATIVE_HUB", "CREATIVE HUB"] and not self.entering_race:
            self._on_creative_hub()
        elif state == "EVENTLAB_MENU":
            self._on_eventlab_menu()
        elif state == "EVENTS_SUBMENU":
            self._on_events_submenu()
        elif state == "FAVORITES_LIST":
            self._on_favorites_list()
        elif state in ["RACE_READY", "choose"]:
            self._on_race_ready()
        elif state == "CAR_SELECT":
            self._on_car_select()
        elif state == "PRE_RACE":
            self._on_pre_race()
        else:
            self._on_unknown(state)

    def _on_cars_tab(self, img: np.ndarray) -> None:
        """CARS 标签页：OCR 读取技能点并决定后续操作。"""
        safe_print(f"{Fore.GREEN}{Style.BRIGHT}{t('farm.cars_scan')}{Style.RESET_ALL}")
        detected_points = module_ocr.read_skill_points(img)
        if detected_points is not None:
            self.ocr_fail_count = 0  # 成功后重置计数
            self.matches_needed = get_matches_needed(detected_points)
            safe_print(f"\n{Fore.GREEN}{Style.BRIGHT}==========================================")
            safe_print(t("farm.scan_ok_title"))
            safe_print(t("farm.scan_ok_points", pts=detected_points))
            safe_print(t("farm.scan_ok_needed", count=self.matches_needed))
            safe_print("==========================================\n")
            self.points_scanned = True
            save_race_state(self.matches_needed, self.matches_completed)

            if self.matches_needed <= 0:
                safe_print(f"\n{Fore.GREEN}{Style.BRIGHT}==========================================")
                safe_print(t("farm.already_full_title"))
                safe_print(t("farm.already_full_desc", pts=detected_points))
                safe_print("==========================================\n")
                self.should_exit = True
                return

            safe_print(f"{Fore.YELLOW}{t('farm.cars_shift_rb')}{Style.RESET_ALL}")
            press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER, delay=0.5)
        else:
            if not self.points_scanned:
                self.ocr_fail_count += 1
                if self.ocr_fail_count >= 10:
                    log_warning(
                        "OCR failed to read skill points 10 times consecutively. Assuming zero points as fallback to avoid infinite loops."
                    )
                    # 假装读取到0点
                    self.matches_needed = get_matches_needed(0)
                    self.points_scanned = True
                    save_race_state(self.matches_needed, self.matches_completed)
                    safe_print(f"{Fore.YELLOW}{t('farm.cars_shift_rb')}{Style.RESET_ALL}")
                    press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER, delay=0.5)
                else:
                    log_warning(t("farm.ocr_fail_retry"))
                    time.sleep(0.5)
            else:
                log_warning(t("farm.ocr_fail_use", count=self.matches_needed))
                safe_print(f"{Fore.YELLOW}{t('farm.cars_shift_rb')}{Style.RESET_ALL}")
                press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER, delay=0.5)

    def _on_other_tab(self, state: str) -> None:
        """非目标标签页：按 RB 翻页。"""
        safe_print(f"{Fore.YELLOW}{t('farm.other_tab', state=state)}{Style.RESET_ALL}")
        press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER, delay=0.5)

    def _on_creative_hub(self) -> None:
        """Creative Hub 标签页：进入 EventLab。"""
        if not self.points_scanned:
            safe_print(f"{Fore.YELLOW}{t('farm.hub_bypass')}{Style.RESET_ALL}")
            press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER, delay=0.5)
        else:
            safe_print(f"{Fore.GREEN}{Style.BRIGHT}{t('farm.hub_enter')}{Style.RESET_ALL}")
            press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.5)

    def _on_eventlab_menu(self) -> None:
        """EventLab 菜单：选择 Play Event。"""
        safe_print(f"{Fore.GREEN}{Style.BRIGHT}{t('farm.eventlab_menu')}{Style.RESET_ALL}")
        press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.5)

    def _on_events_submenu(self) -> None:
        """Events 子菜单：按 RB 找 My Favorites。"""
        safe_print(f"{Fore.YELLOW}{t('farm.events_sub')}{Style.RESET_ALL}")
        press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER, delay=0.5)

    def _on_favorites_list(self) -> None:
        """My Favorites 列表：选中蓝图并进入。"""
        self.entering_race = True
        safe_print(f"{Fore.GREEN}{Style.BRIGHT}{t('farm.favorites')}{Style.RESET_ALL}")
        press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=3.0)

    def _on_race_ready(self) -> None:
        """比赛类型选择：确保 Solo 选中并启动。"""
        safe_print(f"\n{Fore.GREEN}{Style.BRIGHT}==========================================")
        safe_print(t("farm.race_ready_title"))
        safe_print(t("farm.race_ready_solo"))
        safe_print("==========================================\n")

        for button in [vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP, vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT]:
            for _ in range(2):
                press_button(self.gamepad, button, delay=0.3)

        press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=0)
        safe_print(f"{Fore.GREEN}{t('farm.solo_ok')}{Style.RESET_ALL}")
        time.sleep(1.5)

    def _on_car_select(self) -> None:
        """车辆选择：直接确认当前车辆。"""
        safe_print(f"\n{Fore.GREEN}{Style.BRIGHT}==========================================")
        safe_print(t("farm.car_select"))
        safe_print("==========================================\n")
        press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=3.0)

    def _on_pre_race(self) -> None:
        """赛事准备界面：按 A 开始比赛，切换到 racing 模式。"""
        safe_print(f"\n{Fore.GREEN}{Style.BRIGHT}==========================================")
        safe_print(t("farm.pre_race_title"))
        safe_print(t("farm.pre_race_launch"))
        safe_print("==========================================\n")

        press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=0)
        log_success(t("farm.race_start"))
        self.is_racing = True
        self.entering_race = False
        self.racing_print_timer = time.time()
        time.sleep(3.0)

    def _on_unknown(self, state: str) -> None:
        """UNKNOWN 状态：等待 UI 加载 + 自动恢复。"""
        self.unknown_consecutive_count += 1
        safe_print(
            f"{Fore.BLUE}{t('farm.unknown_wait', state=state, count=self.unknown_consecutive_count)}{Style.RESET_ALL}"
        )

        if self.unknown_consecutive_count % 5 == 1 and DEBUG_WRITE_FILES:
            os.makedirs("debug", exist_ok=True)
            try:
                resized, img = self._capture_frame()
                if img is not None:
                    cv2.imwrite("debug/unknown_state.png", img)
            except (OSError, cv2.error) as e:
                log_warning(t("ocr.debug_write_fail", path="unknown_state.png", err=e))

        # 自动恢复
        if self.unknown_consecutive_count >= 15 and not self.waiting_for_gameplay:
            if self.unknown_consecutive_count % 15 == 0:
                log_warning(t("farm.recovery_b", count=self.unknown_consecutive_count))
                press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_B, delay=1.0)
            if self.unknown_consecutive_count % 30 == 0:
                log_warning(t("farm.recovery_start"))
                press_button(self.gamepad, vg.XUSB_BUTTON.XUSB_GAMEPAD_START, delay=1.0)
            if self.unknown_consecutive_count % 60 == 0:
                log_warning(t("farm.recovery_focus"))
                recovery_hwnd = find_game_window()
                if recovery_hwnd:
                    force_foreground(recovery_hwnd)
                time.sleep(2.0)

        # 诊断警告
        if self.unknown_consecutive_count >= 5 and not self.waiting_for_gameplay:
            log_warning("=" * 66)
            log_warning(t("farm.diag_title"))
            log_warning(t("farm.diag_hint"))
            log_warning("=" * 66)

        time.sleep(0.5)

    # ===================================================================
    #  主循环单帧处理
    # ===================================================================

    def tick(self) -> None:
        """处理单帧截图，驱动状态机转换。

        调用者应在 while-not-should_exit 循环中反复调用此方法。
        """
        self._update_client_rect()

        resized, img = self._capture_frame()
        if resized is None:
            time.sleep(0.5)
            return

        # Rate Event 弹窗
        if self._handle_rate_popup(resized):
            return

        # 比赛中
        if self.is_racing:
            self._handle_racing(resized)
            return

        # 等待 Next 画面
        if self.waiting_for_next:
            self._handle_waiting_next(resized)
            return

        # 等待回到自由漫游
        if self.waiting_for_gameplay:
            self._handle_waiting_gameplay(resized)
            return

        # 启动安全守卫
        if self._handle_startup_guard(resized):
            return

        # 脚本重启恢复
        if self._handle_outside_race_end(resized):
            return

        # 菜单状态机
        state = self.detector.detect(resized, mode="menu")
        self._handle_menu_state(state, img)


# ==========================================
# 入口函数（保持向后兼容）
# ==========================================


def main(gamepad: vg.VX360Gamepad | None = None) -> None:
    """
    EventLab 自动跑图入口。

    初始化 Tesseract / GamePad / Window 等依赖，然后委托给
    FarmStateMachine 驱动状态循环。
    """
    safe_print(f"\n{Fore.MAGENTA}{Style.BRIGHT}==================================================")
    safe_print(f"{Fore.MAGENTA}{Style.BRIGHT}{t('farm.title')}")
    safe_print(f"{Fore.MAGENTA}{Style.BRIGHT}=================================================={Style.RESET_ALL}\n")

    # 1. Initialize Tesseract
    module_ocr.setup_tesseract()

    safe_print(f"\n{Fore.YELLOW}==================================================")
    safe_print(t("farm.ocr_title"))
    safe_print(t("farm.ocr_subtitle"))
    safe_print(f"=================================================={Style.RESET_ALL}")

    # 2. Initialize State Detector (单例)
    detector = get_detector()
    log_info(t("farm.detector_init"))

    # 3. Game Window Check & Activation
    hwnd = find_game_window()
    if hwnd:
        log_success(t("farm.window_found"))
        force_foreground(hwnd)
    else:
        log_warning(t("farm.window_missing"))

    # 4. Gamepad Initialization
    owns_gamepad = False
    if gamepad is None:
        log_info(t("farm.init_controller"))
        try:
            gamepad = vg.VX360Gamepad()
            owns_gamepad = True
            log_success(t("farm.controller_ok"))
        except Exception as e:
            raise RuntimeError(f"Failed to initialize virtual controller: {e}") from e
    else:
        log_info(t("farm.controller_reuse"))

    # 倒计时（无自动聚焦时）
    if not hwnd:
        print()
        for i in range(5, 0, -1):
            safe_print(
                f"\r{Fore.YELLOW}[WAIT]{Style.RESET_ALL} {t('farm.switch_window', sec=i)}",
                end="",
                flush=True,
            )
            time.sleep(1.0)
        print("\n")

    log_info(t("farm.loop_start"))

    # 5. 创建状态机并加载保存的进度
    sct = get_mss()
    fsm = FarmStateMachine(gamepad, hwnd, detector, sct)
    fsm.load_saved_state()

    max_runtime_hours = 12
    start_time = time.time()

    try:
        while not fsm.should_exit:
            elapsed_hours = (time.time() - start_time) / 3600
            if elapsed_hours >= max_runtime_hours:
                break
            fsm.tick()

        elapsed_hours = (time.time() - start_time) / 3600
        if elapsed_hours >= max_runtime_hours:
            raise RuntimeError(t("farm.timeout", hours=elapsed_hours))
    finally:
        try:
            gamepad.right_trigger(value=0)
            gamepad.update()
            if owns_gamepad:
                gamepad.reset()
                gamepad.update()
                log_info(t("farm.controller_released"))
            else:
                log_info(t("farm.controller_retained"))
        except OSError as e:
            log_warning(t("farm.controller_cleanup_fail", err=e))
        # 注意: 不关闭 sct (MSS 全局单例)


if __name__ == "__main__":
    main()
