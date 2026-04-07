"""Phase 0 测试 — 事件总线"""

import pytest
import asyncio
from src.orchestrator.event_bus import EventBus
from src.state.game_state import GameEvent, GamePhase, Visibility


@pytest.fixture
def event_bus():
    return EventBus()


def make_event(event_type: str = "test_event", **kwargs) -> GameEvent:
    defaults = {
        "event_type": event_type,
        "phase": GamePhase.DAY_DISCUSSION,
        "round_number": 1,
    }
    defaults.update(kwargs)
    return GameEvent(**defaults)


class TestEventBus:
    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self, event_bus: EventBus):
        received = []

        async def handler(event: GameEvent):
            received.append(event)

        event_bus.subscribe("test_event", handler)
        event = make_event()
        await event_bus.publish(event)

        assert len(received) == 1
        assert received[0].event_type == "test_event"

    @pytest.mark.asyncio
    async def test_wildcard_subscription(self, event_bus: EventBus):
        received = []

        async def handler(event: GameEvent):
            received.append(event.event_type)

        event_bus.subscribe("*", handler)

        await event_bus.publish(make_event("event_a"))
        await event_bus.publish(make_event("event_b"))

        assert received == ["event_a", "event_b"]

    @pytest.mark.asyncio
    async def test_multiple_handlers(self, event_bus: EventBus):
        results = []

        async def handler_a(event: GameEvent):
            results.append("a")

        async def handler_b(event: GameEvent):
            results.append("b")

        event_bus.subscribe("test", handler_a)
        event_bus.subscribe("test", handler_b)
        await event_bus.publish(make_event("test"))

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_priority_ordering(self, event_bus: EventBus):
        results = []

        async def high_priority(event: GameEvent):
            results.append("high")

        async def low_priority(event: GameEvent):
            results.append("low")

        event_bus.subscribe("test", low_priority, priority=10)
        event_bus.subscribe("test", high_priority, priority=1)
        await event_bus.publish(make_event("test"))

        assert results == ["high", "low"]

    @pytest.mark.asyncio
    async def test_unsubscribe(self, event_bus: EventBus):
        received = []

        async def handler(event: GameEvent):
            received.append(event)

        event_bus.subscribe("test", handler)
        event_bus.unsubscribe("test", handler)
        await event_bus.publish(make_event("test"))

        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_event_history(self, event_bus: EventBus):
        await event_bus.publish(make_event("a"))
        await event_bus.publish(make_event("b"))
        await event_bus.publish(make_event("c"))

        assert len(event_bus.event_history) == 3

    @pytest.mark.asyncio
    async def test_handler_error_doesnt_crash(self, event_bus: EventBus):
        results = []

        async def bad_handler(event: GameEvent):
            raise ValueError("boom!")

        async def good_handler(event: GameEvent):
            results.append("ok")

        event_bus.subscribe("test", bad_handler, priority=1)
        event_bus.subscribe("test", good_handler, priority=2)

        # 不应该因为 bad_handler 的异常而中断
        await event_bus.publish(make_event("test"))
        assert results == ["ok"]

    def test_handler_count(self, event_bus: EventBus):
        async def h1(e): pass
        async def h2(e): pass

        event_bus.subscribe("a", h1)
        event_bus.subscribe("b", h2)

        assert event_bus.handler_count == 2

    def test_clear(self, event_bus: EventBus):
        async def h(e): pass
        event_bus.subscribe("test", h)
        event_bus.clear()
        assert event_bus.handler_count == 0

    def test_repr(self, event_bus: EventBus):
        assert "EventBus" in repr(event_bus)
