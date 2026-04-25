"""
AI Agent 实现

通过 LLM 驱动的游戏内角色。
"""

from __future__ import annotations

import hashlib
import logging
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Optional
from src.engine.data_collector import GameDataCollector
from src.agents.base_agent import BaseAgent
from src.agents.memory.episodic_memory import EpisodicMemory, Episode
from src.agents.memory.social_graph import SocialGraph
from src.agents.memory.working_memory import Observation, WorkingMemory
from src.agents.memory.vector_memory import VectorMemory
from src.agents.persona_registry import ARCHETYPES, Archetype, get_archetype
from src.content.trouble_brewing_terms import TROUBLE_BREWING_ROLE_TERMS, get_role_description, get_role_name, get_role_persona_hint
from src.llm.base_backend import LLMBackend
from src.state.game_state import (
    AgentActionLegalContext,
    AgentVisibleState,
    ChatMessage,
    GameEvent,
    GamePhase,
    GameState,
    PlayerState,
    PrivatePlayerView,
    Team,
    Visibility,
    VisiblePlayerInfo,
)

logger = logging.getLogger(__name__)


@dataclass
class ParsedRoleStatement:
    role_id: str
    claim_type: str
    subject_player_ids: tuple[str, ...]
    source_text: str


class Persona:
    """Agent的人格配方"""
    def __init__(
        self,
        description: str,
        speaking_style: str,
        voice_anchor: str = "",
        decision_style: str = "",
        archetype: str = "logic",
    ):
        self.description = description
        self.speaking_style = speaking_style
        self.voice_anchor = voice_anchor
        self.decision_style = decision_style
        self.archetype_key = archetype


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
        player_count: int = 10,
        data_collector: Optional[GameDataCollector] = None
    ) -> None:
        super().__init__(player_id, name)
        
        # 依赖
        self.backend = backend
        self.persona = persona
        self.player_count = player_count
        self.data_collector = data_collector
        
        # 动态计算记忆限制
        # 1. 观察记录：15人局约 45 条，10人局 30 条
        self._obs_limit = max(20, int(player_count * 3))
        # 2. 事实记录：15人局约 30 条
        self._fact_limit = max(15, int(player_count * 2))
        # 3. 反思阈值：积累到多少条观察后触发一次蒸馏
        self._reflection_threshold = max(30, int(player_count * 5))
        
        # 记忆模块
        self.working_memory = WorkingMemory(
            observation_limit=self._obs_limit,
            fact_limit=self._fact_limit,
            internal_thought_limit=5,
            impression_limit=max(5, int(player_count / 2)),
            storage_limit=max(40, int(player_count * 4))
        )
        self.episodic_memory = EpisodicMemory()
        embedding_dimension = int(os.getenv("EMBEDDING_DIMENSION", "1536"))
        self.vector_memory = VectorMemory(backend=backend, dimension=embedding_dimension)
        self.social_graph = SocialGraph(
            my_player_id=player_id,
            note_limit=max(30, int(player_count * 3)),
            claim_limit=max(20, int(player_count * 2)),
            summary_note_limit=6,
            summary_claim_limit=5
        )
        self._last_retrieval_query: str = ""
        self._last_retrieval_items: list[dict[str, Any]] = []
        self._last_social_prime_signature: str = ""
        self._refresh_persona_profile()

    def synchronize_role(self, player_state: PlayerState) -> None:
        super().synchronize_role(player_state)
        # 初始化信任图谱，只针对他人
        # 可以在获取完整玩家列表后进行，这里不强制
        logger.debug(f"[{self.name}] 角色已同步: {self.role_id} ({self.team} 阵营)")
        self._refresh_persona_profile()

    def _stable_hash(self, *parts: Any) -> str:
        seed = "||".join("" if part is None else str(part) for part in parts)
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

    def _pick_stable(self, options: list[str], *parts: Any) -> str:
        if not options:
            return ""
        digest = self._stable_hash(*parts)
        index = int(digest[:8], 16) % len(options)
        return options[index]

    def _refresh_persona_profile(self) -> None:
        role_id = self.role_id or "unknown"
        role_name = get_role_name(role_id)
        role_description = get_role_description(role_id, fallback="普通玩家")
        role_hint = get_role_persona_hint(role_id, fallback="保持自然、连贯且像真人。")
        voice_anchor = self.persona.voice_anchor or self._pick_stable(
            [
                "先说结论再补理由",
                "先观察再表态",
                "喜欢轻微追问",
                "习惯用反问确认细节",
                "更偏向简短而直接",
                "会先给出保守判断",
            ],
            self.player_id,
            role_id,
            "voice_anchor",
        )
        decision_style = self.persona.decision_style or self._pick_stable(
            [
                "谨慎推进，只有在证据够强时才主动出手。",
                "在有把握前先保持试探，不轻易下最终结论。",
                "偏好稳定推进，优先选择最能解释局势的方案。",
                "如果局势模糊，会先选最不容易暴露自己的路径。",
                "倾向于快速形成判断，但不会让语气显得机械。",
                "会在行动前留一手，但仍保持像真人那样摇摆。",
            ],
            self.player_id,
            role_id,
            "decision_style",
        )
        speech_rhythm = self._pick_stable(
            [
                "短句偏多，节奏稳。",
                "喜欢先抛态度再补理由。",
                "偶尔加一点自嘲或试探。",
                "会用反问制造一点压力。",
                "语气比较克制，不会过度激动。",
                "会刻意把话说得更像当场反应。",
            ],
            self.player_id,
            role_id,
            "speech_rhythm",
        )
        risk_tolerance = self._pick_stable(
            ["保守", "均衡", "激进"],
            self.player_id,
            role_id,
            self.persona.description,
            self.persona.speaking_style,
            "risk_tolerance",
        )
        social_style = self._pick_stable(
            ["从众", "独立", "带节奏"],
            self.player_id,
            role_id,
            self.persona.description,
            self.persona.speaking_style,
            "social_style",
        )
        assertiveness = self._pick_stable(
            ["温和", "中性", "强势"],
            self.player_id,
            role_id,
            self.persona.description,
            self.persona.speaking_style,
            "assertiveness",
        )
        # 加载原型 (Archetype)
        archetype = get_archetype(self.persona.archetype_key)
        
        posture = "邪恶阵营" if self.team == "evil" else "正义阵营"
        signature = self._stable_hash(self.player_id, role_id, self.persona.description, self.persona.speaking_style)[:10]
        self.persona_signature = signature
        self.persona_profile = {
            "role_id": role_id,
            "role_name": role_name,
            "role_description": role_description,
            "role_hint": role_hint,
            "voice_anchor": voice_anchor or archetype.voice_anchor,
            "decision_style": decision_style or archetype.thinking_template,
            "speech_rhythm": speech_rhythm,
            "risk_tolerance": risk_tolerance or archetype.risk_preference,
            "social_style": social_style or archetype.social_style,
            "assertiveness": assertiveness or archetype.assertiveness,
            "posture": posture,
            "signature": signature,
            "archetype": archetype,
        }

    def _process_event_for_social_graph(self, event: GameEvent) -> None:
        """根据观察到的事件自动微调对场上其他人的信任分"""
        actor_id = event.actor
        target_id = event.target
        
        # 1. 提名事件：提名者对被提名者通常持有怀疑态度
        if event.event_type == "nomination_started" and actor_id and target_id:
            # 如果我是被提名者，我对提名者的信任度大幅下降
            if target_id == self.player_id:
                self.social_graph.update_trust(actor_id, -0.3)
            # 如果我看到别人提名别人，我对提名者的判断取决于我对被提名者的看法（暂留待以后逻辑化）
            # 当前简化处理：提名行为本身是一个强对抗信号
            
        # 2. 投票事件：观察谁在投谁
        elif event.event_type == "vote_cast" and actor_id and target_id:
            voted_yes = event.payload.get("vote", False)
            # 如果别人投了我且投的是赞成死刑，信用下降
            if target_id == self.player_id and voted_yes:
                self.social_graph.update_trust(actor_id, -0.2)
            # 如果别人投了我且投的是反对死刑，信用上升
            elif target_id == self.player_id and not voted_yes:
                self.social_graph.update_trust(actor_id, 0.15)
                
        # 3. 死亡事件：被执行死刑的人如果身份揭露（如果有的话），可以大幅逆推
        elif event.event_type == "execution_resolved":
            # 这里需要结合 visible_state 的身份变化，如果发现投错好人，则对推进者减分
            pass

    async def observe_event(self, event: GameEvent, visible_state: AgentVisibleState) -> None:
        """接收系统广播的事件并存入工作记忆"""
        if not self._is_event_visible_to_self(event):
            return
        # 将事件格式化为可读的观察结果
        content = self._format_event_to_text(event, visible_state)
        if not content:
            return

        obs = Observation(
            observation_id=event.event_id,
            content=content,
            source_event=event,
            phase=visible_state.phase,
            round_number=visible_state.round_number
        )
        self.working_memory.add_observation(obs)

        # W3-D: 基于事件自动化更新社交图谱
        self._process_event_for_social_graph(event)
        self._remember_critical_event(event, visible_state)
        await self._ingest_visible_event_to_vector_memory(event)

    async def _ingest_visible_event_to_vector_memory(self, event: GameEvent) -> None:
        """将当前玩家可见的事件摄入向量记忆。"""
        try:
            if event.event_type == "player_speaks":
                message = ChatMessage(
                    speaker=event.actor or "unknown",
                    content=event.payload.get("content", ""),
                    phase=event.phase,
                    round_number=event.round_number,
                    target_player=event.target,
                )
                await self.vector_memory.add_message(message)
                return
            await self.vector_memory.add_event(event)
        except Exception as exc:
            logger.warning("[%s] 向量记忆摄入失败: %s", self.name, exc)

    def _remember_critical_event(self, event: GameEvent, visible_state: AgentVisibleState) -> None:
        if event.event_type == "private_info_delivered" and event.target == self.player_id:
            payload = event.payload or {}
            info_type = payload.get("type", "night_info")
            title = payload.get("title") or get_role_name(self.perceived_role_id or self.role_id or "unknown")
            lines = payload.get("lines", [])
            detail = " ".join(str(line) for line in lines[:3]) if isinstance(lines, list) else ""
            remembered = f"{title}: {detail}".strip(": ")
            self.working_memory.remember_fact(remembered or f"你收到了私密信息: {info_type}")
            self._store_private_info_memory(
                info_type,
                remembered or f"你收到了私密信息: {info_type}",
                visible_state,
            )
            self._store_targeted_private_hints(info_type, payload, visible_state)

            teammates = payload.get("teammates", [])
            if teammates:
                teammates_str = ', '.join(teammates)
                self.working_memory.remember_fact(f"【绝密推演可用】已知邪恶同伴名单：{teammates_str}")
                self.working_memory.remember_objective_info(
                    "evil_teammates",
                    f"【绝密推演可用】已知邪恶同伴名单：{teammates_str}",
                    day_number=visible_state.day_number,
                    round_number=visible_state.round_number,
                    source="evil_team_info",
                )
                for teammate_name in teammates:
                    teammate = next((player for player in visible_state.players if player.name == teammate_name), None)
                    if teammate:
                        self.social_graph.init_player(teammate.player_id, teammate.name)
                        self.social_graph.add_note(teammate.player_id, "已由邪恶私密信息确认是己方队友")
                        self.social_graph.update_trust(teammate.player_id, 1.0)

            bluffs = payload.get("bluffs", [])
            if bluffs:
                bluff_names = [get_role_name(role_id) for role_id in bluffs]
                bluffs_str = ', '.join(bluff_names)
                self.working_memory.remember_fact(f"【伪装策略】适合邪恶阵营穿的衣服（bluff）：{bluffs_str}")
                self.working_memory.remember_objective_info(
                    "evil_bluffs",
                    f"【伪装策略】适合邪恶阵营穿的衣服（bluff）：{bluffs_str}",
                    day_number=visible_state.day_number,
                    round_number=visible_state.round_number,
                    source="evil_bluff_info",
                )
            return

        if event.event_type == "nomination_started":
            self.working_memory.remember_objective_info(
                "nomination",
                f"{self._player_name_from_visible_state(event.actor, visible_state)} 提名了 {self._player_name_from_visible_state(event.target, visible_state)}",
                day_number=visible_state.day_number,
                round_number=visible_state.round_number,
                source="event_log",
            )
            return

        if event.event_type == "voting_resolved":
            votes = event.payload.get("votes", 0)
            needed = event.payload.get("needed", 0)
            passed = "通过" if event.payload.get("passed") else "未通过"
            self.working_memory.remember_objective_info(
                "voting_result",
                f"对 {self._player_name_from_visible_state(event.target, visible_state)} 的投票结果：{passed}（{votes}/{needed}）",
                day_number=visible_state.day_number,
                round_number=visible_state.round_number,
                source="event_log",
            )
            return

        # [GAME-3.2] 恶魔感知自己的夜晚击杀结果（哑刀持久化到记忆层）
        if event.event_type == "night_kill" and event.actor == self.player_id:
            target_name = self._player_name_from_visible_state(event.target, visible_state)
            failed = event.payload.get("failed", False)
            reason = event.payload.get("reason", "unknown")
            redirected = event.payload.get("redirected_from")
            
            if failed:
                self.working_memory.remember_objective_info(
                    "kill_failed",
                    f"你在第 {visible_state.round_number} 轮尝试击杀 {target_name} 失败（原因: {reason}）。该目标可能受僧侣保护或为士兵。",
                    day_number=visible_state.day_number,
                    round_number=visible_state.round_number,
                    source="night_kill_result",
                )
                # 追踪失败历史，用于后续决策
                if not hasattr(self, "_kill_failure_history"):
                    self._kill_failure_history: dict[str, int] = {}
                target_id = event.target or "unknown"
                self._kill_failure_history[target_id] = self._kill_failure_history.get(target_id, 0) + 1
                count = self._kill_failure_history[target_id]
                self.working_memory.remember_objective_info(
                    "failed_kill_target",
                    f"{target_name} 是高风险刀人失败目标：已连续失败 {count} 次（原因: {reason}）。",
                    day_number=visible_state.day_number,
                    round_number=visible_state.round_number,
                    source="night_kill_result",
                )
                if count >= 2:
                    self.working_memory.remember_objective_info(
                        "kill_blacklist",
                        f"警告：{target_name} 已被连续攻击 {count} 次均失败，极大概率受到持续保护，应立即放弃该目标。",
                        day_number=visible_state.day_number,
                        round_number=visible_state.round_number,
                        source="night_kill_analysis",
                    )
            elif redirected:
                redirected_name = self._player_name_from_visible_state(redirected, visible_state)
                self.working_memory.remember_objective_info(
                    "kill_redirected",
                    f"你在第 {visible_state.round_number} 轮尝试击杀 {redirected_name}，但攻击被转移到了 {target_name}（可能是市长转位）。",
                    day_number=visible_state.day_number,
                    round_number=visible_state.round_number,
                    source="night_kill_result",
                )
            else:
                self.working_memory.remember_objective_info(
                    "kill_success",
                    f"你在第 {visible_state.round_number} 轮成功击杀了 {target_name}。",
                    day_number=visible_state.day_number,
                    round_number=visible_state.round_number,
                    source="night_kill_result",
                )
            return

        if event.event_type in {"player_death", "execution_resolved"}:
            target_name = self._player_name_from_visible_state(event.target, visible_state)
            reason = event.payload.get("reason")
            summary = f"{target_name} 死亡"
            if reason:
                summary += f"，原因：{reason}"
            self.working_memory.remember_objective_info(
                "death",
                summary,
                day_number=visible_state.day_number,
                round_number=visible_state.round_number,
                source="event_log",
            )
            
            # [Task D] 自动冻结死者记忆
            if event.target and event.target != self.player_id:
                profile = self.social_graph.get_profile(event.target)
                if profile and not profile.is_frozen:
                    # 如果此人有跳身份且没有明显的改口冲突，则冻结
                    if profile.current_self_claim and self.social_graph.claim_conflict_count(event.target) == 0:
                        summary_text = f"死者，跳身份为 {get_role_name(profile.current_self_claim)}，生前表现稳定。"
                        self.social_graph.freeze_player(event.target, summary_text)
            return

        # [GAME-3.3] 角色转移事件（Star-pass）：新恶魔继承身份与 bluffs
        if event.event_type == "role_transfer" and event.target == self.player_id:
            payload = event.payload or {}
            new_role = payload.get("new_role")
            reason = payload.get("reason", "unknown")
            bluffs = payload.get("bluffs", [])
            old_perceived = payload.get("old_perceived_role")
            
            if new_role:
                self.role_id = new_role
                self.true_role_id = new_role
                # 保持公开伪装身份不变
                if old_perceived:
                    self.perceived_role_id = old_perceived
                
                self.working_memory.remember_objective_info(
                    "role_transfer",
                    f"你的角色已从爪牙变为【小恶魔】（原因: {reason}）。你现在是恶魔，每晚需要选择一名玩家击杀。你的公开伪装身份仍然是 {get_role_name(old_perceived or self.perceived_role_id or 'unknown')}。",
                    day_number=visible_state.day_number,
                    round_number=visible_state.round_number,
                    source="role_transfer",
                )
            
            if bluffs:
                bluff_names = [get_role_name(b) for b in bluffs]
                self.working_memory.remember_objective_info(
                    "evil_bluffs",
                    f"可用的伪装角色（bluffs）: {', '.join(bluff_names)}",
                    day_number=visible_state.day_number,
                    round_number=visible_state.round_number,
                    source="role_transfer_bluffs",
                )
            
            logger.info("[%s] 角色转移完成: 新角色=%s, 伪装=%s, bluffs=%s", 
                       self.name, new_role, old_perceived, bluffs)
            return

        if event.event_type == "player_speaks" and event.actor and event.actor != self.player_id:
            actor_name = self._player_name_from_visible_state(event.actor, visible_state)
            statements = self._extract_role_statements(event.payload.get("content", ""), event.actor, visible_state)
            for statement in statements:
                if statement.claim_type == "self_claim":
                    self.social_graph.init_player(event.actor, actor_name)
                    self.social_graph.record_claim(
                        event.actor,
                        statement.role_id,
                        "self_claim",
                        source_text=statement.source_text,
                        round_number=visible_state.round_number,
                        day_number=visible_state.day_number,
                        speaker_id=event.actor,
                        speaker_name=actor_name,
                    )
                    self.social_graph.add_note(event.actor, f"公开跳身份为 {get_role_name(statement.role_id)}")
                    
                    # [Task D] 如果此人之前被冻结，现在改口了，必须解冻
                    profile = self.social_graph.get_profile(event.actor)
                    if profile and profile.is_frozen and profile.current_self_claim != statement.role_id:
                        self.social_graph.thaw_player(event.actor, f"改口跳身份: {statement.role_id}")

                    self.working_memory.remember_fact(f"{actor_name} 公开跳身份为 {get_role_name(statement.role_id)}")
                    self.working_memory.remember_public_info(
                        "role_claim",
                        f"{actor_name} 公开跳身份为 {get_role_name(statement.role_id)}",
                        day_number=visible_state.day_number,
                        round_number=visible_state.round_number,
                        source="public_speech",
                    )
                elif statement.claim_type == "denial":
                    self.social_graph.init_player(event.actor, actor_name)
                    self.social_graph.record_claim(
                        event.actor,
                        statement.role_id,
                        "denial",
                        source_text=statement.source_text,
                        round_number=visible_state.round_number,
                        day_number=visible_state.day_number,
                        speaker_id=event.actor,
                        speaker_name=actor_name,
                    )
                    self.social_graph.add_note(event.actor, f"否认自己是 {get_role_name(statement.role_id)}")
                elif statement.claim_type in {"question", "accusation", "relay"}:
                    for subject_id in statement.subject_player_ids:
                        subject_name = self._player_name_from_visible_state(subject_id, visible_state)
                        self.social_graph.init_player(subject_id, subject_name)
                        
                        # Add to claims_about_others
                        prof = self.social_graph.get_profile(event.actor)
                        if prof:
                            if subject_id not in prof.claims_about_others:
                                prof.claims_about_others[subject_id] = []
                            prof.claims_about_others[subject_id].append(
                                ClaimRecord(
                                    role_id=statement.role_id,
                                    claim_type=statement.claim_type,
                                    source_text=statement.source_text,
                                    round_number=visible_state.round_number,
                                    day_number=visible_state.day_number,
                                    speaker_id=event.actor,
                                    speaker_name=actor_name,
                                )
                            )

                        verb = "质疑像" if statement.claim_type == "question" else "怀疑是"
                        if statement.claim_type == "relay":
                            verb = "转述称其跳了"
                        self.social_graph.add_note(subject_id, f"{actor_name} {verb} {get_role_name(statement.role_id)}")

    def _store_private_info_memory(self, info_type: str, summary: str, visible_state: AgentVisibleState) -> None:
        objective_info_types = {"evil_team_info", "spy_book"}
        high_confidence_info_types = {
            "washerwoman_info",
            "librarian_info",
            "investigator_info",
            "chef_info",
            "empath_info",
            "undertaker_info",
            "fortune_teller_info",
            "ravenkeeper_info",
        }
        if info_type in objective_info_types:
            self.working_memory.remember_objective_info(
                info_type,
                summary,
                day_number=visible_state.day_number,
                round_number=visible_state.round_number,
                source="private_info",
            )
            return
        if info_type in high_confidence_info_types:
            self.working_memory.remember_private_info(
                info_type,
                summary,
                day_number=visible_state.day_number,
                round_number=visible_state.round_number,
                source="storyteller_private_info",
            )
            return
        self.working_memory.remember_private_info(
            info_type,
            summary,
            day_number=visible_state.day_number,
            round_number=visible_state.round_number,
            source="private_info",
        )

    def _extract_role_ids_from_text(self, text: str) -> list[str]:
        haystack = (text or "").lower()
        found: list[str] = []
        for role_id, term in TROUBLE_BREWING_ROLE_TERMS.items():
            zh_name = term["zh_name"].lower()
            en_name = term["en_name"].lower()
            if zh_name in haystack or en_name in haystack or role_id in haystack:
                found.append(role_id)
        return found

    def _role_team_hint(self, role_id: str) -> Team | None:
        from src.engine.roles.base_role import get_role_class

        role_cls = get_role_class(role_id)
        if not role_cls:
            return None
        try:
            return role_cls.get_definition().team
        except Exception:
            return None

    def _store_targeted_private_hints(
        self,
        info_type: str,
        payload: dict[str, Any],
        visible_state: AgentVisibleState,
    ) -> None:
        role_seen = payload.get("role_seen")
        role_name = get_role_name(role_seen) if role_seen else None
        players: list[str] = list(payload.get("players", [])) if isinstance(payload.get("players", []), list) else []

        def player_name(pid: str) -> str:
            return self._player_name_from_visible_state(pid, visible_state)

        if info_type in {"washerwoman_info", "librarian_info", "investigator_info"} and players and role_seen:
            for pid in players:
                if info_type == "investigator_info":
                    summary = f"【绝密线索】根据你收到的情报，{player_name(pid)} 可能是 {role_name}。"
                else:
                    summary = f"【内部直觉】根据目前掌握的信息，{player_name(pid)} 可能是 {role_name}。"
                self.working_memory.remember_private_info(
                    "role_candidate_hint",
                    summary,
                    day_number=visible_state.day_number,
                    round_number=visible_state.round_number,
                    source=info_type,
                )

        if info_type == "fortune_teller_info" and players and payload.get("has_demon", payload.get("result")):
            for pid in players:
                self.working_memory.remember_private_info(
                    "demon_candidate",
                    f"{player_name(pid)} 出现在你的占卜高可信结果里，至少其中一人可能是恶魔。",
                    day_number=visible_state.day_number,
                    round_number=visible_state.round_number,
                    source=info_type,
                )

        for target_key in ("player_id", "target_player", "target"):
            target_id = payload.get(target_key)
            if isinstance(target_id, str) and target_id and role_seen:
                self.working_memory.remember_private_info(
                    "revealed_role",
                    f"{player_name(target_id)} 的身份被高可信信息指出为 {role_name}。",
                    day_number=visible_state.day_number,
                    round_number=visible_state.round_number,
                    source=info_type,
                )
                break

    def _get_evil_strategic_summary(self, visible_state: AgentVisibleState) -> str:
        """为邪恶阵营提供战略分析建议。"""
        if self.team != Team.EVIL.value:
            return ""

        claims = self.social_graph.get_all_self_claims()
        monk_players = [pid for pid, role in claims.items() if role == "monk"]
        soldier_players = [pid for pid, role in claims.items() if role == "soldier"]
        mayor_players = [pid for pid, role in claims.items() if role == "mayor"]

        summary_parts = ["【邪恶阵营决策建议】"]
        
        # 1. 防御角色风险 (GAME-3.1)
        if monk_players:
            summary_parts.append(f"- **僧侣风险**: 玩家 {', '.join(monk_players)} 申明了僧侣。注意他们可能保护了核心信息位。")
        if soldier_players:
            summary_parts.append(f"- **士兵风险**: 玩家 {', '.join(soldier_players)} 申明了士兵。恶魔刀他们将无效。")
        if mayor_players:
            summary_parts.append(f"- **市长风险**: 玩家 {', '.join(mayor_players)} 申明了市长。攻击他们可能导致【杀戮转移】。")
        
        # 2. 哑刀与失败回溯分析 (GAME-3.2)
        kill_events = [e for e in visible_state.visible_event_log if e.event_type == "night_kill"]
        death_events = [e for e in visible_state.visible_event_log if e.event_type == "player_death"]
        
        if kill_events:
            failures_per_target: dict[str, int] = {}
            redirections: list[str] = []
            
            for e in kill_events:
                intended_target = e.target or "unknown"
                # 检查该次攻击后是否有对应的死亡事件
                actual_deaths = [
                    de for de in death_events 
                    if de.timestamp > e.timestamp and de.phase == e.phase and de.round_number == e.round_number
                ]
                
                target_died = any(de.target == intended_target for de in actual_deaths)
                if not target_died or e.payload.get("failed"):
                    failures_per_target[intended_target] = failures_per_target.get(intended_target, 0) + 1
                    
                    # [GAME-3.2] 市长转位分析：如果目标没死但其他人死了
                    if actual_deaths and not target_died:
                        other_dead = ", ".join([de.target for de in actual_deaths])
                        redirections.append(f"针对 {intended_target} 的攻击似乎被【转移】到了 {other_dead}")

            last_kill = kill_events[-1]
            last_target = last_kill.target
            last_failures = failures_per_target.get(last_target, 0) if last_target else 0
            is_last_failed = last_failures > 0 # 简化判断，实际应看最近一次
            
            if is_last_failed:
                target_name = self._player_name_from_visible_state(last_target, visible_state)
                if last_failures >= 2:
                    summary_parts.append(f"- **高危警报**: 你已经连续 {last_failures} 次尝试击杀 {target_name} 失败！这极大概率意味着该目标受到【隐形僧侣】的长期保护，或者是【士兵】。**请务必立即更换目标**。")
                elif redirections:
                    summary_parts.append(f"- **转位警示**: {redirections[-1]}。这高度疑似【市长】在场导致的转位，请谨慎处理。")
                else:
                    summary_parts.append(f"- **哑刀警示**: 昨晚对 {target_name} 的击杀尝试失败了。可能是僧侣保护、士兵或隐形成员。")

        # 3. [GAME-3.1] 隐性保护推断：连续平安夜分析
        night_death_counts: dict[int, int] = {}
        for de in death_events:
            if de.phase == GamePhase.NIGHT:
                night_death_counts[de.round_number] = night_death_counts.get(de.round_number, 0) + 1
        
        current_round = visible_state.round_number
        peaceful_nights = 0
        for r in range(1, current_round):
            if night_death_counts.get(r, 0) == 0:
                peaceful_nights += 1
        
        if peaceful_nights >= 2 and not monk_players:
             summary_parts.append(f"- **隐性防御推断**: 本局已出现 {peaceful_nights} 次夜晚无死亡且无人申明僧侣。场上极大概率存在【隐形僧侣】或【士兵/市长】。建议优先刀掉那些表现活跃但一直没死的“稳坐”玩家。")

        # 4. 战术建议
        if self.role_id == "imp":
            my_trust = self.social_graph.get_profile(self.player_id).trust_score if self.social_graph.get_profile(self.player_id) else 0
            if my_trust < -0.6:
                summary_parts.append("- **战术建议**: 你目前疑点极高。考虑今晚“自杀”传位给爪牙（Star-pass）以洗清嫌疑。")
        
        if self.perceived_role_id in ["fortune_teller", "empath", "undertaker"]:
            summary_parts.append(f"- **伪装同步**: 你目前的伪装身份是 {get_role_name(self.perceived_role_id)}。请确保护航此身份。")

        if len(summary_parts) <= 1:
            return ""
        return "\n".join(summary_parts)

    def _build_persona_prompt_block(self, action_type: str, visible_state: Optional[AgentVisibleState] = None) -> str:
        profile = self.persona_profile or {}
        strategy_block = ""
        if visible_state and action_type in ["night_action", "nomination_intent", "nominate"]:
            strategy_block = self._get_evil_strategic_summary(visible_state)
            if strategy_block:
                strategy_block = f"\n\n{strategy_block}\n"

        action_hints = {
            "speak": "任务：像真人一样在群聊中发言。**禁止单纯复述已知事实**（如：某人死了）。如果你是邪恶阵营，严禁自爆身份，**严禁使用‘我更信的一条线’、‘已知邪恶队友’、‘bluff’等机器人术语**。发言要口语化，直接表达观点、质疑或总结别人的看法。",
            "nominate": "你的任务是决定是否提名。如果不确定或不想提名，请果断输出 {\"action\": \"none\"} 放弃提名，不要勉强。",
            "nomination_intent": "你的任务是先判断是否提名。不要像规则机器，先想清楚再说。不确信可直接不提名。",
            "vote": "你的任务是投票。请从性格角度出发，不一定要投给可疑分最高的人；不要像算分机器一样刻板。",
            "defense_speech": "你是被提名者。请像真人一样辩解，语气要贴合你的性格。",
            "night_action": "你在夜晚执行角色能力。请选择符合角色和局势的目标，语气保持自然。",
            "death_trigger": "你刚刚因为夜晚死亡而触发角色能力。请选择合适目标并自然表达。",
        }
        return f"""【稳定人格锚点】
- 角色名: {profile.get('role_name', get_role_name(self.role_id or 'unknown'))}
- 角色说明: {profile.get('role_description', get_role_description(self.role_id or 'unknown'))}
- 个性提示: {self.persona.description}
- 说话风格: {self.persona.speaking_style}{strategy_block}
- 人格签名: {profile.get('signature', self.persona_signature or 'unknown')}
- 角色气质: {profile.get('role_hint', '保持自然、连贯且像真人。')}
- 表达锚点: {profile.get('voice_anchor', '先说结论再补理由')}
- 决策风格: {profile.get('decision_style', '保持谨慎但自然')}
- 语句节奏: {profile.get('speech_rhythm', '短句、自然、不过度模板化')}
- 风险偏好: {profile.get('risk_tolerance', '均衡')}
- 社交倾向: {profile.get('social_style', '独立')}
- 压力方式: {profile.get('assertiveness', '中性')}
- 行为约束: {profile.get('posture', '保持像真人一样思考')}
- 当前动作风格: {action_hints.get(action_type, '保持自然、像人类一样反应。')}
- 规则提醒: 不论局势如何变化，都尽量保持同一个稳定的人设，不要每个回合像不同的人。
"""

    async def _reflect(self, visible_state: AgentVisibleState) -> None:
        """
        内部反思逻辑：将当前 WorkingMemory 中的原始观察总结为“局势印象”并存回。
        这是减少上下文窗口压力、形成长期认知的核心。
        """
        if self.working_memory.is_empty:
            return

        recent_context = self.working_memory.get_recent_context(limit=self._obs_limit)
        system_prompt = f"""你是一名正在深入思考《血染钟楼》对局局势的玩家：{self.name} ({self.perceived_role_id})。
你要根据当前的近期记忆，总结出你的【局势总体印象】。

请输出一段 200 字以内的总结，包含：
1. 场上谁看起来最可疑，为什么？
2. 场上谁是你目前愿意暂时信任的盟友？
3. 目前存在的重大矛盾或未解之谜。
4. 你目前采取的公开策略（如：假装是占卜师，或者保持低调）。

请只返回总结文本，不要 JSON，不要额外说明。"""

        try:
            from src.llm.base_backend import Message
            response = await self.backend.generate(
                system_prompt=system_prompt,
                messages=[Message(role="user", content=f"这是你的近期记忆，请提炼局势印象：\n\n{recent_context}")]
            )
            impression = response.content.strip()
            if impression:
                # 存入持久化印象层
                self.working_memory.add_impression(f"记忆反思（D{visible_state.day_number}）: {impression}")
                
                # 构造一条总结性的观察片段，存入观察层并触发压缩
                summary_obs = Observation(
                    observation_id=f"reflect-{visible_state.day_number}-{visible_state.round_number}",
                    content=f"【自我反思总结】我现在的总体印象是：{impression[:100]}...",
                    phase=visible_state.phase,
                    round_number=visible_state.round_number
                )
                self.working_memory.compact(summary_obs)
                logger.info(f"[{self.name}] 完成了一次记忆反思与蒸馏。")
        except Exception as e:
            logger.error(f"[{self.name}] 记忆反思失败: {e}")

    async def act(
        self,
        visible_state: AgentVisibleState,
        action_type: str,
        legal_context: AgentActionLegalContext | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """决定如何行动"""
        logger.info(
            "[%s] 需要执行动作: %s persona=%s role=%s",
            self.name,
            action_type,
            self.persona_signature or "unknown",
            self.role_id or "unknown",
        )

        # W3-C: 检查记忆深度，必要时触发反思 (针对大局人数动态缩放)
        if len(self.working_memory.observations) > self._reflection_threshold:
            await self._reflect(visible_state)

        legal_context = legal_context or AgentActionLegalContext()
        self._prime_social_graph_from_state(visible_state)

        slayer_target = None
        if self._can_attempt_slayer_shot(visible_state, legal_context, action_type):
            slayer_target = self._select_slayer_shot_target(visible_state)
            if slayer_target:
                target_id, suspicion = slayer_target
                target_name = self._player_name_from_visible_state(target_id, visible_state)
                logger.info("[%s] 主动决定发动猎手技能: target=%s suspicion=%.2f", self.name, target_id, suspicion)
                return {
                    "action": "slayer_shot",
                    "target": target_id,
                    "reasoning": f"我是猎手，当前对 {target_name} 的恶魔怀疑度极高（{suspicion:.2f}），决定白天主动开枪。",
                }
        
        # W3-C: 语义记忆检索 (Task B)
        search_query = f"{action_type} {kwargs.get('target', '')}"
        retrieved_items = await self.vector_memory.search(search_query, top_k=5)
        self._last_retrieval_query = search_query.strip()
        self._last_retrieval_items = list(retrieved_items)
        retrieved_text = ""
        if retrieved_items:
            retrieved_text = "\n【相关的历史记忆回溯】\n" + "\n".join([f"- {it['text']}" for it in retrieved_items])

        # W3-C/A3-MEM-3: 严格按 MemoryTier 分块提取记忆
        objective_memories = self.working_memory.get_objective_memory_summaries()
        high_confidence_memories = self.working_memory.get_private_memory_summaries()
        public_memories = self.working_memory.get_public_memory_summaries()
        
        tier_text_blocks = []
        if objective_memories:
            tier_text_blocks.append("【绝对客观事实 (OBJECTIVE - 100%可信)】\n" + "\n".join([f"- {m}" for m in objective_memories]))
        if high_confidence_memories:
            tier_text_blocks.append("【高可信度线索 (HIGH_CONFIDENCE - 夜晚结果或私密信息)】\n" + "\n".join([f"- {m}" for m in high_confidence_memories]))
        if public_memories:
            # 限制公开记忆的条数避免刷屏
            tier_text_blocks.append("【公开讨论与声明 (PUBLIC - 可能存在欺骗与伪装)】\n" + "\n".join([f"- {m}" for m in public_memories[-15:]]))
        
        obs_text = self.working_memory.get_recent_context(self._obs_limit)
        tiered_memory_text = "\n\n".join(tier_text_blocks)
        episodic_text = self.episodic_memory.get_summary(max_episodes=8)
        social_text = self.social_graph.get_graph_summary()
        visible_state_text = self._build_visible_state_summary(visible_state)
        
        full_context = f"{visible_state_text}\n{obs_text}\n{social_text}\n{retrieved_text}"
        
        visible_players = ", ".join(
            f"{p.name}({p.player_id},{'alive' if p.is_alive else 'dead'})"
            for p in visible_state.players
        )
        perceived_role = self.perceived_role_id or self.role_id
        action_context = self._build_action_context(visible_state, legal_context, action_type)
        persona_block = self._build_persona_prompt_block(action_type, visible_state)

        system_prompt = f"""你是一名正在玩《血染钟楼》(Blood on the Clocktower) 的真实玩家。
你的名字是 {self.name}，你认知的角色是 {perceived_role}，阵营是 {self.team}。
你的个性是：{self.persona.description}，表达风格是：{self.persona.speaking_style}。

【核心原则：玩家优先级】
1. **你是玩家，不是 AI**：表现得像一个人在和朋友社交。会有犹豫、怀疑、幽默或偶尔的强势。
2. **社交推演**：除了规则和技能，更要关注别人的发言逻辑以及过往行为的一致性。
3. **保密与欺骗 (CRITICAL)**：
   - 如果你是邪恶阵营：**绝对不可**在公开频道（speak）中直接承认你的真实身份或泄露队友、真实技能结果。你必须伪装成一个好人。**严禁直接背诵你的私密信息或队友名单**。
   - 如果你是正义阵营：也要保护好你的关键信息，除非你认为说出来对正义方更有利。
   - 所有的【高可信度线索】和【绝对客观事实】都是你的私人底牌，**严禁**直接照抄到 content 中。你必须经过拟人化的加工。
4. **沉浸式对话**：发言要自然，像在群聊或面杀现场。禁止使用“我更信的一条线”、“根据事实记录”等生硬开场。
5. **拒绝机械复述**：不要单纯复述场上的已知公共信息（如：谁死了、谁被提名了）。这些信息每个人都知道。你应当关注的是这些信息背后的意义，或者别人没发现的疑点。
6. **长线记忆**：不要只看眼前，要结合你在“往期回忆”和“社交图谱”中记录的线索。

{persona_block}

【你的记忆与档案】
{episodic_text}

{social_text}

【你可见的局势摘要】
{visible_state_text}

当前游戏状态：
- 阶段：{visible_state.phase} (第 {visible_state.day_number} 天, 第 {visible_state.round_number} 轮)
- 你看到的身份：{perceived_role} ({self.team} 阵营)
- 当前玩家列表：{visible_players}
- 当前需要执行的动作类型：{action_type}
- 当前动作补充要求：{action_context}

【你的目标】
{"作为邪恶阵营，隐藏恶魔，混淆视听，剪除正义之士。" if self.team == "evil" else "作为正义阵营，通过逻辑与沟通找出恶魔并处决。"}

【核心分层记忆】
{tiered_memory_text}

【近期临时观察 (仅供参考上下文)】
{obs_text}

【JSON 格式规范】
请务必返回如下结构的 JSON，不要包含任何多余文字：
{{
  "action": "speak/nominate/vote/night_action/slayer_shot/skip_discussion/none",
  "content": "你的中文发言内容 (仅 speak 时需要)",
  "tone": "语气 (calm/passionate/accusatory/defensive)",
  "target": "player_id (nominate/slayer_shot 时为字符串；night_action 时若角色需多目标可为 [id1, id2] 或 'id1,id2')",
  "targets": ["player_id1", "player_id2"],
  "decision": true/false (仅 vote 时需要),
  "reasoning": "此处写下你作为一个玩家的真实心境和逻辑推理（不公开）"
}}"""

        try:
            from src.llm.base_backend import Message
            response = await self.backend.generate(
                system_prompt=system_prompt, 
                messages=[Message(role="user", content=f"请只返回适用于动作 `{action_type}` 的 JSON 决策，不要输出任何额外说明。")]
            )
            response_text = response.content
            clean_json = response_text.replace("```json", "").replace("```", "").strip()
            decision = json.loads(clean_json)
            decision = self._normalize_decision(visible_state, legal_context, action_type, decision)
            
            # 记录到数据仓库 (Task C)
            if self.data_collector:
                thought = decision.get("reasoning", "")
                self.data_collector.record_thought_trace(
                    player_id=self.player_id,
                    role_id=self.role_id,
                    phase=str(visible_state.phase),
                    round_number=visible_state.round_number,
                    thought=thought,
                    action=decision,
                    context={"retrieved_text_len": len(retrieved_text) if 'retrieved_text' in locals() else 0}
                )
                
            if "reasoning" in decision:
                logger.info(f"[{self.name}] 内部思考: {decision['reasoning']}")
            return decision
        except Exception as e:
            logger.error(f"[{self.name}] LLM 调用失败: {e}")
            return self._fallback_decision(visible_state, legal_context, action_type, reason=f"llm_error:{type(e).__name__}")

    async def think(self, prompt: str, visible_state: AgentVisibleState) -> str:
        """
        内部思考过程，不产生对外影响，仅存入工作记忆
        """
        # 简单实现，后续可以真实调用LLM做 reflect
        thought_process = f"思考结果: 针对 '{prompt}' 的总结。"
        self.working_memory.add_thought(thought_process)
        return thought_process

    async def archive_phase_memory(self, visible_state: AgentVisibleState) -> None:
        """
        在阶段切换前把当前阶段的工作记忆提炼为情节记忆。
        W3-D: 升级为逻辑摘要，而不仅是文本切片。
        """
        if self.working_memory.is_empty:
            return

        # 获取当前阶段的所有观察和思考
        current_obs = [obs.content for obs in self.working_memory.observations if obs.phase == visible_state.phase]
        current_thoughts = self.working_memory.internal_thoughts[-5:] # 取最近的思考
        
        if not current_obs and not current_thoughts:
            self.working_memory.clear_transient()
            return

        summary = ""
        # 如果信息量较多，调用 LLM 进行提炼；否则使用简单拼接
        if len(current_obs) > 3:
            try:
                from src.llm.base_backend import Message
                obs_context = "\n".join([f"- {o}" for o in current_obs])
                thought_context = "\n".join([f"- {t}" for t in current_thoughts])
                
                distill_prompt = f"""请对刚结束的阶段进行极简归纳（30字以内）。
涉及阶段：{visible_state.phase} (D{visible_state.day_number})
发生事件：
{obs_context}
内部判断：
{thought_context}
请总结核心进展和当前对谁最怀疑。"""
                
                response = await self.backend.generate(
                    system_prompt="你是一个逻辑严密的血染钟楼玩家。请提供精炼的阶段归纳。",
                    messages=[Message(role="user", content=distill_prompt)]
                )
                summary = response.content.strip() or "阶段总结完成"
            except Exception as e:
                logger.warning(f"[{self.name}] 内存归档LLM调用失败: {e}")

        # 兜底：信息量少或 LLM 失败时使用规则总结
        if not summary:
            parts = []
            if current_obs: parts.append(f"事态: {';'.join(current_obs[:2])}")
            if current_thoughts: parts.append(f"想法: {current_thoughts[-1]}")
            summary = " | ".join(parts)

        episode = Episode(
            phase=visible_state.phase,
            round_number=visible_state.round_number,
            day_number=visible_state.day_number,
            summary=summary[:280],
        )
        # [Task B] 将阶段总结存入向量记忆
        if getattr(self, "vector_memory", None):
            import asyncio
            asyncio.create_task(
                self.vector_memory.add_text(
                    f"阶段总结 ({visible_state.phase}): {summary[:280]}", 
                    {"type": "phase_summary", "phase": str(visible_state.phase), "round": visible_state.round_number}
                )
            )
        # 提取关键事件标签
        for obs in self.working_memory.observations:
            if obs.phase == visible_state.phase and obs.source_event:
                if obs.source_event.event_type not in episode.key_events:
                    episode.key_events.append(obs.source_event.event_type)
        
        self.episodic_memory.add_episode(episode)
        self.working_memory.clear_transient()
        logger.info(f"[{self.name}] 归档了阶段记忆: {visible_state.phase}")

    def build_data_snapshot_summary(self) -> dict[str, Any]:
        """为数据采集提供轻量 AI 摘要。"""
        claim_summary: dict[str, list[str]] = {}
        for player_id, profile in self.social_graph.profiles.items():
            if not profile.claim_history:
                continue
            claim_summary[player_id] = [
                self.social_graph._format_claim_record(record)
                for record in profile.claim_history[-2:]
            ]

        embedding_status: dict[str, Any] = {}
        if hasattr(self.backend, "get_embedding_status"):
            try:
                embedding_status = dict(getattr(self.backend, "get_embedding_status")())
            except Exception:
                embedding_status = {}

        vector_stats = self.vector_memory.get_stats() if hasattr(self.vector_memory, "get_stats") else {}
        last_query = vector_stats.get("last_query") or self._last_retrieval_query
        top_hits = vector_stats.get("last_hits_preview") or [item.get("text", "") for item in self._last_retrieval_items[:3]]
        hit_count = vector_stats.get("last_hit_count", len(self._last_retrieval_items))

        return {
            "working_memory_summary": {
                "objective": self.working_memory.get_objective_memory_summaries()[-3:],
                "high_confidence": self.working_memory.get_private_memory_summaries()[-3:],
                "public": self.working_memory.get_public_memory_summaries()[-3:],
                "observations": [obs.content for obs in self.working_memory.observations[-3:]],
                "impressions": self.working_memory.impressions[-3:],
            },
            "social_graph_summary": self.social_graph.get_graph_summary(),
            "claim_history_summary": claim_summary,
            "retrieval_summary": {
                "status": vector_stats.get("status", "unknown"),
                "embeddings_enabled": vector_stats.get("embeddings_enabled"),
                "disable_reason": vector_stats.get("disable_reason") or embedding_status.get("disabled_reason"),
                "last_query": last_query,
                "hit_count": hit_count,
                "top_hits": top_hits,
                "vector_stats": vector_stats,
                "embedding_status": embedding_status,
            },
        }

    def _player_name_from_visible_state(self, player_id: str | None, visible_state: AgentVisibleState) -> str:
        if not player_id:
            return "某个目标"
        if visible_state.self_view and player_id == visible_state.self_view.player_id:
            return visible_state.self_view.name
        for player in visible_state.players:
            if player.player_id == player_id:
                return player.name
        return player_id

    def _format_event_to_text(self, event: GameEvent, visible_state: AgentVisibleState) -> str:
        """将事件对象渲染为自然语言描述"""
        actor = self._player_name_from_visible_state(event.actor, visible_state) if event.actor else "系统"
        target = self._player_name_from_visible_state(event.target, visible_state) if event.target else "某个目标"

        if event.event_type == "player_speaks":
            msg = event.payload.get("content", "")
            return f"💬 {actor} 说: '{msg}'"
        elif event.event_type == "nomination_started":
            return f"⚠️ {actor} 发起了对 {target} 的处决提名。"
        elif event.event_type == "vote_cast":
            decision = "赞成" if event.payload.get("vote") else "反对"
            return f"✋ {actor} 对处决 {target} 投了 {decision}票。"
        elif event.event_type == "voting_resolved":
            passed = event.payload.get("passed", False)
            return f"⚖️ 对 {target} 的投票结果出炉: 票数{'足够' if passed else '不足'}将其送上处决台。"
        elif event.event_type in {"player_death", "execution_resolved"}:
            return f"💀 {target} 已经死亡。"
        elif event.event_type == "private_info_delivered":
            info_type = event.payload.get("type", "night_info")
            title = event.payload.get("title")
            lines = event.payload.get("lines", [])
            detail = " ".join(str(line) for line in lines[:2]) if isinstance(lines, list) else ""
            if title and detail:
                return f"🌙 你收到了私密信息 {title}: {detail}"
            if detail:
                return f"🌙 你收到了私密信息 {info_type}: {detail}"
            return f"🌙 你收到了私密信息: {info_type}"
            
        return f"系统事件: {event.event_type}"

    def _iter_role_terms(self) -> list[tuple[str, str, str]]:
        role_terms: list[tuple[str, str, str]] = []
        for role_id, term in TROUBLE_BREWING_ROLE_TERMS.items():
            role_terms.append((role_id, term["zh_name"], term["en_name"]))
        return sorted(role_terms, key=lambda item: len(item[1]), reverse=True)

    def _extract_role_statements(
        self,
        content: str,
        speaker_id: str,
        visible_state: AgentVisibleState,
    ) -> list[ParsedRoleStatement]:
        text = (content or "").strip()
        if not text:
            return []
        lowered = text.lower()
        statements: list[ParsedRoleStatement] = []

        for role_id, zh_name, en_name in self._iter_role_terms():
            if zh_name not in text and en_name.lower() not in lowered:
                continue

            # Check for relay first (e.g. "X says he is Y")
            relay_found = False
            for player in visible_state.players:
                if player.player_id == speaker_id: continue
                if player.name not in text: continue
                relay_patterns = (
                    rf"{re.escape(player.name)}.*说.*(?:跳|是).{{0,4}}{re.escape(zh_name)}",
                    rf"{re.escape(player.name)}.*自报.*{re.escape(zh_name)}"
                )
                if any(re.search(p, text) for p in relay_patterns):
                    statements.append(ParsedRoleStatement(
                        role_id=role_id, claim_type="relay", subject_player_ids=(player.player_id,), source_text=text
                    ))
                    relay_found = True
                    break
            if relay_found:
                continue

            denial_patterns = (
                f"我不是{zh_name}",
                f"我没跳{zh_name}",
                f"我没有跳{zh_name}",
                f"我什么时候说我是{zh_name}",
                f"我从来没说过我是{zh_name}",
            )
            if any(pattern in text for pattern in denial_patterns):
                statements.append(
                    ParsedRoleStatement(
                        role_id=role_id,
                        claim_type="denial",
                        subject_player_ids=(speaker_id,),
                        source_text=text,
                    )
                )
                continue

            self_claim_patterns = (
                rf"我(?:跳|报|明牌)(?:了|个)?{re.escape(zh_name)}",
                rf"我是{re.escape(zh_name)}",
                rf"\bi am {re.escape(en_name.lower())}\b",
                rf"\bi'm {re.escape(en_name.lower())}\b",
                rf"\bclaim(?:ed)? {re.escape(en_name.lower())}\b",
            )
            if any(re.search(pattern, lowered if "i am" in pattern or "claim" in pattern else text) for pattern in self_claim_patterns):
                statements.append(
                    ParsedRoleStatement(
                        role_id=role_id,
                        claim_type="self_claim",
                        subject_player_ids=(speaker_id,),
                        source_text=text,
                    )
                )
                continue

            for player in visible_state.players:
                if player.player_id == speaker_id:
                    continue
                if player.name not in text:
                    continue
                # accusation/question checks
                if re.search(rf"{re.escape(player.name)}.*(?:是不是|是).{{0,4}}{re.escape(zh_name)}", text):
                    statements.append(
                        ParsedRoleStatement(
                            role_id=role_id,
                            claim_type="question",
                            subject_player_ids=(player.player_id,),
                            source_text=text,
                        )
                    )
                    break
                if re.search(rf"{re.escape(player.name)}.*(?:像|可能是|就是).{{0,4}}{re.escape(zh_name)}", text):
                    statements.append(
                        ParsedRoleStatement(
                            role_id=role_id,
                            claim_type="accusation",
                            subject_player_ids=(player.player_id,),
                            source_text=text,
                        )
                    )
                    break

        deduped: list[ParsedRoleStatement] = []
        seen: set[tuple[str, str, tuple[str, ...]]] = set()
        for statement in statements:
            key = (statement.role_id, statement.claim_type, statement.subject_player_ids)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(statement)
        return deduped

    def _build_action_context(self, visible_state: AgentVisibleState, legal_context: AgentActionLegalContext, action_type: str) -> str:
        memory_brief = self._build_memory_signal_brief(visible_state)
        if action_type in {"nominate", "nomination_intent"}:
            legal_targets = list(legal_context.legal_nomination_targets)
            if legal_targets:
                threshold = self._nomination_threshold(visible_state)
                base = (
                    f"你可以合法提名的目标只有这些：{', '.join(legal_targets)}。"
                    f"只有当怀疑度明显高于 {threshold:.2f} 时才提名；"
                    "如果没有足够理由，请返回 action=none。"
                )
                if self._can_attempt_slayer_shot(visible_state, legal_context, action_type):
                    base += " 如果你是猎手且已经对某人形成极强恶魔判断，也可以改为返回 action=slayer_shot 并指定 target。"
                return f"{base}\n{memory_brief}" if memory_brief else base
            base = "当前没有合法提名目标，请返回 action=none。"
            return f"{base}\n{memory_brief}" if memory_brief else base
        if action_type == "vote":
            nominee = self._player_name_from_visible_state(visible_state.current_nominee, visible_state) if visible_state.current_nominee else "无"
            threshold = legal_context.votes_required
            current_yes = visible_state.yes_votes
            remaining_voters = list(legal_context.remaining_voters)

            me = visible_state.self_view
            ghost_context = ""
            if me and not me.is_alive:
                ghost_context = f"\n- **注意**：你已经死亡，仅剩 {me.ghost_votes_remaining} 票可能决定胜利，请非常慎重地使用。"

            status_context = (
                f"\n- 当前已举手人数：{current_yes} 人"
                f"\n- 处决所需总票数：{threshold} 人"
                f"\n- 尚未表态的人员名单：{', '.join(remaining_voters)}"
            )

            base = (
                f"当前投票对象是：{nominee}。"
                f"{status_context}{ghost_context}"
                "\n只有在你认为目标确认为邪恶阵营，或者你认为这一票是决定性的一票（帮助正义方翻盘或帮助邪恶方处决关键好人）时才投赞成票。"
            )
            return f"{base}\n{memory_brief}" if memory_brief else base
        if action_type == "defense_speech":
            speech_priority = self._build_speech_priority_brief(visible_state)
            base = (
                "你是被提名者，需要进行简短辩解。请返回 action=speak 和一段自然中文。"
                " 辩解时优先引用绝对客观事实与高可信私密信息；公开声明只能作为辅助，"
                "如果公开说法与高可信信息冲突，应更偏向高可信信息。"
            )
            if speech_priority:
                base = f"{base}\n{speech_priority}"
            return f"{base}\n{memory_brief}" if memory_brief else base
        if action_type in {"night_action", "death_trigger"}:
            legal_targets = list(legal_context.legal_night_targets)
            target_count = getattr(legal_context, "required_targets", 1)
            can_self = getattr(legal_context, "can_target_self", False)
            context_msg = f"优先从这些玩家里选择：{', '.join(legal_targets)}。"
            if target_count > 1:
                context_msg += f" 本次行动必须选择正好 {target_count} 个目标。"
            if can_self:
                context_msg += " 你可以选择你自己。"
            return f"{context_msg}\n{memory_brief}" if memory_brief else context_msg
        speech_priority = self._build_speech_priority_brief(visible_state)
        if self.team == "evil":
            base = (
                "作为邪恶阵营，你必须伪装身份并给出虚假推导。**绝不能**泄露你的真实身份、队友、或任何私密底牌。"
                " 发言时应当‘假装’依赖某些伪造的事实或逻辑，引导好人互踩。"
            )
        else:
            base = (
                "作为正义阵营，请自然发言。如果你没有确切信息，可以简短表达。 "
                "发言时优先依赖绝对客观事实与高可信私密信息；公开声明只作辅助参考。"
            )
        if self._can_attempt_slayer_shot(visible_state, legal_context, action_type):
            base += " 如果你是猎手且已经锁定高价值恶魔候选，也可以直接返回 action=slayer_shot 并指定 target。"
        if speech_priority:
            base = f"{base}\n{speech_priority}"
        return f"{base}\n{memory_brief}" if memory_brief else base

    def _build_memory_signal_brief(self, visible_state: AgentVisibleState) -> str:
        lines: list[str] = []
        objective = self.working_memory.get_objective_memory_summaries()
        private = self.working_memory.get_private_memory_summaries()
        public = self.working_memory.get_public_memory_summaries("role_claim")

        if objective:
            lines.append("【禁区：绝对不可直接说出的客观真相】")
            for item in objective[-2:]:
                lines.append(f"- {item}")
        if private:
            lines.append("【禁区：严禁泄露给正义阵营的高可信私密信息】")
            for item in private[-3:]:
                lines.append(f"- {item}")
        if public:
            lines.append("公开声明只能作为辅助参考：")
            for item in public[-2:]:
                lines.append(f"- {item}")

        empath_hint = self._empath_neighbor_signal_summary(visible_state)
        if empath_hint:
            lines.append(empath_hint)
        chef_hint = self._chef_signal_summary()
        if chef_hint:
            lines.append(chef_hint)
        return "\n".join(lines)

    @staticmethod
    def _profile_claimed_role_id(profile: Any) -> str | None:
        if not profile:
            return None
        return getattr(profile, "current_self_claim", getattr(profile, "claimed_role_id", None))

    def _build_speech_priority_brief(self, visible_state: AgentVisibleState) -> str:
        lines: list[str] = []
        objective = self.working_memory.get_objective_memory_summaries()
        private = self.working_memory.get_private_memory_summaries()
        public_claims = self.working_memory.get_public_memory_summaries("role_claim")

        if objective:
            lines.append("你当前最稳的客观事实：")
            for item in objective[-2:]:
                lines.append(f"- {item}")

        if private:
            lines.append("你当前最值得优先引用的高可信信息：")
            for item in private[-3:]:
                lines.append(f"- {item}")

        conflict_lines: list[str] = []
        for profile in self.social_graph.profiles.values():
            claimed_role_id = self._profile_claimed_role_id(profile)
            if not claimed_role_id:
                continue
            claim_name = get_role_name(claimed_role_id)
            for summary in self.working_memory.get_private_memory_summaries("role_candidate_hint"):
                if profile.name in summary and "可能是" in summary:
                    mentioned_roles = self._extract_role_ids_from_text(summary)
                    if mentioned_roles and claimed_role_id not in mentioned_roles:
                        conflict_lines.append(
                            f"- {profile.name} 公开跳 {claim_name}，但你的高可信信息更像在指向别的身份：{summary}"
                        )
                        break
            for summary in self.working_memory.get_private_memory_summaries("demon_candidate"):
                if profile.name in summary:
                    conflict_lines.append(
                        f"- {profile.name} 的公开说法需要谨慎对待，因为你的高可信信息把他卷入了恶魔候选：{summary}"
                    )
                    break
            for summary in self.working_memory.get_private_memory_summaries("revealed_role"):
                if profile.name in summary:
                    mentioned_roles = self._extract_role_ids_from_text(summary)
                    if mentioned_roles and claimed_role_id not in mentioned_roles:
                        conflict_lines.append(
                            f"- {profile.name} 公开跳 {claim_name}，但你的高可信结果直接揭示了另一种身份：{summary}"
                        )
                        break

        if conflict_lines:
            lines.append("公开说法与高可信信息的冲突：")
            lines.extend(conflict_lines[:3])
        elif public_claims:
            lines.append("公开跳身份只能作辅助参考：")
            for item in public_claims[-2:]:
                lines.append(f"- {item}")

        return "\n".join(lines)

    def _empath_neighbor_ids(self, visible_state: AgentVisibleState) -> tuple[str, ...]:
        me = visible_state.self_view
        if not me or me.perceived_role_id != "empath":
            return ()
        seat_order = list(visible_state.seat_order or tuple(player.player_id for player in visible_state.players))
        if me.player_id not in seat_order:
            return ()
        alive_lookup = {player.player_id: player.is_alive for player in visible_state.players}
        my_idx = seat_order.index(me.player_id)
        n = len(seat_order)
        if n <= 1:
            return ()

        def find_neighbor(step: int) -> str | None:
            idx = my_idx
            for _ in range(n - 1):
                idx = (idx + step) % n
                pid = seat_order[idx]
                if alive_lookup.get(pid, True):
                    return pid
            return None

        left = find_neighbor(-1)
        right = find_neighbor(1)
        result: list[str] = []
        for pid in (left, right):
            if pid and pid not in result:
                result.append(pid)
        return tuple(result)

    def _empath_neighbor_signal_summary(self, visible_state: AgentVisibleState) -> str:
        if not visible_state.self_view or visible_state.self_view.perceived_role_id != "empath":
            return ""
        summaries = self.working_memory.get_private_memory_summaries("empath_info")
        if not summaries:
            return ""
        latest = summaries[-1]
        neighbor_names = [self._player_name_from_visible_state(pid, visible_state) for pid in self._empath_neighbor_ids(visible_state)]
        if neighbor_names:
            return f"作为共情者，你当前活着的邻座是：{', '.join(neighbor_names)}。最近结果：{latest}"
        return f"作为共情者，你最近的结果是：{latest}"

    def _chef_signal_summary(self) -> str:
        summaries = self.working_memory.get_private_memory_summaries("chef_info")
        if not summaries:
            return ""
        return f"作为厨师，你的高可信首夜结果是：{summaries[-1]}"

    def _latest_numeric_value(self, category: str, patterns: tuple[str, ...]) -> int | None:
        summaries = self.working_memory.get_private_memory_summaries(category)
        if not summaries:
            return None
        summary = summaries[-1]
        for pattern in patterns:
            match = re.search(pattern, summary)
            if match:
                try:
                    return int(match.group(1))
                except Exception:
                    return None
        return None

    def _build_legal_action_context(self, game_state: GameState, visible_state: AgentVisibleState) -> AgentActionLegalContext:
        from src.engine.rule_engine import RuleEngine
        from src.engine.roles.base_role import get_role_class

        nomination_targets: list[str] = []
        for player in game_state.players:
            if player.player_id == self.player_id:
                continue
            can_nominate, _ = RuleEngine.can_nominate(game_state, self.player_id, player.player_id)
            if can_nominate:
                nomination_targets.append(player.player_id)

        night_targets = [
            player.player_id
            for player in game_state.get_alive_players()
            if player.player_id != self.player_id
        ]
        voters_so_far = set(game_state.votes_today.keys())
        seat_order = visible_state.seat_order or tuple(player.player_id for player in visible_state.players)
        remaining_voters = [pid for pid in seat_order if pid not in voters_so_far]
        required_targets = 1
        can_target_self = False
        player = game_state.get_player(self.player_id)
        if player:
            role_cls = get_role_class(player.true_role_id or player.role_id)
            if role_cls:
                role_instance = role_cls()
                try:
                    required_targets = max(0, int(role_instance.get_required_targets(game_state, game_state.phase) or 0))
                except Exception:
                    required_targets = 1
                try:
                    can_target_self = bool(role_instance.can_target_self())
                except Exception:
                    can_target_self = False
        return AgentActionLegalContext(
            legal_nomination_targets=tuple(nomination_targets),
            legal_night_targets=tuple(night_targets),
            votes_required=RuleEngine.votes_required(game_state),
            remaining_voters=tuple(remaining_voters),
            required_targets=required_targets,
            can_target_self=can_target_self,
        )

    def _is_event_visible_to_self(self, event: GameEvent) -> bool:
        if event.visibility == Visibility.PUBLIC:
            return True
        if event.visibility == Visibility.STORYTELLER_ONLY:
            return self.player_id in {event.actor, event.target}
        if event.visibility == Visibility.PRIVATE:
            return event.actor == self.player_id or event.target == self.player_id
        if event.visibility == Visibility.TEAM_EVIL:
            return self.team == Team.EVIL.value
        if event.visibility == Visibility.TEAM_GOOD:
            return self.team == Team.GOOD.value
        return False

    def _is_chat_visible_to_self(self, message) -> bool:
        if message.speaker == self.player_id:
            return True
        recipients = getattr(message, "recipient_ids", None)
        if not recipients:
            return True
        return self.player_id in recipients

    def _build_visible_state(self, game_state: GameState) -> AgentVisibleState:
        return AgentVisibleState(
            game_id=game_state.game_id,
            phase=game_state.phase,
            round_number=game_state.round_number,
            day_number=game_state.day_number,
            self_view=self.private_view if isinstance(self.private_view, PrivatePlayerView) else None,
            players=tuple(
                VisiblePlayerInfo(
                    player_id=player.player_id,
                    name=player.name,
                    is_alive=player.is_alive,
                )
                for player in game_state.players
            ),
            current_nominee=game_state.current_nominee,
            current_nominator=game_state.current_nominator,
            seat_order=game_state.seat_order or tuple(player.player_id for player in game_state.players),
            nominations_today=game_state.nominations_today,
            nominees_today=game_state.nominees_today,
            yes_votes=sum(1 for vote in game_state.votes_today.values() if vote is True),
            voted_player_ids=tuple(game_state.votes_today.keys()),
            public_chat_history=tuple(
                message for message in game_state.chat_history if self._is_chat_visible_to_self(message)
            ),
            visible_event_log=tuple(
                event for event in game_state.event_log if self._is_event_visible_to_self(event)
            ),
        )

    def _build_visible_state_summary(self, visible_state: AgentVisibleState) -> str:
        lines = [
            f"- 公开阶段：{visible_state.phase}，第 {visible_state.day_number} 天，第 {visible_state.round_number} 轮",
            f"- 存活人数：{sum(1 for p in visible_state.players if p.is_alive)}/{len(visible_state.players)}",
        ]
        if visible_state.self_view:
            lines.append(
                f"- 你的认知身份：{visible_state.self_view.perceived_role_id} / {visible_state.self_view.current_team.value} 阵营"
            )
        if visible_state.current_nominator or visible_state.current_nominee:
            lines.append(
                f"- 当前提名链：{visible_state.current_nominator or '无'} -> {visible_state.current_nominee or '无'}"
            )
        if visible_state.nominees_today:
            nominees = ", ".join(visible_state.nominees_today)
            lines.append(f"- 今日被提名过的玩家：{nominees}")
        if visible_state.nominations_today:
            nominators = ", ".join(visible_state.nominations_today)
            lines.append(f"- 今日已提名过的玩家：{nominators}")
        if visible_state.yes_votes:
            lines.append(f"- 今日已投赞成票数：{visible_state.yes_votes}")
        return "\n".join(lines)

    def build_evil_night_coordination_message(
        self,
        action: dict[str, Any],
        visible_state: AgentVisibleState,
        legal_context: AgentActionLegalContext | None = None,
    ) -> str:
        if self.team != Team.EVIL.value:
            return ""
        if visible_state.phase not in {GamePhase.FIRST_NIGHT, GamePhase.NIGHT}:
            return ""

        action_name = action.get("action")
        target_id = action.get("target")
        if action_name != "night_action" or not isinstance(target_id, str):
            return ""

        role_id = self.perceived_role_id or self.role_id
        target_name = self._player_name_from_visible_state(target_id, visible_state)

        if role_id == "imp":
            score = self._target_signal_score(target_id, visible_state)
            return f"我今晚准备刀 {target_name}，这条线当前可疑度最高（{score:.2f}），白天可以顺着这条继续施压。"

        if role_id == "poisoner":
            priority = self._poisoner_priority_for_target(target_id, visible_state)
            return f"我今晚准备毒 {target_name}，这人更像关键信息位（优先级 {priority:.2f}），白天看他的信息表现。"

        if role_id in {"scarlet_woman", "spy", "baron"}:
            return f"我今晚会继续盯 {target_name} 这条线，白天如果他跳身份或带节奏，我会顺着配合。"

        return ""

    def _visible_alive_count(self, visible_state: AgentVisibleState) -> int:
        return sum(1 for player in visible_state.players if player.is_alive)

    def _sync_social_graph(self, game_state: GameState) -> None:
        for player in game_state.players:
            self.social_graph.init_player(player.player_id, player.name)

    def _prime_social_graph_from_state(self, visible_state: AgentVisibleState) -> None:
        visible_messages = list(visible_state.public_chat_history)
        state_signature = self._stable_hash(
            visible_state.day_number,
            visible_state.round_number,
            len(visible_messages),
            len(visible_state.visible_event_log),
        )
        if state_signature == self._last_social_prime_signature:
            return

        self._last_social_prime_signature = state_signature
        for player in visible_state.players:
            self.social_graph.init_player(player.player_id, player.name)

        suspicion_keywords = ("怀疑", "可疑", "怪", "假", "骗", "不对", "危险")
        trust_keywords = ("信任", "支持", "同意", "靠谱", "好人", "合理")
        # W3-C: 获取人格原型以调整信任度变化速率
        profile_p = self.persona_profile or {}
        archetype = profile_p.get("archetype")
        decay_multi = archetype.trust_decay_rate if isinstance(archetype, Archetype) else 1.0
        growth_multi = archetype.trust_growth_rate if isinstance(archetype, Archetype) else 1.0

        for message in visible_messages[-10:]:
            content = message.content.lower()
            for player in visible_state.players:
                if player.player_id == self.player_id:
                    continue
                player_name = player.name.lower()
                if player_name not in content:
                    continue
                profile = self.social_graph.get_profile(player.player_id)
                if not profile:
                    continue
                if any(keyword in content for keyword in suspicion_keywords):
                    # 怀疑信号增强
                    profile.trust_score = max(-1.0, profile.trust_score - (0.18 * decay_multi))
                    profile.notes.append(f"聊天里出现对 {player.name} 的怀疑信号")
                if any(keyword in content for keyword in trust_keywords):
                    # 信任信号增强
                    profile.trust_score = min(1.0, profile.trust_score + (0.10 * growth_multi))
                    profile.notes.append(f"聊天里出现对 {player.name} 的信任信号")

    def _recent_context_texts(self, visible_state: AgentVisibleState, limit: int = 12) -> list[str]:
        texts: list[str] = []
        for obs in self.working_memory.observations[-limit:]:
            if obs.content:
                texts.append(obs.content)
        for message in visible_state.public_chat_history[-limit:]:
            speaker = next((player for player in visible_state.players if player.player_id == message.speaker), None)
            speaker_name = speaker.name if speaker else message.speaker
            target_name = ""
            if message.target_player:
                target_player = next((player for player in visible_state.players if player.player_id == message.target_player), None)
                target_name = f" -> {target_player.name}" if target_player else f" -> {message.target_player}"
            texts.append(f"{speaker_name}{target_name}: {message.content}")
        for event in visible_state.visible_event_log[-limit:]:
            if event.event_type in {"player_speaks", "nomination_started", "vote_cast", "voting_resolved", "execution_resolved", "player_death", "private_info_delivered"}:
                texts.append(self._format_event_to_text(event, visible_state))
        return texts

    def _count_mentions(self, texts: list[str], keyword: str) -> int:
        if not keyword:
            return 0
        lowered = keyword.lower()
        count = 0
        for text in texts:
            haystack = text.lower()
            if lowered in haystack:
                count += haystack.count(lowered)
        return count

    def _persona_modifier(self, key: str, mapping: dict[str, float], default: float = 0.0) -> float:
        profile = self.persona_profile or {}
        return mapping.get(str(profile.get(key, "")), default)

    def _nomination_threshold(self, visible_state: AgentVisibleState) -> float:
        threshold = 0.60
        # W3-C: 引入人格原型偏置
        profile = self.persona_profile or {}
        archetype = profile.get("archetype")
        if isinstance(archetype, Archetype):
            threshold += archetype.nomination_threshold_offset

        alive_count = self._visible_alive_count(visible_state)
        if alive_count <= 5:
            threshold -= 0.03
        elif alive_count >= 8:
            threshold += 0.02

        threshold -= min(0.08, max(0, visible_state.day_number - 1) * 0.02)
        threshold += self._persona_modifier("risk_tolerance", {"保守": 0.08, "均衡": 0.02, "激进": -0.05})
        threshold += self._persona_modifier("social_style", {"从众": 0.03, "独立": 0.0, "带节奏": -0.04})
        threshold += self._persona_modifier("assertiveness", {"温和": 0.04, "中性": 0.0, "强势": -0.04})
        if self.team == "evil":
            threshold -= 0.02
        return max(0.40, min(0.85, threshold))

    def _nomination_margin(self) -> float:
        return max(
            0.03,
            min(
                0.10,
                0.05
                + self._persona_modifier("risk_tolerance", {"保守": 0.03, "均衡": 0.01, "激进": -0.01})
                + self._persona_modifier("assertiveness", {"温和": 0.02, "中性": 0.0, "强势": -0.02}),
            ),
        )

    def _vote_threshold(self, visible_state: AgentVisibleState) -> float:
        threshold = 0.54
        # W3-C/D: 引入人格原型偏置
        profile = self.persona_profile or {}
        archetype = profile.get("archetype")
        if isinstance(archetype, Archetype):
            threshold += archetype.vote_threshold_offset

        alive_count = self._visible_alive_count(visible_state)
        if alive_count <= 5:
            threshold -= 0.02
        elif alive_count >= 8:
            threshold += 0.02

        # W3-D: 亡魂投票保护逻辑 (Ghost Vote Protection)
        me = visible_state.self_view
        if me and not me.is_alive:
            # 死亡玩家如果只有一票，门槛大幅提高，倾向于保留至最后
            if me.ghost_votes_remaining <= 1:
                threshold += 0.15
            else:
                threshold += 0.05

        threshold -= min(0.05, max(0, visible_state.day_number - 1) * 0.015)
        threshold += self._persona_modifier("risk_tolerance", {"保守": 0.04, "均衡": 0.01, "激进": -0.04})
        threshold += self._persona_modifier("social_style", {"从众": 0.02, "独立": 0.0, "带节奏": -0.03})
        threshold += self._persona_modifier("assertiveness", {"温和": 0.03, "中性": 0.0, "强势": -0.03})
        if self.team == "evil":
            threshold -= 0.01
        return max(0.20, min(0.95, threshold))

    def _target_signal_score(self, target_id: str, visible_state: AgentVisibleState) -> float:
        if not target_id or target_id == self.player_id:
            return 0.0

        target = next((player for player in visible_state.players if player.player_id == target_id), None)
        if not target:
            return 0.0

        texts = self._recent_context_texts(visible_state)
        mention_hits = self._count_mentions(texts, target.name)
        score = 0.16 + min(0.24, mention_hits * 0.06)

        if target_id in visible_state.nominees_today:
            score += 0.12
        if target_id == visible_state.current_nominee:
            score += 0.06
        if visible_state.current_nominator and visible_state.current_nominator == target_id:
            score += 0.03

        profile = self.social_graph.get_profile(target_id)
        if profile:
            if profile.trust_score < 0:
                score += min(0.20, abs(profile.trust_score) * 0.25)
            elif profile.trust_score > 0:
                score -= min(0.12, profile.trust_score * 0.12)
            if profile.notes:
                score += min(0.08, len(profile.notes) * 0.02)
            claim_signals = self.social_graph.claim_signal_summary(target_id)
            if claim_signals["conflicts"]:
                score += min(0.20, claim_signals["conflicts"] * 0.10)
            if claim_signals["denial"] and claim_signals["self_claim"]:
                score += min(0.08, claim_signals["denial"] * 0.04)

        confirmed_teammates = "\n".join(
            self.working_memory.get_objective_memory_summaries("evil_teammates")
            + self.working_memory.get_private_memory_summaries("evil_teammates")
        )
        if confirmed_teammates and target.name in confirmed_teammates:
            if self.team == Team.EVIL.value:
                score = max(0.0, score - 0.35)
            else:
                score += 0.05

        high_confidence_signals = [
            ("fortune_teller_info", 0.16, ("恶魔", "邪恶", "可疑", "至少一人可能", "之一可能")),
            ("investigator_info", 0.16, ("爪牙", "邪恶", "可疑")),
            ("empath_info", 0.08, ("邪恶邻座", "邪恶", "有", "2")),
            ("chef_info", 0.06, ("邪恶相邻", "邪恶", "有", "2")),
        ]
        for category, weight, keywords in high_confidence_signals:
            for summary in self.working_memory.get_private_memory_summaries(category):
                if target.name in summary and any(keyword in summary for keyword in keywords):
                    score += weight
                    break

        targeted_private_summaries = [
            *self.working_memory.get_private_memory_summaries("role_candidate_hint"),
            *self.working_memory.get_private_memory_summaries("demon_candidate"),
            *self.working_memory.get_private_memory_summaries("revealed_role"),
        ]
        claimed_role_id = self._profile_claimed_role_id(profile)
        for summary in targeted_private_summaries:
            if target.name not in summary:
                continue
            mentioned_roles = self._extract_role_ids_from_text(summary)
            mentioned_teams = {self._role_team_hint(role_id) for role_id in mentioned_roles if self._role_team_hint(role_id)}

            if "可能是" in summary and "恶魔" in summary:
                score += 0.14
            elif "可能是" in summary and mentioned_teams == {Team.EVIL}:
                score += 0.14
            elif "可能是" in summary and mentioned_teams and mentioned_teams <= {Team.GOOD}:
                score -= 0.06
            elif "身份被高可信信息指出为" in summary and mentioned_roles:
                if any(self._role_team_hint(role_id) == Team.EVIL for role_id in mentioned_roles):
                    score += 0.18
                elif all(self._role_team_hint(role_id) == Team.GOOD for role_id in mentioned_roles):
                    score -= 0.10

            if claimed_role_id and mentioned_roles:
                if claimed_role_id in mentioned_roles:
                    score -= 0.12
                else:
                    score += 0.07

        empath_count = self._latest_numeric_value("empath_info", (r"邪恶玩家数量：(\d+)",))
        if empath_count is not None:
            neighbor_ids = set(self._empath_neighbor_ids(visible_state))
            if target_id in neighbor_ids:
                if empath_count == 0:
                    score -= 0.12
                elif empath_count == 1:
                    score += 0.04
                elif empath_count >= 2:
                    score += 0.12

        recent_texts = texts[-8:]
        if any(target.name in text and "可疑" in text for text in recent_texts):
            score += 0.08
        if any(target.name in text and "怀疑" in text for text in recent_texts):
            score += 0.05
        if any(target.name in text and "信任" in text for text in recent_texts):
            score -= 0.06
        if self.persona_profile.get("social_style") == "从众" and mention_hits > 0:
            score += 0.03

        return max(0.0, min(1.0, score))

    def _select_nomination_target(self, visible_state: AgentVisibleState, legal_context: AgentActionLegalContext, intent_mode: bool = False) -> tuple[str, float, float] | None:
        legal_targets = list(legal_context.legal_nomination_targets)
        if not legal_targets:
            return None

        scored_targets = sorted(
            ((self._target_signal_score(target_id, visible_state), target_id) for target_id in legal_targets),
            key=lambda item: (-item[0], item[1]),
        )
        best_score, best_target = scored_targets[0]
        runner_up_score = scored_targets[1][0] if len(scored_targets) > 1 else 0.0
        threshold = self._nomination_threshold(visible_state)
        if intent_mode:
            threshold = max(0.25, threshold - 0.30)
            margin = max(0.01, self._nomination_margin() - 0.03)
        else:
            margin = self._nomination_margin()
        if best_score < threshold:
            return None
        if len(scored_targets) > 1 and (best_score - runner_up_score) < margin:
            return None
        return best_target, best_score, threshold

    def _nomination_candidate_band(
        self,
        legal_targets: list[str],
        visible_state: AgentVisibleState,
        tolerance: float = 0.04,
    ) -> tuple[list[str], float]:
        if not legal_targets:
            return [], 0.0
        scored_targets = [
            (self._target_signal_score(target_id, visible_state), target_id)
            for target_id in legal_targets
        ]
        best_score = max(score for score, _ in scored_targets)
        band = sorted(
            [
                target_id
                for score, target_id in scored_targets
                if (best_score - score) <= tolerance
            ]
        )
        return band, best_score

    def _choose_nomination_target_from_band(
        self,
        legal_targets: list[str],
        visible_state: AgentVisibleState,
        action_type: str,
        salt: str,
        tolerance: float = 0.04,
    ) -> tuple[str | None, float]:
        candidate_band, best_score = self._nomination_candidate_band(
            legal_targets,
            visible_state,
            tolerance=tolerance,
        )
        if not candidate_band:
            return None, 0.0
        if len(candidate_band) == 1:
            return candidate_band[0], best_score
        target = self._stable_choice(
            candidate_band,
            visible_state.round_number,
            visible_state.day_number,
            action_type,
            salt,
        )
        return target, best_score

    def _select_night_targets(
        self,
        visible_state: AgentVisibleState,
        legal_context: AgentActionLegalContext,
    ) -> list[str]:
        required_targets = max(1, int(getattr(legal_context, "required_targets", 1) or 1))
        legal_targets = list(legal_context.legal_night_targets)
        if getattr(legal_context, "can_target_self", False) and self.player_id not in legal_targets:
            legal_targets.append(self.player_id)

        ordered_targets: list[str] = []
        seen: set[str] = set()
        for candidate in legal_targets:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            ordered_targets.append(candidate)

        if len(ordered_targets) < required_targets:
            return []

        if required_targets == 1 and (self.perceived_role_id or self.role_id) == "poisoner":
            poisoner_order = self._rank_poisoner_targets(ordered_targets, visible_state)
            if poisoner_order:
                return [poisoner_order[0]]

        scored_targets = sorted(
            [
                (
                    self._target_signal_score(target_id, visible_state),
                    target_id,
                )
                for target_id in ordered_targets
            ],
            key=lambda item: (-item[0], item[1]),
        )

        selected: list[str] = []
        for _, target_id in scored_targets:
            if target_id in selected:
                continue
            selected.append(target_id)
            if len(selected) >= required_targets:
                break

        if len(selected) < required_targets:
            return []
        return selected[:required_targets]

    def _known_evil_teammate_ids(self, visible_state: AgentVisibleState) -> set[str]:
        summaries = self.working_memory.get_objective_memory_summaries("evil_teammates")
        teammate_ids: set[str] = set()
        for player in visible_state.players:
            if player.player_id == self.player_id:
                continue
            if any(player.name in summary for summary in summaries):
                teammate_ids.add(player.player_id)
        return teammate_ids

    def _poisoner_priority_for_target(self, target_id: str, visible_state: AgentVisibleState) -> float:
        teammate_ids = self._known_evil_teammate_ids(visible_state)
        if target_id in teammate_ids:
            return -1.0

        profile = self.social_graph.get_profile(target_id)
        claim_role_id = self._profile_claimed_role_id(profile)
        info_role_weights = {
            "fortune_teller": 0.48,
            "undertaker": 0.42,
            "empath": 0.40,
            "monk": 0.34,
            "investigator": 0.32,
            "washerwoman": 0.30,
            "librarian": 0.30,
            "chef": 0.26,
        }
        score = 0.0
        if claim_role_id:
            score += info_role_weights.get(claim_role_id, 0.0)

        target_name = self._player_name_from_visible_state(target_id, visible_state)
        for summary in self.working_memory.get_private_memory_summaries("revealed_role"):
            if target_name in summary:
                role_ids = self._extract_role_ids_from_text(summary)
                for role_id in role_ids:
                    score += info_role_weights.get(role_id, 0.0) * 0.9

        for summary in self.working_memory.get_private_memory_summaries("role_candidate_hint"):
            if target_name in summary:
                role_ids = self._extract_role_ids_from_text(summary)
                for role_id in role_ids:
                    score += info_role_weights.get(role_id, 0.0) * 0.75

        if claim_role_id in {"mayor", "virgin"}:
            score += 0.08

        score += max(0.0, min(0.15, self._target_signal_score(target_id, visible_state) * 0.2))
        return score

    def _rank_poisoner_targets(self, ordered_targets: list[str], visible_state: AgentVisibleState) -> list[str]:
        ranked = sorted(
            (
                (self._poisoner_priority_for_target(target_id, visible_state), target_id)
                for target_id in ordered_targets
            ),
            key=lambda item: (-item[0], item[1]),
        )
        viable = [target_id for score, target_id in ranked if score >= 0]
        return viable or [target_id for _, target_id in ranked]

    def _coerce_target_values(self, raw_target: Any) -> list[str]:
        """把 LLM/脚本返回的目标字段递归拍平为字符串列表。"""
        flattened: list[str] = []

        def visit(value: Any) -> None:
            if value is None:
                return
            if isinstance(value, str):
                for piece in value.split(","):
                    piece = piece.strip()
                    if piece:
                        flattened.append(piece)
                return
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    visit(item)
                return
            text = str(value).strip()
            if text:
                flattened.append(text)

        visit(raw_target)
        return flattened

    def _select_vote_decision(self, visible_state: AgentVisibleState, legal_context: AgentActionLegalContext, model_vote: bool | None = None) -> tuple[bool, float, float]:
        nominee_id = visible_state.current_nominee
        threshold = self._vote_threshold(visible_state)
        if not nominee_id:
            return False, 0.0, threshold

        suspicion = self._target_signal_score(nominee_id, visible_state)
        
        # W3-D: 群体压力与势头感知 (Group Momentum)
        req_votes = legal_context.votes_required
        current_yes = visible_state.yes_votes
        
        social_style = self.persona_profile.get("social_style", "独立")
        if social_style == "从众":
            # 如果已经有很多票了，跟票意愿增加（门槛降低）
            if current_yes >= req_votes / 2:
                threshold -= 0.05
        elif social_style == "带节奏":
            # 如果票数还很少，且我是前序位，可能想带节奏，门槛降低
            if current_yes < 2:
                threshold -= 0.03
                
        # 决定性一票检测 (Deciding Vote Detection)
        # 如果加上我刚好能处决，门槛微降
        if current_yes == req_votes - 1:
            threshold -= 0.02

        margin = 0.06
        if suspicion >= threshold + margin:
            return True, suspicion, threshold
        if suspicion <= threshold - margin:
            return False, suspicion, threshold
        if model_vote is not None:
            return bool(model_vote), suspicion, threshold
            
        # 兜底：基于人格偏好稳定选择
        return self._persona_vote_bias(visible_state), suspicion, threshold

    def _can_attempt_slayer_shot(
        self,
        visible_state: AgentVisibleState,
        legal_context: AgentActionLegalContext,
        action_type: str,
    ) -> bool:
        me = visible_state.self_view
        perceived_role = (me.perceived_role_id if me else None) or self.perceived_role_id or self.role_id
        if perceived_role != "slayer":
            return False
        if not legal_context.can_slayer_shot:
            return False
        return action_type in {"speak", "nomination_intent"}

    def _select_slayer_shot_target(self, visible_state: AgentVisibleState) -> tuple[str, float] | None:
        candidates = [
            player.player_id
            for player in visible_state.players
            if player.player_id != self.player_id and player.is_alive
        ]
        if not candidates:
            return None

        scored = sorted(
            ((self._target_signal_score(player_id, visible_state), player_id) for player_id in candidates),
            key=lambda item: (-item[0], item[1]),
        )
        best_score, best_target = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0.0
        score_gap = best_score - second_score
        target_name = self._player_name_from_visible_state(best_target, visible_state)

        has_hard_evidence = any(
            target_name in summary
            for category in ("revealed_role", "demon_candidate")
            for summary in self.working_memory.get_private_memory_summaries(category)
        )

        if has_hard_evidence and best_score >= 0.35:
            return best_target, best_score
        if best_score >= 0.74 and score_gap >= 0.10:
            return best_target, best_score
        return None

    def _reasoning_evidence_candidates(self, target_id: str | None, visible_state: AgentVisibleState) -> list[str]:
        if not target_id:
            return []

        target = next((player for player in visible_state.players if player.player_id == target_id), None)
        if not target:
            return []

        target_name = target.name
        profile = self.social_graph.get_profile(target_id)
        claim_signals = self.social_graph.claim_signal_summary(target_id)
        candidates: list[str] = []

        objective_candidates = [
            *self.working_memory.get_objective_memory_summaries("evil_teammates"),
            *self.working_memory.get_objective_memory_summaries("evil_bluffs"),
        ]
        for summary in objective_candidates:
            if target_name in summary:
                candidates.append(f"客观信息：{summary}")

        targeted_private_summaries = [
            *self.working_memory.get_private_memory_summaries("revealed_role"),
            *self.working_memory.get_private_memory_summaries("demon_candidate"),
            *self.working_memory.get_private_memory_summaries("role_candidate_hint"),
        ]
        claimed_role_id = self._profile_claimed_role_id(profile)
        for summary in targeted_private_summaries:
            if target_name in summary:
                candidates.append(f"高可信信息：{summary}")
                mentioned_roles = self._extract_role_ids_from_text(summary)
                if claimed_role_id and mentioned_roles and claimed_role_id not in mentioned_roles:
                    candidates.append(f"高可信信息：{target_name} 的公开自报 {claimed_role_id} 与这条线索冲突")

        if claim_signals["conflicts"] or (claim_signals["self_claim"] and claim_signals["denial"]):
            candidates.append(f"公开信息：{target_name} 的身份说法前后不一致")

        high_confidence_summaries = [
            *self.working_memory.get_private_memory_summaries("fortune_teller_info"),
            *self.working_memory.get_private_memory_summaries("investigator_info"),
            *self.working_memory.get_private_memory_summaries("empath_info"),
            *self.working_memory.get_private_memory_summaries("chef_info"),
        ]
        for summary in high_confidence_summaries:
            if target_name in summary:
                candidates.append(f"高可信信息：{summary}")

        if profile and profile.claim_history:
            recent_claim = profile.claim_history[-1]
            if recent_claim.claim_type == "self_claim" and recent_claim.role_id:
                candidates.append(f"公开信息：{target_name} 最近自报 {recent_claim.role_id}")
            if recent_claim.claim_type == "denial" and recent_claim.role_id:
                candidates.append(f"公开信息：{target_name} 最近否认自己是 {recent_claim.role_id}")

        public_claims = self.working_memory.get_public_memory_summaries("role_claim")
        for summary in reversed(public_claims):
            if target_name in summary:
                candidates.append(f"公开信息：{summary}")

        return candidates

    def _best_reasoning_evidence(self, target_id: str | None, visible_state: AgentVisibleState) -> str:
        candidates = self._reasoning_evidence_candidates(target_id, visible_state)
        return candidates[0] if candidates else ""

    def _augment_reasoning_with_evidence(
        self,
        reasoning: str,
        *,
        action_type: str,
        target_id: str | None,
        visible_state: AgentVisibleState,
        suspicion: float | None = None,
        threshold: float | None = None,
    ) -> str:
        base = reasoning.strip()
        evidence_candidates = self._reasoning_evidence_candidates(target_id, visible_state)
        parts = [base] if base else []
        if evidence_candidates:
            parts.append(f"依据={evidence_candidates[0]}")
            for extra in evidence_candidates[1:3]:
                if not extra.startswith("公开信息："):
                    parts.append(f"补充={extra}")
                elif action_type in {"nominate", "nomination_intent", "vote"} and "前后不一致" in extra:
                    parts.append(f"补充={extra}")
        if suspicion is not None and threshold is not None:
            label = "怀疑度"
            parts.append(f"{label}={suspicion:.2f} 阈值={threshold:.2f}")
        if action_type in {"nominate", "nomination_intent", "vote"}:
            parts.append(f"风格={self.persona_profile.get('social_style', '独立')}")
        return " | ".join(part for part in parts if part)

    def _stable_choice(self, options: list[str], round_number: int, day_number: int, action_type: str, salt: str = "") -> str:
        if not options:
            return ""
        digest = self._stable_hash(
            self.player_id,
            self.role_id or "unknown",
            round_number,
            day_number,
            action_type,
            salt,
        )
        index = int(digest[:8], 16) % len(options)
        return options[index]

    def _persona_vote_bias(self, visible_state: AgentVisibleState) -> bool:
        profile = self.persona_profile or {}
        bias = profile.get("decision_style", "")
        nominee = visible_state.current_nominee
        if nominee == self.player_id:
            return False
        if self.team == "evil":
            return bias.startswith("谨慎") or bias.startswith("保持") or bias.startswith("会在")
        return not bias.startswith("压迫") and not bias.startswith("果断")

    def _persona_fallback_speech(self, action_type: str, reason: str, visible_state: AgentVisibleState, legal_context: AgentActionLegalContext) -> dict[str, Any]:
        profile = self.persona_profile or {}
        role_name = profile.get("role_name", self.name)
        stable_line = self._preferred_speech_anchor_line(visible_state)
        evil_coordination = self._evil_coordination_line(visible_state)
        if action_type == "defense_speech":
            if evil_coordination:
                content = evil_coordination
            elif stable_line:
                content = f"先别急着把票压上来，我更相信我已经确认过的线索：{stable_line}"
            else:
                content = self._stable_choice(
                    [
                        "我觉得现在最重要的是把信息说清楚，而不是急着扣帽子。",
                        "我知道我看起来有点像目标，但我希望大家再给我一点解释的机会。",
                        "先别急着把票压上来，我愿意把我的判断过程说完整。",
                    ],
                    visible_state.round_number,
                    visible_state.day_number,
                    action_type,
                    "defense",
                )
            return {
                "action": "speak",
                "content": content,
                "tone": "defensive",
                "reasoning": f"兜底辩解，保持角色风格 {role_name}。({reason})",
            }
        if action_type == "vote":
            return {
                "action": "vote",
                "decision": self._persona_vote_bias(visible_state),
                "reasoning": f"兜底投票，保持角色风格 {role_name}。({reason})",
            }
        if action_type in {"nominate", "nomination_intent"}:
            wants_to_pass = self._stable_choice(["yes", "yes", "no"], visible_state.round_number, visible_state.day_number, action_type, "pass_bias") == "yes"
            legal_targets = list(legal_context.legal_nomination_targets)
            
            if not legal_targets or wants_to_pass:
                return {"action": "none", "target": None, "reasoning": f"兜底选择放弃提名。({reason})"}

            target, _ = self._choose_nomination_target_from_band(
                legal_targets,
                visible_state,
                action_type,
                "nominate_band",
                tolerance=0.05,
            )
            return {
                "action": "nominate",
                "target": target,
                "reasoning": f"兜底强行提名目标。({reason})",
            }
        if action_type in {"night_action", "death_trigger"}:
            legal_targets = list(legal_context.legal_night_targets)
            target = self._stable_choice(legal_targets, visible_state.round_number, visible_state.day_number, action_type, "night") if legal_targets else None
            return {
                "action": action_type,
                "target": target,
                "reasoning": f"兜底夜晚行动，按稳定人格选择目标。({reason})",
            }
        if evil_coordination:
            content = evil_coordination
        elif stable_line:
            content = f"我先说我更信哪条线：{stable_line}。公开场上的说法我会参考，但不会放在这之上。"
        else:
            content = self._stable_choice(
                [
                    "我先听大家说完，再决定要不要站队。",
                    "我还在观察局势，暂时不想把话说死。",
                    "先别急着下结论，我想再听听更多细节。",
                ],
                visible_state.round_number,
                visible_state.day_number,
                action_type,
                "speech",
            )
        return {
            "action": "speak",
            "content": content,
            "tone": "calm",
            "reasoning": f"兜底发言，保持角色风格 {role_name}。({reason})",
        }

    def _evil_coordination_line(self, visible_state: AgentVisibleState) -> str:
        if self.team != Team.EVIL:
            return ""
        teammate_summaries = self.working_memory.get_objective_memory_summaries("evil_teammates")
        if not teammate_summaries:
            return ""

        evil_teammate_ids: set[str] = set()
        for player in visible_state.players:
            if player.player_id == self.player_id:
                continue
            if any(player.name in summary for summary in teammate_summaries):
                evil_teammate_ids.add(player.player_id)

        if not evil_teammate_ids:
            return ""

        claims = self.social_graph.get_all_self_claims()
        for teammate_id in evil_teammate_ids:
            claim_role_id = claims.get(teammate_id)
            if not claim_role_id:
                continue
            teammate_name = self._player_name_from_visible_state(teammate_id, visible_state)
            claim_name = get_role_name(claim_role_id)
            return f"我暂时更愿意把 {teammate_name} 当成一个在认真给信息的人，他跳 {claim_name} 这条线我不会先急着否掉。"

        bluff_summaries = self.working_memory.get_objective_memory_summaries("evil_bluffs")
        if bluff_summaries:
            return "我觉得现在别急着拆场上的每一个身份，先看发言逻辑和投票轨迹更稳。"
        return ""

    def _preferred_speech_anchor_line(self, visible_state: AgentVisibleState) -> str:
        """优先选择最适合真实公开发言引用的高可信/客观线索。"""
        preferred_private_categories = (
            "revealed_role",
            "role_candidate_hint",
            "demon_candidate",
            "evil_teammates",
        )
        for category in preferred_private_categories:
            summaries = self.working_memory.get_private_memory_summaries(category)
            if summaries:
                return summaries[-1]
        private = self.working_memory.get_private_memory_summaries()
        if private:
            return private[-1]
        objective = self.working_memory.get_objective_memory_summaries()
        if objective:
            return objective[-1]
        return ""

    def _stabilize_speech_content_with_memory(
        self,
        content: str,
        visible_state: AgentVisibleState,
        action_type: str,
    ) -> str:
        """让真实发言也能更稳定地引用高可信/客观线索。"""
        text = content.strip()
        if not text:
            return text

        stable_line = self._preferred_speech_anchor_line(visible_state)
        if not stable_line:
            return text
        if stable_line in text:
            return text
        if len(text) > 60:
            return text

        prefix = "我先把我最确认的一条线说清楚：" if action_type == "defense_speech" else "我先说我更信的一条线："
        return f"{prefix}{stable_line}。{text}"

    def _normalize_decision(self, visible_state: AgentVisibleState, legal_context: AgentActionLegalContext, action_type: str, decision: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(decision, dict):
            return self._fallback_decision(visible_state, legal_context, action_type, reason="non_dict_response")

        reasoning = str(decision.get("reasoning", ""))
        tone = str(decision.get("tone", "calm"))

        if action_type in {"speak", "nomination_intent"} and decision.get("action") == "slayer_shot" and legal_context.can_slayer_shot:
            target = decision.get("target")
            candidate_ids = {player.player_id for player in visible_state.players if player.is_alive and player.player_id != self.player_id}
            if isinstance(target, str) and target in candidate_ids:
                suspicion = self._target_signal_score(target, visible_state)
                return {
                    "action": "slayer_shot",
                    "target": target,
                    "reasoning": self._augment_reasoning_with_evidence(
                        reasoning or "决定发动猎手技能。",
                        action_type="slayer_shot",
                        target_id=target,
                        visible_state=visible_state,
                        suspicion=suspicion,
                        threshold=0.74,
                    ),
                }

        if action_type in {"nominate", "nomination_intent"}:
            target = decision.get("target")
            if decision.get("action") == "none" or str(target).lower() == "none":
                return {"action": "none", "target": None, "reasoning": reasoning or "放弃提名。"}
                
            legal_targets = list(legal_context.legal_nomination_targets)
            if target in legal_targets:
                suspicion = self._target_signal_score(target, visible_state)
                threshold = self._nomination_threshold(visible_state)
                return {
                    "action": "nominate",
                    "target": target,
                    "reasoning": self._augment_reasoning_with_evidence(
                        reasoning or "决定提名。",
                        action_type=action_type,
                        target_id=target,
                        visible_state=visible_state,
                        suspicion=suspicion,
                        threshold=threshold,
                    ),
                }
            
            return self._fallback_decision(visible_state, legal_context, action_type, reason="invalid_nomination_target")


        if action_type == "vote":
            final_vote = decision.get("decision")
            if isinstance(final_vote, bool):
                suspicion, threshold = (0.0, self._vote_threshold(visible_state))
                if visible_state.current_nominee:
                    suspicion = self._target_signal_score(visible_state.current_nominee, visible_state)
                return {
                    "action": "vote",
                    "decision": final_vote,
                    "reasoning": self._augment_reasoning_with_evidence(
                        reasoning or "完成投票。",
                        action_type=action_type,
                        target_id=visible_state.current_nominee,
                        visible_state=visible_state,
                        suspicion=suspicion,
                        threshold=threshold,
                    ),
                }
            return self._fallback_decision(visible_state, legal_context, action_type, reason="invalid_vote_decision")

        if action_type == "defense_speech":
            content = str(decision.get("content", "")).strip()
            if not content:
                return self._fallback_decision(visible_state, legal_context, action_type, reason="empty_defense_speech")
            content = self._stabilize_speech_content_with_memory(content, visible_state, action_type)
            return {"action": "speak", "content": content, "tone": tone, "reasoning": reasoning}

        if action_type in {"night_action", "death_trigger"}:
            targets = self._coerce_target_values(decision.get("targets"))
            if not targets:
                targets = self._coerce_target_values(decision.get("target"))
            
            legal_targets = list(legal_context.legal_night_targets)
            # 兼容自选逻辑
            if getattr(legal_context, "can_target_self", False):
                legal_targets.append(self.player_id)

            required_targets = max(0, int(getattr(legal_context, "required_targets", 1) or 0))
            if not targets:
                if required_targets > 0:
                    return self._fallback_decision(visible_state, legal_context, action_type, reason="missing_night_target")
                # 某些角色可能没有目标
                return {"action": action_type, "target": None, "targets": [], "reasoning": reasoning}

            if required_targets > 0 and len(targets) != required_targets:
                return self._fallback_decision(visible_state, legal_context, action_type, reason="invalid_night_target_count")
            if len(set(targets)) != len(targets):
                return self._fallback_decision(visible_state, legal_context, action_type, reason="duplicate_night_targets")

            # 校验所有目标是否合法
            all_valid = all(t in legal_targets for t in targets)
            if decision.get("action") in {"night_action", "death_trigger"} and all_valid:
                payload: dict[str, Any] = {"action": action_type, "reasoning": reasoning}
                if len(targets) == 1:
                    payload["target"] = targets[0]
                else:
                    payload["target"] = targets[0]
                    payload["targets"] = targets
                return payload
            
            return self._fallback_decision(visible_state, legal_context, action_type, reason="illegal_night_target")

        if decision.get("action") == "skip_discussion":
            return {"action": "skip_discussion", "reasoning": reasoning or "我选择暂时结束发言。"}

        content = str(decision.get("content", "")).strip()
        if not content:
            return self._fallback_decision(visible_state, legal_context, action_type, reason="empty_speech")
        content = self._stabilize_speech_content_with_memory(content, visible_state, action_type)
        return {"action": "speak", "content": content, "tone": tone, "reasoning": reasoning}

    def _fallback_decision(self, visible_state: AgentVisibleState, legal_context: AgentActionLegalContext, action_type: str, reason: str) -> dict[str, Any]:
        fallback = self._persona_fallback_speech(action_type, reason, visible_state, legal_context)
        if action_type in {"nominate", "nomination_intent"}:
            selection = self._select_nomination_target(visible_state, legal_context, intent_mode=(action_type == "nomination_intent"))
            if selection:
                target, score, threshold = selection
                return {
                    "action": "nominate",
                    "target": target,
                    "reasoning": self._augment_reasoning_with_evidence(
                        f"兜底提名，按稳定人格选择更可疑的目标。({reason})",
                        action_type=action_type,
                        target_id=target,
                        visible_state=visible_state,
                        suspicion=score,
                        threshold=threshold,
                    ),
                }
            if action_type == "nomination_intent":
                legal_targets = list(legal_context.legal_nomination_targets)
                if legal_targets:
                    target, score = self._choose_nomination_target_from_band(
                        legal_targets,
                        visible_state,
                        action_type,
                        "intent_band",
                        tolerance=0.05,
                    )
                    if score >= 0.18:
                        return {
                            "action": "nominate",
                            "target": target,
                            "reasoning": self._augment_reasoning_with_evidence(
                                f"兜底提名，局势足够可疑，主动推动提名。({reason})",
                                action_type=action_type,
                                target_id=target,
                                visible_state=visible_state,
                                suspicion=score,
                                threshold=self._nomination_threshold(visible_state),
                            ),
                        }
            if action_type == "nominate":
                legal_targets = list(legal_context.legal_nomination_targets)
                if legal_targets:
                    target, score = self._choose_nomination_target_from_band(
                        legal_targets,
                        visible_state,
                        action_type,
                        "fallback_force_band",
                        tolerance=0.05,
                    )
                    # 只有怀疑度极高(>0.65)且不在pass_bias中的时候才强制提名
                    if (
                        target
                        and score > 0.65
                        and self._stable_choice(
                            ["yes", "no"],
                            visible_state.round_number,
                            visible_state.day_number,
                            action_type,
                            "fallback_force",
                        ) == "yes"
                    ):
                        return {
                            "action": "nominate",
                            "target": target,
                            "reasoning": self._augment_reasoning_with_evidence(
                                f"兜底提名，怀疑度极高，强制推动。({reason})",
                                action_type=action_type,
                                target_id=target,
                                visible_state=visible_state,
                                suspicion=score,
                                threshold=self._nomination_threshold(visible_state),
                            ),
                        }
            return {"action": "none", "target": None, "reasoning": fallback.get("reasoning", f"决定放弃此轮行动。({reason})")}
        if action_type == "vote":
            vote, suspicion, threshold = self._select_vote_decision(visible_state, legal_context, None)
            return {
                "action": "vote",
                "decision": vote,
                "reasoning": self._augment_reasoning_with_evidence(
                    fallback.get('reasoning', f'兜底投票决策。({reason})'),
                    action_type=action_type,
                    target_id=visible_state.current_nominee,
                    visible_state=visible_state,
                    suspicion=suspicion,
                    threshold=threshold,
                ),
            }
        if action_type == "defense_speech":
            return fallback
        if action_type in {"night_action", "death_trigger"}:
            required_targets = max(0, int(getattr(legal_context, "required_targets", 1) or 0))
            selected_targets = self._select_night_targets(visible_state, legal_context)
            if not selected_targets:
                return fallback
            if required_targets > 1 and len(selected_targets) >= required_targets:
                return {
                    "action": action_type,
                    "target": selected_targets[0],
                    "targets": selected_targets[:required_targets],
                    "reasoning": fallback.get("reasoning", f"兜底夜晚行动。({reason})"),
                }
            if len(selected_targets) == 1:
                return {
                    "action": action_type,
                    "target": selected_targets[0],
                    "reasoning": fallback.get("reasoning", f"兜底夜晚行动。({reason})"),
                }
            return {
                "action": action_type,
                "target": None,
                "targets": selected_targets,
                "reasoning": fallback.get("reasoning", f"兜底夜晚行动。({reason})"),
            }
        return fallback
