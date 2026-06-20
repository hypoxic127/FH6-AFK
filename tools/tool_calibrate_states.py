# -*- coding: utf-8 -*-
"""
tool_calibrate_states.py — 状态检测校准工具
============================================
在各个游戏界面运行，自动采集参考数据（直方图/亮度值）。

用法:
  python tool_calibrate_states.py                  # 交互模式
  python tool_calibrate_states.py --state RACE_END  # 指定状态
  python tool_calibrate_states.py --list            # 列出所有可校准状态

校准完成后数据保存到 state_references.json
"""

import os
import sys
import time

import cv2
import numpy as np

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import module_macro
from module_state_detect import NAV_PAGES, RACING_ROIS, TAB_ZONES, StateDetector

ALL_STATES = {
    # 主菜单标签 (需要在对应标签页激活时校准)
    "TAB_CAMPAIGN": "主菜单 - Campaign 标签激活",
    "TAB_CARS": "主菜单 - Cars 标签激活",
    "TAB_MY_HORIZON": "主菜单 - My Horizon 标签激活",
    "TAB_ONLINE": "主菜单 - Online 标签激活",
    "TAB_CREATIVE_HUB": "主菜单 - Creative Hub 标签激活",
    "TAB_STORE": "主菜单 - Store 标签激活",
    # 导航子页面
    "EVENTLAB_MENU": "EventLab 菜单 (Play Event 可见)",
    "FAVORITES_LIST": "My Favorites 赛事列表",
    "RACE_READY": "比赛类型选择 (Choose 界面)",
    "CAR_SELECT": "车辆选择界面",
    "PRE_RACE": "赛前准备 (Start Race Event)",
    # 比赛状态
    "RACE_END": "比赛结束 (Restart/Continue 按钮)",
    "NEXT_SCREEN": "结算画面 (Next 按钮)",
    "PLAYING": "驾驶中 (有速度表 HUD)",
}


def capture_game_screenshot():
    """截取游戏窗口截图，返回 1600x900 resized。"""
    hwnd = module_macro.find_game_window()
    if not hwnd:
        print("[ERROR] 游戏窗口未找到!")
        return None
    module_macro.force_foreground(hwnd)
    time.sleep(0.5)
    resized, _, _, _, _ = module_macro.capture_screenshot(hwnd)
    return resized


def interactive_mode():
    """交互式校准：用户选择状态，工具自动截图采集。"""
    detector = StateDetector()

    print("\n" + "=" * 60)
    print("   状态检测校准工具 — 交互模式")
    print("=" * 60)
    print("\n可校准的状态:")
    print("-" * 60)

    state_list = list(ALL_STATES.items())
    for i, (state, desc) in enumerate(state_list, 1):
        print(f"  {i:2d}. {state:25s} | {desc}")

    print(f"\n  {len(state_list) + 1:2d}. {'ALL':25s} | 连续校准所有状态")
    print(f"  {len(state_list) + 2:2d}. {'TEST':25s} | 测试当前界面的检测结果")
    print("-" * 60)

    while True:
        try:
            choice = input("\n请输入编号 (q=退出): ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice.lower() == "q":
            break

        try:
            idx = int(choice)
        except ValueError:
            print("  无效输入")
            continue

        if idx == len(state_list) + 2:
            # TEST 模式
            test_detection(detector)
            continue

        if idx == len(state_list) + 1:
            # ALL 模式：逐个校准
            calibrate_all(detector, state_list)
            continue

        if 1 <= idx <= len(state_list):
            state_name, desc = state_list[idx - 1]
            calibrate_single(detector, state_name, desc)
        else:
            print("  超出范围")


def calibrate_single(detector, state_name, desc):
    """校准单个状态。"""
    print(f"\n  → 准备校准: {state_name} ({desc})")
    print("  → 请将游戏切换到该界面，然后按 Enter...")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        return

    print("  → 3 秒后截图...")
    time.sleep(3)

    resized = capture_game_screenshot()
    if resized is None:
        print("  [ERROR] 截图失败!")
        return

    # 保存截图用于验证
    os.makedirs("debug/calibration", exist_ok=True)
    cv2.imwrite(f"debug/calibration/{state_name}.png", resized)

    # 采集参考数据
    detector.capture_reference(resized, state_name)
    print(f"  ✅ {state_name} 校准完成! 截图已保存到 debug/calibration/{state_name}.png")

    # 立即测试
    result = detector.detect(resized)
    print(f"  → 检测测试: detect() = '{result}'")


def calibrate_all(detector, state_list):
    """连续校准所有状态。"""
    print("\n  ═══ 连续校准模式 ═══")
    print("  每个状态校准前会等待你切换到对应界面")

    for i, (state_name, desc) in enumerate(state_list, 1):
        print(f"\n  [{i}/{len(state_list)}] {state_name}: {desc}")
        print("  → 请将游戏切换到该界面，然后按 Enter (s=跳过)...")
        try:
            resp = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if resp == "s":
            print(f"  → 跳过 {state_name}")
            continue

        print("  → 3 秒后截图...")
        time.sleep(3)

        resized = capture_game_screenshot()
        if resized is None:
            print("  [ERROR] 截图失败，跳过")
            continue

        os.makedirs("debug/calibration", exist_ok=True)
        cv2.imwrite(f"debug/calibration/{state_name}.png", resized)
        detector.capture_reference(resized, state_name)
        print(f"  ✅ {state_name} 校准完成!")

    print("\n  ═══ 全部校准完成 ═══")


def test_detection(detector):
    """测试当前界面的检测结果。"""
    print("\n  → 测试当前界面检测...")
    print("  → 3 秒后截图...")
    time.sleep(3)

    resized = capture_game_screenshot()
    if resized is None:
        print("  [ERROR] 截图失败!")
        return

    h, w = resized.shape[:2]

    # 运行完整检测
    t0 = time.time()
    state = detector.detect(resized, mode="menu")
    t_menu = (time.time() - t0) * 1000

    t0 = time.time()
    state_racing = detector.detect(resized, mode="racing")
    t_racing = (time.time() - t0) * 1000

    print("\n  ┌─ 检测结果 ─────────────────────")
    print(f"  │  Menu 模式:   {state}  ({t_menu:.0f}ms)")
    print(f"  │  Racing 模式: {state_racing or 'None'}  ({t_racing:.0f}ms)")

    # 显示标签栏亮度
    from module_state_detect import TAB_BAR_X, TAB_BAR_Y

    tab_roi = resized[int(h * TAB_BAR_Y[0]) : int(h * TAB_BAR_Y[1]), int(w * TAB_BAR_X[0]) : int(w * TAB_BAR_X[1])]
    tab_gray = cv2.cvtColor(tab_roi, cv2.COLOR_BGR2GRAY)
    th, tw = tab_gray.shape[:2]
    print("  │")
    print("  │  标签栏亮度:")
    for tab_name, (x1, x2) in TAB_ZONES.items():
        zone = tab_gray[:, int(tw * x1) : int(tw * x2)]
        b = float(np.mean(zone))
        print(f"  │    {tab_name:20s}: {b:.1f}")

    # 显示目标车辆检测
    is_target = detector.detect_target_car(resized)
    print("  │")
    print(f"  │  目标车辆: {'✅ Subaru Impreza 22B-STI' if is_target else '❌ 不匹配'}")
    print("  └──────────────────────────────\n")

    # 保存测试截图
    os.makedirs("debug", exist_ok=True)
    cv2.imwrite("debug/test_detection.png", resized)


def single_state_mode(state_name):
    """命令行指定状态的校准模式。"""
    if state_name not in ALL_STATES:
        print(f"[ERROR] 未知状态: {state_name}")
        print(f"可用状态: {', '.join(ALL_STATES.keys())}")
        return

    detector = StateDetector()
    desc = ALL_STATES[state_name]
    print(f"\n  → 校准: {state_name} ({desc})")
    print("  → 3 秒后截图...")
    time.sleep(3)

    resized = capture_game_screenshot()
    if resized is None:
        print("  [ERROR] 截图失败!")
        return

    os.makedirs("debug/calibration", exist_ok=True)
    cv2.imwrite(f"debug/calibration/{state_name}.png", resized)
    detector.capture_reference(resized, state_name)
    print(f"  ✅ {state_name} 校准完成!")


def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--list":
            print("\n可校准状态:")
            for state, desc in ALL_STATES.items():
                print(f"  {state:25s} | {desc}")
            return
        if arg == "--state" and len(sys.argv) > 2:
            single_state_mode(sys.argv[2])
            return
        print(f"用法: python {sys.argv[0]} [--list | --state STATE_NAME]")
        return

    interactive_mode()


if __name__ == "__main__":
    main()
