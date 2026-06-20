# -*- coding: utf-8 -*-
"""
tests/test_event_bus.py — 事件总线发布/订阅行为
================================================
覆盖 engine/event_bus.py：注册/发布/移除、多监听器顺序、单个监听器异常隔离、
默认时间戳注入、None 数据兜底、全局单例。
"""

from engine.event_bus import EventBus, get_bus


class TestEventBusBasics:
    def test_emit_calls_listener(self) -> None:
        bus = EventBus()
        received = []
        bus.on("log", lambda d: received.append(d))
        bus.emit("log", {"msg": "hi"})
        assert len(received) == 1 and received[0]["msg"] == "hi"

    def test_multiple_listeners_called_in_order(self) -> None:
        bus = EventBus()
        order = []
        bus.on("ev", lambda d: order.append("a"))
        bus.on("ev", lambda d: order.append("b"))
        bus.emit("ev", {})
        assert order == ["a", "b"]

    def test_off_removes_listener(self) -> None:
        bus = EventBus()
        hits = []

        def cb(d):
            hits.append(1)

        bus.on("ev", cb)
        bus.off("ev", cb)
        bus.emit("ev", {})
        assert hits == []

    def test_unknown_event_is_noop(self) -> None:
        bus = EventBus()
        # 发布无监听器的事件不应抛错
        bus.emit("nobody_listening", {"x": 1})

    def test_off_missing_listener_is_safe(self) -> None:
        bus = EventBus()
        bus.off("ev", lambda d: None)  # 移除从未注册的回调不应抛错


class TestEventBusResilience:
    def test_listener_exception_does_not_block_others(self) -> None:
        """一个监听器抛异常不应中断其它监听器（emit 内部已捕获）。"""
        bus = EventBus()
        hits = []

        def boom(d):
            raise RuntimeError("boom")

        bus.on("ev", boom)
        bus.on("ev", lambda d: hits.append("ok"))
        bus.emit("ev", {})  # 不应向外抛出
        assert hits == ["ok"]


class TestEventBusData:
    def test_emit_injects_timestamp(self) -> None:
        bus = EventBus()
        got = {}
        bus.on("ev", lambda d: got.update(d))
        bus.emit("ev", {})
        assert "timestamp" in got and isinstance(got["timestamp"], float)

    def test_emit_none_data_defaults_to_dict(self) -> None:
        bus = EventBus()
        got = []
        bus.on("ev", lambda d: got.append(d))
        bus.emit("ev")  # data=None
        assert got and isinstance(got[0], dict) and "timestamp" in got[0]


class TestEventBusSingleton:
    def test_get_bus_returns_singleton(self) -> None:
        assert get_bus() is get_bus()
