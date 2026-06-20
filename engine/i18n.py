# -*- coding: utf-8 -*-
"""
engine/i18n.py — Centralized internationalization (i18n) module.
================================================================
Holds all user-facing translatable strings in English and Chinese.
Modules call ``t("key", **kwargs)`` to get the localized message.

Usage:
    from engine.i18n import set_lang, t

    set_lang("zh")              # once at startup
    log_info(t("ctrl_connected"))  # everywhere else
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Global language state
# ---------------------------------------------------------------------------

_lang: str = "en"


def set_lang(lang: str) -> None:
    """Set the active display language.

    Args:
        lang: ``"en"`` or ``"zh"``.
    """
    global _lang
    _lang = lang


def t(key: str, **kwargs) -> str:
    """Look up a translated string and apply ``str.format(**kwargs)``.

    Falls back to English if the key is missing for the current language,
    then to the raw key if neither language has it.

    Args:
        key: Translation key (e.g. ``"farm.racing_hold_rt"``).
        **kwargs: Format parameters (e.g. ``count=5``).
    """
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(_lang, entry.get("en", key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


# ---------------------------------------------------------------------------
# Translation table — organized by module prefix
# ---------------------------------------------------------------------------

_STRINGS: dict[str, dict[str, str]] = {
    # ==================================================================
    #  macro/core.py
    # ==================================================================
    "core.current_state": {
        "en": "   🔥 Current State: {state}",
        "zh": "   🔥 当前状态: {state}",
    },
    "core.task_desc": {
        "en": "   👉 Task: {desc}",
        "zh": "   👉 任务描述: {desc}",
    },
    "core.nav_step": {
        "en": "    [Navigation Step {num}] {title}",
        "zh": "    [导航第 {num} 步] {title}",
    },
    "core.window_minimized": {
        "en": "Game window is minimized, restoring...",
        "zh": "游戏窗口已最小化，正在恢复...",
    },
    "core.capture_fail": {
        "en": "Screenshot capture failed: {err}",
        "zh": "截图捕获失败: {err}",
    },
    "core.coord_fail": {
        "en": "Failed to get window coordinates: {err}. Using full screen.",
        "zh": "获取窗口坐标失败: {err}. 默认使用全屏。",
    },
    "core.mss_reset": {
        "en": "MSS screenshot instance reset",
        "zh": "MSS 截图实例已重置",
    },
    # ==================================================================
    #  farm/skills.py — main entry
    # ==================================================================
    "farm.title": {
        "en": "   FORZA HORIZON 6 AUTOMATED RACE ENTRY - STATE MACHINE",
        "zh": "   FORZA HORIZON 6 自动跑图状态机",
    },
    "farm.ocr_title": {
        "en": "   OCR-ONLY SKILL POINTS SCANNER",
        "zh": "   OCR 技能点扫描器",
    },
    "farm.ocr_subtitle": {
        "en": "   (Must visit CARS menu tab to scan points initially)",
        "zh": "   (需先访问 CARS 标签页扫描技能点)",
    },
    "farm.detector_init": {
        "en": "StateDetector initialized (Color Histogram + OCR hybrid)",
        "zh": "StateDetector 已初始化 (颜色直方图 + OCR 混合模式)",
    },
    "farm.window_found": {
        "en": "Forza Horizon 6 game window detected.",
        "zh": "已检测到 Forza Horizon 6 游戏窗口。",
    },
    "farm.window_missing": {
        "en": "Forza Horizon 6 window not found! Running in fallback mode.",
        "zh": "未找到 Forza Horizon 6 窗口！将使用备用模式运行。",
    },
    "farm.init_controller": {
        "en": "Initializing virtual Xbox 360 controller...",
        "zh": "正在初始化虚拟 Xbox 360 控制器...",
    },
    "farm.controller_ok": {
        "en": "Virtual controller successfully initialized.",
        "zh": "虚拟控制器初始化成功。",
    },
    "farm.controller_reuse": {
        "en": "Reusing existing virtual controller from parent module.",
        "zh": "复用父模块传入的虚拟控制器。",
    },
    "farm.switch_window": {
        "en": "Please switch to the Forza Horizon 6 window... {sec}s remaining",
        "zh": "请切换到 Forza Horizon 6 窗口... 剩余 {sec} 秒",
    },
    "farm.loop_start": {
        "en": "Starting Real-time Visual State Machine loop (Press Ctrl+C to terminate)...",
        "zh": "启动实时视觉状态机循环 (按 Ctrl+C 终止)...",
    },
    "farm.controller_released": {
        "en": "Virtual controller safely released.",
        "zh": "虚拟控制器已安全释放。",
    },
    "farm.controller_retained": {
        "en": "RT released. Controller ownership retained by parent module.",
        "zh": "RT 已释放。控制器所有权保留给父模块。",
    },
    "farm.archived": {
        "en": "Archived play count to {path}",
        "zh": "比赛记录已归档至 {path}",
    },
    "farm.archive_fail": {
        "en": "Failed to archive play count to file: {err}",
        "zh": "归档比赛记录失败: {err}",
    },
    "farm.state_cleared": {
        "en": "Race state file cleared ({path})",
        "zh": "比赛状态文件已清除 ({path})",
    },
    "farm.state_clear_fail": {
        "en": "Failed to clear race state file: {err}",
        "zh": "清除比赛状态文件失败: {err}",
    },
    # farm/skills.py — saved state resume
    "farm.resume_title": {
        "en": "   [RESUMING FROM SAVED STATE]",
        "zh": "   [从保存状态恢复]",
    },
    "farm.resume_completed": {
        "en": "   Matches Already Completed: {count}",
        "zh": "   已完成比赛: {count} 场",
    },
    "farm.resume_updated": {
        "en": "   Last Updated: {time}",
        "zh": "   上次更新: {time}",
    },
    "farm.resume_scan": {
        "en": "   (Will scan CARS tab for fresh skill points)",
        "zh": "   (将扫描 CARS 标签页获取最新技能点)",
    },
    # farm/skills.py — racing
    "farm.racing_rt": {
        "en": "[RACING] Holding Right Trigger (RT) to accelerate... Scanning for race end...",
        "zh": "[比赛中] 按住 RT 加速... 扫描终点...",
    },
    "farm.match_done_title": {
        "en": "   [MATCH PLAYED & SETTLED SUCCESSFULLY]",
        "zh": "   [比赛完成并结算成功]",
    },
    "farm.match_done_num": {
        "en": "   Match Number Completed: {count}",
        "zh": "   已完成第 {count} 场比赛",
    },
    "farm.match_done_orig": {
        "en": "   Original Matches Needed: {count}",
        "zh": "   原始所需比赛场次: {count}",
    },
    "farm.match_done_remain": {
        "en": "   Remaining Matches Needed: {count}",
        "zh": "   剩余所需比赛场次: {count}",
    },
    "farm.restart_race": {
        "en": "Race finished! {remain} races remaining, pressing X to restart race...",
        "zh": "比赛结束！剩余 {remain} 场，按 X 重新开始...",
    },
    "farm.all_done": {
        "en": "Race finished! All {count} races completed! Pressing A to view rewards...",
        "zh": "比赛结束！全部 {count} 场完成！按 A 查看奖励...",
    },
    "farm.wait_next": {
        "en": "Waiting for rewards screen to transition to Next screen...",
        "zh": "等待奖励界面过渡到 Next 画面...",
    },
    "farm.next_found": {
        "en": "Rewards settled! Detected Next screen. Pressing B to exit...",
        "zh": "奖励已结算！检测到 Next 画面。按 B 退出...",
    },
    "farm.wait_next_skip_playing": {
        "en": "⚠ Next screen skipped — already in free-roam. Pressing START...",
        "zh": "⚠ 跳过了 Next 画面 — 已在自由漫游中。按 START...",
    },
    "farm.wait_next_timeout_retry": {
        "en": "⚠ Next screen not detected after {sec}s, pressing B to advance...",
        "zh": "⚠ 等待 {sec}s 仍未检测到 Next 画面，按 B 推进...",
    },
    "farm.wait_next_force_exit": {
        "en": "⚠ Force exit after {sec}s — Next screen never detected. Pressing B...",
        "zh": "⚠ 等待 {sec}s 后强制退出 — 始终未检测到 Next 画面。按 B...",
    },
    "farm.wait_gameplay": {
        "en": "Waiting for game window to return to gameplay...",
        "zh": "等待游戏画面回到自由漫游...",
    },
    "farm.gameplay_found": {
        "en": "Returned to gameplay! Pressing START to open pause menu...",
        "zh": "已回到游戏！按 START 打开暂停菜单...",
    },
    "farm.goal_reached_title": {
        "en": "   [ALL TARGET MATCHES SUCCESSFULLY COMPLETED]",
        "zh": "   [所有目标比赛已全部完成]",
    },
    "farm.goal_reached_desc": {
        "en": "   Skill point goal has been successfully reached!",
        "zh": "   技能点目标已成功达成！",
    },
    "farm.goal_reached_menu": {
        "en": "   Returned to Menu successfully.",
        "zh": "   已成功返回菜单。",
    },
    # farm/skills.py — startup guard & recovery
    "farm.startup_guard": {
        "en": "[STARTUP SAFEGUARD] Detected gameplay screen. Pressing START to open pause menu...",
        "zh": "[启动守卫] 检测到游戏画面。按 START 打开暂停菜单...",
    },
    "farm.outside_race_end": {
        "en": "Detected race end outside racing mode. Handling as race end...",
        "zh": "在非比赛模式下检测到比赛结束。按比赛结束处理...",
    },
    "farm.reenter_menu": {
        "en": "Successfully re-entered the game menu!",
        "zh": "已成功重新进入游戏菜单！",
    },
    "farm.safety_guard": {
        "en": "[SAFETY GUARD] Active state: {state}, but skill points NOT scanned yet! Pressing B to back out...",
        "zh": "[安全守卫] 当前状态: {state}，但技能点尚未扫描！按 B 返回...",
    },
    # farm/skills.py — menu states
    "farm.cars_scan": {
        "en": "[STATE: CARS] Arrived at CARS tab! Scanning skill points...",
        "zh": "[状态: CARS] 到达 CARS 标签页！正在扫描技能点...",
    },
    "farm.scan_ok_title": {
        "en": "   [SKILL POINTS SCAN SUCCESS on CARS TAB]",
        "zh": "   [CARS 标签页技能点扫描成功]",
    },
    "farm.scan_ok_points": {
        "en": "   Current Points: {pts} / 999",
        "zh": "   当前技能点: {pts} / 999",
    },
    "farm.scan_ok_needed": {
        "en": "   Matches Needed: {count} (10 pts/match)",
        "zh": "   所需比赛场次: {count} (每场 10 点)",
    },
    "farm.already_full_title": {
        "en": "   [GOAL ALREADY REACHED]",
        "zh": "   [目标已达成]",
    },
    "farm.already_full_desc": {
        "en": "   Current points {pts} >= 999. No matches needed!",
        "zh": "   当前技能点 {pts} >= 999。无需比赛！",
    },
    "farm.cars_shift_rb": {
        "en": "[STATE: CARS] Shifting right (RB)...",
        "zh": "[状态: CARS] 按 RB 翻页...",
    },
    "farm.ocr_fail_retry": {
        "en": "OCR failed to read skill points on CARS tab. Enforcing initial scan, retrying on next frame...",
        "zh": "CARS 标签页 OCR 读取技能点失败。强制初始扫描，下帧重试...",
    },
    "farm.ocr_fail_use": {
        "en": "OCR failed. Using current matches_needed: {count}",
        "zh": "OCR 失败。使用当前 matches_needed: {count}",
    },
    "farm.other_tab": {
        "en": "[STATE: {state}] Not in Creative Hub, shifting right (RB)...",
        "zh": "[状态: {state}] 不在 Creative Hub，按 RB 翻页...",
    },
    "farm.hub_bypass": {
        "en": "[STATE: CREATIVE HUB] Initial points not scanned yet! Bypassing, shifting right (RB)...",
        "zh": "[状态: CREATIVE HUB] 技能点尚未初始扫描！跳过，按 RB 翻页...",
    },
    "farm.hub_enter": {
        "en": "[STATE: CREATIVE_HUB] Arrived at Creative Hub! Entering EventLab (A)...",
        "zh": "[状态: CREATIVE_HUB] 到达 Creative Hub！进入 EventLab (A)...",
    },
    "farm.eventlab_menu": {
        "en": "[STATE: EVENTLAB_MENU] Entering EventLab menu, selecting Play Event (A)...",
        "zh": "[状态: EVENTLAB_MENU] 进入 EventLab 菜单，选择 Play Event (A)...",
    },
    "farm.events_sub": {
        "en": "[STATE: EVENTS_SUBMENU] Shifting right (RB) to find My Favorites...",
        "zh": "[状态: EVENTS_SUBMENU] 按 RB 查找 My Favorites...",
    },
    "farm.favorites": {
        "en": "[STATE: FAVORITES_LIST] Arrived at My Favorites! Selecting Event (A)...",
        "zh": "[状态: FAVORITES_LIST] 到达 My Favorites！选择赛事 (A)...",
    },
    "farm.race_ready_title": {
        "en": "   [STATE: RACE_READY] Arrived at Choose Race Type!",
        "zh": "   [状态: RACE_READY] 到达选择比赛类型！",
    },
    "farm.race_ready_solo": {
        "en": "   Ensuring SOLO is selected and launching...",
        "zh": "   确保选中 SOLO 并启动...",
    },
    "farm.solo_ok": {
        "en": "SOLO selected! Transitioning to Car Selection...",
        "zh": "SOLO 已选中！进入选车界面...",
    },
    "farm.car_select": {
        "en": "   [STATE: CAR_SELECT] Confirming current car (A)...",
        "zh": "   [状态: CAR_SELECT] 确认当前车辆 (A)...",
    },
    "farm.pre_race_title": {
        "en": "   [STATE: PRE_RACE] Arrived at Pre-Race Lobby!",
        "zh": "   [状态: PRE_RACE] 到达赛前大厅！",
    },
    "farm.pre_race_launch": {
        "en": "   Launching Start Race Event...",
        "zh": "   启动比赛...",
    },
    "farm.race_start": {
        "en": "Start Race Event selected! Transitioning to racing mode...",
        "zh": "已选择开始比赛！进入比赛模式...",
    },
    "farm.unknown_wait": {
        "en": "[STATE: {state}] Waiting for UI to load... [Consecutive: {count}/5]",
        "zh": "[状态: {state}] 等待 UI 加载... [连续: {count}/5]",
    },
    "farm.recovery_b": {
        "en": "  [AUTO-RECOVERY] {count} consecutive UNKNOWNs, pressing B to exit stuck screen...",
        "zh": "  [自动恢复] 连续 {count} 次 UNKNOWN，尝试按 B 退出卡住画面...",
    },
    "farm.recovery_start": {
        "en": "  [AUTO-RECOVERY] Pressing Start to open menu...",
        "zh": "  [自动恢复] 尝试按 Start 打开菜单...",
    },
    "farm.recovery_focus": {
        "en": "  [AUTO-RECOVERY] Attempting to regain window focus...",
        "zh": "  [自动恢复] 尝试重新获取窗口焦点...",
    },
    "farm.diag_title": {
        "en": "  [DIAGNOSTIC WARNING: GAME SCREEN IS OBSCURED OR LOST FOCUS]",
        "zh": "  [诊断警告：游戏画面被遮挡或失去焦点]",
    },
    "farm.diag_hint": {
        "en": "  Please verify: game is windowed/borderless, not minimized, not covered.",
        "zh": "  请确认：游戏为窗口化/无边框模式，未最小化，未被遮挡。",
    },
    "farm.client_rect_fail": {
        "en": "Failed to get client rect: {err}. Falling back to primary screen.",
        "zh": "获取窗口区域失败: {err}. 回退至主屏幕。",
    },
    "farm.capture_fail": {
        "en": "Failed to capture screen: {err}",
        "zh": "截屏失败: {err}",
    },
    "farm.capture_retry": {
        "en": "MSS screenshot instance reset. Will retry capture on next tick.",
        "zh": "MSS 截图实例已重置，将在下一帧重试截图。",
    },
    "farm.capture_reset_fail": {
        "en": "Failed to reset MSS after capture error: {err}",
        "zh": "截图失败后重置 MSS 出错: {err}",
    },
    "farm.rate_popup": {
        "en": "[Rate Event] Detected popup (yellow pixels: {count}). Pressing A to dismiss...",
        "zh": "[Rate Event] 检测到弹窗 (黄色像素: {count})。按 A 关闭...",
    },
    "farm.rate_popup_error": {
        "en": "Rate popup detection error: {err}",
        "zh": "Rate 弹窗检测出错: {err}",
    },
    "farm.invalid_region": {
        "en": "Invalid capture region (width={w}, height={h}), window may be minimized",
        "zh": "截图区域无效 (宽={w}, 高={h})，窗口可能被最小化",
    },
    "farm.controller_cleanup_fail": {
        "en": "Controller cleanup error (non-critical): {err}",
        "zh": "控制器清理出错（非关键）: {err}",
    },
    "farm.state_saved": {
        "en": "Race state saved: {remain} races remaining, {done} completed",
        "zh": "比赛状态已保存: 剩余 {remain} 场，已完成 {done} 场",
    },
    "farm.timeout": {
        "en": "State Machine safety timeout: ran for {hours:.1f} hours without completing all races.",
        "zh": "状态机安全超时: 已运行 {hours:.1f} 小时，仍未完成所有比赛。",
    },
    # ==================================================================
    #  OCR messages (engine/ocr.py)
    # ==================================================================
    "ocr.psm_result": {
        "en": "[OCR PSM{psm}] Result: {val}",
        "zh": "[OCR PSM{psm}] 识别结果: {val}",
    },
    "ocr.final_result": {
        "en": "[OCR Final] Adopted value: {val}",
        "zh": "[OCR 最终] 采用值: {val}",
    },
    "ocr.zero_detect": {
        "en": "[Zero Points Detected] Matched zero-point screen (text: '{text}'), skill points = 0.",
        "zh": "[零技能点检测] 成功匹配到零技能点界面特征 (识别文本: '{text}')，判定当前技能点为 0。",
    },
    "ocr.tesseract_ok": {
        "en": "Tesseract is available in system PATH.",
        "zh": "Tesseract 可在系统 PATH 中找到。",
    },
    "ocr.debug_write_fail": {
        "en": "Failed to write debug image '{path}': {err}",
        "zh": "写入调试图片 '{path}' 失败: {err}",
    },
    "ocr.psm_error": {
        "en": "[OCR PSM{psm}] Tesseract error: {err}",
        "zh": "[OCR PSM{psm}] Tesseract 出错: {err}",
    },
    "ocr.zero_detect_error": {
        "en": "[OCR] Zero-point fallback OCR error: {err}",
        "zh": "[OCR] 零技能点保底 OCR 出错: {err}",
    },
    # ==================================================================
    #  macro/master_loop.py
    # ==================================================================
    "loop.ctrl_connected": {
        "en": "Virtual Xbox 360 controller connected!",
        "zh": "虚拟 Xbox 360 控制器已连接！",
    },
    "loop.ctrl_fail": {
        "en": "Failed to load virtual controller driver. Please verify ViGEmBus is installed: {err}",
        "zh": "装载虚拟控制器驱动失败，请检查 ViGEmBus 是否安装正确: {err}",
    },
    "loop.cycle": {
        "en": "--- Cycle #{count} ---",
        "zh": "--- 循环回路 #{count} ---",
    },
    # Buy phase
    "loop.buy_desc": {
        "en": "Buying {count} cars",
        "zh": "购买 {count} 辆车",
    },
    "loop.nav_fail": {
        "en": "5-step navigation failed! Retrying from starting position...",
        "zh": "五步导航寻路失败！正在尝试从起始位置重试...",
    },
    "loop.nav_ok": {
        "en": "5-step navigation completed! Arrived at purchase screen",
        "zh": "五步导航阶段顺利完成！已到达购买画面",
    },
    "loop.buying": {
        "en": "Executing purchase macro...",
        "zh": "正在执行购车宏...",
    },
    "loop.buy_done": {
        "en": "All {count} cars purchased!",
        "zh": "全部 {count} 辆车已购买完毕！",
    },
    "loop.press_b_back": {
        "en": "Pressing B × 4 to return to home tab...",
        "zh": "正在连续按 4 次 B 键返回主页标签...",
    },
    "loop.press_b_n": {
        "en": "  -> Pressing B ({n}/4)...",
        "zh": "  -> 按 B ({n}/4)...",
    },
    "loop.b_back_done": {
        "en": "Returned to home tab after 4× B!",
        "zh": "已按 B 键 4 次返回主页标签！",
    },
    "loop.transition": {
        "en": "Transition [{src}] ====> [{dst}]",
        "zh": "流程转换 [{src}] ====> [{dst}]",
    },
    "loop.buy_single_done": {
        "en": "✅ Buy phase completed (single run)",
        "zh": "✅ 买车阶段完成（单次模式）",
    },
    # Upgrade phase
    "loop.upgrade_desc": {
        "en": "Upgrading NEW cars in garage one by one...",
        "zh": "对车库中的 NEW 车逐辆加点...",
    },
    "loop.upgrade_nav": {
        "en": "Navigating to car #{n}...",
        "zh": "正在导航并选中第 {n} 辆车...",
    },
    "loop.upgrade_no_more": {
        "en": "  No more NEW cars found, upgraded {count} cars",
        "zh": "  导航未找到更多 NEW 车，已加点 {count} 辆",
    },
    "loop.upgrade_selected": {
        "en": "Selected car #{n}, executing upgrade macro...",
        "zh": "已选中第 {n} 辆车并进入详情页，正在执行加点宏...",
    },
    "loop.upgrade_low_pts": {
        "en": "  Insufficient skill points ({pts} < 30), exiting skill tree...",
        "zh": "  技能点不足 ({pts} < 30)，退出技能树回到车库...",
    },
    "loop.upgrade_done": {
        "en": "Upgrade phase completed! Upgraded {count} cars",
        "zh": "加点阶段完成！共加点 {count} 辆车",
    },
    "loop.upgrade_single_done": {
        "en": "✅ Upgrade phase completed (single run)",
        "zh": "✅ 加点阶段完成（单次模式）",
    },
    # Trash phase
    "loop.trash_desc": {
        "en": "Removing upgraded Impreza vehicles...",
        "zh": "移除已加点的 Impreza 车辆...",
    },
    "loop.trash_done": {
        "en": "Trash phase completed! Removed {count} cars",
        "zh": "删车阶段完成！共移除 {count} 辆车",
    },
    "loop.trash_single_done": {
        "en": "✅ Trash phase completed (single run)",
        "zh": "✅ 卖车阶段完成（单次模式）",
    },
    # Farm phase
    "loop.farm_desc": {
        "en": "Skill points exhausted, starting auto-farm mode",
        "zh": "技能点已耗尽，启动全自动跑图刷点模式",
    },
    "loop.farm_note": {
        "en": "Master loop is launching visual navigation and auto-farm module to earn skill points in EventLab...",
        "zh": "主控程序正在启动视觉导航与自动跑图模块，进入 EventLab 赚取技能点...",
    },
    "loop.farm_start": {
        "en": "Launching module_farm_skills (attempt #{n})...",
        "zh": "正在启动 module_farm_skills (第 {n} 次)...",
    },
    "loop.farm_returned": {
        "en": "Farm module returned! Verifying skill points...",
        "zh": "刷图模块已返回！正在验证技能点...",
    },
    "loop.farm_error": {
        "en": "Module error: {err}",
        "zh": "模块运行中出现错误: {err}",
    },
    "loop.farm_retry": {
        "en": "Retrying farm phase in 5 seconds...",
        "zh": "尝试等待 5 秒后重新开始刷图阶段...",
    },
    # Verification sub-flow
    "loop.verify_restore": {
        "en": "  [Verify] Restoring window focus and screenshot context...",
        "zh": "  [验证] 正在恢复窗口焦点和截图上下文...",
    },
    "loop.verify_nav": {
        "en": "  [Verify] Navigating to CARS tab to read skill points...",
        "zh": "  [验证] 正在导航到 CARS 标签页读取技能点...",
    },
    "loop.verify_cars_found": {
        "en": "  [Verify] Arrived at CARS tab! (StateDetector: {state})",
        "zh": "  [验证] 已到达 CARS 标签页！(StateDetector: {state})",
    },
    "loop.verify_rb": {
        "en": "  [Verify] RB #{n}: current state={state}, paging...",
        "zh": "  [验证] RB #{n}: 当前状态={state}，继续翻页...",
    },
    "loop.verify_cars_miss": {
        "en": "  [Verify] Failed to navigate to CARS tab",
        "zh": "  [验证] 未能导航到 CARS 标签页",
    },
    "loop.verify_lb_back": {
        "en": "  [Verify] Pressing LB to return to CAMPAIGN tab...",
        "zh": "  [验证] 按 LB 回到 CAMPAIGN 标签...",
    },
    "loop.verify_pts": {
        "en": "  [Verify] OCR detected skill points: {pts} / {max}",
        "zh": "  [验证] OCR 检测到技能点: {pts} / {max}",
    },
    "loop.verify_ok": {
        "en": "  ✅ Skill points confirmed at {pts} >= {max}!",
        "zh": "  ✅ 技能点已确认到达 {pts} >= {max}！",
    },
    "loop.verify_low": {
        "en": "  ⚠️ Insufficient points! Current {pts}, need {diff} more",
        "zh": "  ⚠️ 技能点不足！当前 {pts}，差 {diff} 点",
    },
    "loop.verify_extra": {
        "en": "  Recalculating: ~{races} more races needed",
        "zh": "  重新计算：预计还需 {races} 场比赛",
    },
    "loop.verify_assume": {
        "en": "  ⚠️ OCR could not read skill points, assuming target reached...",
        "zh": "  ⚠️ OCR 无法读取技能点，假设已达标继续...",
    },
    "loop.farm_verified": {
        "en": "Farm phase completed! Skill points verified at {max}!",
        "zh": "刷图阶段完成！技能点已验证到达 {max}！",
    },
    "loop.farm_skip_buy": {
        "en": "Transition [STATE_FARM_POINTS] =====> [STATE_UPGRADE_CARS] (skipping buy)",
        "zh": "流程转换 [STATE_FARM_POINTS] =====> [STATE_UPGRADE_CARS] (跳过买车)",
    },
    "loop.farm_to_buy": {
        "en": "Transition [STATE_FARM_POINTS] =====> [STATE_BUY_CARS] (new cycle!)",
        "zh": "流程转换 [STATE_FARM_POINTS] =====> [STATE_BUY_CARS] (新一轮开始！)",
    },
    "loop.farm_single_done": {
        "en": "✅ Farm phase completed (single run)",
        "zh": "✅ 刷点阶段完成（单次模式）",
    },
    # Errors & interrupts
    "loop.state_error": {
        "en": "Error in state {state}: {err}",
        "zh": "状态 {state} 执行中发生异常: {err}",
    },
    "loop.state_retry": {
        "en": "Retrying current state in 5 seconds...",
        "zh": "尝试等待 5 秒后重试当前状态...",
    },
    "loop.bot_stopped": {
        "en": "     ⛔ Bot stopped by user",
        "zh": "     ⛔ Bot 已被用户主动停止",
    },
    "loop.ctrl_c": {
        "en": "     ⛔ Master loop interrupted by user (KeyboardInterrupt)",
        "zh": "     ⛔ 主控大脑被用户手动中止 (KeyboardInterrupt)",
    },
    "loop.ctrl_c_exit": {
        "en": "     Safely releasing controller and exiting...",
        "zh": "     正在安全释放控制器并退出主程序...",
    },
    "loop.window_missing": {
        "en": "Forza Horizon 6 window not found!",
        "zh": "未找到 Forza Horizon 6 窗口！",
    },
    # General / shared
    "general.b_x": {
        "en": "  -> B × {n}...",
        "zh": "  -> B × {n}...",
    },
    "general.a_x": {
        "en": "  -> A × {n}...",
        "zh": "  -> A × {n}...",
    },
    "general.up_x": {
        "en": "  -> Up × {n}...",
        "zh": "  -> Up × {n}...",
    },
    "general.exit_skill_tree": {
        "en": "  -> B × 2 exit skill tree...",
        "zh": "  -> B × 2 退出技能树...",
    },
    "general.enter_garage": {
        "en": "  -> A × 1 enter garage...",
        "zh": "  -> A × 1 进入车库...",
    },
    "general.enter_garage_cars": {
        "en": "  -> A × 1 enter garage (Cars confirmed)...",
        "zh": "  -> A × 1 进入车库 (已确认 Cars)...",
    },
    "general.select_main_car": {
        "en": "  -> Selecting main car...",
        "zh": "  -> 正在选中主力车...",
    },
    "general.select_main_car_a": {
        "en": "  -> A × 1 select main car...",
        "zh": "  -> A × 1 选中主力车...",
    },
    "general.detail_confirmed": {
        "en": "  -> B × 1 (detail page confirmed)...",
        "zh": "  -> B × 1 (已确认详情页)...",
    },
    "general.detail_skip": {
        "en": "  ⚠️ Detail page not detected, skipping B press",
        "zh": "  ⚠️ 未检测到详情页，跳过 B 按键",
    },
    "general.cars_skip": {
        "en": "  ⚠️ Cars not detected, skipping A press",
        "zh": "  ⚠️ 未检测到 Cars，跳过 A 按键",
    },
    "general.anna_confirm": {
        "en": "  -> Pressing menu key (free roam confirmed)...",
        "zh": "  -> 按菜单键 (已确认自由漫游)...",
    },
    "general.anna_skip": {
        "en": "  ⚠️ Free roam not detected, still pressing menu key...",
        "zh": "  ⚠️ 未检测到自由漫游，仍然尝试按菜单键...",
    },
    "general.exit_garage_b2": {
        "en": "  -> B × 2 exit garage...",
        "zh": "  -> B × 2 退出车库...",
    },
    # Keys used in master_loop.py that weren't in the original table
    "loop.upgrade_enter": {
        "en": "Selected car #{n}, entering detail page. Running upgrade macro...",
        "zh": "已选中第 {n} 辆车并进入详情页，正在执行加点宏...",
    },
    "loop.pts_low": {
        "en": "  Insufficient skill points ({pts} < 30), exiting skill tree...",
        "zh": "  技能点不足 ({pts} < 30)，退出技能树回到车库...",
    },
    "loop.menu_confirmed": {
        "en": "  -> Pressing menu key (free roam confirmed)...",
        "zh": "  -> 按菜单键 (已确认自由漫游)...",
    },
    "loop.menu_fallback": {
        "en": "  ⚠️ Free roam not detected, still pressing menu key...",
        "zh": "  ⚠️ 未检测到自由漫游，仍然尝试按菜单键...",
    },
    "loop.farm_launching": {
        "en": "Launching visual navigation & auto-farm module to earn skill points in EventLab...",
        "zh": "主控程序正在启动视觉导航与自动跑图模块，进入 EventLab 赚取技能点...",
    },
    "loop.verify_focus": {
        "en": "  [Verify] Restoring window focus and screenshot context...",
        "zh": "  [验证] 正在恢复窗口焦点和截图上下文...",
    },
    "loop.verify_nav_cars": {
        "en": "  [Verify] Navigating to CARS tab to read skill points...",
        "zh": "  [验证] 正在导航到 CARS 标签页读取技能点...",
    },
    "loop.verify_cars_ok": {
        "en": "  [Verify] Arrived at CARS tab! (StateDetector: {state})",
        "zh": "  [验证] 已到达 CARS 标签页！(StateDetector: {state})",
    },
    "loop.verify_cars_fail": {
        "en": "  [Verify] Failed to navigate to CARS tab",
        "zh": "  [验证] 未能导航到 CARS 标签页",
    },
    "loop.verify_ocr_fail": {
        "en": "  ⚠️ OCR could not read skill points, assuming target reached...",
        "zh": "  ⚠️ OCR 无法读取技能点，假设已达标继续...",
    },
    "loop.farm_done": {
        "en": "Farm phase completed! Skill points verified at {max}!",
        "zh": "刷图阶段完成！技能点已验证到达 {max}！",
    },
    "loop.transition_skip_buy": {
        "en": "Transition [STATE_FARM_POINTS] =====> [STATE_UPGRADE_CARS] (skipping buy)",
        "zh": "流程转换 [STATE_FARM_POINTS] =====> [STATE_UPGRADE_CARS] (跳过买车)",
    },
    "loop.transition_new_cycle": {
        "en": "Transition [STATE_FARM_POINTS] =====> [STATE_BUY_CARS] (new cycle!)",
        "zh": "流程转换 [STATE_FARM_POINTS] =====> [STATE_BUY_CARS] (新一轮开始！)",
    },
    "loop.user_stop": {
        "en": "     ⛔ Bot stopped by user",
        "zh": "     ⛔ Bot 已被用户主动停止",
    },
    "loop.kb_interrupt": {
        "en": "     ⛔ Master loop interrupted by user (KeyboardInterrupt)",
        "zh": "     ⛔ 主控大脑被用户手动中止 (KeyboardInterrupt)",
    },
    "loop.kb_releasing": {
        "en": "     Safely releasing controller and exiting...",
        "zh": "     正在安全释放控制器并退出主程序...",
    },
    "general.select_main_a": {
        "en": "  -> A × 1 select main car...",
        "zh": "  -> A × 1 选中主力车...",
    },
    # ==================================================================
    #  macro/upgrade.py
    # ==================================================================
    "upgrade.start": {
        "en": "Running car skill upgrade macro...",
        "zh": "正在执行车辆加点宏...",
    },
    "upgrade.wait_stable": {
        "en": "  -> Waiting 2.0s after selecting car for stability...",
        "zh": "  -> 选好车后等待 2.0 秒以确保稳定...",
    },
    "upgrade.step_down7": {
        "en": "  -> [4] D-pad Down × 7...",
        "zh": "  -> [4] 输入 D-pad Down 7次...",
    },
    "upgrade.ap_result": {
        "en": "  [Available Points] OCR: {pts} (readings: {raw}, {w}x{h})",
        "zh": "  [Available Points] OCR: {pts} (读数: {raw}, {w}x{h})",
    },
    "upgrade.ap_no_digit": {
        "en": "  [Available Points] OCR did not detect any digits!",
        "zh": "  [Available Points] OCR 未识别到数字！",
    },
    "upgrade.ap_low": {
        "en": "  ⚠️ Available Points = {pts} < {min}, insufficient skill points!",
        "zh": "  ⚠️ Available Points = {pts} < {min}，技能点不足！",
    },
    "upgrade.ap_error": {
        "en": "  [Available Points] OCR error: {err}",
        "zh": "  [Available Points] OCR 异常: {err}",
    },
    "upgrade.cannot_afford": {
        "en": "  ⚠️ [{step}] Detected 'Cannot Afford Perk' popup (OCR: '{text}'), pressing A to close...",
        "zh": "  ⚠️ [{step}] 检测到 'Cannot Afford Perk' 弹窗 (OCR: '{text}')，按 A 关闭...",
    },
    "upgrade.afford_fail": {
        "en": "  ⚠️ Insufficient skill points, ending upgrade macro early",
        "zh": "  ⚠️ 技能点不足，提前结束加点宏",
    },
    "upgrade.step_right": {
        "en": "  -> [7] D-pad Right × 1...",
        "zh": "  -> [7] 输入 D-pad Right 1次...",
    },
    "upgrade.loop_up": {
        "en": "  -> [9] Loop {n}/3: D-pad Up × 1...",
        "zh": "  -> [9] 循环 {n}/3: 输入 D-pad Up 1次...",
    },
    "upgrade.loop_a": {
        "en": "  -> [9] Loop {n}/3: Press A to confirm...",
        "zh": "  -> [9] 循环 {n}/3: 按 A 确认...",
    },
    "upgrade.step_left": {
        "en": "  -> [10] D-pad Left × 1...",
        "zh": "  -> [10] 输入 D-pad Left 1次...",
    },
    "upgrade.done": {
        "en": "Car skill upgrade macro completed! Page should match usepoints.png",
        "zh": "车辆加点宏执行完毕！页面特征应与 usepoints.png 一致",
    },
    # ==================================================================
    #  macro/purchase.py — remaining keys
    # ==================================================================
    "buy.ocr_locked": {
        "en": "OCR (PSM {psm}) detected '{word}'! Screen coords: ({x}, {y})",
        "zh": "OCR (PSM {psm}) 检测到 '{word}'！屏幕坐标: ({x}, {y})",
    },
    "buy.target_not_found": {
        "en": "  [!] Left text does not contain '{target}', skipping...",
        "zh": "  [!] 左侧文字中不含 '{target}'，跳过...",
    },
    "buy.roi_empty": {
        "en": "  [!] Left crop region has zero size",
        "zh": "  [!] 裁剪区域左侧大小为 0",
    },
    "buy.cursor_low": {
        "en": "  [!] Highlight border pixel ratio below 0.5, skipping...",
        "zh": "  [!] 高亮边框像素占比低于 0.5，跳过...",
    },
    "buy.tracker_coords": {
        "en": "  Coords -> Cursor: ({cx}, {cy}) | Target: ({tx}, {ty}) | Offset: (dx={dx}, dy={dy}) (tolerance: {tol}px)",
        "zh": "  坐标 -> 光标: ({cx}, {cy}) | 目标: ({tx}, {ty}) | 偏差: (dx={dx}, dy={dy}) (容差: {tol}px)",
    },
    "buy.target_locked": {
        "en": "Target locked! Breaking out of tracking loop",
        "zh": "目标已锁定！跳出追踪循环",
    },
    "buy.oscillation": {
        "en": "  ⚠️ [Deadlock Defense] Control oscillation detected! Force locking!",
        "zh": "  ⚠️ [死循环防御] 检测到控制震荡！强制锁定！",
    },
    "buy.move_right": {
        "en": "  ⚡ Target is to the right, D-pad Right",
        "zh": "  ⚡ 目标在右侧，D-pad Right",
    },
    "buy.move_left": {
        "en": "  ⚡ Target is to the left, D-pad Left",
        "zh": "  ⚡ 目标在左侧，D-pad Left",
    },
    "buy.move_down": {
        "en": "  ⚡ Target is below, D-pad Down",
        "zh": "  ⚡ 目标在下方，D-pad Down",
    },
    "buy.move_up": {
        "en": "  ⚡ Target is above, D-pad Up",
        "zh": "  ⚡ 目标在上方，D-pad Up",
    },
    "buy.pos_verify": {
        "en": "Starting position verification...",
        "zh": "正在启动位置校验确认程序...",
    },
    "buy.pos_ocr": {
        "en": "  [Position Check] OCR read: '{text}'",
        "zh": "  [位置校验] OCR 读取内容: '{text}'",
    },
    "buy.pos_confirmed": {
        "en": "  Verified: read ('22B'/'IMPREZA'), confirmed correct!",
        "zh": "  校验确认：读取到 ('22B'/'IMPREZA')，确认无误！",
    },
    "buy.pos_mismatch": {
        "en": "Position mismatch, aborting navigation",
        "zh": "位置不符，终止导航",
    },
    "buy.confirm_a": {
        "en": "  -> [Confirm] Pressing A to enter...",
        "zh": "  -> [确认阶段] 按 A 以确认进入...",
    },
    "buy.nav_timeout": {
        "en": "  [!] Navigation timeout: {path}",
        "zh": "  [!] 导航超时: {path}",
    },
    "buy.buy_start": {
        "en": "Executing purchase: starting car {n}/{total}...",
        "zh": "正在执行购买流程：开始购买第 {n}/{total} 辆车...",
    },
    "buy.buy_start_menu": {
        "en": "  -> START open purchase menu...",
        "zh": "  -> START 打开购买菜单...",
    },
    "buy.buy_down": {
        "en": "  -> D-pad Down...",
        "zh": "  -> D-pad Down...",
    },
    "buy.buy_done": {
        "en": "Car {n}/{total} purchase commands sent successfully!",
        "zh": "第 {n}/{total} 辆车购买指令全部发送成功！",
    },
    "buy.cc_ocr_mismatch": {
        "en": "Car Collection OCR mismatch (text: '{text}')",
        "zh": "Car Collection OCR 未匹配 (text: '{text}')",
    },
    "buy.cc_page_ok": {
        "en": "Car Collection Page loaded! (OCR: '{text}')",
        "zh": "Car Collection Page 页面加载确认！(OCR: '{text}')",
    },
    "buy.subaru_ocr_mismatch": {
        "en": "Subaru OCR mismatch (text: '{text}')",
        "zh": "Subaru OCR 未匹配 (text: '{text}')",
    },
    "buy.impreza_ocr_mismatch": {
        "en": "Impreza OCR mismatch (text: '{text}')",
        "zh": "Impreza OCR 未匹配 (text: '{text}')",
    },
    # ── garage.py ──────────────────────────────────────────────────
    # --- wait helpers ---
    "garage.dp_found": {
        "en": "  ✅ Detected 'Designs and Paints' (OCR: '{text}', waited {sec}s)",
        "zh": "  ✅ 检测到 'Designs and Paints' (OCR: '{text}'，等待 {sec}s)",
    },
    "garage.dp_waiting": {
        "en": "  Waiting for Designs and Paints... #{n}: OCR='{text}'",
        "zh": "  等待 Designs and Paints... #{n}: OCR='{text}'",
    },
    "garage.dp_timeout": {
        "en": "  ⚠️ 'Designs and Paints' not detected within {sec}s",
        "zh": "  ⚠️ {sec}s 内未检测到 'Designs and Paints'",
    },
    "garage.cars_found": {
        "en": "  ✅ Detected 'My Cars' (OCR: '{text}', waited {sec}s)",
        "zh": "  ✅ 检测到 'My Cars' (OCR: '{text}'，等待 {sec}s)",
    },
    "garage.cars_waiting": {
        "en": "  Waiting for My Cars... #{n}: OCR='{text}'",
        "zh": "  等待 My Cars... #{n}: OCR='{text}'",
    },
    "garage.cars_timeout": {
        "en": "  ⚠️ 'My Cars' not detected within {sec}s",
        "zh": "  ⚠️ {sec}s 内未检测到 'My Cars'",
    },
    "garage.anna_found": {
        "en": "  ✅ Detected free roam UI (OCR: '{text}', waited {sec}s)",
        "zh": "  ✅ 检测到自由漫游界面 (OCR: '{text}'，等待 {sec}s)",
    },
    "garage.anna_waiting": {
        "en": "  Waiting for free roam (ANNA/LINK)... #{n}: OCR='{text}'",
        "zh": "  等待自由漫游 (ANNA/LINK)... #{n}: OCR='{text}'",
    },
    "garage.anna_timeout": {
        "en": "  ⚠️ ANNA/LINK not detected within {sec}s",
        "zh": "  ⚠️ {sec}s 内未检测到 ANNA/LINK",
    },
    # --- grid navigation ---
    "garage.grid_start": {
        "en": "Starting garage grid navigation: {label}...",
        "zh": "正在启动车库网格导航: {label}...",
    },
    "garage.grid_resume": {
        "en": "  Resuming from column {col}, row {row}",
        "zh": "  从第 {col} 列第 {row} 行继续扫描",
    },
    "garage.grid_mode": {
        "en": "  Traversal mode: typewriter (column-by-column top-to-bottom, reset then right)",
        "zh": "  遍历模式: 打字机走位（逐列从上到下，复位后右移）",
    },
    "garage.fast_forward": {
        "en": "  ⏩ Fast-forward: pressing Right {n} times to column {col}...",
        "zh": "  ⏩ 快进: 按 {n} 次 Right 跳到第 {col} 列...",
    },
    "garage.scan_col": {
        "en": "  📋 Scanning column {col}...",
        "zh": "  📋 正在扫描第 {col} 列...",
    },
    "garage.fast_down": {
        "en": "  ⏩ Fast-forward: pressing Down {n} times to row {row}...",
        "zh": "  ⏩ 快进: 按 {n} 次 Down 跳到第 {row} 行...",
    },
    "garage.no_cursor": {
        "en": "    [Row {row}] Cannot detect cursor",
        "zh": "    [行{row}] 无法检测到光标",
    },
    "garage.cursor_pos": {
        "en": "    [Row {row}] Cursor position: ({cx}, {cy})",
        "zh": "    [行{row}] 光标位置: ({cx}, {cy})",
    },
    "garage.empty_slot": {
        "en": "    [Row {row}] 🔲 Empty slot detected, skip",
        "zh": "    [行{row}] 🔲 检测到空位，跳过",
    },
    "garage.empty_col": {
        "en": "    [Row {row}] Row 1 is empty, skip entire column",
        "zh": "    [行{row}] 第 1 行即为空位，跳过整列",
    },
    "garage.brand_done": {
        "en": "    [Row {row}] Empty slot, brand area fully scanned, stop",
        "zh": "    [行{row}] 检测到空位，品牌区域已扫完，停止扫描",
    },
    "garage.reset_up": {
        "en": "  ⬆️ Reset: pressing Up {n} times to row 1...",
        "zh": "  ⬆️ 复位: 按 {n} 次 Up 回到第 1 行...",
    },
    "garage.verify_pass": {
        "en": "    [Row {row}] ✅ {label} verified! Pressing A to enter details... (col {col}, row {row})",
        "zh": "    [行{row}] ✅ {label} 校验通过！按 A 进入详情... (列{col}, 行{row})",
    },
    "garage.verify_fail": {
        "en": "    [Row {row}] Verification failed, skip (total skipped: {total})",
        "zh": "    [行{row}] 校验未通过，跳过 (累计跳过: {total})",
    },
    "garage.enter_legendary": {
        "en": "    [Zone] 🟠 Entering LEGENDARY zone (orange: {px}px)",
        "zh": "    [区域检测] 🟠 进入 LEGENDARY 区域 (橙色: {px}px)",
    },
    "garage.non_legendary": {
        "en": "    [Zone] Non-LEGENDARY card (consecutive {n}/{max})",
        "zh": "    [区域检测] 非 LEGENDARY 卡片 (连续 {n}/{max})",
    },
    "garage.legendary_detect_err": {
        "en": "    [Zone] LEGENDARY detection error: {err}",
        "zh": "    [区域检测] LEGENDARY 检测出错: {err}",
    },
    "garage.has_below": {
        "en": "    [Row {row}] Car below, pressing D-pad Down...",
        "zh": "    [行{row}] 下方有车，按 D-pad Down...",
    },
    "garage.no_below": {
        "en": "    [Row {row}] Empty below, stop scanning this column",
        "zh": "    [行{row}] 下方为空位，停止本列向下扫描",
    },
    "garage.left_zone": {
        "en": "  🏁 Left Impreza zone ({n} consecutive non-Impreza), stop scanning!",
        "zh": "  🏁 已离开 Impreza 区域 (连续 {n} 个非 Impreza)，停止扫描！",
    },
    "garage.next_col": {
        "en": "  ➡️ Pressing Right to column {col}...",
        "zh": "  ➡️ 按 Right 移到第 {col} 列...",
    },
    "garage.max_cols": {
        "en": "  Scanned {n} columns, no more {label} found",
        "zh": "  已扫描 {n} 列，未找到更多 {label}",
    },
    # --- navigate_to_car_in_garage ---
    "garage.last_pos": {
        "en": "  📍 Last position: col {col}, row {row}",
        "zh": "  📍 上次位置: 列{col}, 行{row}",
    },
    "garage.save_pos": {
        "en": "  📍 Position saved: col {col}, row {row}",
        "zh": "  📍 记录位置: 列{col}, 行{row}",
    },
    "garage.pos_reset": {
        "en": "  📍 Upgrade position reset to col 1, row 1",
        "zh": "  📍 加点位置已重置为 列1, 行1",
    },
    # --- _scan_and_delete_cars ---
    "garage.delete_start": {
        "en": "Starting state-machine delete scan...",
        "zh": "正在启动带状态机的删车扫描...",
    },
    "garage.has_new_skip": {
        "en": "  ⚠️ Car still has NEW tag (not upgraded), skip...",
        "zh": "  ⚠️ 该车仍有 NEW 标签（未加点），跳过...",
    },
    "garage.high_class_skip": {
        "en": "  ⚠️ Car is S1/S2 class (main car), skip!",
        "zh": "  ⚠️ 该车是 S1/S2 级别（主力车），跳过！",
    },
    "garage.card_confirmed": {
        "en": "  ✅ Card OCR confirmed: keywords {n}/3 {matched}",
        "zh": "  ✅ 卡片 OCR 确认: 关键词 {n}/3 {matched}",
    },
    "garage.card_mismatch": {
        "en": "  ⚠️ Card OCR mismatch Impreza 22B (hit {n}/3 {matched}, OCR: '{text}'), skip!",
        "zh": "  ⚠️ 卡片 OCR 未匹配 Impreza 22B (命中 {n}/3 {matched}, OCR: '{text}')，跳过！",
    },
    "garage.card_error": {
        "en": "  ⚠️ Card OCR error: {err}, safe skip",
        "zh": "  ⚠️ 卡片 OCR 异常: {err}，安全跳过",
    },
    "garage.delete_col": {
        "en": "  📋 [Delete] Scanning column {col}...",
        "zh": "  📋 [删车] 正在扫描第 {col} 列...",
    },
    "garage.empty_row1": {
        "en": "    [Row {row}] Row 1 empty, skip entire column",
        "zh": "    [行{row}] 第 1 行空位，跳过整列",
    },
    "garage.empty_brand": {
        "en": "    [Row {row}] Empty slot, brand area finished",
        "zh": "    [行{row}] 空位，品牌区域已扫完",
    },
    "garage.removable": {
        "en": "    [Row {row}] ✅ Removable! Pressing A to enter details...",
        "zh": "    [行{row}] ✅ 可删除！按 A 进入详情...",
    },
    "garage.state_fix": {
        "en": "  [State fix] Before delete: (row {old_r}, col {old_c}) → cursor moved to: (row {new_r}, col {new_c})",
        "zh": "  [状态修正] 删除前: (行{old_r}, 列{old_c}) → 光标退到: (行{new_r}, 列{new_c})",
    },
    "garage.restore_down": {
        "en": "  [Restore] Pressing Down to row {row}...",
        "zh": "  [恢复] 按 Down 前进到行{row}...",
    },
    "garage.restore_cross": {
        "en": "  [Restore] Cross-column rollback: Right → Up×2 to row 1...",
        "zh": "  [恢复] 跨列回退：按 Right → Up×2 回到第 1 行...",
    },
    "garage.delete_skip": {
        "en": "    [Row {row}] Verification failed, skip",
        "zh": "    [行{row}] 校验未通过，跳过",
    },
    "garage.delete_down": {
        "en": "    [Row {row}] Car below, pressing Down...",
        "zh": "    [行{row}] 下方有车，按 Down...",
    },
    "garage.delete_no_below": {
        "en": "    [Row {row}] Empty below",
        "zh": "    [行{row}] 下方为空位",
    },
    "garage.empty_cols_stop": {
        "en": "  {n} consecutive columns with no target, brand area finished.",
        "zh": "  连续 {n} 列无目标，品牌区域扫完。",
    },
    "garage.brand_leave": {
        "en": "  🛑 Selected tab: '{text}', left Subaru zone",
        "zh": "  🛑 选中标签: '{text}'，已离开 Subaru 区域",
    },
    "garage.delete_done": {
        "en": "  Scanned {n} columns, deletion complete.",
        "zh": "  已扫描 {n} 列，删车完成。",
    },
    # --- navigate_to_car_for_removal ---
    "garage.has_new_keep": {
        "en": "  ⚠️ Car still has NEW tag (not upgraded), keep, skip...",
        "zh": "  ⚠️ 该车仍有 NEW 标签（未加点），需保留，跳过...",
    },
    "garage.high_class_main": {
        "en": "  ⚠️ Car is S1/S2 class (user's main car), skip!",
        "zh": "  ⚠️ 该车是 S1/S2 级别（用户主力车），跳过！",
    },
    "garage.removable_b": {
        "en": "    No NEW tag and B class, can remove!",
        "zh": "    无 NEW 标签且为 B 级，可以移除！",
    },
    "garage.remove_label": {
        "en": "Removable car",
        "zh": "移除车",
    },
    # --- action_remove_single_car ---
    "garage.removing": {
        "en": "🗑️ Removing car #{n}...",
        "zh": "🗑️ 正在移除第 {n} 辆车...",
    },
    "garage.remove_a": {
        "en": "  -> A Remove Car From Garage...",
        "zh": "  -> A Remove Car From Garage...",
    },
    "garage.remove_confirm_switch": {
        "en": "  -> D-pad Down: switch to confirm button...",
        "zh": "  -> D-pad Down：切换到确认按钮...",
    },
    "garage.remove_confirm": {
        "en": "  -> A: Confirm removal!",
        "zh": "  -> A：确认移除！",
    },
    "garage.removed_ok": {
        "en": "  ✅ Car #{n} successfully removed from garage!",
        "zh": "  ✅ 第 {n} 辆车已成功从车库移除！",
    },
    # --- navigate_to_main_car ---
    "garage.main_start": {
        "en": "Starting garage grid navigation: main car search...",
        "zh": "正在启动车库网格导航: 主力车搜索...",
    },
    "garage.main_mode": {
        "en": "  Scan mode: per-cell PI color detection (no template matching)",
        "zh": "  扫描模式: 逐格 PI 颜色检测（不依赖模板匹配）",
    },
    "garage.main_not_target": {
        "en": "    [Row {row}] ⚠️ S2 but not target (hit {n}/3 {matched}, OCR: '{text}'), skip",
        "zh": "    [行{row}] ⚠️ S2 但非目标车 (命中 {n}/3 {matched}, OCR: '{text}')，跳过",
    },
    "garage.main_found": {
        "en": "    [Row {row}] ✅ Found main car (S2 + Impreza 22B)! Pressing A... (col {col}, row {row})",
        "zh": "    [行{row}] ✅ 找到主力车（S2 + Impreza 22B）！按 A 进入详情... (列{col}, 行{row})",
    },
    "garage.main_skip_s": {
        "en": "    [Row {row}] S class but not target car, skip...",
        "zh": "    [行{row}] S 级但非目标车，跳过...",
    },
    "garage.main_skip_b": {
        "en": "    [Row {row}] B class car, skip...",
        "zh": "    [行{row}] B 级车，跳过...",
    },
    "garage.main_not_found": {
        "en": "  ⚠️ S1/S2 main car not found!",
        "zh": "  ⚠️ 未找到 S1/S2 主力车！",
    },
    # --- action_get_in_car ---
    "garage.get_in": {
        "en": "  Get In Car...",
        "zh": "  Get In Car...",
    },
    "garage.got_in": {
        "en": "  ✅ In the car!",
        "zh": "  ✅ 已上车！",
    },
    # ------------------------------------------------------------------
    # OCR verification logs (engine/ocr.py)
    # ------------------------------------------------------------------
    "ocr.contour_fail": {
        "en": "[DYNAMIC VISION] All contours failed garage grid check! Largest: {w}x{h} at ({cx}, {cy}), area={area}",
        "zh": "[DYNAMIC VISION] 所有轮廓均未通过车库网格校验！最大轮廓: {w}x{h} at ({cx}, {cy}), 面积={area}",
    },
    "ocr.cursor_error": {
        "en": "find_cursor_position error: {err}",
        "zh": "find_cursor_position 执行出错: {err}",
    },
    "ocr.keyword_hit": {
        "en": "  [Multi-keyword hit] Matched {n}/3: {kws}",
        "zh": "  [多关键词命中] 匹配 {n}/3: {kws}",
    },
    "ocr.lock_ok": {
        "en": "[Lock OK] Triple check passed! Keywords {n}/3 {kws} + NEW tag ({yellow}px) + LEGENDARY ({orange}px)",
        "zh": "[锁定成功] 三重校验通过！关键词 {n}/3 {kws} + NEW标签 ({yellow}px) + LEGENDARY ({orange}px)",
    },
    "ocr.lock_fail": {
        "en": "[Lock FAIL] Triple check not all passed:",
        "zh": "[锁定失败] 三重校验未全部通过:",
    },
    "ocr.lock_r1_fail": {
        "en": "  ❌ Reason 1: Keywords insufficient (hit {n}/3 {kws}, need≥2, OCR: '{text}')",
        "zh": "  ❌ 原因1：关键词不足 (命中 {n}/3 {kws}, 需≥2, OCR: '{text}')",
    },
    "ocr.lock_r1_ok": {
        "en": "  ✓ Check 1: Keywords matched {n}/3 {kws}",
        "zh": "  ✓ 检查1：关键词命中 {n}/3 {kws}",
    },
    "ocr.lock_r2_fail": {
        "en": "  ❌ Reason 2: No 'NEW' tag detected (yellow pixels: {px} <= 300)",
        "zh": "  ❌ 原因2：没有检测到 'NEW' 标签 (黄色像素: {px} <= 300)",
    },
    "ocr.lock_r2_ok": {
        "en": "  ✓ Check 2: 'NEW' tag detected (yellow pixels: {px})",
        "zh": "  ✓ 检查2：检测到 'NEW' 标签 (黄色像素: {px})",
    },
    "ocr.lock_r3_fail": {
        "en": "  ❌ Reason 3: Not LEGENDARY (orange pixels: {px} <= 200)",
        "zh": "  ❌ 原因3：不是 LEGENDARY (橙色像素: {px} <= 200)",
    },
    "ocr.lock_r3_ok": {
        "en": "  ✓ Check 3: LEGENDARY badge (orange pixels: {px})",
        "zh": "  ✓ 检查3：LEGENDARY 橙色标签 (橙色像素: {px})",
    },
    "ocr.verify_error": {
        "en": "verify_new_target_car error: {err}",
        "zh": "verify_new_target_car 校验出错: {err}",
    },
    "ocr.new_tag_ok": {
        "en": "[NEW tag] ✓ NEW tag detected (yellow pixels: {px}, area: card bottom)",
        "zh": "[NEW 标签检测] ✓ 检测到 NEW 标签 (黄色像素: {px}，区域:卡片底部)",
    },
    "ocr.new_tag_fail": {
        "en": "[NEW tag] ✗ No NEW tag (yellow pixels: {px} <= 300, area: card bottom), may already have skill points",
        "zh": "[NEW 标签检测] ✗ 未检测到 NEW 标签 (黄色像素: {px} <= 300，区域:卡片底部)，可能已加过点",
    },
    "ocr.new_tag_error": {
        "en": "check_new_tag_only error: {err}",
        "zh": "check_new_tag_only 出错: {err}",
    },
    "ocr.pi_high": {
        "en": "[PI detect] ⚠ High-class vehicle detected (blue: {blue} > orange: {orange})",
        "zh": "[PI 检测] ⚠ 检测到高级别车辆 (蓝色: {blue} > 橙色: {orange})",
    },
    "ocr.pi_b_class": {
        "en": "[PI detect] ✓ B-class vehicle (orange: {orange} > blue: {blue})",
        "zh": "[PI 检测] ✓ B 级车辆 (橙色: {orange} > 蓝色: {blue})",
    },
    "ocr.pi_ambiguous": {
        "en": "[PI detect] ⚠ Color ambiguous (blue: {blue}, orange: {orange}), skip conservatively",
        "zh": "[PI 检测] ⚠ 颜色不明确 (蓝色: {blue}, 橙色: {orange})，保守跳过",
    },
    "ocr.pi_error": {
        "en": "check_is_high_class error: {err}",
        "zh": "check_is_high_class 出错: {err}",
    },
    # ------------------------------------------------------------------
    # Web server banner (web/server.py)
    # ------------------------------------------------------------------
    "web.banner_title": {
        "en": "   🌐 FH6 AutoBot — Web UI Dashboard",
        "zh": "   🌐 FH6 AutoBot — Web UI 控制面板",
    },
    "web.banner_local": {
        "en": "   Local:   http://localhost:{port}",
        "zh": "   本机访问:   http://localhost:{port}",
    },
    "web.banner_lan": {
        "en": "   LAN:     http://{ip}:{port}",
        "zh": "   局域网访问: http://{ip}:{port}",
    },
    "web.banner_hint": {
        "en": "   Open the URL above on your phone to monitor remotely",
        "zh": "   手机扫码或输入上方地址即可远程监控",
    },
    # ------------------------------------------------------------------
    # main_bot.py
    # ------------------------------------------------------------------
    "main.invalid_input": {
        "en": "  ❌ Invalid",
        "zh": "  ❌ 无效",
    },
    # ------------------------------------------------------------------
    # OCR additional logs (engine/ocr.py)
    # ------------------------------------------------------------------
    "ocr.grid_oob": {
        "en": "[GRID] Below area out of bounds (sy1={sy1}, h={h})",
        "zh": "[GRID] 下方超出画面边界 (sy1={sy1}, h={h})",
    },
    "ocr.grid_result": {
        "en": "[GRID] Below cell check: brightness={bright}, variance={var} → {result}",
        "zh": "[GRID] 下方单元格检测: 亮度={bright}, 方差={var} → {result}",
    },
    "ocr.grid_has_car": {
        "en": "has car",
        "zh": "有车",
    },
    "ocr.grid_empty": {
        "en": "empty slot",
        "zh": "空位",
    },
    "ocr.cell_below_error": {
        "en": "has_cell_below error: {err}",
        "zh": "has_cell_below 检测出错: {err}",
    },
    "ocr.empty_slot_detect": {
        "en": "[GRID] Empty slot: brightness={bright}, variance={var} → empty",
        "zh": "[GRID] 空位检测: 亮度={bright}, 方差={var} → 空位",
    },
    "ocr.empty_slot_error": {
        "en": "is_empty_slot error: {err}",
        "zh": "is_empty_slot 检测出错: {err}",
    },
    "ocr.brand_tab_error": {
        "en": "detect_selected_brand_tab OCR error: {err}",
        "zh": "detect_selected_brand_tab OCR 异常: {err}",
    },
    # ------------------------------------------------------------------
    # Utils (engine/utils.py)
    # ------------------------------------------------------------------
    "utils.bring_foreground": {
        "en": "Bringing game window to foreground...",
        "zh": "正在将游戏窗口置于最前...",
    },
}
