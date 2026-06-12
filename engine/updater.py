# -*- coding: utf-8 -*-
"""
engine/updater.py — GitHub Releases 自动更新器
================================================
设计要点（经过两轮代码审查）：

安全措施:
  - 整数元组版本比较，避免字符串比对漏洞
  - regex 清洗版本后缀 (v1.5.4-beta → 1.5.4)
  - Socket read timeout (15s)，无整体下载超时
  - 事务性文件替换 + 失败回滚（不会 brick 用户安装）
  - 过滤 --update 参数，防止无限重启死循环
  - 全局锁防止并发更新
  - GitHub API 1小时检查缓存，避免限流
  - 多镜像轮询兜底（直连 → ghproxy 代理列表）
  - 仅 PyInstaller 打包模式下生效
  - 按文件名(.exe)精确匹配 Release Asset

UX 设计:
  - 后台线程检查，不阻塞主程序启动
  - Console 模式：仅打印日志提示，不弹 input()
  - Web UI 模式：WebSocket 推送横幅 + 一键更新按钮
  - 重启前发送 "rebooting" 事件，前端平滑过渡
  - 重启时继承原始启动参数（过滤 --update）
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from engine.runtime import get_data_dir, is_frozen
from engine.version import __version__

logger = logging.getLogger(__name__)

# ==========================================
# 常量
# ==========================================

GITHUB_REPO: str = "hypoxic127/FH6-AFK"
GITHUB_API_URL: str = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
CHECK_INTERVAL_SECONDS: int = 3600  # 1 小时缓存

# 下载镜像列表（直连优先，依次 fallback）
_DOWNLOAD_MIRRORS: list[str] = [
    "",  # 直连 GitHub
    "https://ghproxy.net/",  # 镜像 1
    "https://mirror.ghproxy.com/",  # 镜像 2
    "https://gh-proxy.com/",  # 镜像 3
]

# Socket read timeout（秒）— 15秒内无数据才断开，不限总时间
_READ_TIMEOUT: int = 15
_API_TIMEOUT: int = 10

# ==========================================
# 全局更新锁（防止并发更新）
# ==========================================
_update_lock: threading.Lock = threading.Lock()
_is_updating: bool = False

# 后台检查结果缓存（供 Web UI 查询）
_cached_update_info: dict[str, Any] | None = None


# ==========================================
# 版本解析
# ==========================================


def parse_version(v: str) -> tuple[int, ...]:
    """将版本字符串解析为整数元组，安全处理后缀。

    Examples:
        parse_version("v1.5.10") → (1, 5, 10)
        parse_version("1.5.4-beta") → (1, 5, 4)
        parse_version("1.6.0.RC1") → (1, 6, 0)

    Args:
        v: 版本字符串，可带 'v' 前缀和 -beta 等后缀

    Returns:
        整数元组，用于比较
    """
    # 移除 'v' 前缀，然后取第一个非数字非点字符之前的部分
    clean: str = re.split(r"[-_A-Za-z]", v.lstrip("v"))[0]
    try:
        return tuple(int(x) for x in clean.split(".") if x)
    except ValueError:
        return (0,)


# ==========================================
# 缓存管理
# ==========================================


def _get_cache_path() -> str:
    """获取更新检查缓存文件路径。"""
    return os.path.join(get_data_dir(), "last_update_check.json")


def _should_check() -> bool:
    """检查距离上次 API 请求是否已过 1 小时。"""
    cache_path: str = _get_cache_path()
    try:
        with open(cache_path, encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
        last_check: float = data.get("timestamp", 0)
        return (time.time() - last_check) >= CHECK_INTERVAL_SECONDS
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return True


def _save_check_time() -> None:
    """保存本次检查的时间戳。"""
    cache_path: str = _get_cache_path()
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"timestamp": time.time()}, f)
    except OSError:
        pass


# ==========================================
# GitHub API 检查
# ==========================================


def check_for_update(force: bool = False) -> dict[str, Any] | None:
    """检查 GitHub Releases 是否有新版本。

    Args:
        force: 忽略缓存强制检查

    Returns:
        有新版本时返回 {"version": "1.5.4", "download_url": "...", "release_url": "..."}
        已是最新或检查失败时返回 None
    """
    global _cached_update_info

    if not force and not _should_check():
        return _cached_update_info

    try:
        req = urllib.request.Request(
            GITHUB_API_URL,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": f"FH6-AutoBot/{__version__}",
            },
        )
        with urllib.request.urlopen(req, timeout=_API_TIMEOUT) as resp:
            data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))

        _save_check_time()

        remote_tag: str = data.get("tag_name", "")
        remote_ver: tuple[int, ...] = parse_version(remote_tag)
        local_ver: tuple[int, ...] = parse_version(__version__)

        if remote_ver <= local_ver:
            _cached_update_info = None
            return None

        # 精确匹配 .exe 资产（避免下载 source code 等其他文件）
        assets: list[dict[str, Any]] = data.get("assets", [])
        exe_url: str | None = next(
            (asset["browser_download_url"] for asset in assets if asset.get("name", "").endswith(".exe")),
            None,
        )

        if not exe_url:
            return None

        _cached_update_info = {
            "version": remote_tag.lstrip("v"),
            "tag": remote_tag,
            "download_url": exe_url,
            "release_url": data.get("html_url", ""),
            "file_size": next(
                (asset.get("size", 0) for asset in assets if asset.get("name", "").endswith(".exe")),
                0,
            ),
        }
        return _cached_update_info

    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
        logger.debug("Update check failed: %s", e)
        return None


# ==========================================
# 下载（多镜像轮询 + 进度回调）
# ==========================================


def download_update(
    url: str,
    dest_path: str,
    progress_cb: Callable[[int, int], None] | None = None,
) -> bool:
    """下载更新文件，自动尝试多个镜像。

    Args:
        url: GitHub Release asset 的原始 URL
        dest_path: 下载保存路径
        progress_cb: 进度回调 (downloaded_bytes, total_bytes)

    Returns:
        下载成功返回 True
    """
    for mirror in _DOWNLOAD_MIRRORS:
        download_url: str = f"{mirror}{url}" if mirror else url
        try:
            req = urllib.request.Request(
                download_url,
                headers={"User-Agent": f"FH6-AutoBot/{__version__}"},
            )
            with urllib.request.urlopen(req, timeout=_READ_TIMEOUT) as resp:
                total: int = int(resp.headers.get("Content-Length", 0))
                downloaded: int = 0
                chunk_size: int = 64 * 1024  # 64 KB

                with open(dest_path, "wb") as f:
                    while True:
                        chunk: bytes = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb:
                            progress_cb(downloaded, total)

            # 基本校验：文件不为空且大于 1 MB（EXE 至少几十 MB）
            file_size: int = os.path.getsize(dest_path)
            if file_size < 1_000_000:
                logger.warning("Downloaded file too small (%d bytes), skipping mirror: %s", file_size, mirror)
                continue

            return True

        except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as e:
            logger.warning("Download failed via '%s': %s", mirror or "direct", e)
            # 清理不完整的文件
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except OSError:
                    pass
            continue

    return False


# ==========================================
# 应用更新（事务性替换 + 回滚）
# ==========================================


def apply_update(new_exe_path: str, reboot: bool = True) -> None:
    """替换当前 EXE 并重启。

    事务性流程:
      1. 旧文件改名为 .old
      2. 新文件移入原位
      3. 如果步骤 2 失败，回滚步骤 1
      4. 启动新进程（继承参数，过滤 --update）
      5. 退出当前进程

    Args:
        new_exe_path: 下载好的新 EXE 临时路径
        reboot: 是否自动重启（False 时仅替换不重启）

    Raises:
        PermissionError: 没有写入权限（如 Program Files 目录）
        RuntimeError: 替换失败且回滚也失败的极端情况
    """
    current_exe: str = sys.executable
    old_exe: str = current_exe + ".old"

    # 清理之前残留的 .old 文件
    if os.path.exists(old_exe):
        try:
            os.remove(old_exe)
        except OSError:
            pass

    # Step 1: 旧文件改名
    try:
        os.rename(current_exe, old_exe)
    except PermissionError:
        raise PermissionError(
            f"No write permission to '{os.path.dirname(current_exe)}'. "
            "Try running as Administrator or move the EXE to a user-writable directory."
        )

    # Step 2: 新文件就位（带回滚）
    try:
        shutil.move(new_exe_path, current_exe)
    except Exception as e:
        # 🚨 回滚：将旧文件恢复
        try:
            os.rename(old_exe, current_exe)
        except OSError as rollback_err:
            raise RuntimeError(
                f"CRITICAL: Update failed AND rollback failed. "
                f"Original error: {e}. Rollback error: {rollback_err}. "
                f"Manual recovery: rename '{old_exe}' back to '{current_exe}'"
            ) from e
        raise RuntimeError(f"Update failed, rolled back to previous version: {e}") from e

    if reboot:
        # 过滤 --update 参数，防止无限重启死循环
        safe_args: list[str] = [arg for arg in sys.argv[1:] if arg != "--update"]
        try:
            subprocess.Popen([current_exe] + safe_args)
        except OSError as e:
            logger.error("Failed to restart: %s", e)
        sys.exit(0)


# ==========================================
# 启动清理
# ==========================================


def cleanup_old_exe() -> None:
    """清理上次更新残留的 .old 文件。"""
    if not is_frozen():
        return
    old_exe: str = sys.executable + ".old"
    if os.path.exists(old_exe):
        try:
            os.remove(old_exe)
            logger.debug("Cleaned up old EXE: %s", old_exe)
        except OSError:
            pass  # 可能被另一个进程占用，下次再清理


# ==========================================
# 高级 API（供 main_bot.py 和 web/server.py 调用）
# ==========================================


def background_check(on_update_found: Callable[[dict[str, Any]], None] | None = None) -> None:
    """在后台线程中检查更新（不阻塞主程序启动）。

    Args:
        on_update_found: 发现新版本时的回调，传入更新信息 dict
    """
    if not is_frozen():
        return

    def _check() -> None:
        info: dict[str, Any] | None = check_for_update()
        if info and on_update_found:
            on_update_found(info)

    t = threading.Thread(target=_check, daemon=True, name="update-checker")
    t.start()


def execute_update(
    progress_cb: Callable[[int, int], None] | None = None,
    pre_reboot_cb: Callable[[], None] | None = None,
) -> str:
    """执行完整的更新流程：检查 → 下载 → 替换 → 重启。

    Args:
        progress_cb: 下载进度回调 (downloaded, total)
        pre_reboot_cb: 重启前回调（用于 Web UI 发送 "rebooting" 事件）

    Returns:
        成功时不会返回（进程退出），失败时返回错误消息

    Raises:
        RuntimeError: 更新流程中的各种错误
    """
    global _is_updating

    if not is_frozen():
        return "Update is only available in packaged EXE mode."

    if not _update_lock.acquire(blocking=False):
        return "Another update is already in progress."

    try:
        _is_updating = True

        # 1. 检查
        info: dict[str, Any] | None = check_for_update(force=True)
        if not info:
            return "Already on the latest version."

        # 2. 下载到临时目录
        temp_dir: str = tempfile.mkdtemp(prefix="fh6_update_")
        temp_exe: str = os.path.join(temp_dir, "FH6AutoBot.exe")

        if not download_update(info["download_url"], temp_exe, progress_cb):
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
            return "Download failed after trying all mirrors."

        # 3. 重启前回调（Web UI 发送 rebooting 事件）
        if pre_reboot_cb:
            pre_reboot_cb()

        # 4. 替换 + 重启
        apply_update(temp_exe, reboot=True)

        # 不会执行到这里（apply_update 会 sys.exit）
        return ""

    except PermissionError as e:
        return str(e)
    except RuntimeError as e:
        return str(e)
    finally:
        _is_updating = False
        _update_lock.release()


def get_cached_update_info() -> dict[str, Any] | None:
    """获取缓存的更新信息（供 Web UI 查询）。"""
    return _cached_update_info
