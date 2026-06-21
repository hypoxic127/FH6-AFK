# -*- coding: utf-8 -*-
"""
tests/test_ocr.py — engine/ocr.py 单元测试

覆盖：
  - HSV 颜色常量合法性
  - detect_selected_brand_tab() 暗区检测算法
  - _ocr_card_text() 预处理管线（合成图像）
  - is_empty_slot() 空位检测（合成图像）
"""

from unittest.mock import Mock

import cv2
import numpy as np
import pytesseract
import pytest

from engine import ocr
from engine.ocr import (
    BRAND_TAB_ROI_X,
    BRAND_TAB_ROI_Y,
    CARD_CROP_H,
    CARD_CROP_W,
    EMPTY_SLOT_BRIGHTNESS_THRESHOLD,
    EMPTY_SLOT_VARIANCE_THRESHOLD,
    # 常量
    HSV_GREEN_BORDER_LOWER,
    HSV_GREEN_BORDER_UPPER,
    HSV_GREEN_CURSOR_LOWER,
    HSV_GREEN_CURSOR_UPPER,
    HSV_YELLOW_NEW_LOWER,
    HSV_YELLOW_NEW_UPPER,
    YEAR_BRAND_OPTIONAL,
    YEAR_BRAND_REQUIRED,
    detect_selected_brand_tab,
    # 函数
    is_empty_slot,
    match_impreza_22b,
    match_year_brand,
)

# ==========================================
# HSV 常量合法性
# ==========================================


class TestHSVConstants:
    """HSV 颜色阈值常量应在 OpenCV 合法范围内。"""

    @pytest.mark.parametrize(
        "lower,upper,name",
        [
            (HSV_GREEN_BORDER_LOWER, HSV_GREEN_BORDER_UPPER, "GREEN_BORDER"),
            (HSV_GREEN_CURSOR_LOWER, HSV_GREEN_CURSOR_UPPER, "GREEN_CURSOR"),
            (HSV_YELLOW_NEW_LOWER, HSV_YELLOW_NEW_UPPER, "YELLOW_NEW"),
        ],
    )
    def test_hsv_range_valid(self, lower: np.ndarray, upper: np.ndarray, name: str) -> None:
        """H∈[0,179], S∈[0,255], V∈[0,255]，且 lower <= upper。"""
        assert lower[0] >= 0 and upper[0] <= 179, f"{name}: H out of range"
        assert lower[1] >= 0 and upper[1] <= 255, f"{name}: S out of range"
        assert lower[2] >= 0 and upper[2] <= 255, f"{name}: V out of range"
        assert np.all(lower <= upper), f"{name}: lower > upper"

    def test_card_crop_positive(self) -> None:
        """卡片裁剪尺寸应为正数。"""
        assert CARD_CROP_W > 0
        assert CARD_CROP_H > 0

    def test_empty_slot_thresholds_positive(self) -> None:
        """空位检测阈值应为正数。"""
        assert EMPTY_SLOT_BRIGHTNESS_THRESHOLD > 0
        assert EMPTY_SLOT_VARIANCE_THRESHOLD > 0


# ==========================================
# IMPREZA 关键词匹配逻辑
# ==========================================


class TestImprezaKeywords:
    """关键词列表和最低命中数应一致且合理。"""

    def test_typical_ocr_text_matches(self) -> None:
        """模拟 OCR 输出，验证匹配逻辑。"""
        ocr_text = "1998 subaru impreza 22b-sti version"
        is_match, matched = match_impreza_22b(ocr_text)
        assert is_match
        assert len(matched) >= 2

    def test_non_target_car_fails(self) -> None:
        """非目标车辆文字不应命中。"""
        ocr_text = "2024 subaru brz premium"
        is_match, _ = match_impreza_22b(ocr_text)
        assert not is_match

    def test_wrx_sti_excluded(self) -> None:
        """2008 Subaru IMPREZA WRX STI 不应通过匹配（缺少 '22b'）。"""
        ocr_text = "2008 subaru impreza wrx sti"
        is_match, matched = match_impreza_22b(ocr_text)
        assert not is_match, f"WRX STI should NOT match but got matched={matched}"


# ==========================================
# 年份+品牌行匹配逻辑
# ==========================================


class TestYearBrandKeywords:
    """年份+品牌行关键词匹配（第2行，灰色静止文字）。"""

    def test_keywords_not_empty(self) -> None:
        assert len(YEAR_BRAND_REQUIRED) >= 1
        assert len(YEAR_BRAND_OPTIONAL) >= 1

    def test_perfect_text_matches(self) -> None:
        """完美 OCR 文本应匹配。"""
        is_match, matched = match_year_brand("1998 subaru")
        assert is_match
        assert len(matched) >= 2

    def test_noisy_text_matches(self) -> None:
        """带噪声的 OCR 文本也应匹配。"""
        # 常见 OCR 噪声模式
        for noisy in ["1995 subar", "199s suba", "1990 subaru"]:
            is_match, _ = match_year_brand(noisy)
            assert is_match, f"Noisy text '{noisy}' should match"

    def test_wrong_year_fails(self) -> None:
        """2008 系列不应匹配。"""
        is_match, _ = match_year_brand("2008 subaru")
        assert not is_match

    def test_wrong_brand_fails(self) -> None:
        """只有年份没有品牌不应匹配。"""
        is_match, _ = match_year_brand("1998 toyota")
        assert not is_match

    def test_empty_text_fails(self) -> None:
        is_match, _ = match_year_brand("")
        assert not is_match


# ==========================================
# detect_selected_brand_tab() — 暗区检测
# ==========================================


class TestDetectSelectedBrandTab:
    """品牌标签栏暗区检测算法（不依赖 OCR 结果精度）。"""

    def test_returns_none_for_none(self) -> None:
        assert detect_selected_brand_tab(None) is None

    def test_returns_none_for_empty(self) -> None:
        assert detect_selected_brand_tab(np.array([])) is None

    def test_returns_none_for_tiny_image(self) -> None:
        """过小的图像应安全返回 None。"""
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        assert detect_selected_brand_tab(img) is None

    def test_finds_dark_region_in_synthetic_strip(self) -> None:
        """合成一张有明显暗区的标签栏图像，验证函数不崩溃。"""
        # 创建 1600x900 亮色图像
        img = np.full((900, 1600, 3), 200, dtype=np.uint8)
        # 在标签栏区域 (y:14%-18%, x:9%-91%) 的中间制造一段暗区
        y1 = int(900 * 0.14)
        y2 = int(900 * 0.18)
        x1 = int(1600 * 0.40)
        x2 = int(1600 * 0.55)
        img[y1:y2, x1:x2] = 30  # 暗区

        # 函数应返回字符串或 None（不崩溃即可）
        result = detect_selected_brand_tab(img)
        # result 是 OCR 结果，合成图不保证能识别文字，
        # 但函数不应抛异常
        assert result is None or isinstance(result, str)

    def test_brand_tab_roi_defaults(self) -> None:
        """默认 ROI 参数应在 0.0-1.0 比例范围内。"""
        assert 0.0 <= BRAND_TAB_ROI_Y[0] < BRAND_TAB_ROI_Y[1] <= 1.0
        assert 0.0 <= BRAND_TAB_ROI_X[0] < BRAND_TAB_ROI_X[1] <= 1.0


# ==========================================
# is_empty_slot() — 空位检测
# ==========================================


class TestIsEmptySlot:
    """车库空位检测（暗色低方差 → 空位）。"""

    def test_dark_uniform_is_empty(self) -> None:
        """纯黑图 → 空位。"""
        # is_empty_slot 需要 1600x900 场景图 + 光标坐标
        img = np.zeros((900, 1600, 3), dtype=np.uint8)
        assert is_empty_slot(img, 800, 450)

    def test_bright_image_is_not_empty(self) -> None:
        """亮色图 → 不是空位。"""
        img = np.full((900, 1600, 3), 180, dtype=np.uint8)
        assert not is_empty_slot(img, 800, 450)

    def test_none_returns_true(self) -> None:
        """None 输入应安全返回 True（保守策略）。"""
        assert is_empty_slot(None, 0, 0)


# ==========================================
# 技能点 OCR：置信度加权投票（纯函数）
# ==========================================


class TestVoteSkillPoints:
    """_vote_skill_points：范围校验 + 置信度加权投票。"""

    def test_empty_returns_none(self) -> None:
        assert ocr._vote_skill_points([]) is None

    def test_filters_out_of_range(self) -> None:
        """>999 的垃圾 4 位读数被过滤，正确 3 位胜出（杀「读高」）。"""
        assert ocr._vote_skill_points([(9991, 95.0), (999, 90.0)]) == 999

    def test_all_out_of_range_returns_none(self) -> None:
        assert ocr._vote_skill_points([(1000, 99.0), (-5, 99.0)]) is None

    def test_confidence_outweighs_single_low(self) -> None:
        """高置信度值胜过单条低置信度值。"""
        assert ocr._vote_skill_points([(99, 10.0), (100, 80.0)]) == 100

    def test_frequency_via_confidence_sum(self) -> None:
        """同值多次出现 → 置信度求和占优。"""
        assert ocr._vote_skill_points([(99, 80.0), (99, 80.0), (999, 80.0)]) == 99

    def test_zero_is_valid(self) -> None:
        assert ocr._vote_skill_points([(0, 95.0)]) == 0


# ==========================================
# 技能点 OCR：范围校验 + 精简变体（集成，mock pytesseract）
# ==========================================


class TestReadSkillPointsRobustness:
    @staticmethod
    def _img() -> np.ndarray:
        # 默认 ROI 比例在 1440p 图上裁剪非空即可（OCR 已被 mock）
        return np.full((1440, 2560, 3), 178, dtype=np.uint8)

    def test_range_clamp_drops_4digit(self, monkeypatch) -> None:
        """4 位垃圾 + 正确 3 位 → 返回 3 位（范围校验生效）。"""
        monkeypatch.setattr("engine.runtime.load_bot_config", lambda: {})
        monkeypatch.setattr(
            pytesseract,
            "image_to_data",
            lambda *a, **k: {"text": ["9991", "999"], "conf": ["95", "90"]},
        )
        assert ocr.read_skill_points(self._img()) == 999

    def test_single_frame_runs_lean_variant_set(self, monkeypatch) -> None:
        """单帧只跑 4 轮 OCR（2 变体 × 2 PSM），防回归到 12 轮。"""
        monkeypatch.setattr("engine.runtime.load_bot_config", lambda: {})
        data_mock = Mock(return_value={"text": [""], "conf": ["-1"]})
        monkeypatch.setattr(pytesseract, "image_to_data", data_mock)
        monkeypatch.setattr(pytesseract, "image_to_string", lambda *a, **k: "")
        assert ocr.read_skill_points(self._img()) is None
        assert data_mock.call_count == 4


# ==========================================
# 技能点 OCR：多帧共识
# ==========================================


class TestReadSkillPointsStable:
    def test_consensus_returns_agreed_value(self, monkeypatch) -> None:
        monkeypatch.setattr(ocr, "read_skill_points", Mock(side_effect=[999, 999, 99, None, 999]))
        assert ocr.read_skill_points_stable([object()] * 5, min_agreement=2) == 999

    def test_insufficient_agreement_returns_none(self, monkeypatch) -> None:
        monkeypatch.setattr(ocr, "read_skill_points", Mock(side_effect=[10, 20, 30]))
        assert ocr.read_skill_points_stable([object()] * 3, min_agreement=2) is None

    def test_all_none_returns_none(self, monkeypatch) -> None:
        monkeypatch.setattr(ocr, "read_skill_points", Mock(return_value=None))
        assert ocr.read_skill_points_stable([object()] * 3) is None

    def test_skips_none_images(self, monkeypatch) -> None:
        rp = Mock(side_effect=[999, 999])
        monkeypatch.setattr(ocr, "read_skill_points", rp)
        assert ocr.read_skill_points_stable([None, object(), None, object()], min_agreement=2) == 999
        assert rp.call_count == 2
