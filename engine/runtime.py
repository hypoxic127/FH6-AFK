# -*- coding: utf-8 -*-
"""
engine/runtime.py — PyInstaller 运行时路径兼容层
==================================================
PyInstaller 打包后，`__file__` 指向临时解压目录（`sys._MEIPASS`），
不是用户的工作目录。本模块提供统一的路径解析，确保：

  - 代码资源（只读）：从打包目录或项目源码目录加载
  - 用户数据（读写）：始终使用 exe 所在目录（非临时目录）
"""

import os
import sys
from typing import Any


def get_base_dir() -> str:
    """获取项目根目录（代码资源所在位置）。

    PyInstaller 打包后返回 sys._MEIPASS（临时解压目录），
    开发模式下返回项目根目录。

    Returns:
        项目根目录的绝对路径
    """
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后
        return sys._MEIPASS  # type: ignore[attr-defined]
    # 开发模式: engine/runtime.py -> 上级目录
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_user_dir() -> str:
    """获取用户数据目录（可读写，用于 race_state.json 等）。

    PyInstaller 打包后返回 exe 所在目录，
    开发模式下返回项目根目录。

    Returns:
        用户数据目录的绝对路径
    """
    if getattr(sys, "frozen", False):
        # exe 所在目录（用户可以在此放配置文件）
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_data_dir() -> str:
    """获取运行时数据目录 (data/)，自动创建。

    所有运行时文件（race_state.json、play_archive.jsonl 等）
    统一存放在此目录下，保持项目根目录整洁。

    Returns:
        data/ 目录的绝对路径
    """
    data_dir = os.path.join(get_user_dir(), "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


_DEFAULT_BOT_CONFIG: dict[str, Any] = {
    "points_per_match": 10,
    "target_points": 999,
    "custom_roi": None,
    "auto_wheelspin": True,  # 升级后是否自动进入 Super Wheelspin 抽奖
    "wheelspin_count": 0,  # 每轮抽奖次数上限，0 = 全部抽完
    "wheelspin_sell_threshold": 250000,  # 重复车售价阈值 (CR)，低于则卖出、高于则保留
}


def load_bot_config() -> dict[str, Any]:
    """加载用户 Bot 配置 (data/bot_config.json)。

    文件不存在或损坏时返回默认值。用于支持不同蓝图的单局点数自定义。

    Returns:
        包含 points_per_match 和 target_points 及 custom_roi 的配置字典
    """
    config_path = os.path.join(get_data_dir(), "bot_config.json")
    if not os.path.exists(config_path):
        return dict(_DEFAULT_BOT_CONFIG)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            import json

            user_cfg = json.load(f)
        merged = dict(_DEFAULT_BOT_CONFIG)
        for k, v in user_cfg.items():
            if k in merged:
                if k in ["points_per_match", "target_points", "wheelspin_count", "wheelspin_sell_threshold"]:
                    try:
                        merged[k] = int(v)
                    except (ValueError, TypeError):
                        pass
                elif k == "auto_wheelspin":
                    # 健壮布尔解析：bool("false") 为 True，故不能直接 bool(v)
                    merged[k] = v if isinstance(v, bool) else str(v).strip().lower() in ("true", "1", "yes", "on")
                else:
                    merged[k] = v
        return merged
    except (IOError, ValueError):
        return dict(_DEFAULT_BOT_CONFIG)


def save_bot_config(config: dict[str, Any]) -> None:
    """保存用户 Bot 配置到 data/bot_config.json。

    Args:
        config: 包含 points_per_match 和/或 target_points 及 custom_roi 的配置字典
    """
    import json

    config_path = os.path.join(get_data_dir(), "bot_config.json")
    merged = load_bot_config()
    merged.update(config)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)


def is_frozen() -> bool:
    """判断是否在 PyInstaller 打包环境中运行。

    Returns:
        True 表示运行在打包的 exe 中
    """
    return getattr(sys, "frozen", False)


def get_historical_stats() -> dict[str, Any]:
    """从 data/play_archive.jsonl 读取比赛历史记录并计算统计数据。

    Returns:
        包含累计比赛、成功率、累计赚取点数及平均单场时间的字典
    """
    import json
    from datetime import datetime
    from typing import Any

    archive_path = os.path.join(get_data_dir(), "play_archive.jsonl")

    total_matches = 0
    success_matches = 0
    total_wheelspins = 0
    total_wheelspin_claimed = 0
    race_records = []

    if os.path.exists(archive_path):
        try:
            with open(archive_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        rec_type = record.get("type", "race")  # 默认视为比赛记录以兼容历史数据
                        if rec_type == "upgrade":
                            total_wheelspins += record.get("wheelspins", 1)
                        elif rec_type == "wheelspin":
                            total_wheelspin_claimed += 1  # 实际抽掉的次数（区别于 upgrade 赚到的）
                        else:  # race
                            total_matches += 1
                            status = record.get("status", "success")
                            if status == "success":
                                success_matches += 1
                            ts_str = record.get("ts")
                            dt = None
                            if ts_str:
                                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                                    try:
                                        dt = datetime.strptime(ts_str, fmt)
                                        break
                                    except ValueError:
                                        continue
                            race_records.append(
                                {"match": record.get("match", total_matches), "dt": dt, "status": status}
                            )
                    except json.JSONDecodeError:
                        continue
        except IOError:
            pass

    success_rate = 100
    if total_matches > 0:
        success_rate = int((success_matches / total_matches) * 100)

    config = load_bot_config()
    points_per_match = config.get("points_per_match", 10)
    est_points = total_matches * points_per_match

    # Sort races by datetime to calculate durations
    races_with_dt = [r for r in race_records if r["dt"] is not None]
    races_with_dt.sort(key=lambda x: x["dt"])

    timestamps = [r["dt"] for r in races_with_dt]

    avg_time_seconds = 0
    if len(timestamps) >= 2:
        deltas = []
        for i in range(len(timestamps) - 1):
            diff = (timestamps[i + 1] - timestamps[i]).total_seconds()
            if 0 < diff < 300:
                deltas.append(diff)
        if deltas:
            avg_time_seconds = int(sum(deltas) / len(deltas))

    # Calculate recent match durations
    for i in range(len(races_with_dt)):
        if i == 0:
            races_with_dt[i]["duration"] = None
        else:
            diff = (races_with_dt[i]["dt"] - races_with_dt[i - 1]["dt"]).total_seconds()
            if 0 < diff < 300:
                races_with_dt[i]["duration"] = int(diff)
            else:
                races_with_dt[i]["duration"] = None

    recent_races = []
    for r in races_with_dt[-30:]:
        recent_races.append(
            {
                "match": r["match"],
                "duration": r["duration"],
                "status": r["status"],
                "ts": r["dt"].strftime("%Y-%m-%dT%H:%M:%S"),
            }
        )

    return {
        "total_matches": total_matches,
        "success_rate": success_rate,
        "est_points": est_points,
        "avg_time_seconds": avg_time_seconds,
        "total_wheelspins": total_wheelspins,
        "total_wheelspin_claimed": total_wheelspin_claimed,
        "recent_races": recent_races,
    }
