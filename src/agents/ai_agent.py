"""
AI Agent 实现

通过 LLM 驱动的游戏内角色。
"""

from __future__ import annotations

import logging
import json
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
        
        # 1. 组装 Prompt
        # 在真实实现中，这里应该调用专门的 PromptEngine
        # 现在先用一个内联的简单 Prompt
        obs_text = self.working_memory.get_recent_context(10)
        
        system_prompt = f"""你是《血染钟楼》(Blood on the Clocktower) 中的一名顶尖玩家。
你的名字是 {self.name}，你的角色 ID 是 {self.role_id}，阵营是 {self.team}。
你的个性是：{self.persona.description}，表达风格是：{self.persona.speaking_style}。

当前游戏状态：
- 阶段：{game_state.phase}
- 轮次/天数：第 {game_state.round_number} 轮，第 {game_state.day_number} 天
- 你的身份：{self.role_id} ({self.team} 阵营)

【你的目标】
{"作为邪恶阵营，你要通过欺骗、混淆视听来隐藏恶魔，并在夜晚有计划地杀减好人，直到场上只剩2人。" if self.team == "evil" else "作为正义阵营，你要通过分析信息、找出潜在的恶魔并投票处决他们。"}

【近期记忆】
{obs_text}

【行动指南】
1. **角色扮演**：始终保持你的个性，不要出戏。
2. **策略性**：如果是好人，分享有价值的信息，但要提防中毒和醉酒。如果是坏人，编造合理伪装，引导好人互踩。
3. **决策严谨**：你的 JSON 必须包含 'action' 字段。
   - speak: 发言。需包含 'content' 和 'tone'。
   - nominate: 提名。需包含 'target' (player_id)。如果不想提名，target 设为 null。
   - vote: 投票。需包含 'decision' (true/false)。
   - night_action: 夜晚行动。需包含 'target' (player_id)。
   - skip_discussion: 获取足够信息后可主动请求结束白天讨论。

请仅返回如下格式的 JSON，不要有任何解释：
{{
  "action": "...",
  "content": "...", 
  "target": "...",
  "decision": true/false,
  "reasoning": "此处写下你内部的逻辑思考（不会被其他玩家看到）"
}}"""

        try:
            from src.llm.base_backend import Message
            response = await self.backend.generate(
                system_prompt=system_prompt, 
                messages=[Message(role="user", content="请根据当前局势做出你的下一个 JSON 决策。")]
            )
            response_text = response.content
            # 简单清理一下可能存在的 Markdown 标记
            clean_json = response_text.replace("```json", "").replace("```", "").strip()
            decision = json.loads(clean_json)
            
            # 记录内部思考到日志，但不广播
            if "reasoning" in decision:
                logger.info(f"[{self.name}] 内部思考: {decision['reasoning']}")
                
            return decision
        except Exception as e:
            logger.error(f"[{self.name}] LLM 调用失败: {e}")
            # 降级处理
            if action_type == "speak":
                return {"action": "speak", "content": "我没什么想说的。", "tone": "neutral"}
            elif action_type == "vote":
                return {"action": "vote", "decision": False}
            elif action_type == "nominate":
                return {"action": "nominate", "target": None}
            elif action_type == "defense_speech":
                return {"action": "speak", "content": "我是好人，请不要处决我。"}
            return {"action": action_type, "status": "fallback"}

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
