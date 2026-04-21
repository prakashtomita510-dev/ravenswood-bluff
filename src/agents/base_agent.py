"""
Agent 基类

定义游戏内所有参与者（AI Agent 或人类玩家扮演的代理）的统一接口规范。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from src.state.game_state import AgentActionLegalContext, AgentVisibleState, GameEvent, PlayerState, PrivatePlayerView, Team


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
        self.perceived_role_id: Optional[str] = None
        self.private_view: Optional[PrivatePlayerView] = None
        self.persona_signature: Optional[str] = None
        self.persona_profile: dict[str, Any] = {}

    @abstractmethod
    async def act(
        self,
        visible_state: AgentVisibleState,
        action_type: str,
        legal_context: AgentActionLegalContext | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        向代理请求一个动作决策

        Args:
            visible_state: 当前玩家可见的游戏状态
            action_type: 期望的动作类型，例如:
                         - "night_action": 夜晚行动选择
                         - "speak": 白天公开讨论发言
                         - "nominate": 提名阶段选择是否提名
                         - "vote": 对提名进行投票
                         - "defense_speech": 被提名后的辩解发言
            legal_context: 当前玩家的合法动作快照
            **kwargs: 额外上下文信息（如 reminder / retry_count / last_error）

        Returns:
            dict: 序列化的动作结构体。例如对于 speak, 返回 {"action": "speak", "content": "我的发言..."}
        """
        ...

    @abstractmethod
    async def observe_event(self, event: GameEvent, visible_state: AgentVisibleState) -> None:
        """
        接受系统中发生的事件，让Agent更新其内部认知状态。
        调度器会根据可见性决定是否调用特定 Agent 的此方法。

        Args:
            event: 发生的游戏事件
            visible_state: 该玩家当前可见的最新状态
        """
        ...

    @abstractmethod
    async def think(self, prompt: str, visible_state: AgentVisibleState) -> str:
        """
        强制Agent进行内部思考，更新其记忆或推理状态。(主要对AI有效)
        
        Args:
            prompt: 引导思考的提示，如 "白天结束了，总结一下大家的情报"
            visible_state: 当前玩家可见的游戏状态
        """
        ...

    async def archive_phase_memory(self, visible_state: AgentVisibleState) -> None:
        """
        在阶段切换前归档当前阶段记忆。
        默认无操作，AI Agent 可覆写。
        """
        return None

    def synchronize_role(self, player_state: PlayerState | PrivatePlayerView) -> None:
        """同步游戏赋予的私有身份信息"""
        if isinstance(player_state, PlayerState):
            player_state = PrivatePlayerView(
                player_id=player_state.player_id,
                name=player_state.name,
                perceived_role_id=player_state.perceived_role_id or player_state.fake_role or player_state.role_id,
                public_claim_role_id=player_state.public_claim_role_id,
                current_team=player_state.current_team or player_state.team,
                is_alive=player_state.is_alive,
                ghost_votes_remaining=player_state.ghost_votes_remaining,
            )

        self.private_view = player_state
        self.perceived_role_id = player_state.perceived_role_id
        self.role_id = player_state.perceived_role_id
        self.team = player_state.current_team.value

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name}({self.player_id}) - {self.role_id}>"
