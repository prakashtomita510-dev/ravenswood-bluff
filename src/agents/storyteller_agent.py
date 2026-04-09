"""说书人代理 (Storyteller Agent)。"""

from __future__ import annotations

import json
import logging
import os
import random
from typing import Any

from src.llm.openai_backend import OpenAIBackend
from src.state.game_state import GamePhase, GameState, RoleType, Team

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


class StorytellerAgent:
    def __init__(self, backend: OpenAIBackend, mode: str = "auto"):
        self.backend = backend
        self.mode = mode
        self.name = "Storyteller"
        self.player_id = "storyteller"
        self.decision_ledger: list[dict[str, Any]] = []

    def _stringify(self, value: Any) -> str:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return str(value)
        return json.dumps(value, ensure_ascii=False, default=str)

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

    def record_judgement(self, category: str, decision: str, reason: str | None = None, **fields: Any) -> dict[str, Any]:
        entry_fields = dict(fields)
        entry_fields.setdefault("bucket", self._classify_judgement_bucket(category, decision, entry_fields))
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

    def summarize_recent_judgements(self, limit: int = 5) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for entry in self.get_recent_judgements(limit):
            details = {
                key: value
                for key, value in entry.items()
                if key not in {"category", "decision", "reason"}
            }
            summaries.append(
                {
                    "category": entry.get("category", ""),
                    "decision": entry.get("decision", ""),
                    "reason": entry.get("reason"),
                    "summary": ", ".join(
                        f"{key}={self._stringify(value)}" for key, value in details.items()
                    )
                    if details
                    else "no_details",
                }
            )
        return summaries

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
        for player in game_state.get_alive_players():
            role_id = player.true_role_id or player.role_id
            role_cls = get_role_class(role_id)
            if not role_cls:
                continue
            role = role_cls()
            if role.can_act_at_phase(game_state, phase) and self.role_requires_player_choice(role_id):
                steps.append(
                    {
                        "player_id": player.player_id,
                        "role_id": role_id,
                        "night_order": role.get_definition().ability.night_order,
                    }
                )
        ordered = sorted(steps, key=lambda item: item["night_order"])
        storyteller_logger.info(
            "[build_night_order] phase=%s steps=%s",
            phase.value,
            ",".join(f"{step['role_id']}@{step['night_order']}" for step in ordered) if ordered else "none",
        )
        self.record_judgement(
            "night_order",
            decision="queued" if ordered else "empty",
            phase=phase.value,
            steps=ordered,
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

    def _build_base_info(self, game_state: GameState, player_id: str, role_id: str) -> tuple[dict, str]:
        from src.engine.roles.base_role import get_role_class

        player = game_state.get_player(player_id)
        if not player:
            return {}, "missing_player"
        role_cls = get_role_class(role_id)
        if not role_cls:
            return {}, "missing_role"
        role = role_cls()
        info = role.build_storyteller_info(game_state, player) or {}
        if info:
            return info, "build_storyteller_info"
        legacy_info = role.get_night_info(game_state, player) or {}
        if legacy_info:
            return legacy_info, "legacy_get_night_info"
        return {}, "empty"

    def _classify_info_scope(self, game_state: GameState, role_id: str, player: Any, info_source: str, suppressed: bool) -> str:
        from src.engine.roles.base_role import get_role_class

        role_cls = get_role_class(role_id)
        if role_cls and role_cls.is_fixed_info_role():
            return "fixed_info.suppressed" if suppressed else "fixed_info"
        if role_cls and role_cls.uses_storyteller_adjudication():
            return "storyteller_info.suppressed" if suppressed else "storyteller_info"
        if info_source == "legacy_get_night_info":
            return "legacy_info.suppressed" if suppressed else "legacy_info"
        return "storyteller_info.suppressed" if suppressed else "storyteller_info"

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

    async def decide_night_info(self, game_state: GameState, player_id: str, role_id: str) -> dict:
        player = game_state.get_player(player_id)
        if not player:
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
            )
            return {}

        info, info_source = self._build_base_info(game_state, player_id, role_id)
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
            )
            return {}

        info_scope = self._classify_info_scope(game_state, role_id, player, info_source, player.ability_suppressed)
        if player.ability_suppressed:
            distorted = self._distort_info(game_state, role_id, info, player)
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

    def _distort_info(self, game_state: GameState, role_id: str, info: dict, player: Any) -> dict:
        distorted = dict(info)
        actor_id = getattr(player, "player_id", None)
        if role_id in {"washerwoman", "librarian", "investigator"}:
            candidate_ids = [p.player_id for p in game_state.players if p.player_id != actor_id]
            random.shuffle(candidate_ids)
            distorted["players"] = candidate_ids[:2]
            excluded_roles: set[str] = set()
            if distorted.get("role_seen"):
                excluded_roles.add(str(distorted["role_seen"]))
            distorted["role_seen"] = self._pick_false_role_seen(game_state, role_id, excluded_roles)
            if role_id == "librarian":
                distorted["has_outsider"] = True
        elif role_id == "chef":
            distorted["pairs"] = max(0, min(game_state.alive_count, distorted.get("pairs", 0) + 1))
        elif role_id == "empath":
            distorted["evil_count"] = 1 if distorted.get("evil_count", 0) == 0 else 0
        elif role_id == "undertaker":
            distorted["role_seen"] = random.choice([p.true_role_id or p.role_id for p in game_state.players])
        elif role_id == "fortune_teller":
            distorted["has_demon"] = not distorted.get("has_demon", False)
        elif role_id == "spy":
            book = [dict(entry) for entry in distorted.get("book", [])]
            if book:
                idx = 0 if len(book) == 1 else random.randrange(len(book))
                entry = dict(book[idx])
                actual_role = entry.get("role_id")
                false_role_type = self._role_type_for_role_id(actual_role)
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
        return distorted

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

    def _role_type_for_role_id(self, role_id: str | None) -> RoleType | None:
        if not role_id:
            return None
        role_cls = self._role_class(role_id)
        if not role_cls:
            return None
        return role_cls.get_definition().role_type

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
        narration = phase_names.get(game_state.phase, f"现在进入 {game_state.phase.value} 阶段。")
        storyteller_logger.info(
            "[narrate_phase] phase=%s narration=%s",
            game_state.phase.value,
            narration,
        )
        self.record_judgement(
            "narration",
            decision="announce",
            phase=game_state.phase.value,
            narration=narration,
        )
        return narration

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
            pending=len(order),
            next_step=step["next_step"]["role_id"] if step["next_step"] else None,
            summary_count=len(step["recent_judgements"]),
        )
        return step
