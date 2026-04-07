"""
事件总线 (Event Bus)

发布/订阅模式的异步事件系统。
所有游戏中发生的事件都通过事件总线进行传播，实现模块间松耦合。
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

from src.state.game_state import GameEvent

# 事件处理器类型：接收 GameEvent，无返回值
EventHandler = Callable[[GameEvent], Coroutine[Any, Any, None]]

logger = logging.getLogger(__name__)


class EventBus:
    """
    异步事件总线

    支持：
    - 按事件类型订阅 / 发布
    - 通配符订阅（"*" 订阅所有事件）
    - 异步事件处理
    - 处理器优先级
    """

    def __init__(self) -> None:
        # { event_type: [(priority, handler), ...] }
        self._handlers: dict[str, list[tuple[int, EventHandler]]] = defaultdict(list)
        self._event_history: list[GameEvent] = []

    def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
        priority: int = 0,
    ) -> None:
        """
        订阅某类事件。

        Args:
            event_type: 事件类型，"*" 表示订阅所有事件
            handler: 异步事件处理函数
            priority: 优先级，数字越小越先执行
        """
        self._handlers[event_type].append((priority, handler))
        # 按优先级排序
        self._handlers[event_type].sort(key=lambda x: x[0])

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """取消订阅"""
        self._handlers[event_type] = [
            (p, h) for p, h in self._handlers[event_type] if h != handler
        ]

    async def publish(self, event: GameEvent) -> None:
        """
        发布一个事件，按优先级顺序通知所有订阅者。

        Args:
            event: 要发布的游戏事件
        """
        self._event_history.append(event)

        # 收集匹配的处理器
        handlers: list[tuple[int, EventHandler]] = []

        # 精确匹配
        if event.event_type in self._handlers:
            handlers.extend(self._handlers[event.event_type])

        # 通配符匹配
        if "*" in self._handlers:
            handlers.extend(self._handlers["*"])

        # 按优先级排序后执行
        handlers.sort(key=lambda x: x[0])

        for _priority, handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    f"Event handler error: {handler.__name__} "
                    f"for event {event.event_type}: {e}"
                )

    async def publish_and_gather(self, event: GameEvent) -> list[Any]:
        """
        发布事件并收集所有处理器的返回值（用于需要聚合结果的场景）。
        """
        self._event_history.append(event)

        handlers: list[tuple[int, EventHandler]] = []
        if event.event_type in self._handlers:
            handlers.extend(self._handlers[event.event_type])
        if "*" in self._handlers:
            handlers.extend(self._handlers["*"])

        handlers.sort(key=lambda x: x[0])

        results = []
        for _priority, handler in handlers:
            try:
                result = await handler(event)
                results.append(result)
            except Exception as e:
                logger.error(f"Event handler error: {handler.__name__}: {e}")
                results.append(None)

        return results

    @property
    def event_history(self) -> list[GameEvent]:
        """获取事件历史"""
        return list(self._event_history)

    @property
    def handler_count(self) -> int:
        """已注册的处理器总数"""
        return sum(len(handlers) for handlers in self._handlers.values())

    def clear(self) -> None:
        """清除所有订阅和历史"""
        self._handlers.clear()
        self._event_history.clear()

    def __repr__(self) -> str:
        return (
            f"EventBus(subscriptions={len(self._handlers)}, "
            f"handlers={self.handler_count}, "
            f"events_published={len(self._event_history)})"
        )
