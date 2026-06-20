# -*- coding: utf-8 -*-
"""
tests/test_utils.py — engine/utils.py 单元测试

覆盖：
  - safe_print()  安全打印
  - 日志函数（log_info / log_success / log_warning / log_error）
  - reset_mss()  MSS 重置逻辑
"""

import pytest

from engine.utils import (
    get_mss,
    log_error,
    log_info,
    log_success,
    log_warning,
    reset_mss,
    safe_print,
)


class TestSafePrint:
    """safe_print 安全打印测试。"""

    def test_ascii_text(self, capsys: pytest.CaptureFixture) -> None:
        safe_print("hello world")
        captured = capsys.readouterr()
        assert "hello world" in captured.out

    def test_unicode_text(self, capsys: pytest.CaptureFixture) -> None:
        safe_print("你好世界 🎮")
        captured = capsys.readouterr()
        assert len(captured.out) > 0  # 不崩溃即可

    def test_empty_string(self, capsys: pytest.CaptureFixture) -> None:
        safe_print("")
        captured = capsys.readouterr()
        assert captured.out.strip() == ""


class TestLogFunctions:
    """日志函数不应崩溃且包含正确前缀。"""

    def test_log_info(self, capsys: pytest.CaptureFixture) -> None:
        log_info("test message")
        captured = capsys.readouterr()
        assert "INFO" in captured.out

    def test_log_success(self, capsys: pytest.CaptureFixture) -> None:
        log_success("test message")
        captured = capsys.readouterr()
        assert "SUCCESS" in captured.out

    def test_log_warning(self, capsys: pytest.CaptureFixture) -> None:
        log_warning("test message")
        captured = capsys.readouterr()
        assert "WARNING" in captured.out

    def test_log_error(self, capsys: pytest.CaptureFixture) -> None:
        log_error("test message")
        captured = capsys.readouterr()
        assert "ERROR" in captured.out


class TestMssSingleton:
    """MSS 截图单例管理测试。"""

    @pytest.mark.hardware
    def test_get_mss_returns_instance(self) -> None:
        """get_mss() 应返回 MSS 实例（需要 Windows 桌面环境）。"""
        sct = get_mss()
        assert sct is not None

    @pytest.mark.hardware
    def test_get_mss_singleton(self) -> None:
        """多次调用应返回同一实例。"""
        sct1 = get_mss()
        sct2 = get_mss()
        assert sct1 is sct2

    @pytest.mark.hardware
    def test_reset_mss_clears(self) -> None:
        """reset 后再 get 应返回新实例。"""
        sct1 = get_mss()
        reset_mss()
        sct2 = get_mss()
        assert sct1 is not sct2


@pytest.mark.usefixtures("tmp_race_state")
class TestGetHistoricalStats:
    """历史统计数据解析功能测试。"""

    def test_empty_log_returns_defaults(self) -> None:
        """无文件或文件为空时返回默认数值。"""
        from engine.runtime import get_historical_stats

        stats = get_historical_stats()
        assert stats["total_matches"] == 0
        assert stats["success_rate"] == 100
        assert stats["est_points"] == 0
        assert stats["avg_time_seconds"] == 0
        assert stats["total_wheelspins"] == 0

    def test_calculate_stats_from_log(self, tmp_race_state) -> None:
        """从模拟的 jsonl 记录中正确计算各项指标，包括超级轮盘数和排除非比赛事件。"""
        import json
        import os
        from engine.runtime import get_data_dir, get_historical_stats

        data_dir = str(tmp_race_state)
        archive_path = os.path.join(data_dir, "play_archive.jsonl")

        # 写入 4 场比赛记录和 2 条升级记录（包含两个 60 秒的比赛间隔，以及一个 10 分钟的比赛间隔）
        # 升级事件插在比赛中间，应该被忽略于时间间隔计算
        records = [
            {"ts": "2026-06-02T08:00:00", "type": "race", "match": 1, "remaining": 9, "status": "success"},
            {"ts": "2026-06-02T08:01:00", "type": "race", "match": 2, "remaining": 8, "status": "success"},
            {"ts": "2026-06-02T08:01:30", "type": "upgrade", "car": "Impreza", "wheelspins": 1},
            {"ts": "2026-06-02T08:02:00", "type": "race", "match": 3, "remaining": 7, "status": "success"},
            {"ts": "2026-06-02T08:02:40", "type": "upgrade", "car": "Impreza", "wheelspins": 1},
            {"ts": "2026-06-02T08:12:00", "type": "race", "match": 4, "remaining": 6, "status": "success"},
        ]

        with open(archive_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

        stats = get_historical_stats()
        assert stats["total_matches"] == 4
        assert stats["success_rate"] == 100
        # 默认 points_per_match = 10，所以 4 场比赛共 40 点
        assert stats["est_points"] == 40
        # 累计升级获得的超级轮盘数应为 2
        assert stats["total_wheelspins"] == 2
        # 比赛时间差为 60s, 60s, 600s. 600s 被过滤，平均时间应为 (60 + 60) / 2 = 60s
        assert stats["avg_time_seconds"] == 60

        # 验证 recent_races 图表数据
        recent = stats["recent_races"]
        assert len(recent) == 4
        assert recent[0]["match"] == 1
        assert recent[0]["duration"] is None  # 第一场无前序比赛
        assert recent[1]["match"] == 2
        assert recent[1]["duration"] == 60  # 8:01 - 8:00 = 60s
        assert recent[2]["match"] == 3
        assert recent[2]["duration"] == 60  # 8:02 - 8:01 = 60s (忽略中间的升级事件)
        assert recent[3]["match"] == 4
        assert recent[3]["duration"] is None  # 8:12 - 8:02 = 600s (超过 300s 阈值，设为 None)
