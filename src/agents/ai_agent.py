"""
AI Agent 实现

通过 LLM 驱动的游戏内角色。
"""

from __future__ import annotations

import hashlib
import logging
import json
from typing import Any

from src.agents.base_agent import BaseAgent
from src.agents.memory.episodic_memory import EpisodicMemory
from src.agents.memory.social_graph import SocialGraph
from src.agents.memory.working_memory import Observation, WorkingMemory
from src.content.trouble_brewing_terms import get_role_description, get_role_name, get_role_persona_hint
from src.llm.base_backend import LLMBackend
from src.state.game_state import GameEvent, GameState, PlayerState

logger = logging.getLogger(__name__)


class Persona:
    """Agent的人格配方"""
    def __init__(
        self,
        description: str,
        speaking_style: str,
        voice_anchor: str = "",
        decision_style: str = "",
    ):
        self.description = description
        self.speaking_style = speaking_style
        self.voice_anchor = voice_anchor
        self.decision_style = decision_style


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
        role_id = self.true_role_id or self.role_id or "unknown"
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
        posture = "邪恶阵营" if self.team == "evil" else "正义阵营"
        signature = self._stable_hash(self.player_id, role_id, self.persona.description, self.persona.speaking_style)[:10]
        self.persona_signature = signature
        self.persona_profile = {
            "role_id": role_id,
            "role_name": role_name,
            "role_description": role_description,
            "role_hint": role_hint,
            "voice_anchor": voice_anchor,
            "decision_style": decision_style,
            "speech_rhythm": speech_rhythm,
            "risk_tolerance": risk_tolerance,
            "social_style": social_style,
            "assertiveness": assertiveness,
            "posture": posture,
            "signature": signature,
        }

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

    def _build_persona_prompt_block(self, action_type: str) -> str:
        profile = self.persona_profile or {}
        action_hints = {
            "speak": "你的任务是像真人一样发言，保持自然，先给态度再给理由。",
            "nominate": "你的任务是决定是否提名。先像人一样判断，再给出目标或放弃。",
            "nomination_intent": "你的任务是先判断是否提名。不要像规则机器，先想清楚再说。",
            "vote": "你的任务是投票。请让决定符合你的性格和局势判断，不要每次都像同一模板。",
            "defense_speech": "你是被提名者。请像真人一样辩解，语气要贴合你的性格。",
            "night_action": "你在夜晚执行角色能力。请选择符合角色和局势的目标，语气保持自然。",
            "death_trigger": "你刚刚因为夜晚死亡而触发角色能力。请选择合适目标并自然表达。",
        }
        return f"""【稳定人格锚点】
- 角色名: {profile.get('role_name', get_role_name(self.true_role_id or self.role_id or 'unknown'))}
- 角色说明: {profile.get('role_description', get_role_description(self.true_role_id or self.role_id or 'unknown'))}
- 个性提示: {self.persona.description}
- 说话风格: {self.persona.speaking_style}
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

    async def act(self, game_state: GameState, action_type: str, **kwargs: Any) -> dict[str, Any]:
        """决定如何行动"""
        logger.info(
            "[%s] 需要执行动作: %s persona=%s role=%s",
            self.name,
            action_type,
            self.persona_signature or "unknown",
            self.true_role_id or self.role_id or "unknown",
        )

        self._prime_social_graph_from_state(game_state)
        obs_text = self.working_memory.get_recent_context(10)
        visible_players = ", ".join(
            f"{p.name}({p.player_id},{'alive' if p.is_alive else 'dead'})"
            for p in game_state.players
        )
        perceived_role = self.perceived_role_id or self.fake_role or self.role_id
        action_context = self._build_action_context(game_state, action_type)
        persona_block = self._build_persona_prompt_block(action_type)

        system_prompt = f"""你是一名正在玩《血染钟楼》(Blood on the Clocktower) 的真实玩家。
你的名字是 {self.name}，你认知的角色是 {perceived_role}，阵营是 {self.team}。
你的个性是：{self.persona.description}，表达风格是：{self.persona.speaking_style}。

【核心原则：玩家优先级】
1. **你是玩家，不是 AI**：表现得像一个人在和朋友社交。会有犹豫、怀疑、幽默或偶尔的强势。
2. **社交推演**：除了规则和技能，更要关注别人的发言逻辑。你会对可疑的人表示怀疑，对信任的人表示支持。
3. **沉浸式对话**：发言要自然，像在群聊或面杀现场。不要直接报数值或死板地回复指令。
4. **策略性欺骗**：如果你是邪恶阵营，你要编造合理的假身份，并试着通过社交手段引导好人互相怀疑。

{persona_block}

当前游戏状态：
- 阶段：{game_state.phase} (第 {game_state.day_number} 天, 第 {game_state.round_number} 轮)
- 你看到的身份：{perceived_role} ({self.team} 阵营)
- 当前玩家列表：{visible_players}
- 当前需要执行的动作类型：{action_type}
- 当前动作补充要求：{action_context}

【你的目标】
{"作为邪恶阵营，隐藏恶魔，混淆视听，剪除正义之士。" if self.team == "evil" else "作为正义阵营，通过逻辑与沟通找出恶魔并处决。"}

【近期记忆】
{obs_text}

【JSON 格式规范】
请务必返回如下结构的 JSON，不要包含任何多余文字：
{{
  "action": "speak/nominate/vote/night_action/skip_discussion/none",
  "content": "你的中文发言内容 (仅 speak 时需要)",
  "tone": "语气 (calm/passionate/accusatory/defensive)",
  "target": "player_id (仅 nominate/night_action 时需要，否则为 null)",
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
            decision = self._normalize_decision(game_state, action_type, decision)
            if "reasoning" in decision:
                logger.info(f"[{self.name}] 内部思考: {decision['reasoning']}")
            return decision
        except Exception as e:
            logger.error(f"[{self.name}] LLM 调用失败: {e}")
            return self._fallback_decision(game_state, action_type, reason=f"llm_error:{type(e).__name__}")

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
        actor_player = game_state.get_player(event.actor) if event.actor else None
        target_player = game_state.get_player(event.target) if event.target else None
        actor = actor_player.name if actor_player else "系统"
        target = target_player.name if target_player else "某个目标"

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
            return f"🌙 你收到了私密信息: {info_type}"
            
        return f"系统事件: {event.event_type}"

    def _build_action_context(self, game_state: GameState, action_type: str) -> str:
        if action_type in {"nominate", "nomination_intent"}:
            legal_targets = self._legal_nomination_targets(game_state)
            if legal_targets:
                threshold = self._nomination_threshold(game_state)
                return (
                    f"你可以合法提名的目标只有这些：{', '.join(legal_targets)}。"
                    f"只有当怀疑度明显高于 {threshold:.2f} 时才提名；"
                    "如果没有足够理由，请返回 action=none。"
                )
            return "当前没有合法提名目标，请返回 action=none。"
        if action_type == "vote":
            nominee = game_state.current_nominee or "无"
            threshold = self._vote_threshold(game_state)
            return (
                f"当前投票对象是：{nominee}。"
                f"只有在你对其怀疑度高于 {threshold:.2f} 时才投赞成票；"
                "如果证据不足，请投反对票。"
            )
        if action_type == "defense_speech":
            return "你是被提名者，需要进行简短辩解。请返回 action=speak 和一段自然中文。"
        if action_type in {"night_action", "death_trigger"}:
            legal_targets = self._legal_night_targets(game_state)
            if legal_targets:
                return f"优先从这些存活玩家里选择目标：{', '.join(legal_targets)}。"
            return "如果没有合适目标，target 可以为 null。"
        return "请自然发言。如果你实在没有信息，可以简短表达保留意见。"

    def _legal_nomination_targets(self, game_state: GameState) -> list[str]:
        from src.engine.rule_engine import RuleEngine

        targets: list[str] = []
        for player in game_state.players:
            if player.player_id == self.player_id:
                continue
            can_nominate, _ = RuleEngine.can_nominate(game_state, self.player_id, player.player_id)
            if can_nominate:
                targets.append(player.player_id)
        return targets

    def _legal_night_targets(self, game_state: GameState) -> list[str]:
        return [
            player.player_id
            for player in game_state.get_alive_players()
            if player.player_id != self.player_id
        ]

    def _sync_social_graph(self, game_state: GameState) -> None:
        for player in game_state.players:
            self.social_graph.init_player(player.player_id, player.name)

    def _prime_social_graph_from_state(self, game_state: GameState) -> None:
        state_signature = self._stable_hash(
            game_state.day_number,
            game_state.round_number,
            len(game_state.chat_history),
            len(game_state.event_log),
        )
        if state_signature == self._last_social_prime_signature:
            return

        self._last_social_prime_signature = state_signature
        self._sync_social_graph(game_state)

        suspicion_keywords = ("怀疑", "可疑", "怪", "假", "骗", "不对", "危险")
        trust_keywords = ("信任", "支持", "同意", "靠谱", "好人", "合理")
        for message in game_state.chat_history[-10:]:
            content = message.content.lower()
            for player in game_state.players:
                if player.player_id == self.player_id:
                    continue
                player_name = player.name.lower()
                if player_name not in content:
                    continue
                profile = self.social_graph.get_profile(player.player_id)
                if not profile:
                    continue
                if any(keyword in content for keyword in suspicion_keywords):
                    profile.trust_score = max(-1.0, profile.trust_score - 0.18)
                    profile.notes.append(f"聊天里出现对 {player.name} 的怀疑信号")
                if any(keyword in content for keyword in trust_keywords):
                    profile.trust_score = min(1.0, profile.trust_score + 0.10)
                    profile.notes.append(f"聊天里出现对 {player.name} 的信任信号")

    def _recent_context_texts(self, game_state: GameState, limit: int = 12) -> list[str]:
        texts: list[str] = []
        for obs in self.working_memory.observations[-limit:]:
            if obs.content:
                texts.append(obs.content)
        for message in game_state.chat_history[-limit:]:
            speaker = game_state.get_player(message.speaker)
            speaker_name = speaker.name if speaker else message.speaker
            target_name = ""
            if message.target_player:
                target_player = game_state.get_player(message.target_player)
                target_name = f" -> {target_player.name}" if target_player else f" -> {message.target_player}"
            texts.append(f"{speaker_name}{target_name}: {message.content}")
        for event in game_state.event_log[-limit:]:
            if event.event_type in {"player_speaks", "nomination_started", "vote_cast", "voting_resolved", "execution_resolved", "player_death"}:
                texts.append(self._format_event_to_text(event, game_state))
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

    def _nomination_threshold(self, game_state: GameState) -> float:
        threshold = 0.60
        if game_state.alive_count <= 5:
            threshold -= 0.03
        elif game_state.alive_count >= 8:
            threshold += 0.02

        threshold -= min(0.08, max(0, game_state.day_number - 1) * 0.02)
        threshold += self._persona_modifier("risk_tolerance", {"保守": 0.08, "均衡": 0.02, "激进": -0.05})
        threshold += self._persona_modifier("social_style", {"从众": 0.03, "独立": 0.0, "带节奏": -0.04})
        threshold += self._persona_modifier("assertiveness", {"温和": 0.04, "中性": 0.0, "强势": -0.04})
        if self.team == "evil":
            threshold -= 0.02
        return max(0.45, min(0.80, threshold))

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

    def _vote_threshold(self, game_state: GameState) -> float:
        threshold = 0.54
        if game_state.alive_count <= 5:
            threshold -= 0.02
        elif game_state.alive_count >= 8:
            threshold += 0.02

        threshold -= min(0.05, max(0, game_state.day_number - 1) * 0.015)
        threshold += self._persona_modifier("risk_tolerance", {"保守": 0.04, "均衡": 0.01, "激进": -0.04})
        threshold += self._persona_modifier("social_style", {"从众": 0.02, "独立": 0.0, "带节奏": -0.03})
        threshold += self._persona_modifier("assertiveness", {"温和": 0.03, "中性": 0.0, "强势": -0.03})
        if self.team == "evil":
            threshold -= 0.01
        return max(0.35, min(0.75, threshold))

    def _target_signal_score(self, game_state: GameState, target_id: str) -> float:
        if not target_id or target_id == self.player_id:
            return 0.0

        target = game_state.get_player(target_id)
        if not target:
            return 0.0

        texts = self._recent_context_texts(game_state)
        mention_hits = self._count_mentions(texts, target.name)
        score = 0.16 + min(0.24, mention_hits * 0.06)

        if target_id in game_state.nominees_today:
            score += 0.12
        if target_id == game_state.current_nominee:
            score += 0.06
        if game_state.current_nominator and game_state.current_nominator == target_id:
            score += 0.03

        profile = self.social_graph.get_profile(target_id)
        if profile:
            if profile.trust_score < 0:
                score += min(0.20, abs(profile.trust_score) * 0.25)
            elif profile.trust_score > 0:
                score -= min(0.12, profile.trust_score * 0.12)
            if profile.notes:
                score += min(0.08, len(profile.notes) * 0.02)

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

    def _select_nomination_target(self, game_state: GameState, intent_mode: bool = False) -> tuple[str, float, float] | None:
        legal_targets = self._legal_nomination_targets(game_state)
        if not legal_targets:
            return None

        scored_targets = sorted(
            ((self._target_signal_score(game_state, target_id), target_id) for target_id in legal_targets),
            key=lambda item: (-item[0], item[1]),
        )
        best_score, best_target = scored_targets[0]
        runner_up_score = scored_targets[1][0] if len(scored_targets) > 1 else 0.0
        threshold = self._nomination_threshold(game_state)
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

    def _select_vote_decision(self, game_state: GameState, model_vote: bool | None = None) -> tuple[bool, float, float]:
        nominee_id = game_state.current_nominee
        threshold = self._vote_threshold(game_state)
        if not nominee_id:
            return False, 0.0, threshold

        suspicion = self._target_signal_score(game_state, nominee_id)
        margin = 0.06
        if suspicion >= threshold + margin:
            return True, suspicion, threshold
        if suspicion <= threshold - margin:
            return False, suspicion, threshold
        if model_vote is not None:
            return bool(model_vote), suspicion, threshold
        return self._persona_vote_bias(game_state), suspicion, threshold

    def _stable_choice(self, options: list[str], game_state: GameState, action_type: str, salt: str = "") -> str:
        if not options:
            return ""
        digest = self._stable_hash(
            self.player_id,
            self.true_role_id or self.role_id or "unknown",
            game_state.round_number,
            game_state.day_number,
            action_type,
            salt,
        )
        index = int(digest[:8], 16) % len(options)
        return options[index]

    def _persona_vote_bias(self, game_state: GameState) -> bool:
        profile = self.persona_profile or {}
        bias = profile.get("decision_style", "")
        nominee = game_state.current_nominee
        if nominee == self.player_id:
            return False
        if self.team == "evil":
            return bias.startswith("谨慎") or bias.startswith("保持") or bias.startswith("会在")
        return not bias.startswith("压迫") and not bias.startswith("果断")

    def _persona_fallback_speech(self, action_type: str, reason: str, game_state: GameState) -> dict[str, Any]:
        profile = self.persona_profile or {}
        role_name = profile.get("role_name", self.name)
        if action_type == "defense_speech":
            content = self._stable_choice(
                [
                    "我觉得现在最重要的是把信息说清楚，而不是急着扣帽子。",
                    "我知道我看起来有点像目标，但我希望大家再给我一点解释的机会。",
                    "先别急着把票压上来，我愿意把我的判断过程说完整。",
                ],
                game_state,
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
                "decision": self._persona_vote_bias(game_state),
                "reasoning": f"兜底投票，保持角色风格 {role_name}。({reason})",
            }
        if action_type in {"nominate", "nomination_intent"}:
            legal_targets = self._legal_nomination_targets(game_state)
            if legal_targets:
                target = self._stable_choice(legal_targets, game_state, action_type, "nominate")
                return {
                    "action": "nominate",
                    "target": target,
                    "reasoning": f"兜底提名，按稳定人格选择最顺手的目标。({reason})",
                }
            return {"action": "none", "target": None, "reasoning": f"当前没有合法提名目标。({reason})"}
        if action_type in {"night_action", "death_trigger"}:
            legal_targets = self._legal_night_targets(game_state)
            target = self._stable_choice(legal_targets, game_state, action_type, "night") if legal_targets else None
            return {
                "action": action_type,
                "target": target,
                "reasoning": f"兜底夜晚行动，按稳定人格选择目标。({reason})",
            }
        content = self._stable_choice(
            [
                "我先听大家说完，再决定要不要站队。",
                "我还在观察局势，暂时不想把话说死。",
                "先别急着下结论，我想再听听更多细节。",
            ],
            game_state,
            action_type,
            "speech",
        )
        return {
            "action": "speak",
            "content": content,
            "tone": "calm",
            "reasoning": f"兜底发言，保持角色风格 {role_name}。({reason})",
        }

    def _normalize_decision(self, game_state: GameState, action_type: str, decision: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(decision, dict):
            return self._fallback_decision(game_state, action_type, reason="non_dict_response")

        reasoning = str(decision.get("reasoning", ""))
        tone = str(decision.get("tone", "calm"))

        if action_type in {"nominate", "nomination_intent"}:
            selection = self._select_nomination_target(game_state, intent_mode=(action_type == "nomination_intent"))
            if not selection and action_type == "nomination_intent":
                return self._fallback_decision(game_state, action_type, reason="nomination_below_threshold")

            legal_targets = self._legal_nomination_targets(game_state)
            if action_type == "nominate" and not selection:
                if not legal_targets:
                    return {"action": "none", "target": None, "reasoning": "当前没有合法提名目标。"}
                chosen_target = max(
                    legal_targets,
                    key=lambda candidate: (self._target_signal_score(game_state, candidate), candidate),
                )
                chosen_score = self._target_signal_score(game_state, chosen_target)
                threshold = self._nomination_threshold(game_state)
                compare_score = chosen_score
            else:
                assert selection is not None
                best_target, best_score, threshold = selection
                chosen_target = best_target
                chosen_score = best_score
                compare_score = best_score

            target = decision.get("target")
            if decision.get("action") == "nominate" and target in legal_targets:
                target_score = self._target_signal_score(game_state, target)
                if target_score >= threshold and abs(target_score - compare_score) <= 0.05:
                    chosen_target = target
                    chosen_score = target_score

            return {
                "action": "nominate",
                "target": chosen_target,
                "reasoning": (
                    f"{reasoning or '根据当前局势决定提名。'} "
                    f"| 怀疑度={chosen_score:.2f} 阈值={threshold:.2f} 风格={self.persona_profile.get('social_style', '独立')}"
                ),
            }

        if action_type == "vote":
            final_vote, suspicion, threshold = self._select_vote_decision(
                game_state,
                decision.get("decision") if isinstance(decision.get("decision"), bool) else None,
            )
            return {
                "action": "vote",
                "decision": final_vote,
                "reasoning": (
                    f"{reasoning or '基于当前信息完成投票。'} "
                    f"| 怀疑度={suspicion:.2f} 阈值={threshold:.2f} 风格={self.persona_profile.get('social_style', '独立')}"
                ),
            }

        if action_type == "defense_speech":
            content = str(decision.get("content", "")).strip() or "我是好人，请再想一想。"
            return {"action": "speak", "content": content, "tone": tone, "reasoning": reasoning}

        if action_type in {"night_action", "death_trigger"}:
            target = decision.get("target")
            legal_targets = self._legal_night_targets(game_state)
            if decision.get("action") in {"night_action", "death_trigger"} and (target in legal_targets or target is None):
                return {"action": action_type, "target": target, "reasoning": reasoning}
            return self._fallback_decision(game_state, action_type, reason="illegal_night_target")

        if decision.get("action") == "skip_discussion":
            return {"action": "skip_discussion", "reasoning": reasoning or "我选择暂时结束发言。"}

        content = str(decision.get("content", "")).strip()
        if not content:
            return self._fallback_decision(game_state, action_type, reason="empty_speech")
        return {"action": "speak", "content": content, "tone": tone, "reasoning": reasoning}

    def _fallback_decision(self, game_state: GameState, action_type: str, reason: str) -> dict[str, Any]:
        fallback = self._persona_fallback_speech(action_type, reason, game_state)
        if action_type in {"nominate", "nomination_intent"}:
            selection = self._select_nomination_target(game_state, intent_mode=(action_type == "nomination_intent"))
            if selection:
                target, score, threshold = selection
                return {
                    "action": "nominate",
                    "target": target,
                    "reasoning": f"兜底提名，按稳定人格选择更可疑的目标。({reason}) | 怀疑度={score:.2f} 阈值={threshold:.2f}",
                }
            if action_type == "nomination_intent":
                legal_targets = self._legal_nomination_targets(game_state)
                if legal_targets:
                    target = max(
                        legal_targets,
                        key=lambda candidate: (self._target_signal_score(game_state, candidate), candidate),
                    )
                    score = self._target_signal_score(game_state, target)
                    if score >= 0.18:
                        return {
                            "action": "nominate",
                            "target": target,
                            "reasoning": f"兜底提名，局势足够可疑，主动推动提名。({reason}) | 怀疑度={score:.2f}",
                        }
            if action_type == "nominate":
                legal_targets = self._legal_nomination_targets(game_state)
                if legal_targets:
                    target = max(
                        legal_targets,
                        key=lambda candidate: (self._target_signal_score(game_state, candidate), candidate),
                    )
                    score = self._target_signal_score(game_state, target)
                    threshold = self._nomination_threshold(game_state)
                    return {
                        "action": "nominate",
                        "target": target,
                        "reasoning": f"兜底提名，当前证据不足但仍选择一个合法目标。({reason}) | 怀疑度={score:.2f} 阈值={threshold:.2f}",
                    }
            return {"action": "none", "target": None, "reasoning": fallback.get("reasoning", f"当前没有合法提名目标。({reason})")}
        if action_type == "vote":
            vote, suspicion, threshold = self._select_vote_decision(game_state, None)
            return {
                "action": "vote",
                "decision": vote,
                "reasoning": f"{fallback.get('reasoning', f'兜底投票决策。({reason})')} | 怀疑度={suspicion:.2f} 阈值={threshold:.2f}",
            }
        if action_type == "defense_speech":
            return fallback
        if action_type in {"night_action", "death_trigger"}:
            if fallback.get("target", None) is not None or not self._legal_night_targets(game_state):
                return fallback
            return {
                "action": action_type,
                "target": None,
                "reasoning": fallback.get("reasoning", f"兜底夜晚行动。({reason})"),
            }
        return fallback
