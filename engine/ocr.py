# -*- coding: utf-8 -*-
"""
FH6_AutoBot 计算机视觉模块 (module_ocr.py)
===========================================
基于 OpenCV + Tesseract OCR 的游戏画面分析引擎，提供以下核心能力：

  1. OCR 文字识别
     - read_skill_points(): 读取技能点数字（多 PSM 投票 + 零技能点保底）
     - read_text_in_roi(): 通用 ROI 区域 OCR

  3. 颜色空间检测
     - has_green_selection_border(): 检测 Forza 高亮选中的绿色边框
     - has_green_selection_border_padded(): 带外扩的绿色边框检测
     - find_cursor_position(): 检测 UI 光标（亮黄绿色焦点框）的中心坐标
     - verify_new_target_car(): 双重校验（OCR 车名 + HSV 检测 NEW 黄色标签）
     - check_is_high_class(): 通过紫色 PI 徽章检测 S1/S2 级别车辆
     - has_cell_below(): 通过亮度/方差采样检测网格下方是否有车

所有函数的输入图像统一为 1600×900 缩放后的 BGR 格式截图。
"""

import os
import shutil
from typing import Callable

import cv2
import numpy as np
import pytesseract
from colorama import Fore, Style

from engine.i18n import t
from engine.utils import log_error, log_success, log_warning, safe_print

# ==========================================
# 全局配置
# ==========================================

# 调试开关：设为 True 时会在 debug/ 目录写入 OCR 调试图片
# 启动方式：python main_bot.py --debug  或在代码中手动设置
# Enable: python main_bot.py --debug  (or set manually)
DEBUG_WRITE_FILES = False


def enable_debug_files() -> None:
    """Enable debug image output to debug/ directory."""
    global DEBUG_WRITE_FILES
    DEBUG_WRITE_FILES = True


# ==========================================
# HSV 颜色阈值常量（全局唯一真相源）
# ==========================================
# 以下阈值通过对 Forza Horizon 6 游戏 UI 的实际截图分析得出，
# 使用 HSV 色彩空间而非 RGB，因为 HSV 对亮度变化更鲁棒。
#
# 绿色边框阈值（用于检测选中状态的高亮绿色边框）
# H=35-85 覆盖从黄绿到蓝绿的范围
HSV_GREEN_BORDER_LOWER = np.array([35, 100, 40])
HSV_GREEN_BORDER_UPPER = np.array([85, 255, 255])

# 绿色光标阈值（用于检测 UI 焦点框，比边框阈值更宽松）
HSV_GREEN_CURSOR_LOWER = np.array([30, 200, 200])
HSV_GREEN_CURSOR_UPPER = np.array([45, 255, 255])

# 黄色 NEW 标签阈值（用于检测车辆卡片上的 "NEW" 标记）
# H=20-30 对应纯黄色范围
HSV_YELLOW_NEW_LOWER = np.array([20, 100, 100])
HSV_YELLOW_NEW_UPPER = np.array([30, 255, 255])

# ==========================================
# 卡片裁剪尺寸常量
# ==========================================
# 车库网格中单张车辆卡片的裁剪区域大小（以光标中心为基准）
CARD_CROP_W = 284  # 卡片裁剪宽度（像素）— 与实际高亮边框匹配
CARD_CROP_H = 217  # 卡片裁剪高度（像素）— 与实际高亮边框匹配

# ==========================================
# 卡片内文字行 ROI（相对于 CARD_CROP 的百分比）
# ==========================================
# 第1行：车名（黑色 #000000，灰度值=0，会跑马灯滚动）
# 例如 "IMPREZA 22B-STI VERSION"
NAME_LINE_Y1: float = 0.0415
NAME_LINE_Y2: float = 0.1613
NAME_LINE_X1: float = 0.0282
NAME_LINE_X2: float = 0.9613
# 第2行：年份+品牌（灰色 #828282，灰度值≈130，静止不滚动）
# 例如 "1998 SUBARU"
# 注意：灰度值 130 > 127，固定阈值 127 的 BINARY_INV 会把文字当成背景丢掉！
YEAR_LINE_Y1: float = 0.1567
YEAR_LINE_Y2: float = 0.2765
YEAR_LINE_X1: float = 0.2641
YEAR_LINE_X2: float = 0.7641

# ==========================================
# 目标车辆识别关键词（全局唯一真相源）
# ==========================================
# 1998 Subaru Impreza 22B-STI Version 的独特特征关键词
# --- 1998 Impreza 22B-STI 识别关键词 ---
# "22b" 是区分 22B-STI 与 2008 WRX STI 的唯一可靠标识，必须命中
# "preza"/"sti" 作为辅助确认（至少命中 1 个）
IMPREZA_22B_REQUIRED: list[str] = ["22b"]  # 必须全部命中
IMPREZA_22B_OPTIONAL: list[str] = ["preza", "sti"]  # 至少命中 1 个
# 向后兼容：保留原常量供 test 使用
IMPREZA_22B_KEYWORDS: list[str] = IMPREZA_22B_REQUIRED + IMPREZA_22B_OPTIONAL
IMPREZA_22B_MIN_MATCH: int = 2  # 向后兼容（但实际匹配逻辑已改用 REQUIRED+OPTIONAL）

# --- 年份+品牌行识别关键词（第2行，灰色静止文字） ---
# 使用宽松部分匹配，因为 OCR 对灰色小字噪声较大
# "1998"→可能读成 "1995"/"199"/"19s" 等，用 "199" 前缀匹配
# "subaru"→可能读成 "subar"/"suba"/"susar" 等，用 "sub" 匹配
YEAR_BRAND_REQUIRED: list[str] = ["199"]  # 年份前缀必须命中
YEAR_BRAND_OPTIONAL: list[str] = ["sub", "uba"]  # 品牌片段至少命中 1 个

# ==========================================
# 空位检测阈值
# ==========================================
EMPTY_SLOT_BRIGHTNESS_THRESHOLD: float = 50.0  # 亮度 ≤ 此值视为暗区
EMPTY_SLOT_VARIANCE_THRESHOLD: float = 5.0  # 方差 ≤ 此值视为纯色


def match_impreza_22b(text: str) -> tuple[bool, list[str]]:
    """检查文本是否匹配 1998 Impreza 22B-STI（排除 2008 WRX STI 等同品牌车型）。

    匹配规则：
    1. REQUIRED 列表中的关键词必须**全部**命中（"22b" 是唯一区分标识）
    2. OPTIONAL 列表中的关键词至少命中 **1 个**（"preza" / "sti"）

    Args:
        text: OCR 识别出的卡片文本（已 lower()）

    Returns:
        (is_match, matched_keywords) 元组
    """
    text_lower = text.lower()
    req_matched = [kw for kw in IMPREZA_22B_REQUIRED if kw in text_lower]
    opt_matched = [kw for kw in IMPREZA_22B_OPTIONAL if kw in text_lower]
    all_matched = req_matched + opt_matched

    is_match = (len(req_matched) == len(IMPREZA_22B_REQUIRED)) and (len(opt_matched) >= 1)
    return is_match, all_matched


def match_year_brand(text: str) -> tuple[bool, list[str]]:
    """检查年份+品牌行文本是否匹配 '1998 SUBARU'。

    使用宽松前缀匹配，因为灰色小字 OCR 噪声较大：
    - "199" 前缀匹配年份（1998 可能被读成 1995/1905/19s 等）
    - "sub"/"uba" 匹配品牌（subaru 可能被读成 susar/suba 等）

    Args:
        text: OCR 识别出的年份行文本（已 lower()）

    Returns:
        (is_match, matched_keywords) 元组
    """
    text_lower = text.lower()
    req_matched = [kw for kw in YEAR_BRAND_REQUIRED if kw in text_lower]
    opt_matched = [kw for kw in YEAR_BRAND_OPTIONAL if kw in text_lower]
    all_matched = req_matched + opt_matched

    is_match = (len(req_matched) == len(YEAR_BRAND_REQUIRED)) and (len(opt_matched) >= 1)
    return is_match, all_matched


def _ocr_year_brand_text(card_img: np.ndarray | None, debug_label: str = "YEAR") -> str:
    """对卡片的年份+品牌行（第2行，灰色 #828282 静止文字）做 OCR。

    文字颜色 #828282（灰度值≈130），背景为浅色。
    固定阈值 127 的 BINARY_INV 失效原因：130 > 127，文字被当成背景丢掉。
    使用 Otsu 自适应阈值可自动找到 130~255 之间的最佳分割点。
    此行文字不会滚动，是稳定的辅助识别信号。

    Args:
        card_img: BGR 格式的完整卡片裁剪图（284×217）
        debug_label: 调试输出时的标签名

    Returns:
        str: 小写化的 OCR 识别文本，失败时返回空字符串
    """
    if card_img is None or card_img.size == 0:
        return ""
    try:
        h, w = card_img.shape[:2]
        # 裁剪年份+品牌行区域
        y1 = int(h * YEAR_LINE_Y1)
        y2 = int(h * YEAR_LINE_Y2)
        x1 = int(w * YEAR_LINE_X1)
        x2 = int(w * YEAR_LINE_X2)
        year_roi = card_img[y1:y2, x1:x2]
        if year_roi.size == 0:
            return ""

        gray = cv2.cvtColor(year_roi, cv2.COLOR_BGR2GRAY)
        # Otsu 自适应阈值 — 灰色文字的最佳二值化方法
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        padded = cv2.copyMakeBorder(thresh, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=[255, 255, 255])
        upscaled = cv2.resize(padded, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        text = pytesseract.image_to_string(upscaled).strip().lower()

        try:
            safe_print(f"\n{Fore.CYAN}=================== [{debug_label} OCR] ===================")
            safe_print(f"{Fore.CYAN}Year+Brand text:")
            safe_print(Fore.WHITE + (text if text else "[empty]"))
            safe_print(f"{Fore.CYAN}{'=' * (len(debug_label) + 36)}\n")
        except UnicodeEncodeError:
            pass
        return text
    except Exception as e:
        log_error(f"_ocr_year_brand_text ({debug_label}) error: {e}")
    return ""


def _ocr_name_line_text(card_img: np.ndarray | None, debug_label: str = "NAME") -> str:
    """对卡片的车名行（第1行，黑色 #000000 文字，可能滚动）做 OCR。

    车名文字颜色 #000000（灰度值=0），背景为浅色。
    使用 Otsu 自适应阈值获得最佳二值化效果。

    Args:
        card_img: BGR 格式的完整卡片裁剪图（284×217）
        debug_label: 调试输出时的标签名

    Returns:
        str: 小写化的 OCR 识别文本，失败时返回空字符串
    """
    if card_img is None or card_img.size == 0:
        return ""
    try:
        h, w = card_img.shape[:2]
        # 裁剪车名行区域
        y1 = int(h * NAME_LINE_Y1)
        y2 = int(h * NAME_LINE_Y2)
        x1 = int(w * NAME_LINE_X1)
        x2 = int(w * NAME_LINE_X2)
        name_roi = card_img[y1:y2, x1:x2]
        if name_roi.size == 0:
            return ""

        gray = cv2.cvtColor(name_roi, cv2.COLOR_BGR2GRAY)
        # 车名 #000000（灰度=0）在浅色背景上 → Otsu 自适应阈值
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        padded = cv2.copyMakeBorder(thresh, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=[255, 255, 255])
        upscaled = cv2.resize(padded, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        text = pytesseract.image_to_string(upscaled).strip().lower()

        try:
            safe_print(f"\n{Fore.YELLOW}=================== [{debug_label} OCR] ===================")
            safe_print(f"{Fore.YELLOW}Car name text:")
            safe_print(Fore.WHITE + (text if text else "[empty]"))
            safe_print(f"{Fore.YELLOW}{'=' * (len(debug_label) + 36)}\n")
        except UnicodeEncodeError:
            pass
        return text
    except Exception as e:
        log_error(f"_ocr_name_line_text ({debug_label}) error: {e}")
    return ""


def verify_impreza_22b(
    card_img: np.ndarray | None,
    debug_label: str = "VERIFY",
    capture_card_fn: "Callable[[], np.ndarray | None] | None" = None,
    max_name_retries: int = 5,
    retry_delay: float = 0.3,
) -> tuple[bool, list[str]]:
    """综合验证卡片是否为 1998 Impreza 22B-STI，双行冗余 OCR + 滚动重试。

    策略：
    1. 先查第2行（年份+品牌，灰色 #828282，静止不滚动）→ 稳定信号
    2. 再查第1行（车名，黑色 #000000，会跑马灯滚动）→ 确认 "22b"
    3. 如果第2行命中但第1行未命中 → 连续重试第1行（因为滚动可能错过）
    4. 第1行命中即确认；所有重试都失败则依赖第2行结果

    Args:
        card_img: BGR 格式的完整卡片裁剪图
        debug_label: 调试标签
        capture_card_fn: 可选回调函数，返回新的卡片裁剪图（用于滚动重试时重新截图）
        max_name_retries: 第1行连续重试次数（仅当第2行命中且第1行未命中时触发）
        retry_delay: 每次重试间隔（秒）

    Returns:
        (is_match, all_matched_keywords) 元组
    """
    import time

    if card_img is None or card_img.size == 0:
        return False, []

    all_matched: list[str] = []

    # === 步骤1：先查第2行（年份+品牌，静止可靠） ===
    year_text = _ocr_year_brand_text(card_img, debug_label=f"{debug_label}_YEAR")
    year_hit, year_kws = match_year_brand(year_text)
    all_matched.extend([f"yr:{kw}" for kw in year_kws])

    # === 步骤2：查第1行（车名，可能滚动） ===
    name_text = _ocr_name_line_text(card_img, debug_label=f"{debug_label}_NAME")
    name_hit, name_kws = match_impreza_22b(name_text)
    all_matched.extend(name_kws)

    # === 步骤3：滚动重试逻辑 ===
    # 条件：第2行确认是 1998 SUBARU，但第1行没找到 "22b"（可能因为滚动错过）
    if year_hit and not name_hit and capture_card_fn is not None:
        try:
            safe_print(
                f"\n{Fore.YELLOW}[{debug_label}] "
                f"年份行命中但车名行未命中 → 启动滚动重试 (最多 {max_name_retries} 次)"
                f"{Style.RESET_ALL}"
            )
        except UnicodeEncodeError:
            pass

        for attempt in range(1, max_name_retries + 1):
            time.sleep(retry_delay)
            try:
                new_card = capture_card_fn()
                if new_card is None or new_card.size == 0:
                    continue
                retry_text = _ocr_name_line_text(new_card, debug_label=f"{debug_label}_RETRY_{attempt}")
                retry_hit, retry_kws = match_impreza_22b(retry_text)
                if retry_hit:
                    name_hit = True
                    # 只追加新命中的关键词（去重）
                    for kw in retry_kws:
                        if kw not in all_matched:
                            all_matched.append(kw)
                    try:
                        safe_print(f"{Fore.GREEN}[{debug_label}] 重试 #{attempt} 命中! kw={retry_kws}{Style.RESET_ALL}")
                    except UnicodeEncodeError:
                        pass
                    break
            except Exception as e:
                log_warning(f"[{debug_label}] 重试 #{attempt} 异常: {e}")

        if not name_hit:
            try:
                safe_print(
                    f"{Fore.YELLOW}[{debug_label}] "
                    f"{max_name_retries} 次重试均未命中车名行，依赖年份行结果"
                    f"{Style.RESET_ALL}"
                )
            except UnicodeEncodeError:
                pass

    # === 最终判定 ===
    # 任一行命中即通过（双行冗余）
    is_match = name_hit or year_hit

    try:
        status = f"{Fore.GREEN}✓ CONFIRMED" if is_match else f"{Fore.RED}✗ REJECTED"
        safe_print(
            f"\n{Fore.MAGENTA}[{debug_label}] name_hit={name_hit} year_hit={year_hit} → {status}{Style.RESET_ALL}"
        )
        safe_print(f"{Fore.MAGENTA}  matched: {all_matched}{Style.RESET_ALL}\n")
    except UnicodeEncodeError:
        pass

    return is_match, all_matched


# ==========================================
# 通用卡片裁剪
# ==========================================


def crop_card_roi(image: np.ndarray | None, cursor_x: int, cursor_y: int) -> np.ndarray | None:
    """根据光标中心坐标裁剪车辆卡片区域。

    在 1600×900 缩放画面中，以 (cursor_x, cursor_y) 为中心，
    裁剪 CARD_CROP_W × CARD_CROP_H 大小的矩形区域。
    坐标会被安全地钳位到图像边界内。

    Args:
        image: 1600×900 BGR 格式截图，None 时返回 None
        cursor_x: 光标中心 X 坐标
        cursor_y: 光标中心 Y 坐标

    Returns:
        裁剪后的卡片 BGR 图像，无效时返回 None
    """
    if image is None or image.size == 0:
        return None
    h, w = image.shape[:2]
    x1 = max(0, cursor_x - CARD_CROP_W // 2)
    x2 = min(w, cursor_x + CARD_CROP_W // 2)
    y1 = max(0, cursor_y - CARD_CROP_H // 2)
    y2 = min(h, cursor_y + CARD_CROP_H // 2)
    roi = image[y1:y2, x1:x2]
    return roi if roi.size > 0 else None


# ==========================================
# 一、Tesseract OCR 初始化
# ==========================================


def setup_tesseract() -> bool:
    """定位并配置 Tesseract OCR 引擎路径。

    查找策略（按优先级）：
    1. 系统 PATH（pytesseract 默认行为）
    2. Windows 注册表（UB-Mannheim 安装器写入的路径，覆盖自定义安装位置）
    3. shutil.which() 搜索
    4. 硬编码常见路径（Program Files / 本地 tools 目录 / PyInstaller 打包路径）

    返回:
        bool: True 表示配置成功，False 表示未找到 Tesseract
    """
    # === 策略 1: 系统 PATH ===
    try:
        pytesseract.get_tesseract_version()
        log_success(t("ocr.tesseract_ok"))
        return True
    except pytesseract.TesseractNotFoundError:
        pass

    # === 策略 2: Windows 注册表 ===
    # UB-Mannheim 安装器写入 HKLM\SOFTWARE\Tesseract-OCR\InstallDir
    # 无论用户装到哪个目录都能找到
    registry_path = _find_tesseract_in_registry()
    if registry_path:
        pytesseract.pytesseract.tesseract_cmd = registry_path
        log_success(f"Tesseract found via Registry: {registry_path}")
        return True

    # === 策略 3: shutil.which() ===
    which_path = shutil.which("tesseract")
    if which_path and os.path.isfile(which_path):
        pytesseract.pytesseract.tesseract_cmd = which_path
        log_success(f"Tesseract found via which: {which_path}")
        return True

    # === 策略 4: 硬编码常见路径 ===
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        from engine.runtime import get_base_dir, get_user_dir

        base_dir = get_base_dir()
        user_dir = get_user_dir()
    except ImportError:
        base_dir = os.path.dirname(script_dir)
        user_dir = base_dir
    common_paths = [
        # 本地 tools 目录（便携版 / CI 打包）
        os.path.join(script_dir, "tools", "tesseract", "tesseract.exe"),
        os.path.join(base_dir, "tools", "tesseract", "tesseract.exe"),
        os.path.join(user_dir, "tesseract", "tesseract.exe"),
        # exe 同级目录
        os.path.join(base_dir, "tesseract", "tesseract.exe"),
        os.path.join(base_dir, "Tesseract-OCR", "tesseract.exe"),
        # Windows 默认安装路径
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
        os.path.expanduser(r"~\AppData\Local\Tesseract-OCR\tesseract.exe"),
    ]
    for path in common_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            log_success(f"Configured Tesseract path: {path}")
            return True

    log_warning(
        "Tesseract OCR not found! Please install from: "
        "https://github.com/UB-Mannheim/tesseract/releases\n"
        "  Or place tesseract.exe in the 'Tesseract-OCR' folder next to this program."
    )
    return False


def _find_tesseract_in_registry() -> str | None:
    """从 Windows 注册表查找 Tesseract 安装路径。

    UB-Mannheim 安装器会写入以下注册表键：
    - HKLM\\SOFTWARE\\Tesseract-OCR\\InstallDir
    - HKCU\\SOFTWARE\\Tesseract-OCR\\InstallDir
    同时检查 32 位和 64 位注册表视图。

    返回:
        Tesseract 可执行文件的完整路径，未找到则返回 None
    """
    if os.name != "nt":
        return None

    import winreg

    # 注册表键 + 视图组合
    reg_specs: list[tuple[int, str]] = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Tesseract-OCR"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Tesseract-OCR"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Tesseract-OCR"),
    ]
    for hive, subkey in reg_specs:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                install_dir, _ = winreg.QueryValueEx(key, "InstallDir")
                exe_path = os.path.join(str(install_dir), "tesseract.exe")
                if os.path.isfile(exe_path):
                    return exe_path
        except (FileNotFoundError, OSError):
            continue
    return None


# ==========================================
# 二、技能点 OCR 读取
# ==========================================


def read_skill_points(img: np.ndarray) -> int | None:
    """
    从游戏画面中 OCR 识别当前的技能点数字。

    技能点显示在暂停菜单 CARS 标签页的左侧区域。
    本函数使用多策略 OCR + 投票机制来提高识别准确率：

    处理流程：
    1. 根据 2560×1440 参考分辨率的百分比坐标裁剪技能点区域
    2. 灰度化 → Otsu 自适应阈值二值化 → 加边距 → 放大 3 倍
    3. 使用 PSM 7（单行文本模式）识别数字，精度最高
    4. 零技能点保底：如果 PSM 7 返回 0 或无结果，使用无限制 OCR 检测 "No Skill Points Available"

    参数:
        img: BGR 格式的游戏画面截图（原始分辨率）

    返回:
        int 或 None: 解析出的技能点数字，失败时返回 None
    """
    h, w, _ = img.shape

    # 技能点数字位于暂停菜单 Car Mastery 区域下方（背景为 #2AECF3 青色，文字为 #000000 黑色）
    # 使用用户精确标注的坐标，有效避开左侧 UI 分隔线，提高识别纯净度
    from engine.runtime import load_bot_config

    config = load_bot_config()
    custom_roi = config.get("custom_roi")

    if custom_roi and len(custom_roi) == 4:
        crop_y1 = int(h * custom_roi[0])
        crop_y2 = int(h * custom_roi[1])
        crop_x1 = int(w * custom_roi[2])
        crop_x2 = int(w * custom_roi[3])
    else:
        crop_y1 = int(h * 0.7244)
        crop_y2 = int(h * 0.7611)
        crop_x1 = int(w * 0.28)
        # 适当放宽右边界，确保能完整容纳三位数字（如 999），避免因为截断导致第三个数字丢失而识别成两位数
        crop_x2 = int(w * 0.307)

    roi = img[crop_y1:crop_y2, crop_x1:crop_x2]
    if roi.size == 0:
        return None

    # 可选：保存 ROI 原图到 debug/ 目录（便于排查识别问题）
    if DEBUG_WRITE_FILES:
        try:
            os.makedirs("debug", exist_ok=True)
            cv2.imwrite("debug/skill_points_roi.png", roi)
        except OSError as e:
            log_warning(t("ocr.debug_write_fail", path="skill_points_roi.png", err=e))

    # 图像预处理：3 种针对「蓝/青底黑字」优化的二值化方法
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    def _auto_polarity(thresh: np.ndarray) -> np.ndarray:
        """确保黑字白底（Tesseract 最佳输入格式）。"""
        border = (thresh[0, :].mean() + thresh[-1, :].mean() + thresh[:, 0].mean() + thresh[:, -1].mean()) / 4
        return cv2.bitwise_not(thresh) if border < 128 else thresh

    def _remove_vertical_lines(thresh: np.ndarray) -> np.ndarray:
        """去除 ROI 左侧的 UI 分隔竖线（1-3px 宽、贯穿全高）。

        扫描前 15% 的列，如果某列 >70% 为前景（黑=0），
        则判定为 UI 竖线而非数字笔画，擦除为白色背景。
        不使用 break：竖线可能不在最左边缘（前方有白色间隙）。
        """
        cleaned = thresh.copy()
        roi_h, roi_w = cleaned.shape
        scan_limit = max(1, int(roi_w * 0.15))
        for col in range(scan_limit):
            black_ratio = np.sum(cleaned[:, col] == 0) / roi_h
            if black_ratio > 0.70:
                cleaned[:, col] = 255
        return cleaned

    # --- 方法 A: Otsu 全局阈值（自适应求最佳分割点，通用性最强） ---
    _, thresh_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thresh_otsu = _remove_vertical_lines(_auto_polarity(thresh_otsu))

    # --- 方法 B: 自适应高斯阈值（抗局部光照渐变，对阴影/反光鲁棒） ---
    thresh_adapt = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 5)
    thresh_adapt = _remove_vertical_lines(_auto_polarity(thresh_adapt))

    # --- 方法 C: 固定阈值 120（蓝底黑字专用） ---
    # 背景 #2AECF3 (灰度值≈178)，黑色数字 (灰度值≈0)，阈值 120 干净分离
    _, thresh_fixed = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)
    thresh_fixed = _remove_vertical_lines(_auto_polarity(thresh_fixed))

    # 对每种变体：加大边距（40px 白色）+ 放大 4 倍
    # 注意：必须使用 INTER_LINEAR，INTER_CUBIC 在 4x 时会导致字形失真
    preprocessed: list[tuple[str, np.ndarray]] = []
    for label, thresh_img in [("otsu", thresh_otsu), ("adaptive", thresh_adapt), ("fixed", thresh_fixed)]:
        padded = cv2.copyMakeBorder(thresh_img, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=[255, 255, 255])
        upscaled = cv2.resize(padded, None, fx=4, fy=4, interpolation=cv2.INTER_LINEAR)
        preprocessed.append((label, upscaled))

    # 可选：保存预处理后图片（便于排查）
    if DEBUG_WRITE_FILES:
        try:
            os.makedirs("debug", exist_ok=True)
            for label, up_img in preprocessed:
                cv2.imwrite(f"debug/skill_points_{label}.png", up_img)
        except OSError as e:
            log_warning(t("ocr.debug_write_fail", path="skill_points_*.png", err=e))

    # ===== OCR 多策略投票 =====
    # 3 种预处理 × 4 种 PSM 模式 = 12 轮识别，取位数最长且出现最多的结果
    # PSM 6 = 自动分割, 7 = 单行, 8 = 单词, 13 = 原始行
    candidates: list[int] = []
    for label, up_img in preprocessed:
        for psm in (6, 7, 8, 13):
            config = f"--psm {psm} -c tessedit_char_whitelist=0123456789"
            try:
                text = pytesseract.image_to_string(up_img, config=config).strip()
                if text.isdigit():
                    val = int(text)
                    candidates.append(val)
                    safe_print(f"{Fore.CYAN}   [OCR] {label}/PSM{psm} → {val}{Style.RESET_ALL}")
            except pytesseract.TesseractError as e:
                log_warning(t("ocr.psm_error", psm=psm, err=e))

    if candidates:
        # 策略：先按位数降序分组，取位数最长的一组；组内取出现次数最多的值
        max_digits = max(len(str(v)) for v in candidates)
        longest_group = [v for v in candidates if len(str(v)) == max_digits]
        # 计数投票
        from collections import Counter

        vote = Counter(longest_group)
        best_val, count = vote.most_common(1)[0]
        safe_print(
            f"{Fore.GREEN}{t('ocr.final_result', val=best_val)} (votes: {count}/{len(candidates)}){Style.RESET_ALL}"
        )
        if best_val > 0:
            return best_val

    # ===== 零技能点保底机制 =====
    # 当数字白名单 OCR 未检测到任何数字时，执行无限制 OCR 扫描。
    # 如果识别文本包含 "no", "avail", "point"（对应 "No Skill Points Available" 界面文字），
    # 或者文本为空，则可确信当前技能点为 0，应该开始刷图。
    fallback_img = preprocessed[0][1] if preprocessed else None
    if fallback_img is not None:
        try:
            raw_text = pytesseract.image_to_string(fallback_img).strip().lower()
            if raw_text and ("no" in raw_text or "avail" in raw_text or "point" in raw_text):
                log_success(t("ocr.zero_detect", text=raw_text))
                return 0
        except pytesseract.TesseractError as e:
            log_warning(t("ocr.zero_detect_error", err=e))

    return None


# ==========================================
# 三、通用卡片 OCR 管线
# ==========================================


def _ocr_card_text(card_img: np.ndarray | None, debug_label: str = "CARD") -> str:
    """
    通用卡片文字提取管线（内部函数）。

    处理流程：灰度化 → 反向二值化 → 加边距 → 2 倍放大 → Tesseract OCR
    使用反向二值化（THRESH_BINARY_INV）是因为 Forza UI 的卡片文字通常是
    浅色文字在深色背景上，反向后变成黑字白底，更适合 Tesseract 识别。

    参数:
        card_img: BGR 格式的卡片区域裁剪图
        debug_label: 调试输出时的标签名（用于区分不同调用场景）

    返回:
        str: 小写化的 OCR 识别文本，失败时返回空字符串
    """
    if card_img is None or card_img.size == 0:
        return ""
    try:
        gray = cv2.cvtColor(card_img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
        padded = cv2.copyMakeBorder(thresh, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=[255, 255, 255])
        upscaled = cv2.resize(padded, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        text = pytesseract.image_to_string(upscaled).strip().lower()
        # 高可见性调试输出
        try:
            safe_print(f"\n{Fore.BLUE}=================== [{debug_label} OCR] ===================")
            safe_print(f"{Fore.BLUE}Recognized text:")
            safe_print(Fore.WHITE + (text if text else "[empty]"))
            safe_print(f"{Fore.BLUE}{'=' * (len(debug_label) + 36)}\n")
        except UnicodeEncodeError:
            pass  # safe_print encoding fallback
        return text
    except Exception as e:
        log_error(f"_ocr_card_text ({debug_label}) error: {e}")
    return ""


# ==========================================
# 四、绿色选中边框检测
# ==========================================


def has_green_selection_border(card_img: np.ndarray | None) -> bool:
    """
    检测卡片图像是否具有绿色选中高亮边框。

    Forza Horizon 6 的 UI 中，当前选中的卡片会有一圈亮绿色的发光边框。
    本函数通过以下步骤检测：
    1. 创建只覆盖卡片外围 15 像素的边框掩码
    2. 在 HSV 色彩空间中筛选绿色像素
    3. 将绿色掩码与边框掩码做 AND 运算
    4. 统计绿色像素数量，超过 1500 个判定为"已选中"

    参数:
        card_img: BGR 格式的卡片区域裁剪图

    返回:
        bool: True 表示卡片被绿色高亮选中
    """
    if card_img is None or card_img.size == 0:
        return False
    try:
        h, w, _ = card_img.shape
        hsv = cv2.cvtColor(card_img, cv2.COLOR_BGR2HSV)

        # 创建仅覆盖外围 15 像素的边框区域掩码
        border_mask = np.zeros((h, w), dtype=np.uint8)
        border_thickness = 15
        border_mask[0:border_thickness, :] = 255  # 上边
        border_mask[h - border_thickness : h, :] = 255  # 下边
        border_mask[:, 0:border_thickness] = 255  # 左边
        border_mask[:, w - border_thickness : w] = 255  # 右边

        # 在 HSV 空间中过滤绿色像素
        lower_green = HSV_GREEN_BORDER_LOWER
        upper_green = HSV_GREEN_BORDER_UPPER

        # 使用 bitwise_and 将绿色掩码限定在边框区域内
        green_mask = cv2.inRange(hsv, lower_green, upper_green)
        green_border_mask = cv2.bitwise_and(green_mask, border_mask)
        green_pixel_count = np.sum(green_border_mask == 255)

        # 调试输出绿色像素计数
        try:
            safe_print(
                f"{Fore.GREEN}[BORDER DEBUG]{Style.RESET_ALL} 边缘绿色边框像素点计数: {green_pixel_count} / 800 (阈值)"
            )
        except UnicodeEncodeError:
            pass

        return green_pixel_count >= 800
    except Exception as e:
        log_error(f"Error checking green selection border: {e}")
    return False


def has_green_selection_border_padded(
    image: np.ndarray | None,
    box_x: int,
    box_y: int,
    box_w: int,
    box_h: int,
    pad: int = 20,
) -> bool:
    """
    带外扩边距的绿色选中边框检测（更鲁棒的版本）。

    与 has_green_selection_border 的区别：
    - 不是在裁剪后的卡片图上检测，而是在原始场景图上检测
    - 在匹配位置周围额外扩展 pad 像素，覆盖模板裁剪偏移导致的边框遗漏
    - 更适合 OCR 定位后的二次验证

    参数:
        scene_img: 完整的 1600×900 场景截图
        crop_x, crop_y: 目标位置的左上角坐标
        w, h: 目标区域的宽度和高度
        pad: 外扩边距（默认 30 像素）

    返回:
        bool: True 表示该区域周围有绿色高亮边框
    """
    if image is None or image.size == 0:
        return False
    try:
        scene_h, scene_w, _ = image.shape

        # 计算带外扩的裁剪坐标（确保不超出画面边界）
        y1 = max(0, box_y - pad)
        y2 = min(scene_h, box_y + box_h + pad)
        x1 = max(0, box_x - pad)
        x2 = min(scene_w, box_x + box_w + pad)

        crop_padded = image[y1:y2, x1:x2]
        hsv = cv2.cvtColor(crop_padded, cv2.COLOR_BGR2HSV)

        # 在整个外扩区域中统计绿色像素（不区分边框/内容）
        lower_green = HSV_GREEN_BORDER_LOWER
        upper_green = HSV_GREEN_BORDER_UPPER

        green_mask = cv2.inRange(hsv, lower_green, upper_green)
        green_pixel_count = np.sum(green_mask == 255)

        # 调试输出
        try:
            safe_print(
                f"{Fore.GREEN}[BORDER DEBUG]{Style.RESET_ALL} 区域(含外扩边框)绿色高亮像素点计数: {green_pixel_count} / 800 (阈值)"
            )
        except UnicodeEncodeError:
            pass

        return green_pixel_count >= 800
    except Exception as e:
        log_error(f"Error checking padded green selection border: {e}")
    return False


# ==========================================
# 五、UI 光标定位
# ==========================================


def find_cursor_position(image: np.ndarray | None) -> tuple[int, int] | None:
    """
    在 1600×900 缩放画面中定位 UI 焦点光标的中心坐标。

    Forza Horizon 6 的 UI 中，当前聚焦的元素会被一个亮黄绿色的矩形边框包围。
    本函数通过以下步骤检测该边框的中心位置：

    1. 将画面从 BGR 转为 HSV 色彩空间
    2. 使用 inRange 过滤出亮黄绿色像素（H=35-85, S>=80, V>=80）
    3. 使用 findContours 寻找所有绿色轮廓
    4. 过滤面积 < 300 的噪声轮廓
    5. 按面积降序排列，选取第一个通过车库网格形状校验的轮廓

    形状校验规则（排除误检的标签栏/标题高亮）：
    - 宽高比不超过 4:1（排除 558×61 这种极扁的标签栏高亮）
    - 最短边 >= 50 像素（排除过细的 UI 装饰线条）
    - 中心 Y 坐标 > 150（排除顶部标签栏区域的高亮）

    参数:
        image: 1600×900 BGR 格式截图

    返回:
        tuple(int, int) 或 None: 光标中心坐标 (cx, cy)，检测不到时返回 None
    """
    if image is None or image.size == 0:
        return None
    try:
        img_h, img_w = image.shape[:2]
        # PERF-4: 先裁剪有效区域再做 HSV 转换，减少 ~35% 像素量
        # 左侧 21% 是详情面板，顶部 19% 是标签栏 — 不含车库网格光标
        crop_x_offset = int(img_w * 0.21)
        crop_y_offset = int(img_h * 0.19)
        roi = image[crop_y_offset:, crop_x_offset:]

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        # 亮黄绿色的 HSV 阈值范围（适用于地平线 UI 高亮绿色边框）
        lower_green = HSV_GREEN_CURSOR_LOWER
        upper_green = HSV_GREEN_CURSOR_UPPER

        mask = cv2.inRange(hsv, lower_green, upper_green)

        # 闭运算（先膨胀后腐蚀）：将高亮边框的 4 条细线桥接为完整矩形轮廓
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        # 寻找绿色区域的轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        # 过滤面积过小的噪声轮廓（阈值 300 像素）
        valid_contours = [c for c in contours if cv2.contourArea(c) >= 300]
        if not valid_contours:
            return None

        # 按面积降序排列，优先尝试最大的轮廓
        valid_contours.sort(key=cv2.contourArea, reverse=True)

        for contour in valid_contours:
            x, y, w, h = cv2.boundingRect(contour)
            # 加回裁剪偏移，映射回原始 1600×900 坐标系
            cx = x + w // 2 + crop_x_offset
            cy = y + h // 2 + crop_y_offset
            area = cv2.contourArea(contour)

            # === 形状校验：排除非车库网格元素（标签栏、菜单标题等） ===
            aspect_ratio = max(w, h) / max(min(w, h), 1)
            min_dim = min(w, h)

            if aspect_ratio > 4.0:
                # 宽高比过大 → 这是标签栏/标题高亮，不是车辆卡片
                try:
                    safe_print(
                        f"{Fore.YELLOW}[DYNAMIC VISION]{Style.RESET_ALL} 跳过异形轮廓: {w}x{h} (宽高比={aspect_ratio:.1f}>4.0), 面积={area:.0f}"
                    )
                except UnicodeEncodeError:
                    pass
                continue

            if min_dim < 50:
                # 最短边太小 → UI 装饰线条或小标签
                try:
                    safe_print(
                        f"{Fore.YELLOW}[DYNAMIC VISION]{Style.RESET_ALL} 跳过过小轮廓: {w}x{h} (最短边={min_dim}<50), 面积={area:.0f}"
                    )
                except UnicodeEncodeError:
                    pass
                continue

            if cy <= 150:
                # 中心在画面顶部 → 标签栏区域，不是车库网格
                try:
                    safe_print(
                        f"{Fore.YELLOW}[DYNAMIC VISION]{Style.RESET_ALL} 跳过顶部轮廓: (cx={cx}, cy={cy}) 在标签栏区域 (cy<=150), {w}x{h}"
                    )
                except UnicodeEncodeError:
                    pass
                continue

            # 通过所有校验 → 这是车库网格中的光标
            try:
                safe_print(
                    f"{Fore.GREEN}[DYNAMIC VISION]{Style.RESET_ALL} 找到高亮焦点位置: (cx={cx}, cy={cy}), 边框尺寸: {w}x{h}, 面积: {area:.0f}"
                )
            except UnicodeEncodeError:
                pass
            return cx, cy

        # 所有轮廓都未通过校验 → 输出调试信息
        top = valid_contours[0]
        x, y, w, h = cv2.boundingRect(top)
        try:
            safe_print(
                f"{Fore.RED}{t('ocr.contour_fail', w=w, h=h, cx=x + w // 2 + crop_x_offset, cy=y + h // 2 + crop_y_offset, area=f'{cv2.contourArea(top):.0f}')}{Style.RESET_ALL}"
            )
        except UnicodeEncodeError:
            pass
        return None
    except Exception as e:
        log_error(t("ocr.cursor_error", err=e))
    return None


# ==========================================
# 六、车辆卡片校验函数
# ==========================================


def verify_new_target_car(
    image: np.ndarray | None,
    cursor_x: int,
    cursor_y: int,
    target_keyword: str = "IMPREZA",
) -> bool:
    """
    双重目标锁定校验机制：OCR 车名 + NEW 标签检测。

    在车库网格导航中，模板匹配可能会误触相邻的非目标车辆。
    本函数通过两道独立的校验来确保精确度：

    校验 1 — OCR 车名文字检测：
      - 在光标位置裁剪卡片区域
      - OCR 识别文字，检查是否包含目标关键字（如 "IMPREZA"）
      - 支持完整匹配 + 滑动窗口部分匹配 + 备选关键字（"22b", "sti", "subaru"）

    校验 2 — NEW 黄色标签 HSV 检测：
      - 在卡片底部右侧区域检测黄色像素
      - NEW 标签表示该车尚未加过技能点，是目标车辆
      - 阈值：黄色像素 > 300 即判定有 NEW 标签

    两道校验都通过才返回 True。

    参数:
        image: 1600×900 BGR 格式截图
        cursor_x, cursor_y: 当前光标中心坐标
        target_keyword: 目标车名关键字（默认 "IMPREZA"）

    返回:
        bool: True 表示双重校验通过
    """
    if image is None or image.size == 0:
        return False
    try:
        roi = crop_card_roi(image, cursor_x, cursor_y)
        if roi is None:
            return False

        # --- 校验 1: 双行冗余 OCR 检查 ---
        # 车名行（白色大字，可能滚动）+ 年份品牌行（灰色小字，静止）
        has_keyword, matched_kws = verify_impreza_22b(roi, debug_label="SKILLPOINT")

        if has_keyword:
            safe_print(f"{Fore.GREEN}{t('ocr.keyword_hit', n=len(matched_kws), kws=matched_kws)}{Style.RESET_ALL}")

        # --- 校验 2: HSV 颜色检查（寻找 'NEW' 黄色标签） ---
        # NEW 标签位于卡片右侧 → 高度 71%-82%、宽度 82%-96%
        roi_h, roi_w = roi.shape[:2]
        roi_bottom = roi[int(roi_h * 0.71) : int(roi_h * 0.82), int(roi_w * 0.82) : int(roi_w * 0.96)]
        hsv_roi = cv2.cvtColor(roi_bottom, cv2.COLOR_BGR2HSV)
        lower_yellow = HSV_YELLOW_NEW_LOWER
        upper_yellow = HSV_YELLOW_NEW_UPPER

        yellow_mask = cv2.inRange(hsv_roi, lower_yellow, upper_yellow)
        yellow_pixels = cv2.countNonZero(yellow_mask)

        has_new_tag = yellow_pixels > 300

        # --- 校验 3: LEGENDARY 橙色稀有度标签检测 ---
        # 1998 Impreza 22B 固定为 LEGENDARY（橙色底色），COMMON/RARE/EPIC 不是目标车
        # 稀有度标签区域: 卡片高度 82%-94%、宽度 4%-70%
        rarity_roi = roi[int(roi_h * 0.82) : int(roi_h * 0.94), int(roi_w * 0.04) : int(roi_w * 0.70)]
        if rarity_roi.size > 0:
            hsv_rarity = cv2.cvtColor(rarity_roi, cv2.COLOR_BGR2HSV)
            # 橙色 HSV: H=10-25, S>100, V>100
            orange_mask = cv2.inRange(hsv_rarity, np.array([10, 100, 100]), np.array([25, 255, 255]))
            orange_pixels = cv2.countNonZero(orange_mask)
            has_legendary = orange_pixels > 200
        else:
            orange_pixels = 0
            has_legendary = False

        # --- 综合判断（三重校验） ---
        if has_keyword and has_new_tag and has_legendary:
            log_success(
                t("ocr.lock_ok", n=len(matched_kws), kws=matched_kws, yellow=yellow_pixels, orange=orange_pixels)
            )
            return True
        else:
            # 打印失败原因（方便调试）
            log_warning(t("ocr.lock_fail"))
            if not has_keyword:
                log_warning(t("ocr.lock_r1_fail", n=len(matched_kws), kws=matched_kws, text="N/A"))
            else:
                log_success(t("ocr.lock_r1_ok", n=len(matched_kws), kws=matched_kws))

            if not has_new_tag:
                log_warning(t("ocr.lock_r2_fail", px=yellow_pixels))
            else:
                log_success(t("ocr.lock_r2_ok", px=yellow_pixels))

            if not has_legendary:
                log_warning(t("ocr.lock_r3_fail", px=orange_pixels))
            else:
                log_success(t("ocr.lock_r3_ok", px=orange_pixels))

            return False

    except Exception as e:
        log_error(t("ocr.verify_error", err=e))
    return False


def check_new_tag_only(image: np.ndarray | None, cursor_x: int, cursor_y: int) -> bool:
    """
    仅检测 NEW 黄色标签（跳过 OCR 车名校验的轻量版本）。

    使用场景：当模板匹配已给出高分（> 0.95）时，车辆身份已被模板确认，
    只需要确认该车是否是尚未加过技能点的"新车"。

    检测原理：
    在卡片底部右侧 45% 的区域中，统计 HSV 黄色像素数量。
    黄色像素 > 300 即判定存在 NEW 标签。

    参数:
        image: 1600×900 BGR 格式截图
        cursor_x, cursor_y: 当前光标中心坐标

    返回:
        bool: True 表示有 NEW 标签（新车），False 表示已加过点
    """
    if image is None or image.size == 0:
        return False
    try:
        roi = crop_card_roi(image, cursor_x, cursor_y)
        if roi is None:
            return False

        # NEW 标签在卡片右侧 → 高度 71%-82%、宽度 82%-96%
        roi_h, roi_w = roi.shape[:2]
        roi_bottom = roi[int(roi_h * 0.71) : int(roi_h * 0.82), int(roi_w * 0.82) : int(roi_w * 0.96)]
        hsv_roi = cv2.cvtColor(roi_bottom, cv2.COLOR_BGR2HSV)
        lower_yellow = HSV_YELLOW_NEW_LOWER
        upper_yellow = HSV_YELLOW_NEW_UPPER
        yellow_mask = cv2.inRange(hsv_roi, lower_yellow, upper_yellow)
        yellow_pixels = cv2.countNonZero(yellow_mask)

        has_new = yellow_pixels > 300
        if has_new:
            log_success(t("ocr.new_tag_ok", px=yellow_pixels))
        else:
            log_warning(t("ocr.new_tag_fail", px=yellow_pixels))
        return has_new
    except Exception as e:
        log_error(t("ocr.new_tag_error", err=e))
    return False


def check_is_high_class(image: np.ndarray | None, cursor_x: int, cursor_y: int) -> bool:
    """
    检测当前卡片的车辆是否为高级别（S1/S2 等）。

    用途：在删车流程中保护用户的主力车（S2 825 Impreza）不被误删。
    B 级车是可以安全删除的，而 S1/S2 级别的车是用户手动升级的主力车。

    检测原理（基于 PI 徽章颜色）：
    - S2 主力车: 徽章左半部分是 **蓝色**，右半部分是黑色
    - B 级车:    徽章左半部分是 **橙色**，右半部分是黑色
    通过 HSV 检测蓝色 vs 橙色像素数量来判定级别。

    参数:
        image: 1600×900 BGR 格式截图
        cursor_x, cursor_y: 当前光标中心坐标

    返回:
        bool: True 表示是高级别车（应跳过），False 表示是 B 级车
    """
    if image is None or image.size == 0:
        return False
    try:
        card = crop_card_roi(image, cursor_x, cursor_y)
        if card is None:
            return False

        card_h, card_w = card.shape[:2]
        # PI 徽章: 卡片高度 82%-94%、宽度 71%-96% 区域
        # 只看右侧 PI 徽章 (S2/B)，避开左侧 LEGENDARY 金色标签和右侧越界
        badge = card[int(card_h * 0.82) : int(card_h * 0.94), int(card_w * 0.71) : int(card_w * 0.96)]

        hsv = cv2.cvtColor(badge, cv2.COLOR_BGR2HSV)

        # S2 徽章精确蓝色 #165EDB → HSV(109, 230, 219)
        # 收窄范围: H=103-115, S≥180, V≥170（仅匹配 S2 徽章蓝）
        blue_mask = cv2.inRange(hsv, np.array([103, 180, 170]), np.array([115, 255, 255]))
        blue_pixels = cv2.countNonZero(blue_mask)

        # 橙色 (B 级徽章): H=5-25, S>100, V>100
        orange_mask = cv2.inRange(hsv, np.array([5, 100, 100]), np.array([25, 255, 255]))
        orange_pixels = cv2.countNonZero(orange_mask)

        # 判定: 蓝色多 → S2，橙色多 → B 级
        if blue_pixels > orange_pixels and blue_pixels > 50:
            log_warning(t("ocr.pi_high", blue=blue_pixels, orange=orange_pixels))
            return True

        if orange_pixels > blue_pixels and orange_pixels > 50:
            log_success(t("ocr.pi_b_class", orange=orange_pixels, blue=blue_pixels))
            return False

        # 兜底: 两种颜色都不明确，保守处理 — 宁可漏删不可误删 S2 主力车
        log_warning(t("ocr.pi_ambiguous", blue=blue_pixels, orange=orange_pixels))
        return True
    except Exception as e:
        log_error(t("ocr.pi_error", err=e))
    return False


# ==========================================
# 八、通用 ROI 区域 OCR
# ==========================================


def read_text_in_roi(
    image: np.ndarray | None,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    whitelist: str | None = None,
) -> str:
    """
    在指定的 ROI（Region of Interest）矩形区域内执行 OCR 文字识别。

    处理流程：
    1. 根据坐标裁剪 ROI 区域
    2. 放大 3 倍以提升小字体识别率
    3. 转灰度（不做二值化，保留更多细节）
    4. 使用 PSM 7（单行文本模式）识别

    参数:
        image: 1600×900 BGR 格式截图
        x1, y1, x2, y2: ROI 矩形区域的坐标
        whitelist: 可选，OCR 字符白名单（如 "0123456789" 只识别数字）

    返回:
        str: 小写化的 OCR 识别文本，失败时返回空字符串
    """
    if image is None or image.size == 0:
        return ""
    try:
        h, w, _ = image.shape
        # 确保坐标在有效范围内
        rx1 = max(0, int(x1))
        rx2 = min(w, int(x2))
        ry1 = max(0, int(y1))
        ry2 = min(h, int(y2))

        roi = image[ry1:ry2, rx1:rx2]
        if roi.size == 0:
            return ""

        # 保存调试原图（仅在调试模式下）
        if DEBUG_WRITE_FILES:
            cv2.imwrite("debug_ocr_raw.png", roi)

        # 图像预处理：放大 3 倍 → 灰度化
        resized_roi = cv2.resize(roi, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(resized_roi, cv2.COLOR_BGR2GRAY)

        if DEBUG_WRITE_FILES:
            cv2.imwrite("debug_ocr_processed.png", gray)

        # OCR 识别配置
        config_str = "--psm 7"  # 单行文本模式
        if whitelist is not None:
            config_str += f" -c tessedit_char_whitelist={whitelist}"

        text = pytesseract.image_to_string(gray, config=config_str).strip().lower()
        return text
    except Exception as e:
        log_error(t("ocr.roi_error", err=e))
    return ""


# ==========================================
# 九、车库网格空位检测
# ==========================================


def has_cell_below(image: np.ndarray | None, cursor_x: int, cursor_y: int) -> bool:
    """
    检测光标下方一行位置是否存在车辆卡片（非空位）。

    使用 CARD_CROP 百分比定位采样区域：
    高度 87%-153%、宽度 13%-88%（相对于 CARD_CROP 裁剪区域）。
    该区域覆盖当前卡片下方到下一行卡片的主体部分。

    判断规则：
    - 空位背景通常很暗（亮度 < 40）且颜色单调（方差 < 15）
    - 车辆卡片通常较亮（亮度 > 40）且有丰富的色彩变化（方差 > 15）
    - 满足任一条件即判定有车

    参数:
        image: 1600×900 BGR 格式截图
        cursor_x, cursor_y: 当前光标中心坐标

    返回:
        bool: True = 下方有车辆卡片, False = 下方是空位或超出边界
    """
    if image is None or image.size == 0:
        return False
    try:
        h, w, _ = image.shape
        crop_w, crop_h = CARD_CROP_W, CARD_CROP_H

        # CARD_CROP 区域的绝对坐标
        card_x1 = max(0, cursor_x - crop_w // 2)
        card_y1 = max(0, cursor_y - crop_h // 2)

        # 采样区域: h101%-192%, w4%-97%
        sy1 = max(0, int(card_y1 + crop_h * 1.01))
        sy2 = min(h, int(card_y1 + crop_h * 1.92))
        sx1 = max(0, int(card_x1 + crop_w * 0.04))
        sx2 = min(w, int(card_x1 + crop_w * 0.97))

        # 超出画面底部 → 没有下一行
        if sy1 >= h - 30:
            safe_print(f"{Fore.YELLOW}[GRID]{Style.RESET_ALL} {t('ocr.grid_oob', sy1=sy1, h=h)}")
            return False

        sample = image[sy1:sy2, sx1:sx2]
        if sample.size == 0:
            return False

        # 计算采样区域的统计特征
        gray_sample = cv2.cvtColor(sample, cv2.COLOR_BGR2GRAY)
        mean_brightness = float(np.mean(gray_sample))  # 平均亮度
        std_brightness = float(np.std(gray_sample))  # 亮度方差（颜色丰富度）

        # 判断规则：亮度 > 40 或方差 > 15 即视为有车
        has_car = mean_brightness > 40 or std_brightness > 15

        safe_print(
            f"{Fore.CYAN}[GRID]{Style.RESET_ALL} {t('ocr.grid_result', bright=f'{mean_brightness:.1f}', var=f'{std_brightness:.1f}', result=t('ocr.grid_has_car') if has_car else t('ocr.grid_empty'))}"
        )
        return has_car

    except Exception as e:
        log_error(t("ocr.cell_below_error", err=e))
    return False


# ==========================================
# 十、车库网格空位检测（统一版）
# ==========================================


def is_empty_slot(image: np.ndarray, cursor_x: int, cursor_y: int) -> bool:
    """
    检测当前光标所在的车库卡片是否为空位。

    通过采样当前卡片下半部分区域（CARD_CROP h87%-153%, w13%-88%）的
    亮度和方差来判断：
    - 空位背景：亮度 ≤ 50 且方差 ≤ 5（几乎纯色深灰）
    - 车辆卡片：亮度 > 50 或方差 > 5（有图像/文字内容）

    此函数是所有车库网格扫描模块的统一空位检测入口，
    替代之前分散在 garage.py 中的 4 处重复内联实现。

    Args:
        image: 1600×900 BGR 格式截图
        cursor_x: 当前光标中心 X 坐标
        cursor_y: 当前光标中心 Y 坐标

    Returns:
        bool: True = 空位, False = 有车辆卡片
    """
    if image is None or image.size == 0:
        return True
    try:
        crop_w, crop_h = CARD_CROP_W, CARD_CROP_H
        card_x1 = max(0, cursor_x - crop_w // 2)
        card_y1 = max(0, cursor_y - crop_h // 2)
        sy1 = max(0, int(card_y1 + crop_h * 0.87))
        sy2 = min(image.shape[0], int(card_y1 + crop_h * 1.53))
        sx1 = max(0, int(card_x1 + crop_w * 0.13))
        sx2 = min(image.shape[1], int(card_x1 + crop_w * 0.88))
        sample = image[sy1:sy2, sx1:sx2]
        if sample.size == 0:
            return True
        gray = cv2.cvtColor(sample, cv2.COLOR_BGR2GRAY)
        mean_brightness = float(np.mean(gray))
        std_brightness = float(np.std(gray))
        is_empty = (
            mean_brightness <= EMPTY_SLOT_BRIGHTNESS_THRESHOLD and std_brightness <= EMPTY_SLOT_VARIANCE_THRESHOLD
        )
        if is_empty:
            safe_print(
                f"{Fore.YELLOW}[GRID]{Style.RESET_ALL} "
                f"{t('ocr.empty_slot_detect', bright=f'{mean_brightness:.1f}', var=f'{std_brightness:.1f}')}"
            )
        return is_empty
    except Exception as e:
        log_error(t("ocr.empty_slot_error", err=e))
    return True


# ==========================================
# 十一、品牌标签栏选中检测（统一版）
# ==========================================

# 品牌标签栏的默认 ROI（百分比坐标）
BRAND_TAB_ROI_Y: tuple[float, float] = (0.14, 0.18)
BRAND_TAB_ROI_X: tuple[float, float] = (0.09, 0.91)


def detect_selected_brand_tab(
    raw_img: np.ndarray,
    roi_y: tuple[float, float] = BRAND_TAB_ROI_Y,
    roi_x: tuple[float, float] = BRAND_TAB_ROI_X,
) -> str | None:
    """
    检测品牌标签栏中当前选中（高亮）的标签文字。

    算法原理：
    游戏 UI 中，选中的品牌标签背景色更暗（深色高亮），未选中的标签背景较亮。
    通过在标签栏灰度图上滑动窗口（10% 宽度，步长 5px），找到平均亮度最低的区域，
    然后向两侧扩展（阈值 120）找到完整的暗区范围，最后对该暗区做 OCR 识别文字。

    此函数统一了之前分散在 navigation.py 和 garage.py 中的 2 处重复实现。

    Args:
        raw_img: 原始分辨率 BGR 截图
        roi_y: 标签栏垂直范围 (y1%, y2%)，默认 (0.14, 0.18)
        roi_x: 标签栏水平范围 (x1%, x2%)，默认 (0.09, 0.91)

    Returns:
        str: 选中标签的 OCR 文字（小写），检测失败返回 None
    """
    if raw_img is None or raw_img.size == 0:
        return None

    rh, rw = raw_img.shape[:2]
    tab_strip = raw_img[int(rh * roi_y[0]) : int(rh * roi_y[1]), int(rw * roi_x[0]) : int(rw * roi_x[1])]
    if tab_strip.size == 0:
        return None

    tab_gray = cv2.cvtColor(tab_strip, cv2.COLOR_BGR2GRAY)
    tab_w = tab_gray.shape[1]
    win = int(tab_w * 0.10)
    if win <= 0 or tab_w <= win:
        return None

    # 滑动窗口找最暗区域
    min_mean: float = 999.0
    min_x: int = 0
    for xi in range(0, tab_w - win, 5):
        m = float(np.mean(tab_gray[:, xi : xi + win]))
        if m < min_mean:
            min_mean = m
            min_x = xi

    # 向两侧扩展暗区
    xs, xe = min_x, min_x + win
    while xs > 0 and float(np.mean(tab_gray[:, max(0, xs - 10) : xs])) < 120:
        xs -= 10
    while xe < tab_w and float(np.mean(tab_gray[:, xe : min(tab_w, xe + 10)])) < 120:
        xe += 10

    # OCR 选中标签文字
    sel_roi = tab_strip[:, xs:xe]
    if sel_roi.size == 0:
        return None
    sel_gray = cv2.cvtColor(sel_roi, cv2.COLOR_BGR2GRAY)
    _, sel_thresh = cv2.threshold(sel_gray, 150, 255, cv2.THRESH_BINARY)

    try:
        text = pytesseract.image_to_string(sel_thresh, config="--psm 7").strip().lower()
        return text if text else None
    except Exception as e:
        log_error(t("ocr.brand_tab_error", err=e))
        return None
