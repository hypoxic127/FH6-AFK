# -*- coding: utf-8 -*-
"""
tests/test_state_manager.py — Web 运行状态聚合器
=================================================
覆盖 web/state_manager.py 的事件→快照聚合逻辑：日志环形缓冲上限、状态/统计更新、
启动/停止与 uptime 计算、最近日志截取、全局单例。直接调用 _on_* 处理器，避免与
全局事件总线耦合。
"""

from web.state_manager import StateManager, get_state_manager


class TestSnapshotUpdates:
    def test_initial_state(self) -> None:
        sm = StateManager()
        st = sm.get_state()
        assert st["current_state"] == "IDLE"
        assert st["bot_running"] is False
        assert st["loop_count"] == 0

    def test_state_change_updates_fields(self) -> None:
        sm = StateManager()
        sm._on_state_change({"state": "STATE_BUY_CARS", "loop_count": 4})
        st = sm.get_state()
        assert st["current_state"] == "STATE_BUY_CARS"
        assert st["loop_count"] == 4

    def test_stats_update_only_known_keys(self) -> None:
        sm = StateManager()
        sm._on_stats_update({"super_wheelspins": 7, "cars_bought": 33, "ignored": 1})
        st = sm.get_state()
        assert st["super_wheelspins"] == 7
        assert st["cars_bought"] == 33
        assert "ignored" not in st

    def test_bot_started_sets_running_and_state(self) -> None:
        sm = StateManager()
        sm._on_bot_started({"initial_state": "STATE_FARM_POINTS", "timestamp": 1000.0})
        st = sm.get_state()
        assert st["bot_running"] is True
        assert st["current_state"] == "STATE_FARM_POINTS"

    def test_uptime_computed_while_running(self) -> None:
        import time

        sm = StateManager()
        sm._on_bot_started({"timestamp": time.time() - 100})  # 100s 前启动 → uptime ≈ 100
        assert sm.get_state()["uptime_seconds"] >= 99

    def test_bot_stopped_clears_running(self) -> None:
        sm = StateManager()
        sm._on_bot_started({"timestamp": 1000.0})
        sm._on_bot_stopped({})
        assert sm.get_state()["bot_running"] is False


class TestLogBuffer:
    def test_logs_appended_and_returned(self) -> None:
        sm = StateManager()
        for i in range(5):
            sm._on_log({"msg": f"line-{i}"})
        recent = sm.get_recent_logs(count=3)
        assert [r["msg"] for r in recent] == ["line-2", "line-3", "line-4"]

    def test_ring_buffer_capped_at_max(self) -> None:
        sm = StateManager()
        for i in range(StateManager.MAX_LOG_HISTORY + 50):
            sm._on_log({"msg": str(i)})
        all_logs = sm.get_recent_logs(count=StateManager.MAX_LOG_HISTORY + 100)
        assert len(all_logs) == StateManager.MAX_LOG_HISTORY  # 超出上限的旧日志被丢弃
        assert all_logs[-1]["msg"] == str(StateManager.MAX_LOG_HISTORY + 49)


class TestSingleton:
    def test_get_state_manager_singleton(self) -> None:
        assert get_state_manager() is get_state_manager()
