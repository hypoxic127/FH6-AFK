# -*- coding: utf-8 -*-
"""
tests/test_farm_skills.py — farm/skills.py 单元测试

覆盖：
  - get_matches_needed()  比赛场次计算
  - save / load / clear race state  断点续跑持久化
"""

import json
import os
from unittest.mock import Mock

import numpy as np
import pytest
import vgamepad as vg

from farm.skills import (
    FarmStateMachine,
    _get_race_state_path,
    clear_race_state,
    get_matches_needed,
    load_race_state,
    save_race_state,
)

# ==========================================
# get_matches_needed()
# ==========================================


@pytest.mark.usefixtures("tmp_race_state")
class TestGetMatchesNeeded:
    """比赛场次计算器测试。"""

    def test_zero_points_needs_100_matches(self) -> None:
        """0 点 → 需要 ceil(999/10)=100 场。"""
        assert get_matches_needed(0) == 100

    def test_max_points_needs_zero(self) -> None:
        """999 点 → 不需要跑了。"""
        assert get_matches_needed(999) == 0

    def test_over_max_returns_zero(self) -> None:
        """超过 999 不能返回负数。"""
        assert get_matches_needed(1500) == 0

    def test_partial_points(self) -> None:
        """500 点 → 需要 ceil(499/10) = 50 场。"""
        assert get_matches_needed(500) == 50

    def test_one_match_boundary(self) -> None:
        """990 点 → 需要 1 场 (差 9 点, 每场 10 点)。"""
        assert get_matches_needed(990) == 1

    def test_exact_boundary(self) -> None:
        """989 点 → 需要 1 场。"""
        assert get_matches_needed(989) == 1

    def test_negative_points_clamps(self) -> None:
        """负数技能点也应正常返回（防御性编程）。"""
        result = get_matches_needed(-10)
        assert result >= 100  # 至少 100 场


# ==========================================
# Race State Persistence
# ==========================================


class TestRaceStatePersistence:
    """断点续跑 JSON 持久化测试。"""

    def test_save_creates_file(self, tmp_race_state) -> None:
        """save_race_state 应创建 JSON 文件。"""
        save_race_state(50, 10)
        assert os.path.exists(_get_race_state_path())

    def test_save_load_roundtrip(self, tmp_race_state) -> None:
        """保存后加载应返回相同的数据。"""
        save_race_state(42, 7)
        result = load_race_state()
        assert result is not None
        matches_needed, matches_completed, last_updated = result
        assert matches_needed == 42
        assert matches_completed == 7
        assert isinstance(last_updated, str)

    def test_load_returns_none_when_no_file(self, tmp_race_state) -> None:
        """无文件时 load 应返回 None。"""
        assert load_race_state() is None

    def test_load_returns_none_when_zero_matches(self, tmp_race_state) -> None:
        """matches_needed=0 时 load 应返回 None（已完成）。"""
        save_race_state(0, 100)
        assert load_race_state() is None

    def test_clear_removes_file(self, tmp_race_state) -> None:
        """clear 应删除文件。"""
        save_race_state(10, 5)
        assert os.path.exists(_get_race_state_path())
        clear_race_state()
        assert not os.path.exists(_get_race_state_path())

    def test_clear_noop_when_no_file(self, tmp_race_state) -> None:
        """无文件时 clear 不应报错。"""
        clear_race_state()  # 不应抛异常

    def test_load_handles_corrupt_json(self, tmp_race_state) -> None:
        """损坏的 JSON 不应导致崩溃。"""
        with open(_get_race_state_path(), "w") as f:
            f.write("{invalid json!!!")
        assert load_race_state() is None

    def test_save_json_structure(self, tmp_race_state) -> None:
        """验证 JSON 文件内部结构符合预期。"""
        save_race_state(30, 20)
        with open(_get_race_state_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "matches_needed" in data
        assert "matches_completed" in data
        assert "last_updated" in data
        assert data["matches_needed"] == 30
        assert data["matches_completed"] == 20


# ==========================================
# EventLab 入口锁定（到达 CREATIVE_HUB 后不再扫描菜单标签）
# ==========================================

_RB = vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER
_A = vg.XUSB_BUTTON.XUSB_GAMEPAD_A
_IMG = np.zeros((10, 10, 3), dtype=np.uint8)


class TestEventLabLock:
    """到达 CREATIVE_HUB 后锁定 EventLab：忽略菜单标签、不再按 RB 翻页。"""

    def _fsm(self):
        fsm = FarmStateMachine(gamepad=Mock(), hwnd=123, detector=Mock(), sct=Mock())
        fsm.points_scanned = True  # 已扫描技能点，进入「上锁后进 EventLab」阶段
        return fsm

    @staticmethod
    def _buttons(press_mock):
        """提取每次 press_button(gamepad, button, ...) 的 button 参数。"""
        return [call.args[1] for call in press_mock.call_args_list]

    def test_other_tab_presses_rb_when_unlocked(self, monkeypatch) -> None:
        """未锁定时检测到菜单标签 → 仍按 RB 翻页（原行为不变）。"""
        import farm.skills as skills

        press = Mock()
        monkeypatch.setattr(skills, "press_button", press)
        fsm = self._fsm()
        fsm._handle_menu_state("STORE", _IMG)
        assert _RB in self._buttons(press)

    def test_creative_hub_locks_and_presses_a(self, monkeypatch) -> None:
        """到达 CREATIVE_HUB（已扫描）→ 上锁并按 A 进入。"""
        import farm.skills as skills

        press = Mock()
        monkeypatch.setattr(skills, "press_button", press)
        fsm = self._fsm()
        fsm._on_creative_hub()
        assert fsm.entering_eventlab is True
        assert _A in self._buttons(press)

    def test_locked_ignores_menu_tab(self, monkeypatch) -> None:
        """锁定后检测到菜单标签 → 不按任何键，计数 +1，保持锁定。"""
        import farm.skills as skills

        press = Mock()
        monkeypatch.setattr(skills, "press_button", press)
        monkeypatch.setattr(skills, "interruptible_sleep", lambda s: False)
        fsm = self._fsm()
        fsm.entering_eventlab = True
        fsm._handle_menu_state("STORE", _IMG)
        press.assert_not_called()
        assert fsm.entering_eventlab is True
        assert fsm._eventlab_tab_skips == 1

    def test_locked_still_retries_creative_hub(self, monkeypatch) -> None:
        """锁定后仍响应 CREATIVE_HUB（A 没按进可重试）。"""
        import farm.skills as skills

        press = Mock()
        monkeypatch.setattr(skills, "press_button", press)
        fsm = self._fsm()
        fsm.entering_eventlab = True
        fsm._handle_menu_state("CREATIVE_HUB", _IMG)
        assert _A in self._buttons(press)

    def test_lock_times_out_and_unlocks(self, monkeypatch) -> None:
        """连续忽略标签达上限 → 解锁恢复扫描（卡死兜底）。"""
        import farm.skills as skills

        monkeypatch.setattr(skills, "press_button", Mock())
        monkeypatch.setattr(skills, "interruptible_sleep", lambda s: False)
        fsm = self._fsm()
        fsm.entering_eventlab = True
        for _ in range(fsm._EVENTLAB_LOCK_MAX_SKIPS):
            fsm._handle_menu_state("STORE", _IMG)
        assert fsm.entering_eventlab is False

    def test_favorites_list_clears_lock(self, monkeypatch) -> None:
        """进入 My Favorites → entering_race 置位且锁定标志清除。"""
        import farm.skills as skills

        monkeypatch.setattr(skills, "press_button", Mock())
        fsm = self._fsm()
        fsm.entering_eventlab = True
        fsm._on_favorites_list()
        assert fsm.entering_race is True
        assert fsm.entering_eventlab is False


# ==========================================
# 技能点跨 tick 共识（_on_cars_tab）
# ==========================================


class TestSkillPointsConsensus:
    """CARS 页技能点读数需达成 K-of-N 共识才提交，避免单帧误读污染整局。"""

    def _fsm(self):
        return FarmStateMachine(gamepad=Mock(), hwnd=123, detector=Mock(), sct=Mock())

    def _patch(self, monkeypatch):
        import farm.skills as skills

        monkeypatch.setattr(skills, "press_button", Mock())
        monkeypatch.setattr(skills, "interruptible_sleep", lambda s: False)
        monkeypatch.setattr(skills, "save_race_state", lambda *a, **k: None)
        return skills

    def test_commits_after_agreement(self, monkeypatch) -> None:
        skills = self._patch(monkeypatch)
        monkeypatch.setattr(skills.module_ocr, "read_skill_points", lambda img: 300)
        fsm = self._fsm()
        for _ in range(fsm._SP_MIN_AGREEMENT - 1):
            fsm._on_cars_tab(_IMG)
            assert fsm.points_scanned is False  # 未达共识前不提交
        fsm._on_cars_tab(_IMG)  # 第 N 次达成共识
        assert fsm.points_scanned is True
        assert fsm.matches_needed == get_matches_needed(300)

    def test_no_commit_when_values_differ(self, monkeypatch) -> None:
        skills = self._patch(monkeypatch)
        vals = iter([100, 200, 300])
        monkeypatch.setattr(skills.module_ocr, "read_skill_points", lambda img: next(vals))
        fsm = self._fsm()
        for _ in range(3):
            fsm._on_cars_tab(_IMG)
        assert fsm.points_scanned is False  # 三个不同值，未达共识

    def test_assume_zero_after_persistent_none(self, monkeypatch) -> None:
        skills = self._patch(monkeypatch)
        monkeypatch.setattr(skills.module_ocr, "read_skill_points", lambda img: None)
        fsm = self._fsm()
        for _ in range(10):
            fsm._on_cars_tab(_IMG)
        assert fsm.points_scanned is True  # 连续 None 达阈值 → 当作 0 兜底
        assert fsm.matches_needed == get_matches_needed(0)
