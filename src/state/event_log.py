"""
事件日志管理

管理游戏事件的记录、查询和过滤。
"""

from __future__ import annotations

from src.state.game_state import GameEvent, Visibility


class EventLog:
    """事件日志管理器 — 可变容器，用于运行时收集事件"""

    def __init__(self) -> None:
        self._events: list[GameEvent] = []

    def append(self, event: GameEvent) -> None:
        """追加一个事件"""
        self._events.append(event)

    @property
    def events(self) -> tuple[GameEvent, ...]:
        """获取所有事件的不可变副本"""
        return tuple(self._events)

    def get_public_events(self) -> list[GameEvent]:
        """获取所有公开事件"""
        return [e for e in self._events if e.visibility == Visibility.PUBLIC]

    def get_events_for_team(self, team: str) -> list[GameEvent]:
        """获取某个阵营可见的事件"""
        return [
            e for e in self._events
            if e.visibility in (Visibility.PUBLIC, Visibility.TEAM_EVIL)
            and (team == "evil" or e.visibility == Visibility.PUBLIC)
        ]

    def get_private_events(self, player_id: str) -> list[GameEvent]:
        """获取某个玩家可见的所有事件（公开 + 私人）"""
        return [
            e for e in self._events
            if e.visibility == Visibility.PUBLIC
            or (e.visibility == Visibility.PRIVATE and e.actor == player_id)
            or (e.visibility == Visibility.PRIVATE and e.target == player_id)
        ]

    def get_events_by_type(self, event_type: str) -> list[GameEvent]:
        """按事件类型过滤"""
        return [e for e in self._events if e.event_type == event_type]

    def get_events_in_round(self, round_number: int) -> list[GameEvent]:
        """获取某一轮的所有事件"""
        return [e for e in self._events if e.round_number == round_number]

    def __len__(self) -> int:
        return len(self._events)

    def __repr__(self) -> str:
        return f"EventLog(count={len(self._events)})"
