"""说书人代理 (Storyteller Agent)。"""

from __future__ import annotations

import json
import logging
import os
import random
from dataclasses import asdict, dataclass
from typing import Any
from src.content.trouble_brewing_night_order import (
    build_night_order_tie_groups,
    get_night_order_sort_key,
    get_night_order_spec,
    validate_night_order_value,
)
from src.state.game_state import AbilityTrigger, GamePhase, GameState, RoleType, Team, Visibility

logger = logging.getLogger(__name__)
storyteller_logger = logging.getLogger("storyteller")


def _ensure_storyteller_log_handler() -> None:
    abs_path = os.path.abspath("storyteller_run.log")
    for handler in storyteller_logger.handlers:
        if isinstance(handler, logging.FileHandler) and os.path.abspath(getattr(handler, "baseFilename", "")) == abs_path:
            return
    handler = logging.FileHandler("storyteller_run.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    storyteller_logger.addHandler(handler)
    storyteller_logger.setLevel(logging.INFO)
    storyteller_logger.propagate = False


_ensure_storyteller_log_handler()


@dataclass
class StorytellerDecisionContext:
    truth_view: dict[str, Any]
    public_state: dict[str, Any]
    private_delivery_history: list[dict[str, Any]]
    recent_judgements: list[dict[str, Any]]
    balance_context: dict[str, Any]

    def get_player(self, player_id: str) -> dict[str, Any] | None:
        for p in self.truth_view.get("players", []):
            if p["player_id"] == player_id:
                return p
        return None

    def is_evil(self, player_id: str) -> bool:
        p = self.get_player(player_id)
        return p.get("current_team") == "evil" if p else False

    def is_alive(self, player_id: str) -> bool:
        p = self.get_player(player_id)
        return p.get("is_alive", False) if p else False

    def is_suppressed(self, player_id: str) -> bool:
        p = self.get_player(player_id)
        return p.get("ability_suppressed", False) if p else False

    def get_role(self, player_id: str) -> str:
        p = self.get_player(player_id)
        return p.get("true_role_id", "unknown") if p else "unknown"

    def get_role_type(self, player_id: str) -> str | None:
        p = self.get_player(player_id)
        return p.get("role_type") if p else None

    @property
    def alive_count(self) -> int:
        return self.public_state.get("alive_count", 0)


class StorytellerAgent:
    def __init__(self, backend: Any = None, mode: str = "auto", delegated: bool = False):
        self.backend = backend
        self.mode = mode
        self.delegated = delegated
        self.name = "Storyteller"
        self.player_id = "storyteller"
        self.decision_ledger: list[dict[str, Any]] = []

    def _stringify(self, value: Any) -> str:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return str(value)
        return json.dumps(value, ensure_ascii=False, default=str)

    def _jsonable(self, value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, dict):
            return {str(key): self._jsonable(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._jsonable(item) for item in value]
        if hasattr(value, "value"):
            return getattr(value, "value")
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                pass
        return str(value)

    def _classify_judgement_bucket(self, category: str, decision: str, fields: dict[str, Any]) -> str:
        if category in {"drunk_role"}:
            return "setup"
        if category in {"night_order"}:
            return "night_plan"
        if category in {"night_info"}:
            scope = fields.get("scope") or fields.get("info_scope") or "storyteller_info"
            return f"night_info.{scope}"
        if category in {"narration"}:
            return "phase_narration"
        if category in {"human_step"}:
            return "human_storyteller"
        if category in {"nomination_window", "nomination_choice", "nomination_started", "defense", "voting", "execution"}:
            return "day_judgement"
        return "general"

    def _normalize_judgement_fields(self, category: str, decision: str, fields: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(fields)
        normalized.setdefault("bucket", self._classify_judgement_bucket(category, decision, normalized))
        normalized.setdefault("phase", None)
        normalized.setdefault("day_number", None)
        normalized.setdefault("round_number", None)
        normalized.setdefault("trace_id", None)
        normalized.setdefault("adjudication_path", None)
        normalized.setdefault("distortion_strategy", None)
        return normalized

    def record_judgement(self, category: str, decision: str, reason: str | None = None, **fields: Any) -> dict[str, Any]:
        entry_fields = self._normalize_judgement_fields(category, decision, fields)
        entry = {"category": category, "decision": decision, "reason": reason, **entry_fields}
        self.decision_ledger.append(entry)
        bits = [f"decision={decision}"]
        if reason:
            bits.append(f"reason={reason}")
        bits.extend(f"{key}={self._stringify(value)}" for key, value in entry_fields.items() if value is not None)
        storyteller_logger.info("[judgement][%s] %s", category, " ".join(bits))
        return entry

    def get_recent_judgements(self, limit: int = 20) -> tuple[dict[str, Any], ...]:
        return tuple(self.decision_ledger[-limit:])

    async def analyze_game_situation(self, game_state: GameState) -> str:
        """[A3-ST-6] 分析当前对局局势，记录说书人的“内心独白”。"""
        if not self.backend:
            return "说书人正在维持平衡。"

        context = self._build_storyteller_context(game_state)
        advantage = self._evaluate_team_advantage(StorytellerDecisionContext(
            truth_view={}, public_state={}, event_log_so_far=[], private_delivery_history=[], balance_context=context, suppression_map={}
        ))

        advantage_text = "正义方大优" if advantage > 2 else ("正义方小优" if advantage > 0.5 else ("邪恶方大优" if advantage < -2 else ("邪恶方小优" if advantage < -0.5 else "局势均势")))

        prompt = f"""你是一名《血染钟楼》的说书人（上帝视角）。
当前核心局势：
- 阶段：{context['phase']} (Day {context['day_number']}, Round {context['round_number']})
- 人数：正义 {context['alive_good']} 存活 / 邪恶 {context['alive_evil']} 存活
- 系统客观评估：{advantage_text} (平衡分值: {advantage:.2f})
- 近期关键裁量记录：{context['recent_judgements']}

作为说书人，你的核心目标是让对局悬念迭起、充满戏剧性。如果某一方优势过大，你需要考虑在规则允许的范围内（如利用中毒、醉酒、信息技能的模糊地带）暗中帮助劣势方。

请以第一人称写一段简短的“说书人内心独白”（控制在100字以内），需包含：
1. 你对当前场上哪名玩家或哪个阵营处境最危险的敏锐洞察。
2. 你的下一步隐秘计划（例如：打算如何通过假信息、或者报幕氛围来扰乱优势方的判断，维持脆弱的平衡）。

请直接输出这段极具掌控力与反派魅力的独白，不要有任何客套话。"""
        try:
            from src.llm.base_backend import Message
            response = await self.backend.generate([Message(role="system", content=prompt)])
            thinking = response.strip() if response else "维持当前平衡。"
            self.record_judgement(
                "strategic_analysis",
                decision=advantage_text,
                reason=thinking,
                advantage_score=advantage,
                phase=context['phase'],
                day_number=context['day_number']
            )
            return thinking
        except Exception as e:
            logger.warning(f"analyze_game_situation failed: {e}")
            return "分析失败，维持平衡。"

    def export_judgements(self) -> list[dict[str, Any]]:
        """[A3-DATA-4] 导出完整的说书人判决账本，供复盘和评估使用。"""
        return list(self.decision_ledger)

    def export_judgement_history(self, game_id: str, limit: int | None = None) -> dict[str, Any]:
        """[A3-DATA-4] 导出与单局 game_id 对齐的说书人判决数据。"""
        judgements = self.decision_ledger[-limit:] if limit is not None else self.decision_ledger
        exported = []
        for entry in judgements:
            exported.append(
                {
                    "game_id": game_id,
                    **self._jsonable(entry),
                }
            )
        categories = sorted({str(item.get("category", "")) for item in exported if item.get("category")})
        buckets = sorted({str(item.get("bucket", "")) for item in exported if item.get("bucket")})
        # [A3-ST-3] 增加最低门槛统计
        night_info_count = sum(1 for item in exported if item.get("category") == "night_info")
        delivers = sum(1 for item in exported if item.get("category") == "night_info" and item.get("decision") == "deliver")
        fallbacks = sum(1 for item in exported if "legacy_fallback" in str(item.get("adjudication_path", "")))
        suppressed = sum(1 for item in exported if item.get("decision") == "suppressed")
        distorted = sum(1 for item in exported if item.get("distortion_strategy") not in {None, "none"})
        
        statistics = {
            "judgement_count": len(exported),
            "night_info_total": night_info_count,
            "night_info_delivers": delivers,
            "night_info_suppressed": suppressed,
            "night_info_distorted": distorted,
            "fallback_count": fallbacks,
            "fallback_rate": round(fallbacks / len(exported), 3) if exported else 0,
            "distortion_rate": round(distorted / night_info_count, 3) if night_info_count else 0,
        }

        return {
            "game_id": game_id,
            "judgement_count": len(exported),
            "categories": categories,
            "buckets": buckets,
            "statistics": statistics,
            "judgements": exported,
            "recent_summary": self.summarize_recent_judgements(min(len(exported), 10)),
        }

    def summarize_recent_judgements(self, limit: int = 5) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for entry in self.get_recent_judgements(limit):
            details = {
                key: value
                for key, value in entry.items()
                if key not in {
                    "category",
                    "decision",
                    "reason",
                    "bucket",
                    "phase",
                    "day_number",
                    "round_number",
                    "trace_id",
                    "adjudication_path",
                    "distortion_strategy",
                }
            }
            summaries.append(
                {
                    "category": entry.get("category", ""),
                    "bucket": entry.get("bucket", ""),
                    "decision": entry.get("decision", ""),
                    "reason": entry.get("reason"),
                    "phase": entry.get("phase"),
                    "day_number": entry.get("day_number"),
                    "round_number": entry.get("round_number"),
                    "trace_id": entry.get("trace_id"),
                    "adjudication_path": entry.get("adjudication_path"),
                    "distortion_strategy": entry.get("distortion_strategy"),
                    "summary": ", ".join(
                        f"{key}={self._stringify(value)}" for key, value in details.items()
                    )
                    if details
                    else "no_details",
                }
            )
        return summaries

    def build_decision_context(self, game_state: GameState, recent_limit: int = 8) -> StorytellerDecisionContext:
        """[A3-ST-1] 统一说书人裁量输入边界。"""
        balance_context = self._build_storyteller_context(game_state)
        return StorytellerDecisionContext(
            truth_view=self._build_truth_view(game_state),
            public_state=self._build_public_state_view(game_state),
            private_delivery_history=self._build_private_delivery_history(game_state),
            recent_judgements=self.summarize_recent_judgements(recent_limit),
            balance_context=balance_context,
        )

    def _build_truth_view(self, game_state: GameState) -> dict[str, Any]:
        return {
            "seat_order": list(game_state.seat_order),
            "players": [
                {
                    "player_id": player.player_id,
                    "name": player.name,
                    "true_role_id": player.true_role_id or player.role_id,
                    "perceived_role_id": player.perceived_role_id,
                    "role_type": self._role_type_for_role_id(player.true_role_id or player.role_id).value if self._role_type_for_role_id(player.true_role_id or player.role_id) else None,
                    "current_team": (player.current_team or player.team).value,
                    "is_alive": player.is_alive,
                    "is_poisoned": player.is_poisoned,
                    "is_drunk": player.is_drunk,
                    "ability_suppressed": player.ability_suppressed,
                    "statuses": [status.value for status in player.statuses],
                    "storyteller_notes": list(player.storyteller_notes),
                    "ongoing_effects": list(player.ongoing_effects),
                }
                for player in game_state.players
            ],
            "bluffs": list(game_state.bluffs),
            "payload": self._jsonable(game_state.payload),
        }

    def _build_public_state_view(self, game_state: GameState) -> dict[str, Any]:
        public_events = [
            {
                "event_type": event.event_type,
                "phase": event.phase.value,
                "round_number": event.round_number,
                "trace_id": event.trace_id,
                "actor": event.actor,
                "target": event.target,
                "payload": self._jsonable(event.payload),
            }
            for event in game_state.event_log
            if event.visibility == Visibility.PUBLIC
        ]
        return {
            "phase": game_state.phase.value,
            "round_number": game_state.round_number,
            "day_number": game_state.day_number,
            "alive_count": game_state.alive_count,
            "players": [
                {
                    "player_id": player.player_id,
                    "name": player.name,
                    "is_alive": player.is_alive,
                    "public_claim_role_id": player.public_claim_role_id,
                }
                for player in game_state.players
            ],
            "public_events": public_events[-40:],
            "nomination_history": self._jsonable(game_state.payload.get("nomination_history", [])),
        }

    def _build_private_delivery_history(self, game_state: GameState) -> list[dict[str, Any]]:
        deliveries = []
        for event in game_state.event_log:
            if event.event_type != "private_info_delivered":
                continue
            deliveries.append(
                {
                    "target": event.target,
                    "phase": event.phase.value,
                    "round_number": event.round_number,
                    "trace_id": event.trace_id,
                    "payload": self._jsonable(event.payload),
                }
            )
        return deliveries[-40:]

    def _build_event_log_so_far(self, game_state: GameState) -> list[dict[str, Any]]:
        return [
            {
                "event_type": event.event_type,
                "phase": event.phase.value,
                "round_number": event.round_number,
                "trace_id": event.trace_id,
                "actor": event.actor,
                "target": event.target,
                "visibility": event.visibility.value,
                "payload": self._jsonable(event.payload),
            }
            for event in game_state.event_log[-80:]
        ]

    def _build_storyteller_context(self, game_state: GameState) -> dict[str, Any]:
        alive_good = sum(1 for player in game_state.players if player.is_alive and (player.current_team or player.team) == Team.GOOD)
        alive_evil = sum(1 for player in game_state.players if player.is_alive and (player.current_team or player.team) == Team.EVIL)
        hard_lock_risk = alive_evil == 0 or alive_good <= 1
        early_end_risk = game_state.day_number <= 2 and (alive_good <= 2 or alive_evil == 1)
        return {
            "alive_good": alive_good,
            "alive_evil": alive_evil,
            "alive_total": game_state.alive_count,
            "phase": game_state.phase.value,
            "day_number": game_state.day_number,
            "round_number": game_state.round_number,
            "hard_lock_risk": hard_lock_risk,
            "early_end_risk": early_end_risk,
            "recent_judgements": self.summarize_recent_judgements(8),
        }

    def _evaluate_team_advantage(self, context: StorytellerDecisionContext) -> float:
        """[A3-ST-5] 评估当前对局优势方。正值代表正义阵营优势，负值代表邪恶阵营优势。"""
        # 1. 人数优势
        alive_good = context.balance_context.get("alive_good", 0)
        alive_evil = context.balance_context.get("alive_evil", 0)
        margin = alive_good - alive_evil
        
        # 2. 进度修正 (前期好人多是正常的)
        day = context.balance_context.get("day_number", 1)
        if day <= 1:
            margin -= 1
            
        # 3. 风险修正
        if context.balance_context.get("hard_lock_risk"):
            margin -= 2 # 好人陷入僵局，某种意义上是坏人优势
            
        return float(margin)

    def build_balance_sample(self, game_state: GameState, player_id: str, role_id: str) -> dict[str, Any]:
        decision_context = self.build_decision_context(game_state, recent_limit=8)
        player = game_state.get_player(player_id)
        info, info_source, contract_mode = self._adjudicate_raw_info(game_state, player_id, role_id)
        adjudication_path = self._resolve_adjudication_path(role_id, info_source)
        chosen_info = info
        distortion_strategy = "none"
        suppressed = bool(player and player.ability_suppressed)
        if suppressed and info and player:
            chosen_info, distortion_strategy = self._apply_suppression_to_info(decision_context, role_id, info, player_id)

        candidates: list[dict[str, Any]] = []
        if info:
            candidates.append(
                {
                    "kind": "truthful",
                    "selected": not suppressed,
                    "info": self._jsonable(info),
                    "source": info_source,
                    "contract_mode": contract_mode,
                }
            )
        if suppressed and chosen_info:
            candidates.append(
                {
                    "kind": "suppressed_variant",
                    "selected": True,
                    "info": self._jsonable(chosen_info),
                    "source": info_source,
                    "contract_mode": contract_mode,
                    "distortion_strategy": distortion_strategy,
                }
            )

        return {
            "game_id": game_state.game_id,
            "script_id": game_state.config.script_id if game_state.config else "trouble_brewing",
            "seed": game_state.payload.get("seed"),
            "round_number": game_state.round_number,
            "day_number": game_state.day_number,
            "phase": game_state.phase.value,
            "player_id": player_id,
            "role_id": role_id,
            "players_truth": decision_context.truth_view,
            "players_public_state": decision_context.public_state,
            "event_log_so_far": self._build_event_log_so_far(game_state),
            "private_delivery_history": decision_context.private_delivery_history,
            "storyteller_context": decision_context.balance_context,
            "decision_context": self._jsonable(asdict(decision_context)),
            "candidate_adjudications": candidates,
            "chosen_adjudication": {
                "info": self._jsonable(chosen_info),
                "source": info_source,
                "contract_mode": contract_mode,
                "adjudication_path": adjudication_path,
                "distortion_strategy": distortion_strategy,
                "suppressed": suppressed,
            },
        }

    async def decide_drunk_role(self, script: Any, in_play_roles: list[str]) -> str:
        from src.engine.roles.base_role import get_role_class

        townsfolk_pool = [
            role_id
            for role_id in script.roles
            if get_role_class(role_id).get_definition().role_type == RoleType.TOWNSFOLK
            and role_id not in in_play_roles
        ]
        chosen = random.choice(townsfolk_pool) if townsfolk_pool else "washerwoman"
        storyteller_logger.info(
            "[decide_drunk_role] candidates=%s chosen=%s",
            ",".join(townsfolk_pool) if townsfolk_pool else "none",
            chosen,
        )
        self.record_judgement(
            "drunk_role",
            decision=chosen,
            candidates=townsfolk_pool,
        )
        return chosen

    async def build_night_order(self, game_state: GameState, phase: GamePhase) -> list[dict]:
        from src.engine.roles.base_role import get_role_class

        steps: list[dict] = []
        mismatches: list[dict[str, Any]] = []
        for player in game_state.get_alive_players():
            role_id = player.true_role_id or player.role_id
            role_cls = get_role_class(role_id)
            if not role_cls:
                continue
            role = role_cls()
            mismatch = validate_night_order_value(role_id, role.get_definition().ability.night_order)
            if mismatch:
                mismatches.append(mismatch)
            if role.can_act_at_phase(game_state, phase) and self.role_requires_player_choice(role_id):
                seat_index = (
                    game_state.seat_order.index(player.player_id)
                    if game_state.seat_order and player.player_id in game_state.seat_order
                    else len(game_state.players)
                )
                spec = get_night_order_spec(role_id)
                steps.append(
                    {
                        "player_id": player.player_id,
                        "role_id": role_id,
                        "night_order": role.get_definition().ability.night_order,
                        "official_order": spec.sort_order if spec else None,
                        "rulebook_index": spec.sort_order if spec else None,
                        "seat_index": seat_index,
                    }
                )
        ordered = sorted(
            steps,
            key=lambda item: get_night_order_sort_key(
                item["role_id"],
                item["night_order"],
                item.get("seat_index", 0),
            ),
        )
        tie_groups = build_night_order_tie_groups(ordered)
        storyteller_logger.info(
            "[build_night_order] phase=%s steps=%s",
            phase.value,
            ",".join(f"{step['role_id']}@{step['night_order']}" for step in ordered) if ordered else "none",
        )
        if mismatches:
            storyteller_logger.warning(
                "[build_night_order] canonical_mismatches=%s",
                json.dumps(mismatches, ensure_ascii=False),
            )
        if tie_groups:
            storyteller_logger.info(
                "[build_night_order] tie_groups=%s",
                json.dumps(tie_groups, ensure_ascii=False),
            )
        self.record_judgement(
            "night_order",
            decision="validated_with_mismatches" if mismatches else ("validated_with_ties" if tie_groups else ("validated" if ordered else "empty")),
            phase=phase.value,
            steps=ordered,
            canonical_reference="trouble_brewing_night_order",
            mismatches=mismatches,
            tie_groups=tie_groups,
            tie_strategy="canonical_rolebook_then_seat_order",
        )
        return ordered

    def role_requires_player_choice(self, role_id: str) -> bool:
        from src.engine.roles.base_role import get_role_class

        role_cls = get_role_class(role_id)
        if not role_cls:
            return False
        return role_cls.needs_night_target()

    def role_receives_storyteller_info(self, role_id: str) -> bool:
        from src.engine.roles.base_role import get_role_class

        role_cls = get_role_class(role_id)
        if not role_cls:
            return False
        return role_cls.uses_storyteller_adjudication()

    def _build_base_info(self, game_state: GameState, player_id: str, role_id: str) -> tuple[dict, str, str]:
        from src.engine.roles.base_role import get_role_class

        player = game_state.get_player(player_id)
        if not player:
            return {}, "missing_player", "unavailable"
        role_cls = get_role_class(role_id)
        if not role_cls:
            return {}, "missing_role", "unavailable"
        role = role_cls()
        contract_mode = "fixed_info" if role_cls.is_fixed_info_role() else "storyteller_info"
        info = role.build_storyteller_info(game_state, player) or {}
        if info:
            return info, "build_storyteller_info", contract_mode
        legacy_info = role.get_night_info(game_state, player) or {}
        if legacy_info:
            return legacy_info, "legacy_get_night_info", f"{contract_mode}.legacy_fallback"
        return {}, "empty", contract_mode

    def _adjudicate_raw_info(self, game_state: GameState, player_id: str, role_id: str) -> tuple[dict, str, str]:
        info, info_source, contract_mode = self._build_base_info(game_state, player_id, role_id)
        return info, info_source, contract_mode

    def _classify_info_scope(self, role_id: str, info_source: str, suppressed: bool) -> str:
        from src.engine.roles.base_role import get_role_class

        role_cls = get_role_class(role_id)
        if role_cls and role_cls.is_fixed_info_role():
            return "fixed_info.suppressed" if suppressed else "fixed_info"
        if role_cls and role_cls.uses_storyteller_adjudication():
            return "storyteller_info.suppressed" if suppressed else "storyteller_info"
        if info_source == "legacy_get_night_info":
            return "legacy_info.suppressed" if suppressed else "legacy_info"
        return "storyteller_info.suppressed" if suppressed else "storyteller_info"

    def _resolve_adjudication_path(self, role_id: str, info_source: str) -> str:
        from src.engine.roles.base_role import get_role_class

        role_cls = get_role_class(role_id)
        if info_source == "legacy_get_night_info":
            if role_cls and role_cls.is_fixed_info_role():
                return "fixed_info.legacy_fallback"
            if role_cls and role_cls.uses_storyteller_adjudication():
                return "storyteller_info.legacy_fallback"
            return "legacy_fallback"
        if role_cls and role_cls.is_fixed_info_role():
            return "fixed_info.adjudicated"
        if role_cls and role_cls.uses_storyteller_adjudication():
            return "storyteller_info.adjudicated"
        return "adjudicated"

    def _distort_fixed_info(self, context: StorytellerDecisionContext, role_id: str, info: dict, player_id: str) -> tuple[dict, str]:
        distorted = dict(info)
        actor_id = player_id
        if role_id in {"washerwoman", "librarian", "investigator"}:
            preferred_type = {
                "washerwoman": RoleType.TOWNSFOLK,
                "librarian": RoleType.OUTSIDER,
                "investigator": RoleType.MINION,
            }.get(role_id)
            target_player = self._pick_false_target_player(context, actor_id, preferred_type)
            if target_player:
                target_pid = target_player["player_id"]
                decoys = [p["player_id"] for p in context.truth_view.get("players", []) if p["player_id"] not in {actor_id, target_pid}]
                pair = [target_pid]
                if decoys:
                    pair.append(random.choice(decoys))
                random.shuffle(pair)
                distorted["players"] = pair
                distorted["role_seen"] = target_player.get("true_role_id") or target_player.get("role_id")
            if role_id == "librarian":
                distorted["has_outsider"] = True
            return distorted, f"{role_id}_pair_role_seen_distortion"
        if role_id == "chef":
            actual_pairs = distorted.get("pairs", 0)
            advantage = self._evaluate_team_advantage(context)
            if advantage > 1.0:
                # 好人优势，给个假信息误导（通常是把 0 变成 1，或者把 1 变成 0）
                distorted["pairs"] = 1 if actual_pairs == 0 else 0
                return distorted, "chef_pairs_offset.help_evil"
            return distorted, "chef_pairs_passthrough"
        if role_id == "empath":
            actual_count = distorted.get("evil_count", 0)
            advantage = self._evaluate_team_advantage(context)
            if advantage > 1.0:
                # 好人优势，给个假信息
                distorted["evil_count"] = 1 if actual_count == 0 else 0
                return distorted, "empath_binary_flip.help_evil"
            elif advantage < -1.0:
                # 坏人优势，尽量给真信息（即使中毒也可能给真的，或者给个比较温和的假信息）
                # 这里我们保持原样，因为 _distort_fixed_info 只在能力被抑制时调用。
                # 如果要“尽量给真信息”，我们可以选择不翻转。
                return distorted, "empath_mercy_truth.help_good"
            
            distorted["evil_count"] = 1 if actual_count == 0 else 0
            return distorted, "empath_binary_flip.default"
        if role_id == "undertaker":
            players = context.truth_view.get("players", [])
            if players:
                distorted["role_seen"] = random.choice([p.get("true_role_id") or p.get("role_id") for p in players])
            return distorted, "undertaker_random_role_seen"
        if role_id == "spy":
            book = [dict(entry) for entry in distorted.get("book", [])]
            if book:
                idx = 0 if len(book) == 1 else random.randrange(len(book))
                entry = dict(book[idx])
                actual_role = entry.get("role_id")
                false_role_type_val = self._role_type_for_role_id(actual_role).value if self._role_type_for_role_id(actual_role) else None
                false_role_type = RoleType(false_role_type_val) if false_role_type_val else None
                false_role_ids = self._role_ids_of_type(false_role_type, exclude_role_id=actual_role) if false_role_type else []
                if not false_role_ids:
                    false_role_ids = [role for role in self._all_role_ids() if role != actual_role]
                if false_role_ids:
                    false_role = random.choice(false_role_ids)
                    false_role_cls = self._role_class(false_role)
                    if false_role_cls:
                        entry["role_id"] = false_role
                        entry["team"] = false_role_cls.get_definition().team.value
                book[idx] = entry
                distorted["book"] = book
            return distorted, "spy_book_single_entry_distortion"
        return distorted, "fixed_info_passthrough"

    def _distort_storyteller_info(self, context: StorytellerDecisionContext, role_id: str, info: dict) -> tuple[dict, str]:
        distorted = dict(info)
        if role_id == "fortune_teller":
            actual = distorted.get("has_demon", False)
            advantage = self._evaluate_team_advantage(context)
            if advantage > 1.0:
                # 好人优势，误导他们：如果是假，给真；如果是真，给假
                distorted["has_demon"] = not actual
                return distorted, "fortune_teller_mislead.help_evil"
            elif advantage < -1.0:
                # 坏人优势，尽量给真信息（不翻转）
                return distorted, "fortune_teller_truth.help_good"
            distorted["has_demon"] = not actual
            return distorted, "fortune_teller_boolean_flip"
        
        if role_id == "ravenkeeper":
            advantage = self._evaluate_team_advantage(context)
            if advantage < -1.0:
                # 坏人优势大，毒死了也大发慈悲给个真信息
                return distorted, "ravenkeeper_truth.help_good"
            
            # 给个错误的身份
            actual_role = distorted.get("role_id")
            false_roles = [r for r in self._all_role_ids() if r != actual_role]
            if false_roles:
                distorted["role_id"] = random.choice(false_roles)
            return distorted, "ravenkeeper_random_role_distortion"

        return distorted, "storyteller_info_passthrough"

    async def _apply_suppression_to_info_async(self, context: StorytellerDecisionContext, role_id: str, info: dict, player_id: str) -> tuple[dict, str]:
        """异步版本的抑制逻辑，支持 LLM 介入。"""
        from src.engine.roles.base_role import get_role_class

        role_cls = get_role_class(role_id)
        
        # 如果开启了 AI 模式且有 backend，尝试用 LLM 做“更有趣”的虚假信息选择
        if self.mode == "auto" and self.backend and role_cls and not role_cls.is_fixed_info_role():
             # 目前暂未实现全量 LLM 虚假信息生成，先走增强的启发式，未来可在此注入 LLM 决策
             pass

        if role_cls and role_cls.is_fixed_info_role():
            return self._distort_fixed_info(context, role_id, info, player_id)
        if role_cls and role_cls.uses_storyteller_adjudication():
            return self._distort_storyteller_info(context, role_id, info)
        return dict(info), "unspecified_suppression_passthrough"

    def _apply_suppression_to_info(self, context: StorytellerDecisionContext, role_id: str, info: dict, player_id: str) -> tuple[dict, str]:
        # 兼容同步调用
        from src.engine.roles.base_role import get_role_class
        role_cls = get_role_class(role_id)
        if role_cls and role_cls.is_fixed_info_role():
            return self._distort_fixed_info(context, role_id, info, player_id)
        if role_cls and role_cls.uses_storyteller_adjudication():
            return self._distort_storyteller_info(context, role_id, info)
        return dict(info), "unspecified_suppression_passthrough"

    def _pick_false_role_seen(self, game_state: GameState, role_id: str, excluded_roles: set[str]) -> str:
        from src.engine.roles.base_role import get_all_role_ids, get_role_class

        preferred_type = {
            "washerwoman": RoleType.TOWNSFOLK,
            "librarian": RoleType.OUTSIDER,
            "investigator": RoleType.MINION,
        }.get(role_id)

        candidate_roles: list[str] = []
        if preferred_type:
            for player in game_state.players:
                actual_role_id = player.true_role_id or player.role_id
                if actual_role_id in excluded_roles:
                    continue
                role_cls = get_role_class(actual_role_id)
                if role_cls and role_cls.get_definition().role_type == preferred_type:
                    candidate_roles.append(actual_role_id)

            if not candidate_roles:
                for actual_role_id in get_all_role_ids():
                    if actual_role_id in excluded_roles:
                        continue
                    role_cls = get_role_class(actual_role_id)
                    if role_cls and role_cls.get_definition().role_type == preferred_type:
                        candidate_roles.append(actual_role_id)

        if not candidate_roles:
            candidate_roles = [role_id for role_id in get_all_role_ids() if role_id not in excluded_roles]

        return random.choice(candidate_roles) if candidate_roles else "unknown"

    def _role_type_for_role_id(self, role_id: str | None) -> RoleType | None:
        if not role_id:
            return None
        role_cls = self._role_class(role_id)
        if not role_cls:
            return None
        return role_cls.get_definition().role_type

    def _pick_false_target_player(
        self,
        context: StorytellerDecisionContext,
        actor_id: str | None,
        preferred_type: RoleType | None,
    ) -> dict[str, Any] | None:
        eligible_players = [p for p in context.truth_view.get("players", []) if p["player_id"] != actor_id]
        if not eligible_players:
            return None
        
        pref_val = preferred_type.value if preferred_type else None
        typed_players = [
            p for p in eligible_players
            if pref_val and p.get("role_type") == pref_val
        ]
        pool = typed_players or eligible_players
        
        # [A3-ST-5] 主动干预：如果好人优势，优先选邪恶队友作为假信息目标，帮他们“穿衣服”
        advantage = self._evaluate_team_advantage(context)
        if advantage > 1.0:
            evil_pool = [p for p in pool if p.get("current_team") == "evil"]
            if evil_pool:
                return random.choice(evil_pool)
                
        return random.choice(pool)

    async def decide_night_info(self, game_state: GameState, player_id: str, role_id: str) -> dict:
        context = self.build_decision_context(game_state)
        player_truth = context.get_player(player_id)
        if not player_truth:
            return {}
        
        if not self.role_receives_storyteller_info(role_id):
            storyteller_logger.info(
                "[decide_night_info] player=%s role=%s skipped=no_storyteller_info",
                player_id,
                role_id,
            )
            self.record_judgement(
                "night_info",
                decision="skip",
                reason="no_storyteller_info",
                player_id=player_id,
                role_id=role_id,
                phase=context.public_state["phase"],
                day_number=context.public_state["day_number"],
                round_number=context.public_state["round_number"],
            )
            return {}

        info, info_source, contract_mode = self._adjudicate_raw_info(game_state, player_id, role_id)
        if not info:
            storyteller_logger.info(
                "[decide_night_info] player=%s role=%s skipped=no_info",
                player_id,
                role_id,
            )
            self.record_judgement(
                "night_info",
                decision="skip",
                reason="no_info",
                player_id=player_id,
                role_id=role_id,
                source=info_source,
                contract_mode=contract_mode,
                phase=game_state.phase.value,
                day_number=game_state.day_number,
                round_number=game_state.round_number,
            )
            return {}

        info_scope = self._classify_info_scope(role_id, info_source, context.is_suppressed(player_id))
        adjudication_path = self._resolve_adjudication_path(role_id, info_source)
        if context.is_suppressed(player_id):
            distorted, distortion_strategy = await self._apply_suppression_to_info_async(context, role_id, info, player_id)
            storyteller_logger.info(
                "[decide_night_info] player=%s role=%s suppressed=true info_type=%s summary=%s",
                player_id,
                role_id,
                distorted.get("type", "unknown"),
                self._summarize_info(distorted),
            )
            self.record_judgement(
                "night_info",
                decision="suppressed",
                player_id=player_id,
                role_id=role_id,
                info_type=distorted.get("type", "unknown"),
                scope=info_scope,
                summary=self._summarize_info(distorted),
                source=info_source,
                contract_mode=contract_mode,
                adjudication_path=adjudication_path,
                distortion_strategy=distortion_strategy,
                phase=context.public_state["phase"],
                day_number=context.public_state["day_number"],
                round_number=context.public_state["round_number"],
            )
            return distorted
        storyteller_logger.info(
            "[decide_night_info] player=%s role=%s suppressed=false info_type=%s summary=%s",
            player_id,
            role_id,
            info.get("type", "unknown"),
            self._summarize_info(info),
        )
        self.record_judgement(
            "night_info",
            decision="deliver",
            player_id=player_id,
            role_id=role_id,
            info_type=info.get("type", "unknown"),
            scope=info_scope,
            summary=self._summarize_info(info),
            source=info_source,
            contract_mode=contract_mode,
            adjudication_path=adjudication_path,
            distortion_strategy="none",
            phase=context.public_state["phase"],
            day_number=context.public_state["day_number"],
            round_number=context.public_state["round_number"],
        )
        return info

    def _summarize_info(self, info: dict) -> str:
        if not info:
            return "empty"
        summary_bits = []
        for key in ("type", "title", "role_seen", "pairs", "evil_count", "has_demon"):
            if key in info:
                summary_bits.append(f"{key}={info[key]}")
        if "players" in info and isinstance(info["players"], list):
            summary_bits.append(f"players={len(info['players'])}")
        if "book" in info and isinstance(info["book"], list):
            summary_bits.append(f"book={len(info['book'])}")
        if "teammates" in info and isinstance(info["teammates"], list):
            summary_bits.append(f"teammates={len(info['teammates'])}")
        return ", ".join(summary_bits) if summary_bits else "details_present"

    def _all_role_ids(self) -> list[str]:
        from src.engine.roles.base_role import get_all_role_ids

        return list(get_all_role_ids())

    def _role_class(self, role_id: str):
        from src.engine.roles.base_role import get_role_class

        return get_role_class(role_id)

    def _role_ids_of_type(self, role_type: RoleType, exclude_role_id: str | None = None) -> list[str]:
        ids: list[str] = []
        for role_id in self._all_role_ids():
            if role_id == exclude_role_id:
                continue
            role_cls = self._role_class(role_id)
            if role_cls and role_cls.get_definition().role_type == role_type:
                ids.append(role_id)
        return ids

    async def narrate_phase(self, game_state: GameState) -> str:
        phase_names = {
            GamePhase.SETUP: "小镇尚未苏醒，命运正在分配身份。",
            GamePhase.FIRST_NIGHT: "夜幕初降，每双闭上的眼睛都藏着秘密。",
            GamePhase.DAY_DISCUSSION: "晨雾散开，谎言与真相同时开口。",
            GamePhase.NOMINATION: "怀疑开始聚焦，绞索在空气里慢慢收紧。",
            GamePhase.VOTING: "请注视彼此，举手将决定谁走上断头台。",
            GamePhase.EXECUTION: "裁决即将落下，小镇将为今天的选择付出代价。",
            GamePhase.NIGHT: "夜色再次降临，真正的行动在黑暗里发生。",
            GamePhase.GAME_OVER: "故事落幕，所有隐藏的名字都将被翻开。",
        }
        # [A3-ST-5] 氛围引导：根据对局形势增加报幕风味
        context = self.build_decision_context(game_state)
        advantage = self._evaluate_team_advantage(context)
        flavor = ""
        
        if game_state.phase == GamePhase.DAY_DISCUSSION:
            if advantage > 2.0:
                flavor = " 正义的锋芒势不可挡。"
            elif advantage < -1.0:
                flavor = " 邪恶的阴霾挥之不去，小镇似乎命悬一线。"
        elif game_state.phase == GamePhase.NIGHT:
            if game_state.day_number >= 3:
                flavor = " 鲜血染红了月色，这一夜注定不平静。"

        narration = phase_names.get(game_state.phase, f"现在进入 {game_state.phase.value} 阶段。") + flavor
        storyteller_logger.info(
            "[narrate_phase] phase=%s narration=%s",
            game_state.phase.value,
            narration,
        )
        self.record_judgement(
            "narration",
            decision="announce",
            phase=game_state.phase.value,
            day_number=game_state.day_number,
            round_number=game_state.round_number,
            narration=narration,
        )
        return narration

    async def decide_initial_setup_info(self, game_state: GameState) -> GameState:
        """为所有需要的角色预先决定初始信息（如：洗衣妇看到的两个玩家和角色，厨师得到的邻座数等）。"""
        new_payload = dict(game_state.payload)
        
        # 1. 预报身份类角色
        for player in game_state.players:
            # [A3-ST-BUGFIX] 使用 perceived_role_id 确保酒鬼也能在 SETUP 阶段生成初始信息载荷
            role_id = player.perceived_role_id or player.role_id
            if role_id in {"washerwoman", "librarian", "investigator", "chef"}:
                from src.engine.roles.base_role import get_role_class
                role_cls = get_role_class(role_id)
                if role_cls:
                    role_instance = role_cls()
                    # 生成初始信息。对于酒鬼，这里生成的是基于他自以为身份的“事实”信息，
                    # 实际发放时会在 _distribute_night_info 中因 ability_suppressed 被打乱。
                    info = role_instance.build_storyteller_info(game_state, player)
                    if info:
                        key = f"initial_info:{role_id}:{player.player_id}"
                        new_payload[key] = info
                        storyteller_logger.info(f"[decide_initial_setup_info] player={player.player_id} role={role_id} (perceived) info={info}")
                        self.record_judgement("initial_setup_info", decision="preset", player_id=player.player_id, role_id=role_id, info=info, phase=game_state.phase.value, day_number=game_state.day_number, round_number=game_state.round_number)
        
        # 2. 预言家宿敌 (Red Herring)
        # [A3-ST-5] 智能选择红鲱鱼：优先选择对当前局势有“调节”作用的好人。
        # 比如：选择一个可疑的好人作为红鲱鱼，可以让预言家查验他时得到“有恶魔”的结果，增加干扰。
        ft_player = next((p for p in game_state.players if (p.perceived_role_id or p.role_id) == "fortune_teller"), None)
        if ft_player and "fortune_teller_red_herring" not in new_payload:
            # 候选人：非恶魔的好人（且不是占卜师自己）
            candidates = [p for p in game_state.players if p.team == Team.GOOD and p.player_id != ft_player.player_id]
            if candidates:
                # [A3-ST-5] 智能逻辑：
                # 如果正义方初始强度高，红鲱鱼选个“干净”的人（比如调查员点名过的人），让预言家查出“有恶魔”，增加正义方内耗。
                # 此处目前基于基础评分系统
                context = self.build_decision_context(game_state)
                advantage = self._evaluate_team_advantage(context)
                
                # 如果局势对正义方有利（advantage > 0），选个看起来“像好人”的人作为红鲱鱼来迷惑他们。
                if advantage >= 0:
                    # 倾向于选择非关键信息位的好人作为宿敌
                    low_prio_roles = {RoleType.OUTSIDER, RoleType.TOWNSFOLK}
                    red_herring = random.choice(candidates) # 兜底
                else:
                    # 局势不利于正义方时，随便选一个，尽量不干扰核心推导。
                    red_herring = random.choice(candidates)
                
                new_payload["fortune_teller_red_herring"] = red_herring.player_id
                storyteller_logger.info(f"[decide_initial_setup_info] fortune_teller_red_herring set to {red_herring.player_id} (advantage={advantage:.2f})")
                self.record_judgement("initial_setup_info", decision="set_red_herring", target=red_herring.player_id, reason=f"balancing_advantage_{advantage:.2f}", phase=game_state.phase.value, day_number=game_state.day_number, round_number=game_state.round_number)

        return game_state.with_update(payload=new_payload)

    async def decide_misregistration(self, game_state: GameState) -> GameState:
        """为间谍和隐士做出误报决策。"""
        new_payload = dict(game_state.payload)
        context = self.build_decision_context(game_state)
        advantage = self._evaluate_team_advantage(context)
        
        for player in game_state.players:
            role_id = player.true_role_id or player.role_id
            if role_id == "recluse":
                # [A3-ST-5] 智能隐士误报：
                # 如果正义方有优势 (advantage > 1.0)，隐士大概率误报为邪恶或恶魔，增加干扰。
                # 如果邪恶方有优势 (advantage < -1.0)，隐士保持登记为好人，避免送人头。
                should_misregister = False
                if advantage > 1.0:
                    should_misregister = random.random() < 0.8
                elif advantage < -1.0:
                    should_misregister = random.random() < 0.2
                else:
                    should_misregister = random.random() < 0.5

                if should_misregister:
                    team = Team.EVIL
                    role_type = random.choice([RoleType.MINION, RoleType.DEMON])
                    new_payload[f"misregistration:team:{player.player_id}"] = team.value
                    new_payload[f"misregistration:type:{player.player_id}"] = role_type.value
                    self.record_judgement("misregistration", decision="active", player_id=player.player_id, role_id="recluse", team=team.value, type=role_type.value, reason=f"balancing_advantage_{advantage:.2f}", phase=game_state.phase.value, day_number=game_state.day_number, round_number=game_state.round_number)
                else:
                    new_payload.pop(f"misregistration:team:{player.player_id}", None)
                    new_payload.pop(f"misregistration:type:{player.player_id}", None)
            
            elif role_id == "spy":
                # [A3-ST-5] 智能间谍误报：
                # 如果正义方有优势 (advantage > 1.0)，间谍大概率误报为好人或村民，降低被发现概率。
                # 如果邪恶方有优势 (advantage < -1.0)，间谍保持登记为邪恶，甚至主动引火上身吸引注意力。
                should_misregister = False
                if advantage > 1.0:
                    should_misregister = random.random() < 0.8
                elif advantage < -1.0:
                    should_misregister = random.random() < 0.2
                else:
                    should_misregister = random.random() < 0.5

                if should_misregister:
                    team = Team.GOOD
                    role_type = RoleType.TOWNSFOLK
                    new_payload[f"misregistration:team:{player.player_id}"] = team.value
                    new_payload[f"misregistration:type:{player.player_id}"] = role_type.value
                    self.record_judgement("misregistration", decision="active", player_id=player.player_id, role_id="spy", team=team.value, type=role_type.value, reason=f"balancing_advantage_{advantage:.2f}", phase=game_state.phase.value, day_number=game_state.day_number, round_number=game_state.round_number)
                else:
                    new_payload.pop(f"misregistration:team:{player.player_id}", None)
                    new_payload.pop(f"misregistration:type:{player.player_id}", None)
                    
        return game_state.with_update(payload=new_payload)

    async def get_human_storyteller_step(self, game_state: GameState, phase: GamePhase) -> dict:
        order = await self.build_night_order(game_state, phase)
        step = {
            "mode": self.mode,
            "phase": phase.value,
            "pending_steps": order,
            "next_step": order[0] if order else None,
            "recent_judgements": self.summarize_recent_judgements(),
        }
        storyteller_logger.info(
            "[get_human_storyteller_step] phase=%s next_step=%s pending=%s",
            phase.value,
            step["next_step"]["role_id"] if step["next_step"] else "none",
            len(order),
        )
        self.record_judgement(
            "human_step",
            decision="report",
            phase=phase.value,
            day_number=game_state.day_number,
            round_number=game_state.round_number,
            pending=len(order),
            next_step=step["next_step"]["role_id"] if step["next_step"] else None,
            summary_count=len(step["recent_judgements"]),
        )
        return step
