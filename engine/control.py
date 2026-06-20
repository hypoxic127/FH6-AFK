# -*- coding: utf-8 -*-
"""
engine/control.py — 协作式停止原语
==================================
集中管理「停止 bot」的跨线程信号与异常类型，供所有层（engine/macro/farm/web）共用。

为什么放在 engine 层（最底层）：
  `engine/utils.py:press_button` 是几乎所有手柄动作的唯一出口，需要在按键前检查停止标志。
  按依赖方向（web → macro → engine）它不能 import macro，因此停止原语必须下沉到 engine 层。
  本模块只依赖标准库 threading，不会引入循环导入。

设计要点：
  - `BotStoppedError` 继承 `BaseException`（而非 `Exception`）：使其能穿过热路径上大量宽泛的
    `except Exception` 而不被吞掉，干净地传播到顶层终止 bot。
  - 协作式优先：`check_stop()` 在安全点抛出，`interruptible_sleep()` 让等待可被立即唤醒；
    Web UI 的异步异常注入仅作为「线程卡在 C 调用里」时的兜底。
"""

import threading


class BotStoppedError(BaseException):
    """用户主动停止 bot 时抛出。

    刻意继承 ``BaseException`` 而非 ``Exception``，以免被业务代码里宽泛的
    ``except Exception`` 误捕导致停止信号丢失。
    """


# 全局停止事件，由 Web UI 的 stop_bot 处理器（或终端 Ctrl-C 流程）设置
_stop_event: threading.Event = threading.Event()


def request_stop() -> None:
    """设置停止标志，协作式检查点将在下一个安全点退出。"""
    _stop_event.set()


def clear_stop() -> None:
    """清除停止标志（每次启动前调用）。"""
    _stop_event.clear()


def is_stop_requested() -> bool:
    """是否已请求停止（供截图层判断：停止期间的截图失败属预期，应静默处理）。"""
    return _stop_event.is_set()


def check_stop() -> None:
    """检查停止标志，若已设置则抛出 BotStoppedError（在安全点中断）。"""
    if _stop_event.is_set():
        raise BotStoppedError("Bot stopped by user")


def interruptible_sleep(seconds: float) -> bool:
    """可被停止信号立即唤醒的 sleep。

    返回 True 表示被停止唤醒（提前返回），False 表示正常睡满 ``seconds``。
    用于替换热路径上较长的 ``time.sleep``，使协作式停止响应迅速。
    """
    return _stop_event.wait(seconds)
