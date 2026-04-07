"""
AI Agent 实现

通过 LLM 驱动的游戏内角色。
"""

from __future__ import annotations

import logging
from typing import Any

from src.agents.base_agent import BaseAgent
from src.agents.memory.episodic_memory import EpisodicMemory
from src.agents.memory.social_graph import SocialGraph
from src.agents.memory.working_memory import Observation, WorkingMemory
from src.llm.base_backend import LLMBackend
from src.state.game_state import GameEvent, GameState, PlayerState

logger = logging.getLogger(__name__)


class Persona:
    """Agent的人格配方"""
    def __init__(self, description: str, speaking_style: str):
        self.description = description
        self.speaking_style = speaking_style


class AIAgent(BaseAgent):
    """
    AI 智能体
    """

    def __init__(
        self,
        player_id: str,
        name: str,
        backend: LLMBackend,
        persona: Persona,
    ) -> None:
        super().__init__(player_id, name)
        
        # 依赖
        self.backend = backend
        self.persona = persona
        
        # 记忆模块
        self.working_memory = WorkingMemory()
        self.episodic_memory = EpisodicMemory()
        self.social_graph = SocialGraph(my_player_id=player_id)

    def synchronize_role(self, player_state: PlayerState) -> None:
        super().synchronize_role(player_state)
        # 初始化信任图谱，只针对他人
        # 可以在获取完整玩家列表后进行，这里不强制
        logger.debug(f"[{self.name}] 角色已同步: {self.role_id} ({self.team} 阵营)")

    async def observe_event(self, event: GameEvent, game_state: GameState) -> None:
        """接收系统广播的事件并存入工作记忆"""
        # 将事件格式化为可读的观察结果
        content = self._format_event_to_text(event, game_state)
        if not content:
            return

        obs = Observation(
            observation_id=event.event_id,
            content=content,
            source_event=event,
            phase=game_state.phase,
            round_number=game_state.round_number
        )
        self.working_memory.add_observation(obs)

        # 这里还能基于特定事件直接触发对某个人的信任度调整（简单的预置逻辑）
        # ...

    async def act(self, game_state: GameState, action_type: str, **kwargs: Any) -> dict[str, Any]:
        """决定如何行动"""
        logger.info(f"[{self.name}] 需要执行动作: {action_type}")
        
        # 这是 Agent 的核心入口，会调用 Prompt 引擎组装信息，向 LLM 请求回复
        # 具体的调用逻辑将在推理模块和对话模块中展开实现
        
        # 现阶段为了测试跑通，返回伪造/占位符数据
        if action_type == "speak":
            return {"action": "speak", "content": "我作为一个村民，觉得今天天气不错。"}
        elif action_type == "vote":
            return {"action": "vote", "decision": False}
        elif action_type == "night_action":
            return {"action": "night_action", "target": None}
            
        return {"action": action_type, "status": "not_implemented_yet"}

    async def think(self, prompt: str, game_state: GameState) -> str:
        """
        内部思考过程，不产生对外影响，仅存入工作记忆
        """
        # 简单实现，后续可以真实调用LLM做 reflect
        thought_process = f"思考结果: 针对 '{prompt}' 的总结。"
        self.working_memory.add_thought(thought_process)
        return thought_process

    def _format_event_to_text(self, event: GameEvent, game_state: GameState) -> str:
        """将事件对象渲染为自然语言描述"""
        actor = game_state.get_player(event.actor).name if event.actor else "系统"
        target = game_state.get_player(event.target).name if event.target else "某个目标"

        if event.event_type == "player_speaks":
            msg = event.payload.get("content", "")
            return f"💬 {actor} 说: '{msg}'"
        elif event.event_type == "nomination":
            return f"⚠️ {actor} 发起了对 {target} 的处决提名。"
        elif event.event_type == "vote":
            decision = "赞成" if event.payload.get("vote") else "反对"
            return f"✋ {actor} 对处决 {target} 投了 {decision}票。"
        elif event.event_type == "voting_result":
            passed = event.payload.get("passed", False)
            return f"⚖️ 对 {target} 的投票结果出炉: 票数{'足够' if passed else '不足'}将其送上处决台。"
        elif event.event_type == "player_death":
            return f"💀 {target} 已经死亡。"
            
        return f"系统事件: {event.event_type}"
