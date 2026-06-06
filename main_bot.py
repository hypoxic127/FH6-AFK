# -*- coding: utf-8 -*-
"""
FORZA HORIZON 6 AUTOBOT — Main Entry Point (main_bot.py)
=========================================================
Entry point for the full automation system. Provides an interactive
language → mode → phase selection flow.

Four-phase loop:
  Farm Points → Buy Cars → Upgrade Cars → Trash Cars → (loop)

Usage:
    python main_bot.py
    python main_bot.py --web
    python main_bot.py --console
    python main_bot.py --lang en
    python main_bot.py --lang zh
    python main_bot.py --debug
"""

from macro import (
    STATE_BUY_CARS,
    STATE_FARM_POINTS,
    STATE_TRASH_CARS,
    STATE_UPGRADE_CARS,
    run_master_bot_loop,
)

# ---------------------------------------------------------------------------
# Bilingual string tables
# ---------------------------------------------------------------------------
_STRINGS: dict[str, dict[str, str]] = {
    # Language selector (always bilingual)
    "lang_title": {
        "en": "   FH6-AFK — Language / 语言选择",
        "zh": "   FH6-AFK — Language / 语言选择",
    },
    "lang_opt_en": {
        "en": "  [1] 🇺🇸  English",
        "zh": "  [1] 🇺🇸  English",
    },
    "lang_opt_zh": {
        "en": "  [2] 🇨🇳  中文",
        "zh": "  [2] 🇨🇳  中文",
    },
    "lang_prompt": {
        "en": "  Select language [1/2] (default 1): ",
        "zh": "  Select language [1/2] (default 1): ",
    },
    # Mode selector
    "mode_title": {
        "en": "   FH6-AFK — Mode Selection",
        "zh": "   FH6-AFK — 启动模式选择",
    },
    "mode_web": {
        "en": "  [1] 🌐  Web UI Dashboard",
        "zh": "  [1] 🌐  Web UI 控制面板",
    },
    "mode_web_desc": {
        "en": "       Browser-based GUI, supports remote monitoring",
        "zh": "       浏览器可视化操作，支持手机远程监控",
    },
    "mode_console": {
        "en": "  [2] 💻  Terminal Console",
        "zh": "  [2] 💻  终端控制台模式",
    },
    "mode_console_desc": {
        "en": "       Classic CLI interaction for advanced users",
        "zh": "       经典命令行交互，适合高级用户",
    },
    "mode_prompt": {
        "en": "  Select mode [1/2] (default 1): ",
        "zh": "  选择模式 [1/2] (默认 1): ",
    },
    # Phase selector
    "phase_title": {
        "en": "   FORZA HORIZON 6 AUTOBOT — Startup Menu",
        "zh": "   FORZA HORIZON 6 AUTOBOT — 启动菜单",
    },
    "phase_1": {
        "en": "  [1] 🏎️  Farm Points  (STATE_FARM_POINTS)",
        "zh": "  [1] 🏎️  刷技能点  (STATE_FARM_POINTS)",
    },
    "phase_1_desc": {
        "en": "       OCR scan skill points → auto-grind EventLab to 999",
        "zh": "       OCR 扫描技能点 → 自动跑 EventLab 刷满 999",
    },
    "phase_2": {
        "en": "  [2] 🛒  Buy Cars  (STATE_BUY_CARS)",
        "zh": "  [2] 🛒  买车  (STATE_BUY_CARS)",
    },
    "phase_2_desc": {
        "en": "       Navigate to Car Collection → bulk-buy Subaru Impreza",
        "zh": "       导航至 Car Collection → 批量购买 Subaru Impreza",
    },
    "phase_3": {
        "en": "  [3] ⚡  Upgrade Cars  (STATE_UPGRADE_CARS)",
        "zh": "  [3] ⚡  加技能点  (STATE_UPGRADE_CARS)",
    },
    "phase_3_desc": {
        "en": "       Enter garage → spend skill points on each Impreza",
        "zh": "       进入车库 → 逐辆选择 Impreza 并消耗技能点升级",
    },
    "phase_4": {
        "en": "  [4] 🗑️  Trash Cars  (STATE_TRASH_CARS)",
        "zh": "  [4] 🗑️  卖车  (STATE_TRASH_CARS)",
    },
    "phase_4_desc": {
        "en": "       Enter garage → batch-remove upgraded Imprezas",
        "zh": "       进入车库 → 批量移除已升级完的 Impreza",
    },
    "phase_5": {
        "en": "  [5] ⏭️  Skip Buy  (Farm → Upgrade → Trash loop)",
        "zh": "  [5] ⏭️  跳过买车  (刷点 → 加点 → 卖车 循环)",
    },
    "phase_5_desc": {
        "en": "       Skip buying phase; use cars already in garage",
        "zh": "       跳过买车阶段，适用于车库已有未加点的车",
    },
    "phase_0": {
        "en": "  [0] 🔄  Auto Loop  (default: full cycle from Farm)",
        "zh": "  [0] 🔄  自动循环  (默认：从刷点开始完整循环)",
    },
    "phase_prompt": {
        "en": "  Select phase [0-5] (default 0): ",
        "zh": "  选择阶段 [0-5] (默认 0): ",
    },
    # Feedback
    "selected": {"en": "  ✅ Selected: ", "zh": "  ✅ 已选择: "},
    "skip_buy_msg": {
        "en": "  ✅ Selected: Skip Buy loop (Farm → Upgrade → Trash)",
        "zh": "  ✅ 已选择: 跳过买车循环 (刷点 → 加点 → 卖车)",
    },
    "invalid": {
        "en": "  ❌ Invalid choice.",
        "zh": "  ❌ 无效选择。",
    },
    "launching_web": {
        "en": "  🚀 Launching Web UI",
        "zh": "  🚀 正在启动 Web UI",
    },
}

# Phase display names
_PHASE_NAMES: dict[str, dict[str | None, str]] = {
    "en": {
        None: "Auto Loop",
        STATE_FARM_POINTS: "Farm Points",
        STATE_BUY_CARS: "Buy Cars",
        STATE_UPGRADE_CARS: "Upgrade Cars",
        STATE_TRASH_CARS: "Trash Cars",
    },
    "zh": {
        None: "自动循环",
        STATE_FARM_POINTS: "刷技能点",
        STATE_BUY_CARS: "买车",
        STATE_UPGRADE_CARS: "加技能点",
        STATE_TRASH_CARS: "卖车",
    },
}


def _t(key: str, lang: str) -> str:
    """Look up a translated string by key and language code."""
    return _STRINGS[key][lang]


# ---------------------------------------------------------------------------
# Interactive selectors
# ---------------------------------------------------------------------------


def _select_language() -> str:
    """Display language selection menu.

    Returns:
        str: "en" or "zh"
    """
    print("\n" + "=" * 50)
    print(_t("lang_title", "en"))
    print("=" * 50)
    print()
    print(_t("lang_opt_en", "en"))
    print()
    print(_t("lang_opt_zh", "en"))
    print()
    print("=" * 50)

    while True:
        choice: str = input(_t("lang_prompt", "en")).strip()
        if choice in ("", "1"):
            return "en"
        if choice == "2":
            return "zh"
        print("  ❌ Invalid")


def _select_mode(lang: str) -> str:
    """Display mode selection menu in the chosen language.

    Args:
        lang: Language code ("en" or "zh").

    Returns:
        str: "web" or "console"
    """
    print("\n" + "=" * 50)
    print(_t("mode_title", lang))
    print("=" * 50)
    print()
    print(_t("mode_web", lang))
    print(_t("mode_web_desc", lang))
    print()
    print(_t("mode_console", lang))
    print(_t("mode_console_desc", lang))
    print()
    print("=" * 50)

    while True:
        choice: str = input(_t("mode_prompt", lang)).strip()
        if choice in ("", "1"):
            return "web"
        if choice == "2":
            return "console"
        print(_t("invalid", lang))


def show_start_menu(lang: str = "en"):
    """Display the startup phase selection menu.

    Args:
        lang: Language code ("en" or "zh").

    Returns:
        tuple[str | None, bool]: (state constant, skip_buy flag)
    """
    print("\n" + "=" * 58)
    print(_t("phase_title", lang))
    print("=" * 58)
    print()
    for i in range(1, 6):
        print(_t(f"phase_{i}", lang))
        print(_t(f"phase_{i}_desc", lang))
        print()
    print(_t("phase_0", lang))
    print()
    print("=" * 58)

    state_map: dict[str, str | None] = {
        "0": None,
        "1": STATE_FARM_POINTS,
        "2": STATE_BUY_CARS,
        "3": STATE_UPGRADE_CARS,
        "4": STATE_TRASH_CARS,
        "5": STATE_FARM_POINTS,
    }

    while True:
        choice = input(_t("phase_prompt", lang)).strip()
        if choice == "":
            choice = "0"
        if choice in state_map:
            selected = state_map[choice]
            skip_buy = choice == "5"
            if skip_buy:
                print(f"\n{_t('skip_buy_msg', lang)}")
            else:
                print(f"\n{_t('selected', lang)}{_PHASE_NAMES[lang][selected]}")
            print()
            return selected, skip_buy
        else:
            print(_t("invalid", lang))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FH6 AutoBot — Full AFK Automation Tool")
    parser.add_argument("--web", action="store_true", help="Launch Web UI directly")
    parser.add_argument("--console", action="store_true", help="Launch console directly")
    parser.add_argument("--lang", choices=["en", "zh"], default=None, help="Language (en/zh)")
    parser.add_argument("--port", type=int, default=6800, help="Web UI port (default 6800)")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug image output to debug/ folder",
    )
    args = parser.parse_args()

    # Enable debug file output if requested
    if args.debug:
        from engine.ocr import enable_debug_files

        enable_debug_files()
        print("  [DEBUG] Debug image output enabled → debug/")

    # Step 1: Language selection
    lang: str = args.lang if args.lang else _select_language()

    # Apply language globally for all runtime logs
    from engine.i18n import set_lang

    set_lang(lang)

    # Step 2: Mode selection (CLI flags take priority)
    if args.web:
        mode = "web"
    elif args.console:
        mode = "console"
    else:
        mode = _select_mode(lang)

    # Step 3: Launch
    if mode == "web":
        from web.server import start_server

        print(f"\n{_t('launching_web', lang)} (http://localhost:{args.port}) ...\n")
        start_server(port=args.port)
    else:
        initial_state, skip_buy = show_start_menu(lang)
        run_master_bot_loop(initial_state=initial_state, skip_buy=skip_buy)
