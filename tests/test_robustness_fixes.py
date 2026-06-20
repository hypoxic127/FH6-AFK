# -*- coding: utf-8 -*-
"""
tests/test_robustness_fixes.py — 三个运行期容错修复的回归测试
================================================================
P1：is_stop_requested 与停止信号
P2b：结算画面卡死 30s 自动存调试图（每次等待只存一次）
P3：手动停止/teardown 期间截图失败应静默；BotStoppedError 不被吞、原样抛出
"""

import glob
import os
from unittest.mock import Mock

import numpy as np
import pytest

# ================================================================
# P1 / P3 基础：is_stop_requested 反映停止标志
# ================================================================


class TestStopFlag:
    def test_is_stop_requested_reflects_event(self) -> None:
        from macro.master_loop import clear_stop, is_stop_requested, request_stop

        clear_stop()
        assert is_stop_requested() is False
        request_stop()
        try:
            assert is_stop_requested() is True
        finally:
            clear_stop()
        assert is_stop_requested() is False


# ================================================================
# P3：截图异常的停止感知处理
# ================================================================


class TestCaptureStopHandling:
    def _patch_capture_env(self, monkeypatch, grab_exc):
        """让 get_client_rect 返回合法区域、_get_mss().grab 抛指定异常。"""
        import macro.core as core

        monkeypatch.setattr(core, "get_client_rect", lambda hwnd: (0, 0, 100, 100))
        fake = Mock()
        fake.grab.side_effect = grab_exc
        monkeypatch.setattr(core, "_get_mss", lambda: fake)
        # 隔离 MSS 重置副作用
        monkeypatch.setattr("engine.utils.reset_mss", lambda: None)

    def test_silent_when_stop_requested(self, monkeypatch) -> None:
        """停止进行中 → 截图失败不打 ERROR，返回 None。"""
        import macro.core as core
        from macro.master_loop import clear_stop, request_stop

        self._patch_capture_env(monkeypatch, RuntimeError("ScreenShotError"))
        log_error = Mock()
        monkeypatch.setattr(core, "log_error", log_error)

        request_stop()
        try:
            assert core.capture_raw_screenshot(123) is None
        finally:
            clear_stop()
        log_error.assert_not_called()

    def test_logs_error_when_not_stopping(self, monkeypatch) -> None:
        """非停止状态 → 截图失败仍按 ERROR 记录，返回 None。"""
        import macro.core as core
        from macro.master_loop import clear_stop

        clear_stop()
        self._patch_capture_env(monkeypatch, RuntimeError("ScreenShotError"))
        log_error = Mock()
        monkeypatch.setattr(core, "log_error", log_error)

        assert core.capture_raw_screenshot(123) is None
        log_error.assert_called_once()

    def test_bot_stopped_error_is_reraised(self, monkeypatch) -> None:
        """grab 抛 BotStoppedError → 不被吞，原样抛出以尽快终止。"""
        import macro.core as core
        from macro.master_loop import BotStoppedError, clear_stop

        clear_stop()
        self._patch_capture_env(monkeypatch, BotStoppedError("stopped"))
        monkeypatch.setattr(core, "log_error", Mock())

        with pytest.raises(BotStoppedError):
            core.capture_raw_screenshot(123)


# ================================================================
# P2b：结算卡死自动存图
# ================================================================


class TestStuckSnapshot:
    def _make_fsm(self):
        from farm.skills import FarmStateMachine

        detector = Mock()
        detector.detect.return_value = None  # 不触发任何状态转移
        return FarmStateMachine(gamepad=Mock(), hwnd=123, detector=detector, sct=Mock())

    def test_save_stuck_snapshot_writes_file(self, monkeypatch, tmp_path) -> None:
        import macro.core as core

        monkeypatch.setattr(core, "capture_raw_screenshot", lambda hwnd: np.zeros((10, 10, 3), dtype=np.uint8))
        monkeypatch.setattr("engine.runtime.get_data_dir", lambda: str(tmp_path))

        fsm = self._make_fsm()
        fsm._save_stuck_snapshot()

        files = glob.glob(os.path.join(str(tmp_path), "debug", "next_stuck_*.png"))
        assert len(files) == 1

    def test_handle_waiting_next_saves_once(self, monkeypatch, tmp_path) -> None:
        """卡死超 30s → 调试图只存一次（多次 tick 不重复存）。"""
        import time

        import macro.core as core

        capture = Mock(return_value=np.zeros((10, 10, 3), dtype=np.uint8))
        monkeypatch.setattr(core, "capture_raw_screenshot", capture)
        monkeypatch.setattr("engine.runtime.get_data_dir", lambda: str(tmp_path))

        fsm = self._make_fsm()
        fsm._wait_next_start = time.time() - 31  # 已卡 31s
        fsm._wait_next_debug_saved = False

        frame = np.zeros((900, 1600, 3), dtype=np.uint8)
        fsm._handle_waiting_next(frame)
        fsm._handle_waiting_next(frame)

        assert fsm._wait_next_debug_saved is True
        assert capture.call_count == 1
