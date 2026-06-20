# -*- coding: utf-8 -*-
"""
tests/test_vision_gates.py — 车库视觉决策门的双向 + 兜底覆盖
==============================================================
这些是 `engine/ocr.py` 中“给一张图返回一个保留/删除/空位判定”的纯函数，
无硬件依赖、却是删车安全的关键逻辑。本文件用合成图（在正确的 ROI 子区域
填入特定 HSV 颜色 / 亮度）覆盖每个门的**两个方向 + 出错兜底**，特别是钉住
“破坏性方向”（删除），避免将来误改成“永远保留/永远删除”而测试仍然全绿。

几何依据（与 ocr.py 常量一致）：
  CARD_CROP_W=284, CARD_CROP_H=217 → 以光标为中心裁卡片
  check_is_high_class PI 徽章: card[h0.82-0.94, w0.71-0.96]
  check_new_tag_only NEW 标签:  card[h0.71-0.82, w0.82-0.96]
  is_empty_slot 采样:           card[h0.87-1.53, w0.13-0.88]
  has_cell_below 采样:          card[h1.01-1.92, w0.04-0.97]
"""

import cv2
import numpy as np

from engine.ocr import (
    CARD_CROP_H,
    CARD_CROP_W,
    check_is_high_class,
    check_new_tag_only,
    find_cursor_position,
    has_cell_below,
    is_empty_slot,
)

# 光标中心：使所有 ROI（含向下延伸的采样区）都落在 1600×900 画面内
CX, CY = 800, 450


def _blank() -> np.ndarray:
    """全黑 1600×900 BGR 画面（亮度/方差均为 0）。"""
    return np.zeros((900, 1600, 3), dtype=np.uint8)


def _bgr(h: int, s: int, v: int) -> tuple[int, int, int]:
    """由 HSV 生成对应 BGR 像素值（保证 inRange 命中目标颜色范围）。"""
    px = np.uint8([[[h, s, v]]])
    b, g, r = cv2.cvtColor(px, cv2.COLOR_HSV2BGR)[0, 0]
    return int(b), int(g), int(r)


def _fill_card_subroi(img, cx, cy, h_frac, w_frac, color) -> None:
    """在以 (cx,cy) 为中心的卡片内，按比例子区域填充颜色（就地修改 img）。"""
    card_x1 = max(0, cx - CARD_CROP_W // 2)
    card_y1 = max(0, cy - CARD_CROP_H // 2)
    y1 = int(card_y1 + CARD_CROP_H * h_frac[0])
    y2 = int(card_y1 + CARD_CROP_H * h_frac[1])
    x1 = int(card_x1 + CARD_CROP_W * w_frac[0])
    x2 = int(card_x1 + CARD_CROP_W * w_frac[1])
    img[y1:y2, x1:x2] = color


# HSV 落在各检测函数阈值区间内的颜色
_ORANGE = _bgr(16, 255, 255)  # B 级徽章: H∈[5,25]
_BLUE = _bgr(109, 255, 255)  # S2 徽章:  H∈[103,115], S≥180, V≥170
_YELLOW = _bgr(25, 255, 255)  # NEW 标签: H∈[20,30]
_GREEN = _bgr(37, 255, 255)  # 光标边框: H∈[30,45], S≥200, V≥200


# ================================================================
# check_is_high_class — 保留(S2)/删除(B) 双向
# ================================================================


class TestCheckIsHighClass:
    def test_blue_badge_is_high_class(self) -> None:
        """蓝色 PI 徽章 → S2 主力车 → True（保留）。"""
        img = _blank()
        _fill_card_subroi(img, CX, CY, (0.82, 0.94), (0.71, 0.96), _BLUE)
        assert check_is_high_class(img, CX, CY) is True

    def test_orange_badge_is_b_class(self) -> None:
        """橙色 PI 徽章 → B 级车 → False（可删）。钉住破坏性方向，防止退化为永远保留。"""
        img = _blank()
        _fill_card_subroi(img, CX, CY, (0.82, 0.94), (0.71, 0.96), _ORANGE)
        assert check_is_high_class(img, CX, CY) is False


# ================================================================
# check_new_tag_only — 有/无 NEW 标签 双向
# ================================================================


class TestCheckNewTagOnly:
    def test_yellow_tag_detected(self) -> None:
        """卡片右下出现足量黄色像素 → 有 NEW 标签 → True。"""
        img = _blank()
        _fill_card_subroi(img, CX, CY, (0.71, 0.82), (0.82, 0.96), _YELLOW)
        assert check_new_tag_only(img, CX, CY) is True

    def test_no_yellow_means_no_tag(self) -> None:
        """无黄色像素 → 无 NEW 标签 → False。"""
        assert check_new_tag_only(_blank(), CX, CY) is False


# ================================================================
# is_empty_slot — 空位/有车 双向 + None 兜底
# ================================================================


class TestIsEmptySlot:
    def test_dark_uniform_is_empty(self) -> None:
        """采样区暗且纯色（全黑）→ 空位 → True。"""
        assert is_empty_slot(_blank(), CX, CY) is True

    def test_bright_region_is_occupied(self) -> None:
        """采样区明亮 → 有车 → False。"""
        img = _blank()
        _fill_card_subroi(img, CX, CY, (0.87, 1.53), (0.13, 0.88), (200, 200, 200))
        assert is_empty_slot(img, CX, CY) is False

    def test_none_image_defaults_empty(self) -> None:
        """None 图像 → 兜底视为空位 True（不会触发删除）。"""
        assert is_empty_slot(None, CX, CY) is True


# ================================================================
# has_cell_below — 下方有车/空 双向 + None 兜底
# ================================================================


class TestHasCellBelow:
    def test_bright_below_has_car(self) -> None:
        """下方采样区明亮 → 有车 → True。"""
        img = _blank()
        _fill_card_subroi(img, CX, CY, (1.01, 1.92), (0.04, 0.97), (200, 200, 200))
        assert has_cell_below(img, CX, CY) is True

    def test_dark_below_is_empty(self) -> None:
        """下方为暗区（全黑）→ 无车 → False。"""
        assert has_cell_below(_blank(), CX, CY) is False

    def test_none_image_returns_false(self) -> None:
        """None 图像 → False（无下一行）。"""
        assert has_cell_below(None, CX, CY) is False


# ================================================================
# find_cursor_position — 检出绿色高亮框 / 无框 / None
# ================================================================


class TestFindCursorPosition:
    def test_green_box_returns_center(self) -> None:
        """画面中存在绿色高亮方框 → 返回其中心坐标。"""
        img = _blank()
        # 80×80 绿色填充块，置于网格区域（避开左 21% 详情面板 / 顶 19% 标签栏）
        img[400:480, 700:780] = _GREEN
        pos = find_cursor_position(img)
        assert pos is not None
        cx, cy = pos
        assert abs(cx - 740) <= 20 and abs(cy - 440) <= 20

    def test_no_green_returns_none(self) -> None:
        """无高亮框 → None。"""
        assert find_cursor_position(_blank()) is None

    def test_none_image_returns_none(self) -> None:
        """None 图像 → None。"""
        assert find_cursor_position(None) is None
