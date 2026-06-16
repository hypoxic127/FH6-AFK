# -*- coding: utf-8 -*-
"""
web/server.py — Flask + SocketIO Web 控制面板服务器
====================================================
提供实时日志推送、状态监控和远程控制功能。

启动方式::

    python main_bot.py --web          # 启动 Web UI 模式
    python main_bot.py --web --port 9000  # 自定义端口
"""

from __future__ import annotations

import ctypes
import logging
import os
import socket
import threading
import time
from typing import Any

from flask import Flask, send_from_directory
from flask_socketio import SocketIO

from engine.event_bus import get_bus
from engine.runtime import get_base_dir
from macro.master_loop import BotStoppedError, clear_stop, request_stop
from web.state_manager import get_state_manager

# 抑制 Flask/Werkzeug 的请求日志和 WebSocket 升级错误
# Python 3.14 + Werkzeug 会在 WS 升级时产生 "write() before start_response" 噪音
logging.getLogger("werkzeug").setLevel(logging.CRITICAL)

# ==========================================
# Flask 应用 + SocketIO
# ==========================================
_static_dir: str = os.path.join(get_base_dir(), "web", "static")
_app: Flask = Flask(
    __name__,
    static_folder=_static_dir,
    static_url_path="/static",
)
_app.config["SECRET_KEY"] = "fh6-autobot-web-ui"

_socketio: SocketIO = SocketIO(
    _app,
    cors_allowed_origins="*",
    async_mode="threading",
    logger=False,
    engineio_logger=False,
)

# Bot 线程引用
_bot_thread: threading.Thread | None = None
_bot_stop_event: threading.Event = threading.Event()
_lan_url: str = ""


# ==========================================
# HTTP 路由
# ==========================================
@_app.route("/")
def index() -> str:
    """返回主页 HTML。"""
    return send_from_directory(_app.static_folder, "index.html")


# ==========================================
# WebSocket 事件处理
# ==========================================
@_socketio.on("connect")
def handle_connect() -> None:
    """客户端连接时推送当前状态、最近日志、版本和更新信息。"""
    manager = get_state_manager()
    _socketio.emit("state_update", manager.get_state())
    if _lan_url:
        _socketio.emit("lan_url", {"url": _lan_url})
    for log_entry in manager.get_recent_logs():
        _socketio.emit("log", log_entry)

    # 推送版本号和缓存的更新信息
    from engine.version import __version__

    _socketio.emit("version_info", {"version": __version__})
    from engine.updater import get_cached_update_info

    cached = get_cached_update_info()
    if cached:
        _socketio.emit(
            "update_available",
            {
                "version": cached["version"],
                "current": __version__,
                "release_url": cached.get("release_url", ""),
                "file_size": cached.get("file_size", 0),
            },
        )

    # 推送 Bot 配置（单局点数等）
    from engine.runtime import load_bot_config

    _socketio.emit("bot_config", load_bot_config())


@_socketio.on("get_bot_config")
def handle_get_bot_config() -> None:
    """客户端请求当前 Bot 配置。"""
    from engine.runtime import load_bot_config

    _socketio.emit("bot_config", load_bot_config())


@_socketio.on("save_bot_config")
def handle_save_bot_config(data: dict[str, int] | None = None) -> None:
    """保存 Bot 配置（单局点数/目标点数）。"""
    if not data:
        return
    from engine.runtime import save_bot_config

    save_bot_config(data)
    _socketio.emit("bot_config", data)
    get_bus().emit("log", {"level": "info", "msg": f"Bot config updated: {data}"})


@_socketio.on("start_bot")
def handle_start_bot(data: dict[str, Any] | None = None) -> None:
    """启动 bot 线程。"""
    global _bot_thread
    if _bot_thread and _bot_thread.is_alive():
        _socketio.emit("error", {"msg": "Bot 已在运行中"})
        return

    if data is None:
        data = {}

    initial_state = data.get("initial_state")
    skip_buy = data.get("skip_buy", False)
    loop = data.get("loop", False)

    _bot_stop_event.clear()
    clear_stop()

    # Reset MSS to ensure a fresh GDI device context for the new run
    from engine.utils import reset_mss

    reset_mss()

    def _run_bot() -> None:
        """在子线程中运行 bot 主循环。"""
        try:
            bus = get_bus()
            bus.emit("bot_started", {"initial_state": initial_state or "STATE_FARM_POINTS"})

            from macro import run_master_bot_loop

            run_master_bot_loop(initial_state=initial_state, skip_buy=skip_buy, loop=loop)
        except BotStoppedError:
            pass  # 正常停止，由 handle_stop_bot 发出日志
        except KeyboardInterrupt:
            pass
        except Exception as e:
            get_bus().emit("log", {"level": "error", "msg": f"Bot 异常退出: {e}"})
        finally:
            get_bus().emit("bot_stopped", {})

    _bot_thread = threading.Thread(target=_run_bot, daemon=True, name="bot-worker")
    _bot_thread.start()
    _socketio.emit("bot_status", {"running": True})


def _kill_thread(thread: threading.Thread) -> bool:
    """向目标线程注入 BotStoppedError 异常，使其立即中断。

    使用 CPython 私有 API PyThreadState_SetAsyncExc。
    返回 True 表示注入成功。
    """
    if not thread.is_alive():
        return False
    tid = thread.ident
    if tid is None:
        return False
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_ulong(tid),
        ctypes.py_object(BotStoppedError),
    )
    return res == 1


@_socketio.on("stop_bot")
def handle_stop_bot() -> None:
    """立即停止 bot 线程。"""
    _bot_stop_event.set()
    request_stop()

    # 向 bot 线程注入异常，立即中断 time.sleep / I/O / 任何 Python 代码
    if _bot_thread and _bot_thread.is_alive():
        _kill_thread(_bot_thread)

    get_bus().emit("bot_stopped", {})
    _socketio.emit("bot_status", {"running": False})
    get_bus().emit("log", {"level": "warning", "msg": "⛔ Bot 已被 Web UI 手动停止"})

    # Reset MSS — _kill_thread leaves GDI handles in corrupt state
    from engine.utils import reset_mss

    reset_mss()


@_socketio.on("get_state")
def handle_get_state() -> None:
    """客户端请求最新状态。"""
    _socketio.emit("state_update", get_state_manager().get_state())


@_socketio.on("check_update")
def handle_check_update() -> None:
    """检查是否有新版本。"""
    from engine.updater import check_for_update
    from engine.version import __version__

    info = check_for_update(force=True)
    if info:
        _socketio.emit(
            "update_available",
            {
                "version": info["version"],
                "current": __version__,
                "release_url": info.get("release_url", ""),
                "file_size": info.get("file_size", 0),
            },
        )
    else:
        _socketio.emit("update_status", {"msg": f"Already on latest version (v{__version__})"})


@_socketio.on("do_update")
def handle_do_update() -> None:
    """执行一键更新：下载 → 替换 → 重启。"""
    from engine.updater import execute_update

    def _progress(downloaded: int, total: int) -> None:
        _socketio.emit("update_progress", {"downloaded": downloaded, "total": total})

    def _pre_reboot() -> None:
        # 通知前端：即将重启，请显示"重启中"而非"断线"
        _socketio.emit("rebooting", {"msg": "Update complete, restarting..."})
        time.sleep(0.5)  # 留时间给 WebSocket 发送完

    result: str = execute_update(progress_cb=_progress, pre_reboot_cb=_pre_reboot)
    if result:
        _socketio.emit("update_status", {"msg": result, "error": True})


# ==========================================
# 事件总线 → WebSocket 广播桥接
# ==========================================
def _bridge_events() -> None:
    """将事件总线的事件桥接到 WebSocket 广播。"""
    bus = get_bus()

    def _on_log(data: dict[str, Any]) -> None:
        _socketio.emit("log", data)

    def _on_state_change(data: dict[str, Any]) -> None:
        _socketio.emit("state_update", get_state_manager().get_state())

    def _on_bot_started(data: dict[str, Any]) -> None:
        _socketio.emit("bot_status", {"running": True})
        _socketio.emit("state_update", get_state_manager().get_state())

    def _on_bot_stopped(data: dict[str, Any]) -> None:
        _socketio.emit("bot_status", {"running": False})
        _socketio.emit("state_update", get_state_manager().get_state())

    bus.on("log", _on_log)
    bus.on("state_change", _on_state_change)
    bus.on("bot_started", _on_bot_started)
    bus.on("bot_stopped", _on_bot_stopped)


# ==========================================
# 公共 API
# ==========================================
def _get_local_ip() -> str:
    """获取本机局域网 IP 地址。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def start_server(port: int = 6800) -> None:
    """启动 Web UI 服务器。

    Args:
        port: HTTP 监听端口，默认 6800
    """
    # 初始化状态管理器（订阅事件总线）
    get_state_manager()
    # 桥接事件到 WebSocket
    _bridge_events()

    global _lan_url
    local_ip = _get_local_ip()
    _lan_url = f"http://{local_ip}:{port}"
    from engine.i18n import t
    from engine.utils import safe_print

    safe_print("")
    safe_print("=" * 55)
    safe_print(t("web.banner_title"))
    safe_print("=" * 55)
    safe_print("")
    safe_print(t("web.banner_local", port=port))
    safe_print(t("web.banner_lan", ip=local_ip, port=port))
    safe_print(t("web.banner_hint"))
    safe_print("")
    safe_print("=" * 55)
    safe_print("")

    _socketio.run(_app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
