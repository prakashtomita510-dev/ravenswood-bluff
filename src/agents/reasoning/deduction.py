"""
推理模块 (Reasoning & Strategy)

处理Agent对于当前局势的分析、阵营推断和策略制定。
"""

from __future__ import annotations

import logging
from typing import Optional

from src.agents.memory.social_graph import SocialGraph
from src.agents.memory.working_memory import WorkingMemory
from src.llm.base_backend import LLMBackend, Message
from src.state.game_state import GameState, PlayerState

logger = logging.getLogger(__name__)


class DeductionEngine:
    """推理引擎：驱动Agent内省与策略规划"""

    def __init__(self, backend: LLMBackend):
        self.backend = backend

    async def analyze_situation(
        self,
        game_state: GameState,
        me: PlayerState,
        working_memory: WorkingMemory,
        episodic_summary: str,
        social_graph_summary: str,
        persona_desc: str,
    ) -> str:
        """
        全盘分析当前局势，返回内省思考结果
        """
        system_prompt = self._build_system_prompt(me, persona_desc)
        
        # 组装上下文
        context = []
        context.append(f"【当前阶段】 第{game_state.round_number}轮 {game_state.phase.value}")
        context.append(f"【存活人数】 {game_state.alive_count}/{game_state.player_count}")
        context.append("\n" + episodic_summary)
        context.append("\n" + social_graph_summary)
        context.append("\n" + working_memory.get_recent_context(limit=15))
        
        context_str = "\n".join(context)
        
        user_prompt = (
            f"基于以上信息，请进行内部推理。\n"
            f"{context_str}\n\n"
            f"请思考：\n"
            f"1. 目前的局势对你的阵营（{me.team.value}）是否有利？\n"
            f"2. 谁最有可能是你的敌人？谁是可以信任的盟友？\n"
            f"3. 你的下一步策略是什么？\n\n"
            f"请用第一人称简洁地输出一段内心独白。"
        )
        
        messages = [Message(role="user", content=user_prompt)]
        
        try:
            # 推理阶段可以使用温度较高，允许发散
            resp = await self.backend.generate(system_prompt, messages, temperature=0.7)
            return resp.content or "（无法完成有效推理）"
        except Exception as e:
            logger.error(f"推理引擎异常: {e}")
            return f"（感到一阵头晕，暂时无法思考: {e}）"

    def _build_system_prompt(self, me: PlayerState, persona_desc: str) -> str:
        return (
            f"你正在玩桌游《血染钟楼》(鸦木布拉夫小镇)。\n"
            f"你的名字是: {me.name}\n"
            f"你的角色是: {me.role_id}\n"
            f"你属于: {me.team.value} 阵营\n\n"
            f"你的人格设定:\n{persona_desc}\n\n"
            f"这是你的私人思考时刻，你不需要撒谎，你应该尽全力为了 {me.team.value} 阵营的胜利而思考。"
        )
