# -*- coding: utf-8 -*-
"""
tests/test_runtime.py — Bot 配置读写 & 历史统计解析
====================================================
覆盖 engine/runtime.py 的纯 IO/逻辑分支：
  - load_bot_config: 默认值 / int 强转 / 非法值回退 / custom_roi 透传 / 坏 JSON 兜底
  - save_bot_config: 合并写入 + 往返
  - get_historical_stats: jsonl 解析（比赛+升级、空行/坏行容错、成功率/均时计算）
全部用临时目录，避免污染项目 data/。
"""

import json
import os

import pytest

import engine.runtime as runtime


@pytest.fixture
def data_dir(tmp_path, monkeypatch: pytest.MonkeyPatch) -> str:
    """把 runtime.get_data_dir 指向临时目录。"""
    d = str(tmp_path)
    monkeypatch.setattr(runtime, "get_data_dir", lambda: d)
    return d


def _write_config(data_dir: str, raw: dict) -> None:
    with open(os.path.join(data_dir, "bot_config.json"), "w", encoding="utf-8") as f:
        json.dump(raw, f)


class TestLoadBotConfig:
    def test_defaults_when_missing(self, data_dir: str) -> None:
        cfg = runtime.load_bot_config()
        assert cfg["points_per_match"] == 10
        assert cfg["target_points"] == 999
        assert cfg["custom_roi"] is None

    def test_int_coercion_from_string(self, data_dir: str) -> None:
        _write_config(data_dir, {"points_per_match": "15", "target_points": "500"})
        cfg = runtime.load_bot_config()
        assert cfg["points_per_match"] == 15
        assert cfg["target_points"] == 500

    def test_invalid_int_falls_back_to_default(self, data_dir: str) -> None:
        _write_config(data_dir, {"points_per_match": "abc"})
        assert runtime.load_bot_config()["points_per_match"] == 10

    def test_custom_roi_passthrough(self, data_dir: str) -> None:
        roi = [0.72, 0.76, 0.28, 0.31]
        _write_config(data_dir, {"custom_roi": roi})
        assert runtime.load_bot_config()["custom_roi"] == roi

    def test_unknown_keys_ignored(self, data_dir: str) -> None:
        _write_config(data_dir, {"bogus": 1, "points_per_match": 7})
        cfg = runtime.load_bot_config()
        assert "bogus" not in cfg
        assert cfg["points_per_match"] == 7

    def test_corrupt_json_returns_default(self, data_dir: str) -> None:
        with open(os.path.join(data_dir, "bot_config.json"), "w", encoding="utf-8") as f:
            f.write("{ this is not json")
        assert runtime.load_bot_config()["points_per_match"] == 10


class TestSaveBotConfig:
    def test_save_then_load_roundtrip(self, data_dir: str) -> None:
        runtime.save_bot_config({"points_per_match": 12})
        runtime.save_bot_config({"custom_roi": [0.1, 0.2, 0.3, 0.4]})
        cfg = runtime.load_bot_config()
        # 第二次保存应合并而非覆盖第一次
        assert cfg["points_per_match"] == 12
        assert cfg["custom_roi"] == [0.1, 0.2, 0.3, 0.4]


class TestHistoricalStats:
    def test_empty_when_no_archive(self, data_dir: str) -> None:
        stats = runtime.get_historical_stats()
        assert stats["total_matches"] == 0
        assert stats["total_wheelspins"] == 0
        assert stats["success_rate"] == 100  # 无数据时默认 100
        assert stats["recent_races"] == []

    def test_counts_and_rates(self, data_dir: str) -> None:
        lines = [
            json.dumps({"ts": "2026-06-20T10:00:00", "type": "race", "match": 1, "status": "success"}),
            json.dumps({"ts": "2026-06-20T10:01:00", "type": "race", "match": 2, "status": "success"}),
            json.dumps({"ts": "2026-06-20T10:02:30", "type": "race", "match": 3, "status": "fail"}),
            json.dumps({"type": "upgrade", "car": "Impreza", "wheelspins": 2}),
            "",  # 空行应被跳过
            "not-json-line",  # 坏行应被容错跳过
        ]
        with open(os.path.join(data_dir, "play_archive.jsonl"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        stats = runtime.get_historical_stats()
        assert stats["total_matches"] == 3
        assert stats["total_wheelspins"] == 2
        assert stats["success_rate"] == 66  # 2/3 → int 66
        assert stats["est_points"] == 30  # 3 场 × 默认 10 点
        assert stats["avg_time_seconds"] == 75  # (60s + 90s) / 2
        assert len(stats["recent_races"]) == 3
