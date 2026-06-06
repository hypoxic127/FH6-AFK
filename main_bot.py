# -*- coding: utf-8 -*-
"""
FORZA HORIZON 6 AUTOBOT — Main Entry Point (main_bot.py)
=========================================================
Entry point for the full automation system. Provides an interactive
bilingual (EN/CN) menu for selecting the startup phase.

Four-phase loop / 四阶段循环:
  Farm Points → Buy Cars → Upgrade Cars → Trash Cars → (loop)

Usage / 使用方法:
    python main_bot.py

Select [0] for full auto-loop (default: start from Farm Points).
Select [1]-[4] to start from a specific phase.
"""

from macro import (
    STATE_BUY_CARS,
    STATE_FARM_POINTS,
    STATE_TRASH_CARS,
    STATE_UPGRADE_CARS,
    run_master_bot_loop,
)


def show_start_menu():
    """Display the bilingual startup phase selection menu.

    Returns:
        tuple[str | None, bool]: (state constant, skip_buy flag)
    """
    print("\n" + "=" * 58)
    print("   FORZA HORIZON 6 AUTOBOT — Startup Menu / 启动菜单")
    print("=" * 58)
    print()
    print("  [1] 🏎️  Farm Points / 刷技能点  (STATE_FARM_POINTS)")
    print("       OCR scan skill points → auto-grind EventLab to 999")
    print("       OCR 扫描技能点 → 自动跑 EventLab 刷满 999")
    print()
    print("  [2] 🛒  Buy Cars / 买车  (STATE_BUY_CARS)")
    print("       Navigate to Car Collection → bulk-buy Subaru Impreza")
    print("       导航至 Car Collection → 批量购买 Subaru Impreza")
    print()
    print("  [3] ⚡  Upgrade Cars / 加技能点  (STATE_UPGRADE_CARS)")
    print("       Enter garage → spend skill points on each Impreza")
    print("       进入车库 → 逐辆选择 Impreza 并消耗技能点升级")
    print()
    print("  [4] 🗑️  Trash Cars / 卖车  (STATE_TRASH_CARS)")
    print("       Enter garage → batch-remove upgraded Imprezas")
    print("       进入车库 → 批量移除已升级完的 Impreza")
    print()
    print("  [5] ⏭️  Skip Buy / 跳过买车  (Farm → Upgrade → Trash)")
    print("       Skip buying phase; use cars already in garage")
    print("       跳过买车阶段，适用于车库已有未加点的车")
    print()
    print("  [0] 🔄  Auto Loop / 自动循环  (default / 默认)")
    print("       Full 4-phase loop starting from Farm Points")
    print("       从刷技能点开始完整四阶段循环")
    print()
    print("=" * 58)

    # Map option numbers to state constants
    state_map: dict[str, str | None] = {
        "0": None,  # Default: start from FARM_POINTS
        "1": STATE_FARM_POINTS,
        "2": STATE_BUY_CARS,
        "3": STATE_UPGRADE_CARS,
        "4": STATE_TRASH_CARS,
        "5": STATE_FARM_POINTS,  # Skip buy, loop from farm
    }

    # Bilingual display names
    names: dict[str | None, str] = {
        None: "Auto Loop / 自动循环",
        STATE_FARM_POINTS: "Farm Points / 刷技能点",
        STATE_BUY_CARS: "Buy Cars / 买车",
        STATE_UPGRADE_CARS: "Upgrade Cars / 加技能点",
        STATE_TRASH_CARS: "Trash Cars / 卖车",
    }

    # Wait for valid input
    while True:
        choice = input("  Select phase / 选择阶段 [0-5] (default 0): ").strip()
        if choice == "":
            choice = "0"  # Empty input → default
        if choice in state_map:
            selected = state_map[choice]
            skip_buy = choice == "5"
            if skip_buy:
                print("\n  ✅ Selected: Skip Buy loop / 跳过买车循环 (Farm → Upgrade → Trash)")
            else:
                print(f"\n  ✅ Selected / 已选择: {names[selected]}")
            print()
            return selected, skip_buy
        else:
            print("  ❌ Invalid choice / 无效选择, enter 0-5.")


def _select_mode() -> str:
    """Display bilingual mode selection menu at startup.

    Returns:
        str: "web" or "console"
    """
    print("\n" + "=" * 58)
    print("   FH6-AFK — Mode Selection / 启动模式选择")
    print("=" * 58)
    print()
    print("  [1] 🌐  Web UI Dashboard / 控制面板")
    print("       Browser-based GUI, supports remote monitoring")
    print("       浏览器可视化操作，支持手机远程监控")
    print()
    print("  [2] 💻  Terminal Console / 终端控制台")
    print("       Classic CLI interaction for advanced users")
    print("       经典命令行交互，适合高级用户")
    print()
    print("=" * 58)

    while True:
        choice: str = input("  Select mode / 选择模式 [1/2] (default 1): ").strip()
        if choice in ("", "1"):
            return "web"
        if choice == "2":
            return "console"
        print("  ❌ Invalid choice / 无效选择, enter 1 or 2.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="FH6 AutoBot — Full AFK Automation Tool / 全自动挂机工具"
    )
    parser.add_argument("--web", action="store_true", help="Launch Web UI directly / 直接启动 Web UI")
    parser.add_argument("--console", action="store_true", help="Launch console directly / 直接启动控制台")
    parser.add_argument("--port", type=int, default=6800, help="Web UI port (default 6800)")
    args = parser.parse_args()

    # Priority: CLI flags > interactive selection
    if args.web:
        mode = "web"
    elif args.console:
        mode = "console"
    else:
        mode = _select_mode()

    if mode == "web":
        from web.server import start_server

        print(f"\n  🚀 Launching Web UI / 启动 Web UI (http://localhost:{args.port}) ...\n")
        start_server(port=args.port)
    else:
        initial_state, skip_buy = show_start_menu()
        run_master_bot_loop(initial_state=initial_state, skip_buy=skip_buy)
