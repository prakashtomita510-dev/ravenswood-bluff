"""
工作记忆 (Working Memory)

存储当前阶段的即时信息，作为传递给LLM的短期上下文窗口。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
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


@dataclass
class MemoryTier(StrEnum):
    OBJECTIVE = "objective"
    HIGH_CONFIDENCE = "high_confidence"
    PUBLIC = "public"


@dataclass
class MemoryFact:
    """带可信度等级的长期保留事实。"""
    category: str
    summary: str
    tier: MemoryTier
    day_number: int | None = None
    round_number: int | None = None
    source: str = "memory"


class WorkingMemory:
    """
    工作记忆管理器
    
    维护Agent在**当前游戏阶段**能回想起来的最直接上下文。
    一般在阶段转换（例如白天进入夜晚）时，会被总结并归档到短期记忆/长期记忆中，然后清空。
    """

    def __init__(
        self,
        observation_limit: int = 30,
        fact_limit: int = 20,
        internal_thought_limit: int = 5,
        impression_limit: int = 5,
        storage_limit: int = 40
    ) -> None:
        self.observation_limit = observation_limit
        self.fact_limit = fact_limit
        self.internal_thought_limit = internal_thought_limit
        self.impression_limit = impression_limit
        self.storage_limit = storage_limit

        self.observations: list[Observation] = []
        # 最近的自我内部思考
        self.internal_thoughts: list[str] = []
        # 记忆蒸馏后的持久化印象 (W3-C)
        self.impressions: list[str] = []
        # 跨阶段必须保留的关键事实（主要是公开信息与公共声明）
        self.anchor_facts: list[str] = []
        # 分层可信度记忆
        self.objective_memory: list[MemoryFact] = []
        self.high_confidence_memory: list[MemoryFact] = []
        self.public_fact_memory: list[MemoryFact] = []

    def add_observation(self, obs: Observation) -> None:
        """添加一条观察记录"""
        self.observations.append(obs)

    def add_thought(self, thought: str) -> None:
        """添加一条自我内省/推理过程"""
        self.internal_thoughts.append(thought)

    def add_impression(self, impression: str) -> None:
        """添加一条持久化印象"""
        self.impressions.append(impression)

    def remember_fact(self, fact: str) -> None:
        """兼容旧接口：普通公开信息。"""
        fact = (fact or "").strip()
        if not fact:
            return
        if fact in self.anchor_facts:
            self.anchor_facts.remove(fact)
        self.anchor_facts.append(fact)
        self.anchor_facts = self.anchor_facts[-self.fact_limit:]
        self.remember_public_info("public_fact", fact)

    def _remember_memory_fact(
        self,
        tier: MemoryTier,
        category: str,
        summary: str,
        *,
        day_number: int | None = None,
        round_number: int | None = None,
        source: str = "private_info",
    ) -> None:
        summary = (summary or "").strip()
        if not summary:
            return
        item = MemoryFact(
            category=category,
            summary=summary,
            tier=tier,
            day_number=day_number,
            round_number=round_number,
            source=source,
        )
        storage = self._storage_for_tier(tier)
        storage[:] = [
            existing for existing in storage
            if not (existing.category == item.category and existing.summary == item.summary)
        ]
        storage.append(item)
        del storage[:-self.storage_limit]

    def _storage_for_tier(self, tier: MemoryTier) -> list[MemoryFact]:
        tier_value = tier.value if isinstance(tier, MemoryTier) else str(tier)
        if tier is MemoryTier.OBJECTIVE or tier_value == MemoryTier.OBJECTIVE.value:
            return self.objective_memory
        if tier is MemoryTier.HIGH_CONFIDENCE or tier_value == MemoryTier.HIGH_CONFIDENCE.value:
            return self.high_confidence_memory
        return self.public_fact_memory

    def remember_objective_info(
        self,
        category: str,
        summary: str,
        *,
        day_number: int | None = None,
        round_number: int | None = None,
        source: str = "objective",
    ) -> None:
        self._remember_memory_fact(
            MemoryTier.OBJECTIVE,
            category,
            summary,
            day_number=day_number,
            round_number=round_number,
            source=source,
        )

    def remember_private_info(
        self,
        category: str,
        summary: str,
        *,
        day_number: int | None = None,
        round_number: int | None = None,
        source: str = "private_info",
    ) -> None:
        self._remember_memory_fact(
            MemoryTier.HIGH_CONFIDENCE,
            category,
            summary,
            day_number=day_number,
            round_number=round_number,
            source=source,
        )

    def remember_public_info(
        self,
        category: str,
        summary: str,
        *,
        day_number: int | None = None,
        round_number: int | None = None,
        source: str = "public",
    ) -> None:
        self._remember_memory_fact(
            MemoryTier.PUBLIC,
            category,
            summary,
            day_number=day_number,
            round_number=round_number,
            source=source,
        )

    def get_private_memory_summaries(self, category: str | None = None) -> list[str]:
        items = self.high_confidence_memory
        if category is not None:
            items = [item for item in items if item.category == category]
        return [item.summary for item in items]

    def get_objective_memory_summaries(self, category: str | None = None) -> list[str]:
        items = self.objective_memory
        if category is not None:
            items = [item for item in items if item.category == category]
        return [item.summary for item in items]

    def get_public_memory_summaries(self, category: str | None = None) -> list[str]:
        items = self.public_fact_memory
        if category is not None:
            items = [item for item in items if item.category == category]
        return [item.summary for item in items]

    def compact(self, summary_observation: Observation) -> None:
        """
        记忆压缩：清空当前的 observations，替换为一个总结性的 observation。
        同时保留最近的 internal_thoughts 以维持思考连贯性。
        """
        self.observations = [summary_observation]
        # 思考一般不建议完全清空，保留最近的限制条数
        self.internal_thoughts = self.internal_thoughts[-self.internal_thought_limit:]

    def get_recent_context(self, limit: int | None = None) -> str:
        """
        获取最近的上下文，渲染为文本以供LLM读取
        """
        context_limit = limit or self.observation_limit
        context_parts = []
        
        # 0. 绝对可信信息层
        if self.objective_memory:
            context_parts.append("【你确认掌握的绝对客观事实】")
            for item in self.objective_memory[-self.fact_limit:]:
                marker = ""
                if item.day_number is not None or item.round_number is not None:
                    marker = f"(D{item.day_number or '-'}R{item.round_number or '-'}) "
                context_parts.append(f"- {marker}{item.summary}")
            context_parts.append("")

        # 1. 高可信私密信息层
        if self.high_confidence_memory:
            context_parts.append("【你确认掌握的高可信私密信息】")
            for item in self.high_confidence_memory[-self.fact_limit:]:
                marker = ""
                if item.day_number is not None or item.round_number is not None:
                    marker = f"(D{item.day_number or '-'}R{item.round_number or '-'}) "
                context_parts.append(f"- {marker}{item.summary}")
            context_parts.append("")

        # 2. 公开信息层
        if self.public_fact_memory:
            context_parts.append("【公开场上的普通信息】")
            for item in self.public_fact_memory[-self.fact_limit:]:
                marker = ""
                if item.day_number is not None or item.round_number is not None:
                    marker = f"(D{item.day_number or '-'}R{item.round_number or '-'}) "
                context_parts.append(f"- {marker}{item.summary}")
            context_parts.append("")

        # 3. 提取提炼后的印象 (Impressions Layer)
        if self.anchor_facts:
            context_parts.append("【你确认记住的关键事实】")
            for fact in self.anchor_facts[-self.fact_limit:]:
                context_parts.append(f"- {fact}")
            context_parts.append("")

        if self.impressions:
            context_parts.append("【此前你对场面的总体印象与画像】")
            # 只显示最近的印象
            for imp in self.impressions[-self.impression_limit:]:
                context_parts.append(f"- {imp}")
            context_parts.append("")

        # 4. 提取最近的观察
        recent_obs = self.observations[-context_limit:]
        if recent_obs:
            context_parts.append("【最近看见/听到的事情】")
            for obs in recent_obs:
                context_parts.append(f"- {obs.content}")

        # 5. 提取最近的思考
        recent_thts = self.internal_thoughts[-self.internal_thought_limit:]
        if recent_thts:
            context_parts.append("\n【你刚才的内部推理】")
            for tht in recent_thts:
                context_parts.append(f"- {tht}")
                
        return "\n".join(context_parts)

    def clear(self) -> None:
        """清空工作记忆（通常在阶段更替时调用）"""
        self.observations.clear()
        self.internal_thoughts.clear()
        self.impressions.clear()
        self.anchor_facts.clear()
        self.objective_memory.clear()
        self.high_confidence_memory.clear()
        self.public_fact_memory.clear()

    def clear_transient(self) -> None:
        """仅清空当前阶段的瞬时记忆，保留跨阶段印象。"""
        self.observations.clear()
        self.internal_thoughts.clear()

    @property
    def is_empty(self) -> bool:
        return len(self.observations) == 0 and len(self.internal_thoughts) == 0
