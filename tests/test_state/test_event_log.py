"""Phase 0 测试 — 事件日志"""

import pytest
from src.state.event_log import EventLog
from src.state.game_state import GameEvent, GamePhase, Visibility


def make_event(
    event_type: str = "test",
    visibility: Visibility = Visibility.PUBLIC,
    actor: str = None,
    target: str = None,
    round_number: int = 1,
) -> GameEvent:
    return GameEvent(
        event_type=event_type,
        phase=GamePhase.DAY_DISCUSSION,
        round_number=round_number,
        visibility=visibility,
        actor=actor,
        target=target,
    )


class TestEventLog:
    def test_append_and_len(self):
        log = EventLog()
        log.append(make_event())
        log.append(make_event())
        assert len(log) == 2

    def test_events_immutable_copy(self):
        log = EventLog()
        log.append(make_event())
        events = log.events
        assert isinstance(events, tuple)
        assert len(events) == 1

    def test_get_public_events(self):
        log = EventLog()
        log.append(make_event(visibility=Visibility.PUBLIC))
        log.append(make_event(visibility=Visibility.PRIVATE, actor="p1"))
        log.append(make_event(visibility=Visibility.STORYTELLER_ONLY))
        assert len(log.get_public_events()) == 1

    def test_get_private_events(self):
        log = EventLog()
        log.append(make_event(visibility=Visibility.PUBLIC))
        log.append(make_event(visibility=Visibility.PRIVATE, actor="p1"))
        log.append(make_event(visibility=Visibility.PRIVATE, actor="p2"))
        log.append(make_event(visibility=Visibility.PRIVATE, target="p1"))

        p1_events = log.get_private_events("p1")
        assert len(p1_events) == 3  # 1 public + 1 as actor + 1 as target

    def test_get_events_by_type(self):
        log = EventLog()
        log.append(make_event(event_type="death"))
        log.append(make_event(event_type="speak"))
        log.append(make_event(event_type="death"))
        assert len(log.get_events_by_type("death")) == 2

    def test_get_events_in_round(self):
        log = EventLog()
        log.append(make_event(round_number=1))
        log.append(make_event(round_number=2))
        log.append(make_event(round_number=1))
        assert len(log.get_events_in_round(1)) == 2

    def test_repr(self):
        log = EventLog()
        assert "EventLog" in repr(log)
