"""
Agent 基类

定义游戏内所有参与者（AI Agent 或人类玩家扮演的代理）的统一接口规范。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from src.state.game_state import GameEvent, GameState, PlayerState


class BaseAgent(ABC):
    """
    智能体/玩家代理基类

    系统中的所有玩家实体（不管背后是LLM还是真实人类WebSocket连接）
    都会提供给调度层一个相同的接口 `act()`。
    """

    def __init__(self, player_id: str, name: str) -> None:
        self.player_id = player_id
        self.name = name
        
        # 这些属性在游戏开始时(SETUP)会通过 update_state 被注入
        self.role_id: Optional[str] = None
        self.team: Optional[str] = None

    @abstractmethod
    async def act(self, game_state: GameState, action_type: str, **kwargs: Any) -> dict[str, Any]:
        """
        向代理请求一个动作决策

        Args:
            game_state: 当前全局游戏状态
            action_type: 期望的动作类型，例如:
                         - "night_action": 夜晚行动选择
                         - "speak": 白天公开讨论发言
                         - "nominate": 提名阶段选择是否提名
                         - "vote": 对提名进行投票
            **kwargs: 额外上下文信息

        Returns:
            dict: 序列化的动作结构体。例如对于 speak, 返回 {"action": "speak", "content": "我的发言..."}
        """
        ...

    @abstractmethod
    async def observe_event(self, event: GameEvent, game_state: GameState) -> None:
        """
        接受系统中发生的事件，让Agent更新其内部认知状态。
        调度器会根据可见性决定是否调用特定 Agent 的此方法。

        Args:
            event: 发生的游戏事件
            game_state: 最新的游戏状态
        """
        ...

    @abstractmethod
    async def think(self, prompt: str, game_state: GameState) -> str:
        """
        强制Agent进行内部思考，更新其记忆或推理状态。(主要对AI有效)
        
        Args:
            prompt: 引导思考的提示，如 "白天结束了，总结一下大家的情报"
            game_state: 当前游戏状态
        """
        ...

    def synchronize_role(self, player_state: PlayerState) -> None:
        """同步游戏赋予的角色信息"""
        self.role_id = player_state.role_id
        self.team = player_state.team.value

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name}({self.player_id}) - {self.role_id}>"
