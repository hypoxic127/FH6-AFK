# -*- coding: utf-8 -*-
"""
tests/test_stop_mechanism.py — Web UI 停止机制重构的回归测试
=============================================================
覆盖「协作式优先、注入式兜底」重构：
  - engine.control 原语：request_stop / is_stop_requested / check_stop / interruptible_sleep
  - BotStoppedError 改为 BaseException：能穿透宽泛 except Exception 不被吞
  - master_loop 对 engine.control 的再导出保持向后兼容
  - press_button 在按键前 check_stop（停止时不按键并抛出）
  - web.server._finalize_stop：协作退出则不注入，卡死才注入兜底
"""

from unittest.mock import Mock

import pytest

# ================================================================
# engine.control 基础原语
# ================================================================


class TestEngineControl:
    def test_request_and_is_stop_requested(self) -> None:
        from engine.control import clear_stop, is_stop_requested, request_stop

        clear_stop()
        assert is_stop_requested() is False
        request_stop()
        try:
            assert is_stop_requested() is True
        finally:
            clear_stop()
        assert is_stop_requested() is False

    def test_check_stop_raises_only_when_set(self) -> None:
        from engine.control import BotStoppedError, check_stop, clear_stop, request_stop

        clear_stop()
        check_stop()  # 未置位 → 不抛
        request_stop()
        try:
            with pytest.raises(BotStoppedError):
                check_stop()
        finally:
            clear_stop()

    def test_interruptible_sleep_returns_false_normally(self) -> None:
        from engine.control import clear_stop, interruptible_sleep

        clear_stop()
        assert interruptible_sleep(0.01) is False

    def test_interruptible_sleep_returns_true_immediately_when_stopped(self) -> None:
        """已请求停止时应立即返回 True，而非睡满 5s。"""
        import time

        from engine.control import clear_stop, interruptible_sleep, request_stop

        clear_stop()
        request_stop()
        try:
            start = time.time()
            assert interruptible_sleep(5.0) is True
            assert time.time() - start < 1.0  # 证明是立即返回而非阻塞
        finally:
            clear_stop()


# ================================================================
# BotStoppedError 的 BaseException 语义
# ================================================================


class TestBotStoppedErrorSemantics:
    def test_is_baseexception_not_exception(self) -> None:
        from engine.control import BotStoppedError

        assert issubclass(BotStoppedError, BaseException)
        assert not issubclass(BotStoppedError, Exception)

    def test_not_swallowed_by_except_exception(self) -> None:
        """穿透 except Exception，正是它不被业务热路径吞掉的关键。"""
        from engine.control import BotStoppedError

        swallowed = False
        propagated = False
        try:
            try:
                raise BotStoppedError("stop")
            except Exception:
                swallowed = True
        except BotStoppedError:
            propagated = True
        assert swallowed is False
        assert propagated is True


# ================================================================
# master_loop 再导出向后兼容
# ================================================================


class TestMasterLoopReexport:
    def test_reexports_same_objects(self) -> None:
        import engine.control as c
        import macro.master_loop as m

        assert m.BotStoppedError is c.BotStoppedError
        assert m.request_stop is c.request_stop
        assert m.clear_stop is c.clear_stop
        assert m.is_stop_requested is c.is_stop_requested


# ================================================================
# press_button 停止门控
# ================================================================


class TestPressButtonGating:
    def test_skips_and_raises_when_stopped(self) -> None:
        """停止已请求 → 按键前抛 BotStoppedError，绝不按下（避免卡住的按键）。"""
        from engine.control import BotStoppedError, clear_stop, request_stop
        from engine.utils import press_button

        gp = Mock()
        clear_stop()
        request_stop()
        try:
            with pytest.raises(BotStoppedError):
                press_button(gp, "A", delay=0)
        finally:
            clear_stop()
        gp.press_button.assert_not_called()
        gp.release_button.assert_not_called()

    def test_presses_normally_when_not_stopped(self) -> None:
        from engine.control import clear_stop
        from engine.utils import press_button

        gp = Mock()
        clear_stop()
        press_button(gp, "A", delay=0)
        gp.press_button.assert_called_once()
        gp.release_button.assert_called_once()


# ================================================================
# web.server._finalize_stop：协作优先，注入兜底
# ================================================================


class TestFinalizeStop:
    def test_no_inject_when_thread_exits_cooperatively(self, monkeypatch) -> None:
        import web.server as server

        kill = Mock(return_value=True)
        monkeypatch.setattr(server, "_kill_thread", kill)
        monkeypatch.setattr("engine.utils.reset_mss", lambda: None)

        thread = Mock()
        thread.is_alive.side_effect = [True, False]  # 进入时存活，join 后已退出
        server._finalize_stop(thread)

        kill.assert_not_called()

    def test_injects_when_thread_stuck(self, monkeypatch) -> None:
        import web.server as server

        kill = Mock(return_value=True)
        monkeypatch.setattr(server, "_kill_thread", kill)
        monkeypatch.setattr("engine.utils.reset_mss", lambda: None)

        thread = Mock()
        thread.is_alive.return_value = True  # 始终存活 = 卡在 C 调用
        server._finalize_stop(thread)

        kill.assert_called_once_with(thread)

    def test_none_thread_is_safe(self, monkeypatch) -> None:
        import web.server as server

        monkeypatch.setattr("engine.utils.reset_mss", lambda: None)
        server._finalize_stop(None)  # 不应抛异常
