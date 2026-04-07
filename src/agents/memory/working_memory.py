"""
工作记忆 (Working Memory)

存储当前阶段的即时信息，作为传递给LLM的短期上下文窗口。
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from src.state.game_state import ChatMessage, GameEvent, GamePhase


class Observation(BaseModel):
    """
    单个观察片段
    
    这是Agent感知到的世界切片。可能是游戏事件、别人的发言、或者系统的提示。
    """
    observation_id: str
    content: str
    source_event: Optional[GameEvent] = None
    source_message: Optional[ChatMessage] = None
    phase: GamePhase
    round_number: int


class WorkingMemory:
    """
    工作记忆管理器
    
    维护Agent在**当前游戏阶段**能回想起来的最直接上下文。
    一般在阶段转换（例如白天进入夜晚）时，会被总结并归档到短期记忆/长期记忆中，然后清空。
    """

    def __init__(self) -> None:
        self.observations: list[Observation] = []
        # 最近的自我内部思考
        self.internal_thoughts: list[str] = []

    def add_observation(self, obs: Observation) -> None:
        """添加一条观察记录"""
        self.observations.append(obs)

    def add_thought(self, thought: str) -> None:
        """添加一条自我内省/推理过程"""
        self.internal_thoughts.append(thought)

    def get_recent_context(self, limit: int = 20) -> str:
        """
        获取最近的上下文，渲染为文本以供LLM读取
        """
        context_parts = []
        
        # 提取最近的观察
        recent_obs = self.observations[-limit:]
        if recent_obs:
            context_parts.append("【最近看见/听到的事情】")
            for obs in recent_obs:
                context_parts.append(f"- {obs.content}")

        # 提取最近的思考
        recent_thts = self.internal_thoughts[-5:]
        if recent_thts:
            context_parts.append("\n【你刚才的内部推理】")
            for tht in recent_thts:
                context_parts.append(f"- {tht}")
                
        return "\n".join(context_parts)

    def clear(self) -> None:
        """清空工作记忆（通常在阶段更替时调用）"""
        self.observations.clear()
        self.internal_thoughts.clear()

    @property
    def is_empty(self) -> bool:
        return len(self.observations) == 0 and len(self.internal_thoughts) == 0
