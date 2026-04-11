"""游戏主循环 (Game Orchestrator)。"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import uuid
from typing import Any

from src.agents.base_agent import BaseAgent
from src.content.trouble_brewing_terms import get_role_name
from src.engine.nomination import NominationManager
from src.engine.phase_manager import PhaseManager
from src.engine.rule_engine import RuleEngine
from src.engine.roles.base_role import get_role_class
from src.engine.victory_checker import VictoryChecker
from src.orchestrator.event_bus import EventBus
from src.orchestrator.information_broker import InformationBroker
from src.state.event_log import EventLog
from src.state.game_state import (
    AbilityTrigger,
    ChatMessage,
    GameConfig,
    GameEvent,
    GamePhase,
    GameState,
    GrimoireInfo,
    PlayerGrimoireInfo,
    PlayerState,
    PlayerStatus,
    RoleType,
    Team,
    Visibility,
)
from src.state.snapshot import SnapshotManager

logger = logging.getLogger(__name__)
storyteller_logger = logging.getLogger("storyteller")


class GameOrchestrator:
    """顶级容器，协调规则、Agent 和状态。"""

    def __init__(self, initial_state: GameState):
        self.state = initial_state
        self.phase_manager = PhaseManager()
        self.event_bus = EventBus()
        self.event_log = EventLog()
        self.snapshot_manager = SnapshotManager()
        self.broker = InformationBroker()
        self.storyteller_agent = None
        self.default_agent_backend = None
        self.winner: Team | None = None
        self._setup_done: asyncio.Future | None = None
        self._setup_started = False
        self.event_bus.subscribe("*", self._on_any_event, priority=0)

    def _make_trace_id(self, prefix: str) -> str:
        return f"{prefix}-{str(uuid.uuid4())[:8]}"

    def _get_storyteller_client_id(self) -> str | None:
        return self.state.config.storyteller_client_id if self.state.config else None

    def _update_payload(self, **kwargs: Any) -> None:
        payload = dict(self.state.payload)
        payload.update(kwargs)
        self.state = self.state.with_update(payload=payload)

    def _set_nomination_state(self, **kwargs: Any) -> None:
        payload = dict(self.state.payload)
        nomination_state = dict(payload.get("nomination_state", {}))
        nomination_state.update(kwargs)
        payload["nomination_state"] = nomination_state
        self.state = self.state.with_update(payload=payload)

    def _append_nomination_history(self, entry: dict[str, Any]) -> None:
        payload = dict(self.state.payload)
        day_number = self.state.day_number
        history = [
            item for item in payload.get("nomination_history", [])
            if item.get("day_number") == day_number
        ]
        history.append({"day_number": day_number, **entry})
        payload["nomination_history"] = history[-12:]
        self.state = self.state.with_update(payload=payload)

    def _player_label(self, player_id: str | None) -> str:
        player = self.state.get_player(player_id) if player_id else None
        return player.name if player else (player_id or "未知玩家")

    def _log_storyteller(self, event: str, **fields: Any) -> None:
        parts = [f"{key}={value}" for key, value in fields.items() if value is not None]
        storyteller_logger.info("[%s] %s", event, " ".join(parts) if parts else "")

    def _record_storyteller_judgement(self, category: str, decision: str, reason: str | None = None, **fields: Any) -> None:
        fields.setdefault("phase", self.state.phase.value)
        fields.setdefault("round_number", self.state.round_number)
        if self.storyteller_agent and hasattr(self.storyteller_agent, "record_judgement"):
            self.storyteller_agent.record_judgement(category, decision, reason, **fields)
            return
        parts = [f"decision={decision}"]
        if reason:
            parts.append(f"reason={reason}")
        parts.extend(f"{key}={value}" for key, value in fields.items() if value is not None)
        storyteller_logger.info("[judgement][%s] %s", category, " ".join(parts))

    def _normalize_private_info_payload(self, player: PlayerState, payload: dict) -> dict:
        if not payload:
            return {}
        if payload.get("title") and payload.get("lines"):
            return payload

        role_id = player.true_role_id or player.role_id
        normalized = dict(payload)
        info_type = payload.get("type", "night_info")
        title = payload.get("title")
        lines: list[str] = list(payload.get("lines", []))

        if info_type == "evil_reveal":
            title = title or "邪恶阵营互认"
            teammates = payload.get("teammates", [])
            bluffs = payload.get("bluffs", [])
            lines = [f"你的邪恶队友：{', '.join(teammates) if teammates else '无'}"]
            if bluffs:
                bluff_names = ", ".join(get_role_name(role_id) for role_id in bluffs)
                lines.append(f"你的 3 个不在场角色：{bluff_names}")
        elif info_type == "washerwoman_info":
            title = title or f"{get_role_name(role_id)}信息"
            candidates = ", ".join(self._player_label(pid) for pid in payload.get("players", [])) or "无"
            lines = [f"{candidates} 之中，有一人是 {get_role_name(payload.get('role_seen', 'unknown'))}。"]
        elif info_type == "librarian_info":
            title = title or f"{get_role_name(role_id)}信息"
            if payload.get("has_outsider"):
                candidates = ", ".join(self._player_label(pid) for pid in payload.get("players", [])) or "无"
                lines = [f"{candidates} 之中，有一人是 {get_role_name(payload.get('role_seen', 'unknown'))}。"]
            else:
                lines = ["本局没有外来者。"]
        elif info_type == "investigator_info":
            title = title or f"{get_role_name(role_id)}信息"
            candidates = ", ".join(self._player_label(pid) for pid in payload.get("players", [])) or "无"
            lines = [f"{candidates} 之中，有一人是 {get_role_name(payload.get('role_seen', 'unknown'))}。"]
        elif info_type == "chef_info":
            title = title or f"{get_role_name(role_id)}信息"
            lines = [f"相邻的邪恶玩家对数：{payload.get('pairs', 0)}。"]
        elif info_type == "empath_info":
            title = title or f"{get_role_name(role_id)}信息"
            lines = [f"你存活的邻座中，邪恶玩家数量：{payload.get('evil_count', 0)}。"]
        elif info_type == "undertaker_info":
            title = title or f"{get_role_name(role_id)}信息"
            lines = [f"今天被处决的玩家身份是：{get_role_name(payload.get('role_seen', 'unknown'))}。"]
        elif info_type == "fortune_teller_info":
            title = title or f"{get_role_name(role_id)}信息"
            pair = ", ".join(self._player_label(pid) for pid in payload.get("players", [])) or "这两人"
            result = "至少有一人是恶魔" if payload.get("has_demon") else "这两人都不是恶魔"
            lines = [f"{pair}：{result}。"]
        elif info_type == "ravenkeeper_info":
            title = title or f"{get_role_name(role_id)}信息"
            seen_role = get_role_name(payload.get("role_seen", "unknown"))
            lines = [f"你得知该玩家的身份是：{seen_role}。"]
        else:
            title = title or f"{get_role_name(role_id)}信息"
            if not lines:
                lines = [
                    f"{key}: {value}"
                    for key, value in payload.items()
                    if key not in {"type", "title", "lines"}
                ] or ["你收到了新的私密信息。"]

        normalized["type"] = info_type
        normalized["title"] = title
        normalized["lines"] = lines
        return normalized

    async def _publish_event(self, event: GameEvent) -> None:
        self.state = self.state.with_event(event)
        await self.event_bus.publish(event)

    def register_agent(self, agent: BaseAgent) -> None:
        self.broker.register_agent(agent)
        self._sync_agent(agent.player_id, "BOTC-FLOW-SYNC")

    def _sync_agent(self, player_id: str, trace_id: str) -> None:
        if player_id not in self.broker.agents:
            return
        private_view = self.broker.get_private_view(player_id, self.state)
        if not private_view:
            return
        self.broker.agents[player_id].synchronize_role(private_view)
        p_state = self.state.get_player(player_id)
        logger.info(
            "[role_sync][%s] %s true_role=%s perceived_role=%s current_team=%s",
            trace_id,
            player_id,
            p_state.true_role_id if p_state else "unknown",
            private_view.perceived_role_id,
            private_view.current_team.value,
        )

    def _sync_all_agents(self, trace_id: str = "BOTC-FLOW-SYNC") -> None:
        for player_id in self.broker.agents:
            self._sync_agent(player_id, trace_id)

    async def _on_any_event(self, event: GameEvent) -> None:
        self.event_log.append(event)
        await self.broker.broadcast_event(event, self.state)

    async def run_setup(self, player_count: int, host_id: str, is_human: bool = True):
        if self._setup_started or self.phase_manager.current_phase != GamePhase.SETUP:
            raise RuntimeError("BOTC-FLOW-SETUP: 当前对局已开始或已配置，不能重复 setup")
        await self.run_setup_with_options(player_count, host_id, is_human)

    async def run_setup_with_options(
        self,
        player_count: int,
        host_id: str,
        is_human: bool = True,
        discussion_rounds: int | None = None,
        storyteller_mode: str | None = None,
        audit_mode: bool = False,
        max_nomination_rounds: int | None = None,
        backend_mode: str = "auto",
        human_mode: str | None = None,
        human_client_id: str | None = None,
        storyteller_client_id: str | None = None,
    ) -> None:
        if self._setup_started or self.phase_manager.current_phase != GamePhase.SETUP:
            raise RuntimeError("BOTC-FLOW-SETUP: 当前对局已开始或已配置，不能重复 setup")

        self._setup_started = True
        from src.engine.scripts import SCRIPTS, distribute_roles

        script = SCRIPTS["trouble_brewing"]
        role_ids, bluffs = distribute_roles(script, player_count)
        resolved_human_mode = human_mode or ("player" if is_human else "none")
        resolved_human_client_id = human_client_id or (host_id if resolved_human_mode == "player" else None)
        resolved_storyteller_client_id = storyteller_client_id or (host_id if resolved_human_mode == "storyteller" else None)
        human_seat = random.randint(0, player_count - 1) if resolved_human_mode == "player" and resolved_human_client_id else -1
        players: list[PlayerState] = []
        seat_order: list[str] = []

        for seat_index, role_id in enumerate(role_ids):
            player_id = resolved_human_client_id if seat_index == human_seat else f"p{seat_index + 1}"
            role_cls = get_role_class(role_id)
            team = role_cls.get_definition().team if role_cls else Team.GOOD
            fake_role = None
            statuses = (PlayerStatus.ALIVE,)
            if role_id == "drunken":
                fake_role = await self.storyteller_agent.decide_drunk_role(script, role_ids) if self.storyteller_agent else "washerwoman"
                statuses = (PlayerStatus.ALIVE, PlayerStatus.DRUNK)
            players.append(
                PlayerState(
                    player_id=player_id,
                    name="Human Player" if player_id == resolved_human_client_id else f"Player {seat_index + 1}",
                    role_id=role_id,
                    team=team,
                    true_role_id=role_id,
                    perceived_role_id=fake_role or role_id,
                    current_team=team,
                    fake_role=fake_role,
                    statuses=statuses,
                )
            )
            seat_order.append(player_id)

        payload = dict(self.state.payload)
        if "fortune_teller" in role_ids:
            goods = [p for p in players if p.current_team == Team.GOOD and p.true_role_id != "fortune_teller"]
            if goods:
                payload["fortune_teller_red_herring"] = random.choice(goods).player_id

        self.state = self.state.with_update(
            players=tuple(players),
            seat_order=tuple(seat_order),
            bluffs=tuple(bluffs),
            payload=payload,
            config=GameConfig(
                player_count=player_count,
                script=script,
                script_id=script.script_id,
                human_client_id=resolved_human_client_id,
                human_mode=resolved_human_mode,
                storyteller_client_id=resolved_storyteller_client_id,
                human_player_ids=[resolved_human_client_id] if resolved_human_mode == "player" and resolved_human_client_id else [],
                is_human_participant=resolved_human_mode == "player",
                storyteller_mode=storyteller_mode or ("human" if resolved_human_mode == "storyteller" else getattr(self.storyteller_agent, "mode", "auto")),
                backend_mode=backend_mode,
                audit_mode=audit_mode,
                discussion_rounds=discussion_rounds or 3,
                max_nomination_rounds=max_nomination_rounds,
            ),
        )
        self._update_payload(nomination_state={"stage": "idle"}, nomination_history=[])
        self._update_grimoire()

        from src.agents.ai_agent import AIAgent, Persona
        from src.llm.openai_backend import OpenAIBackend

        backend = self.default_agent_backend or (getattr(self.storyteller_agent, "backend", None)) or OpenAIBackend()
        for player in self.state.players:
            if player.player_id not in self.broker.agents:
                self.register_agent(AIAgent(player.player_id, player.name, backend, Persona("普通的村民", "比较安静观察")))

        self._sync_all_agents("BOTC-FLOW-SETUP")
        if self._setup_done and not self._setup_done.done():
            self._setup_done.set_result(True)

    async def run_game_loop(self) -> Team | None:
        self._setup_done = asyncio.get_running_loop().create_future()
        logger.info("=== 游戏开始 ===")
        self.snapshot_manager.take_snapshot(self.state)
        await self._transition_and_run(GamePhase.SETUP)

        while not self.winner:
            self.winner = self.state.winning_team or VictoryChecker.check_victory(self.state)
            if self.winner:
                await self._transition_and_run(GamePhase.GAME_OVER)
                break

            phase = self.phase_manager.current_phase
            if phase == GamePhase.SETUP:
                await self._setup_done
                await self._transition_and_run(GamePhase.FIRST_NIGHT)
            elif phase in (GamePhase.FIRST_NIGHT, GamePhase.NIGHT):
                await self._transition_and_run(GamePhase.DAY_DISCUSSION)
            elif phase == GamePhase.DAY_DISCUSSION:
                await self._transition_and_run(GamePhase.NOMINATION)
            elif phase in (GamePhase.NOMINATION, GamePhase.EXECUTION):
                await self._transition_and_run(GamePhase.NIGHT)
            else:
                break
        return self.winner

    async def _transition_and_run(self, target_phase: GamePhase) -> None:
        if target_phase != self.phase_manager.current_phase or target_phase == GamePhase.SETUP:
            self.phase_manager.transition_to(target_phase)
        self.state = self.state.with_update(
            phase=target_phase,
            round_number=self.phase_manager.round_number,
            day_number=self.phase_manager.day_number,
        )
        if target_phase == GamePhase.GAME_OVER:
            self._set_nomination_state(
                stage="idle",
                result_phase="game_over",
                current_nominator=None,
                current_nominee=None,
                votes_cast=0,
                yes_votes=0,
                threshold=(self.state.alive_count // 2) + 1 if self.state.alive_count else 0,
                votes={},
                defense_text=None,
                last_result=None,
            )
        phase_event = GameEvent(
            event_type="phase_changed",
            phase=target_phase,
            round_number=self.phase_manager.round_number,
            trace_id=self._make_trace_id("BOTC-FLOW-PHASE"),
            visibility=Visibility.PUBLIC,
            payload={"day_number": self.phase_manager.day_number},
        )
        await self._publish_event(phase_event)
        self.snapshot_manager.take_snapshot(self.state)

        if self.storyteller_agent:
            narration = await self.storyteller_agent.narrate_phase(self.state)
            if narration:
                self.state = self.state.with_message(ChatMessage(
                    speaker="storyteller",
                    content=narration,
                    phase=target_phase,
                    round_number=self.phase_manager.round_number,
                ))

        if target_phase == GamePhase.SETUP:
            await self._run_setup_phase()
        elif target_phase == GamePhase.FIRST_NIGHT:
            await self._run_first_night()
        elif target_phase == GamePhase.NIGHT:
            await self._run_night()
        elif target_phase == GamePhase.DAY_DISCUSSION:
            await self._run_day_discussion()
        elif target_phase == GamePhase.NOMINATION:
            await self._run_nomination_phase()
        elif target_phase == GamePhase.VOTING:
            await self._run_voting_phase()
        elif target_phase == GamePhase.EXECUTION:
            await self._run_execution_phase()

    # --------------- 具体阶段逻辑 ---------------
    
    async def _run_setup_phase(self) -> None:
        logger.info("等说书人(h1)配置游戏人数...")

    async def _run_first_night(self) -> None:
        self._update_grimoire()
        evil_players = [p for p in self.state.players if (p.current_team or p.team) == Team.EVIL]
        for player in evil_players:
            teammates = [p.name for p in evil_players if p.player_id != player.player_id]
            bluffs = list(self.state.bluffs)
            await self._publish_private_info(
                phase=GamePhase.FIRST_NIGHT,
                target=player.player_id,
                trace_id=self._make_trace_id("BOTC-ST-EVIL"),
                payload={
                    "type": "evil_reveal",
                    "title": "邪恶阵营互认",
                    "teammates": teammates,
                    "bluffs": bluffs,
                },
            )
            self._record_storyteller_judgement(
                "evil_reveal",
                decision="deliver",
                phase="first_night",
                player_id=player.player_id,
                teammates=teammates,
                bluffs=bluffs,
            )
        await self._execute_night_actions(GamePhase.FIRST_NIGHT)
        await self._distribute_night_info(GamePhase.FIRST_NIGHT)
        self._sync_all_agents("BOTC-FLOW-NIGHT")
        self._update_grimoire()

    def _update_grimoire(self) -> None:
        ordered_player_ids = self.state.seat_order if self.state.seat_order else tuple(p.player_id for p in self.state.players)
        grimoire_players = []
        for pid in ordered_player_ids:
            player = self.state.get_player(pid)
            if not player:
                continue
            grimoire_players.append(PlayerGrimoireInfo(
                player_id=player.player_id,
                name=player.name,
                role_id=player.role_id,
                true_role_id=player.true_role_id,
                perceived_role_id=player.perceived_role_id,
                public_claim_role_id=player.public_claim_role_id,
                fake_role=player.fake_role,
                team=player.team,
                current_team=player.current_team,
                is_alive=player.is_alive,
                is_poisoned=player.is_poisoned,
                is_drunk=player.is_drunk,
                storyteller_notes=player.storyteller_notes,
                ongoing_effects=player.ongoing_effects,
            ))
        night_actions = tuple(
            {"event_type": event.event_type, "actor": event.actor, "target": event.target, "payload": event.payload, "trace_id": event.trace_id}
            for event in self.state.event_log
            if event.event_type in {"night_action_requested", "night_action_resolved", "private_info_delivered", "role_transfer"}
        )
        self.state = self.state.with_update(grimoire=GrimoireInfo(players=tuple(grimoire_players), night_actions=night_actions))
        self._log_storyteller(
            "grimoire_update",
            players=len(grimoire_players),
            night_actions=len(night_actions),
        )

    async def _publish_private_info(self, phase: GamePhase, target: str, trace_id: str, payload: dict) -> None:
        player = self.state.get_player(target)
        if not player:
            return
        normalized_payload = self._normalize_private_info_payload(player, payload)
        await self._publish_event(GameEvent(
            event_type="private_info_delivered",
            phase=phase,
            round_number=self.state.round_number,
            trace_id=trace_id,
            target=target,
            visibility=Visibility.PRIVATE,
            payload=normalized_payload,
        ))
        self._log_storyteller(
            "private_info_delivered",
            phase=phase.value,
            target=target,
            trace_id=trace_id,
            info_type=normalized_payload.get("type", "unknown"),
            title=normalized_payload.get("title", ""),
        )
        self._record_storyteller_judgement(
            "private_info",
            decision="deliver",
            phase=phase.value,
            target=target,
            trace_id=trace_id,
            info_type=normalized_payload.get("type", "unknown"),
            title=normalized_payload.get("title", ""),
        )

    async def _run_night(self) -> None:
        pre_alive = {p.player_id for p in self.state.get_alive_players()}
        self._clear_transient_statuses()
        await self._execute_night_actions(GamePhase.NIGHT)
        await self._distribute_night_info(GamePhase.NIGHT)
        await self._resolve_on_death_triggers(pre_alive)
        self._sync_all_agents("BOTC-FLOW-NIGHT")
        self._update_grimoire()
        for dead_id in sorted(pre_alive - {p.player_id for p in self.state.get_alive_players()}):
            await self._publish_event(GameEvent(
                event_type="player_death",
                phase=GamePhase.NIGHT,
                round_number=self.state.round_number,
                trace_id=self._make_trace_id("BOTC-RULE-DEATH"),
                target=dead_id,
                visibility=Visibility.PUBLIC,
                payload={"reason": "night"},
            ))

    async def _resolve_on_death_triggers(self, pre_alive: set[str]) -> None:
        newly_dead_ids = sorted(pre_alive - {p.player_id for p in self.state.get_alive_players()})
        for dead_id in newly_dead_ids:
            player = self.state.get_player(dead_id)
            if not player:
                continue
            role_id = player.true_role_id or player.role_id
            role_cls = get_role_class(role_id)
            if not role_cls or role_cls.get_definition().ability.trigger != AbilityTrigger.ON_DEATH:
                continue
            agent = self.broker.agents.get(dead_id)
            if not agent:
                continue
            trace_id = self._make_trace_id("BOTC-ST-DEATH")
            await self._publish_event(GameEvent(
                event_type="death_trigger_requested",
                phase=GamePhase.NIGHT,
                round_number=self.state.round_number,
                trace_id=trace_id,
                actor=dead_id,
                visibility=Visibility.STORYTELLER_ONLY,
                payload={"role_id": role_id},
            ))
            self._log_storyteller(
                "death_trigger_requested",
                actor=dead_id,
                role=role_id,
                trace_id=trace_id,
            )
            self._record_storyteller_judgement(
                "death_trigger",
                decision="request",
                actor=dead_id,
                role=role_id,
                trace_id=trace_id,
            )
            try:
                action = await agent.act(self.state, "death_trigger")
            except Exception as exc:
                logger.warning("死亡触发决策失败: %s", exc)
                action = {"action": "death_trigger", "target": None, "reasoning": f"death_trigger_error:{type(exc).__name__}"}
            target = action.get("target")
            role = role_cls()
            new_state, events = role.execute_ability(self.state, player, target)
            self.state = new_state
            for event in events:
                if event.event_type == "night_info" and event.visibility == Visibility.PRIVATE:
                    payload = dict(event.payload)
                    payload.setdefault("type", f"{role_id}_info")
                    await self._publish_private_info(
                        phase=GamePhase.NIGHT,
                        target=dead_id,
                        trace_id=trace_id,
                        payload=payload,
                    )
                    continue
                await self.event_bus.publish(event)
            self._log_storyteller(
                "death_trigger_resolved",
                actor=dead_id,
                role=role_id,
                target=target,
                trace_id=trace_id,
            )
            self._record_storyteller_judgement(
                "death_trigger",
                decision="resolved",
                actor=dead_id,
                role=role_id,
                target=target,
                trace_id=trace_id,
            )

    async def _execute_night_actions(self, phase: GamePhase) -> None:
        steps = await self.storyteller_agent.build_night_order(self.state, phase) if self.storyteller_agent else []
        self._log_storyteller("night_action_queue", phase=phase.value, steps=len(steps))
        self._record_storyteller_judgement(
            "night_queue",
            decision="queue",
            phase=phase.value,
            steps=[{"player_id": step["player_id"], "role_id": step["role_id"], "night_order": step["night_order"]} for step in steps],
        )
        for step in steps:
            player = self.state.get_player(step["player_id"])
            agent = self.broker.agents.get(step["player_id"])
            if not player or not agent:
                continue
            trace_id = self._make_trace_id("BOTC-ST-ACT")
            await self._publish_event(GameEvent(
                event_type="night_action_requested",
                phase=phase,
                round_number=self.state.round_number,
                trace_id=trace_id,
                actor=player.player_id,
                visibility=Visibility.STORYTELLER_ONLY,
                payload={"role_id": player.true_role_id or player.role_id, "requires_choice": True},
            ))
            self._log_storyteller(
                "night_action_requested",
                phase=phase.value,
                actor=player.player_id,
                role=player.true_role_id or player.role_id,
                trace_id=trace_id,
            )
            self._record_storyteller_judgement(
                "night_action",
                decision="request",
                phase=phase.value,
                actor=player.player_id,
                role=player.true_role_id or player.role_id,
                trace_id=trace_id,
            )
            action = await agent.act(self.state, "night_action")
            role_cls = get_role_class(player.true_role_id or player.role_id)
            targets = action.get("targets") or ([action["target"]] if action.get("target") else [])
            if role_cls and action.get("action") == "night_action" and targets:
                try:
                    primary_target = targets[0]
                    self.state, events = role_cls().execute_ability(
                        self.state,
                        player,
                        target=primary_target,
                        targets=targets,
                    )
                except Exception as exc:
                    logger.warning("夜晚行动无效: actor=%s role=%s targets=%s error=%s", player.player_id, player.true_role_id or player.role_id, targets, exc)
                    events = []
                for event in events:
                    await self.event_bus.publish(event)
                self._log_storyteller(
                    "night_action_executed",
                    phase=phase.value,
                    actor=player.player_id,
                    role=player.true_role_id or player.role_id,
                    targets=",".join(targets) if targets else "none",
                    trace_id=trace_id,
                )
                self._record_storyteller_judgement(
                    "night_action",
                    decision="execute",
                    phase=phase.value,
                    actor=player.player_id,
                    role=player.true_role_id or player.role_id,
                    targets=targets,
                    trace_id=trace_id,
                )
            await self._publish_event(GameEvent(
                event_type="night_action_resolved",
                phase=phase,
                round_number=self.state.round_number,
                trace_id=trace_id,
                actor=player.player_id,
                target=action.get("target"),
                visibility=Visibility.STORYTELLER_ONLY,
                payload={"role_id": player.true_role_id or player.role_id, "targets": targets},
            ))
            self._log_storyteller(
                "night_action_resolved",
                phase=phase.value,
                actor=player.player_id,
                role=player.true_role_id or player.role_id,
                targets=",".join(targets) if targets else "none",
                trace_id=trace_id,
            )
            self._record_storyteller_judgement(
                "night_action",
                decision="resolved",
                phase=phase.value,
                actor=player.player_id,
                role=player.true_role_id or player.role_id,
                targets=targets,
                trace_id=trace_id,
            )

    async def _distribute_night_info(self, phase: GamePhase) -> None:
        for player in self.state.get_alive_players():
            role_id = player.true_role_id or player.role_id
            if self.storyteller_agent and not self.storyteller_agent.role_receives_storyteller_info(role_id):
                continue
            info = await self.storyteller_agent.decide_night_info(self.state, player.player_id, role_id) if self.storyteller_agent else {}
            if not info:
                # 针对酒鬼，使用其以为的身份去获取信息，并强制干扰
                active_role_id = role_id
                if active_role_id == "drunken" and player.perceived_role_id:
                    active_role_id = player.perceived_role_id

                role_cls = get_role_class(active_role_id)
                role = role_cls() if role_cls else None
                info = role.build_storyteller_info(self.state, player) if role else {}
                
                # 如果中毒或醉酒，打乱信息
                if info and player.ability_suppressed:
                    info = self._scramble_info(info)
                    
                if info:
                    self._record_storyteller_judgement(
                        "night_info",
                        decision="fallback",
                        reason="storyteller_returned_empty",
                        phase=phase.value,
                        actor=player.player_id,
                        role=role_id,
                        info_type=info.get("type", "unknown"),
                    )
            if info:
                await self._publish_private_info(
                    phase=phase,
                    target=player.player_id,
                    trace_id=self._make_trace_id("BOTC-ST-INFO"),
                    payload=info,
                )
                self._log_storyteller(
                    "night_info_distributed",
                    phase=phase.value,
                    actor=player.player_id,
                    role=role_id,
                    info_type=info.get("type", "unknown"),
                )
                self._record_storyteller_judgement(
                    "night_info",
                    decision="deliver",
                    phase=phase.value,
                    actor=player.player_id,
                    role=role_id,
                    info_type=info.get("type", "unknown"),
                )
    def _scramble_info(self, info: dict) -> dict:
        import random
        from src.engine.roles.base_role import get_all_role_ids
        scrambled = dict(info)
        info_type = scrambled.get("type", "")
        
        if info_type == "empath_info":
            options = [0, 1, 2]
            if "evil_count" in scrambled and scrambled["evil_count"] in options:
                options.remove(scrambled["evil_count"])
            scrambled["evil_count"] = random.choice(options) if options else 0
        elif info_type == "chef_info":
            scrambled["pairs"] = (scrambled.get("pairs", 0) + random.randint(1, 2)) % 4
        elif info_type == "fortune_teller_info":
            scrambled["has_demon"] = not scrambled.get("has_demon", False)
        elif info_type in ["investigator_info", "librarian_info", "washerwoman_info", "undertaker_info", "ravenkeeper_info"]:
            scrambled["role_seen"] = random.choice(list(get_all_role_ids()))
            
        return scrambled

    def _clear_transient_statuses(self) -> None:
        players = []
        for player in self.state.players:
            statuses = tuple(status for status in player.statuses if status not in {PlayerStatus.PROTECTED, PlayerStatus.POISONED})
            if not statuses:
                statuses = (PlayerStatus.ALIVE,) if player.is_alive else (PlayerStatus.DEAD,)
            players.append(player.with_update(statuses=statuses))
        self.state = self.state.with_update(players=tuple(players))

    async def _run_day_discussion(self) -> None:
        self.state = self.state.with_update(
            nominations_today=(),
            nominees_today=(),
            votes_today={},
            current_nominee=None,
            current_nominator=None,
            execution_candidates=(),
        )
        self._update_payload(nomination_history=[])
        rounds = self.state.config.discussion_rounds if self.state.config else 3
        for discussion_round in range(1, rounds + 1):
            for player in self.state.players:
                agent = self.broker.agents.get(player.player_id)
                if not agent:
                    continue
                action = await agent.act(self.state, "speak")
                if action.get("action") == "skip_discussion":
                    return
                if action.get("action") == "speak" and action.get("content"):
                    await self._publish_event(GameEvent(
                        event_type="player_speaks",
                        phase=GamePhase.DAY_DISCUSSION,
                        round_number=self.state.round_number,
                        trace_id=self._make_trace_id("BOTC-FLOW-SPEAK"),
                        actor=player.player_id,
                        visibility=Visibility.PUBLIC,
                        payload={"content": action["content"], "tone": action.get("tone", "calm"), "round": discussion_round},
                    ))

    async def handle_chat(self, sender_id: str, content: str, is_private: bool = False) -> None:
        sender = self.state.get_player(sender_id)
        if not sender:
            return
        private_window_open = self.phase_manager.current_phase in {GamePhase.FIRST_NIGHT, GamePhase.NIGHT}
        can_use_evil_chat = is_private and private_window_open and (sender.current_team or sender.team) == Team.EVIL
        visibility = Visibility.TEAM_EVIL if can_use_evil_chat else Visibility.PUBLIC
        recipient_ids = tuple(p.player_id for p in self.state.players if (p.current_team or p.team) == Team.EVIL) if visibility == Visibility.TEAM_EVIL else None
        self.state = self.state.with_message(ChatMessage(
            speaker=sender_id,
            content=content,
            phase=self.phase_manager.current_phase,
            round_number=self.phase_manager.round_number,
            recipient_ids=recipient_ids,
        ))
        await self._publish_event(GameEvent(
            event_type="player_speaks",
            phase=self.phase_manager.current_phase,
            round_number=self.phase_manager.round_number,
            trace_id=self._make_trace_id("BOTC-FLOW-CHAT"),
            actor=sender_id,
            visibility=visibility,
            payload={"content": content, "is_private": can_use_evil_chat},
        ))

    async def _run_nomination_phase(self) -> None:
        self._set_nomination_state(
            stage="window_open",
            result_phase="window_open",
            current_nominator=None,
            current_nominee=None,
            votes_cast=0,
            yes_votes=0,
        )
        max_rounds = self.state.config.max_nomination_rounds if self.state.config and self.state.config.max_nomination_rounds else max(1, self.state.alive_count)
        nomination_round = 0
        had_any_nomination = False
        self._log_storyteller("nomination_phase_open", max_rounds=max_rounds, alive=self.state.alive_count)
        self._record_storyteller_judgement(
            "nomination_window",
            decision="open",
            max_rounds=max_rounds,
            alive=self.state.alive_count,
        )

        while nomination_round < max_rounds:
            nomination_round += 1
            intents = await self._collect_nomination_intents(nomination_round)
            chosen = self._select_nomination_intent(intents)
            if not chosen:
                self._set_nomination_state(
                    stage="no_nomination" if not had_any_nomination else "resolved",
                    result_phase="no_nomination" if not had_any_nomination else "vote_resolved",
                    current_nominator=None,
                    current_nominee=None,
                    votes_cast=0,
                    yes_votes=0,
                    round=nomination_round,
                    last_result={"executed": None, "reason": "no_nomination"} if not had_any_nomination else self.state.payload.get("nomination_state", {}).get("last_result", {"executed": None}),
                )
                if not had_any_nomination:
                    self._append_nomination_history({
                        "kind": "no_nomination",
                        "round": nomination_round,
                        "reason": "no_legal_intent",
                        "trace_id": self._make_trace_id("BOTC-FLOW-NOM-NONE"),
                    })
                self._log_storyteller(
                    "nomination_round_no_nomination",
                    round=nomination_round,
                    had_any_nomination=had_any_nomination,
                )
                self._record_storyteller_judgement(
                    "nomination_choice",
                    decision="none",
                    reason="no_legal_intent",
                    round=nomination_round,
                    intents={pid: intent.get("target") if intent else None for pid, intent in intents.items()},
                )
                break

            had_any_nomination = True
            nominator_id, target_id = chosen
            self._record_storyteller_judgement(
                "nomination_choice",
                decision="choose",
                reason="first_legal_intent",
                round=nomination_round,
                nominator=nominator_id,
                nominee=target_id,
            )
            trace_id = self._make_trace_id("BOTC-FLOW-NOM")
            try:
                self.state, events = NominationManager.nominate(self.state, nominator_id, target_id, trace_id)
            except ValueError as exc:
                logger.warning("无效提名: %s", exc)
                self._set_nomination_state(
                    stage="invalid_nomination",
                    result_phase="invalid_nomination",
                    reason=str(exc),
                    round=nomination_round,
                    last_result={"executed": None, "reason": "invalid_nomination"},
                )
                self._append_nomination_history({
                    "kind": "invalid_nomination",
                    "round": nomination_round,
                    "nominator": nominator_id,
                    "nominee": target_id,
                    "reason": str(exc),
                    "trace_id": trace_id,
                })
                self._log_storyteller(
                    "nomination_invalid",
                    round=nomination_round,
                    nominator=nominator_id,
                    nominee=target_id,
                    reason=str(exc),
                )
                self._record_storyteller_judgement(
                    "nomination_choice",
                    decision="invalid",
                    reason=str(exc),
                    round=nomination_round,
                    nominator=nominator_id,
                    nominee=target_id,
                )
                continue

            await self._publish_event(GameEvent(
                event_type="nomination_attempted",
                phase=GamePhase.NOMINATION,
                round_number=self.state.round_number,
                trace_id=trace_id,
                actor=nominator_id,
                target=target_id,
                visibility=Visibility.STORYTELLER_ONLY,
                payload={"accepted": True, "round": nomination_round},
            ))
            for event in events:
                await self.event_bus.publish(event)
            self._set_nomination_state(
                stage="defense",
                result_phase="nomination_started",
                current_nominator=nominator_id,
                current_nominee=target_id,
                votes_cast=0,
                yes_votes=0,
                threshold=RuleEngine.votes_required(self.state),
                round=nomination_round,
                trace_id=trace_id,
                defense_text=None,
                votes={},
            )
            self._log_storyteller(
                "nomination_started",
                round=nomination_round,
                nominator=nominator_id,
                nominee=target_id,
                threshold=RuleEngine.votes_required(self.state),
            )
            self._append_nomination_history({
                "kind": "nomination_started",
                "round": nomination_round,
                "nominator": nominator_id,
                "nominee": target_id,
                "threshold": RuleEngine.votes_required(self.state),
                "trace_id": trace_id,
            })
            self._record_storyteller_judgement(
                "nomination_started",
                decision="start",
                round=nomination_round,
                nominator=nominator_id,
                nominee=target_id,
                threshold=RuleEngine.votes_required(self.state),
                trace_id=trace_id,
            )
            if await self._handle_virgin_trigger(nominator_id, target_id, trace_id):
                self._update_payload(skip_execution_finalize=True)
                self._set_nomination_state(
                    stage="executed",
                    result_phase="execution_resolved",
                    current_nominator=nominator_id,
                    current_nominee=target_id,
                    round=nomination_round,
                    last_result={"executed": nominator_id, "reason": "virgin"},
                )
                self._append_nomination_history({
                    "kind": "execution_resolved",
                    "round": nomination_round,
                    "executed": nominator_id,
                    "reason": "virgin",
                    "trace_id": trace_id,
                })
                self._log_storyteller(
                    "virgin_trigger",
                    round=nomination_round,
                    nominator=nominator_id,
                    nominee=target_id,
                )
                self._record_storyteller_judgement(
                    "execution",
                    decision="virgin_trigger",
                    round=nomination_round,
                    nominator=nominator_id,
                    nominee=target_id,
                    trace_id=trace_id,
                )
                break

            await self._run_defense_and_voting(target_id, trace_id)
            self._log_storyteller(
                "nomination_round_resolved",
                round=nomination_round,
                nominee=target_id,
                votes=self.state.votes_today,
            )
            self._record_storyteller_judgement(
                "voting_resolution",
                decision="resolved",
                round=nomination_round,
                nominee=target_id,
                votes=self.state.votes_today,
                trace_id=trace_id,
            )
            if not self._can_continue_nomination_rounds(nomination_round, max_rounds):
                break

        if self.state.payload.get("skip_execution_finalize"):
            payload = dict(self.state.payload)
            payload.pop("skip_execution_finalize", None)
            self.state = self.state.with_update(payload=payload)
            self._sync_all_agents("BOTC-FLOW-EXEC-SKIP")
            return

        trace_id = self._make_trace_id("BOTC-FLOW-EXEC")
        self.state, events = NominationManager.finalize_execution(self.state, trace_id)
        for event in events:
            await self.event_bus.publish(event)
        final_payload = events[0].payload if events else {"executed": None}
        self._set_nomination_state(
            stage="executed",
            result_phase="execution_resolved",
            current_nominator=None,
            current_nominee=None,
            votes={},
            votes_cast=0,
            yes_votes=0,
            defense_text=None,
            last_result=final_payload,
            round=nomination_round,
        )
        self._append_nomination_history({
            "kind": "execution_resolved",
            "round": nomination_round,
            "executed": final_payload.get("executed"),
            "votes": final_payload.get("votes"),
            "trace_id": trace_id,
        })
        self._sync_all_agents(trace_id)
        self._log_storyteller(
            "execution_finalized",
            round=nomination_round,
            executed=final_payload.get("executed"),
            votes=final_payload.get("votes"),
            trace_id=trace_id,
        )
        self._record_storyteller_judgement(
            "execution",
            decision="finalize",
            round=nomination_round,
            executed=final_payload.get("executed"),
            votes=final_payload.get("votes"),
            trace_id=trace_id,
        )

    def _select_nomination_intent(self, intents: dict[str, dict[str, Any]]) -> tuple[str, str] | None:
        for player_id in self.state.seat_order or tuple(p.player_id for p in self.state.players):
            intent = intents.get(player_id)
            if not intent:
                continue
            target_id = intent.get("target")
            if intent.get("action") == "nominate" and target_id:
                return player_id, target_id
        if self.state.config and self.state.config.audit_mode:
            return self._select_audit_nomination_fallback()
        return None

    def _select_audit_nomination_fallback(self) -> tuple[str, str] | None:
        seat_order = self.state.seat_order or tuple(p.player_id for p in self.state.players)
        for nominator_id in seat_order:
            nominator = self.state.get_player(nominator_id)
            if not nominator or not nominator.is_alive:
                continue
            if nominator_id in self.state.nominations_today:
                continue
            for target_id in seat_order:
                if target_id == nominator_id:
                    continue
                target = self.state.get_player(target_id)
                if not target or not target.is_alive:
                    continue
                if target_id in self.state.nominees_today:
                    continue
                allowed, _ = RuleEngine.can_nominate(self.state, nominator_id, target_id)
                if allowed:
                    self._log_storyteller(
                        "nomination_audit_fallback",
                        nominator=nominator_id,
                        nominee=target_id,
                    )
                    self._record_storyteller_judgement(
                        "nomination_choice",
                        decision="audit_fallback",
                        reason="no_agent_crossed_threshold",
                        nominator=nominator_id,
                        nominee=target_id,
                    )
                    return nominator_id, target_id
        return None

    def _can_continue_nomination_rounds(self, nomination_round: int, max_rounds: int) -> bool:
        if nomination_round >= max_rounds:
            return False
        alive_players = [player for player in self.state.players if player.is_alive]
        remaining_nominators = [player for player in alive_players if player.player_id not in self.state.nominations_today]
        remaining_nominees = [player for player in alive_players if player.player_id not in self.state.nominees_today]
        return bool(remaining_nominators and remaining_nominees)

    async def _collect_nomination_intents(self, nomination_round: int) -> dict[str, dict[str, Any]]:
        await self._publish_event(GameEvent(
            event_type="nomination_window_opened",
            phase=GamePhase.NOMINATION,
            round_number=self.state.round_number,
            trace_id=self._make_trace_id("BOTC-FLOW-NOMWIN"),
            visibility=Visibility.PUBLIC,
            payload={"round": nomination_round},
        ))
        self._set_nomination_state(
            stage="nomination",
            current_nominator=None,
            current_nominee=None,
            votes_cast=0,
            yes_votes=0,
            threshold=RuleEngine.votes_required(self.state),
            round=nomination_round,
        )
        self._log_storyteller(
            "nomination_window_opened",
            round=nomination_round,
            alive=self.state.alive_count,
        )
        ordered_players = [
            self.state.get_player(pid)
            for pid in (self.state.seat_order or tuple(p.player_id for p in self.state.players))
        ]
        eligible_players = [
            player for player in ordered_players
            if player and player.is_alive and player.player_id not in self.state.nominations_today
        ]
        tasks: list[tuple[str, asyncio.Task]] = []
        human_ids = set(self.state.config.human_player_ids if self.state.config else [])
        for player in eligible_players:
            agent = self.broker.agents.get(player.player_id)
            if not agent:
                continue
            action_type = "nominate" if player.player_id in human_ids else "nomination_intent"
            tasks.append((player.player_id, asyncio.create_task(agent.act(self.state, action_type))))
        results: dict[str, dict[str, Any]] = {}
        for player_id, task in tasks:
            trace_id = self._make_trace_id("BOTC-FLOW-NOMINTENT")
            try:
                action = await task
            except Exception as exc:
                action = {"action": "none", "reasoning": f"nomination_intent_error:{type(exc).__name__}"}
            await self._publish_event(GameEvent(
                event_type="nomination_intent_submitted",
                phase=GamePhase.NOMINATION,
                round_number=self.state.round_number,
                trace_id=trace_id,
                actor=player_id,
                target=action.get("target"),
                visibility=Visibility.STORYTELLER_ONLY,
                payload={"action": action.get("action"), "round": nomination_round},
            ))
            results[player_id] = action
            self._log_storyteller(
                "nomination_intent_submitted",
                round=nomination_round,
                actor=player_id,
                action=action.get("action"),
                target=action.get("target"),
            )
        return results

    async def _handle_virgin_trigger(self, nominator_id: str, nominee_id: str, trace_id: str) -> bool:
        nominee = self.state.get_player(nominee_id)
        nominator = self.state.get_player(nominator_id)
        if not nominee or not nominator:
            return False
        if nominee.true_role_id != "virgin" or "virgin_used" in nominee.storyteller_notes:
            return False
        role_cls = get_role_class(nominator.true_role_id or nominator.role_id)
        if not role_cls or role_cls.get_definition().role_type != RoleType.TOWNSFOLK:
            self.state = self.state.with_player_update(nominee_id, storyteller_notes=nominee.storyteller_notes + ("virgin_used",))
            return False
        self.state = self.state.with_player_update(nominator_id, is_alive=False)
        self.state = self.state.with_player_update(nominee_id, storyteller_notes=nominee.storyteller_notes + ("virgin_used",))
        await self._publish_event(GameEvent(
            event_type="execution_resolved",
            phase=GamePhase.EXECUTION,
            round_number=self.state.round_number,
            trace_id=trace_id,
            target=nominator_id,
            visibility=Visibility.PUBLIC,
            payload={"executed": nominator_id, "reason": "virgin"},
        ))
        self._log_storyteller(
            "virgin_resolved",
            nominator=nominator_id,
            nominee=nominee_id,
            executed=nominator_id,
            trace_id=trace_id,
        )
        return True

    async def _run_defense_and_voting(self, nominee_id: str, trace_id: str) -> None:
        agent = self.broker.agents.get(nominee_id)
        defense_text = "我无告可陈。"
        if agent:
            self._record_storyteller_judgement(
                "defense",
                decision="request",
                nominee=nominee_id,
                trace_id=trace_id,
            )
            defense = await agent.act(self.state, "defense_speech")
            defense_text = defense.get("content", defense_text)
            self._set_nomination_state(stage="defense", defense_text=defense_text)
            self._log_storyteller(
                "defense_started",
                nominee=nominee_id,
                trace_id=trace_id,
                content=defense_text,
            )
            self._record_storyteller_judgement(
                "defense",
                decision="deliver",
                nominee=nominee_id,
                trace_id=trace_id,
                content=defense_text,
            )
            await self._publish_event(GameEvent(
                event_type="defense_started",
                phase=GamePhase.NOMINATION,
                round_number=self.state.round_number,
                trace_id=trace_id,
                actor=nominee_id,
                target=nominee_id,
                visibility=Visibility.PUBLIC,
                payload={"content": defense_text},
            ))
        else:
            self._record_storyteller_judgement(
                "defense",
                decision="skip",
                reason="no_agent",
                nominee=nominee_id,
                trace_id=trace_id,
            )
        self._set_nomination_state(stage="voting", result_phase="defense_started")
        self._log_storyteller("voting_opened", nominee=nominee_id, trace_id=trace_id)
        self._record_storyteller_judgement(
            "voting",
            decision="open",
            nominee=nominee_id,
            trace_id=trace_id,
            defense_text=defense_text,
            threshold=RuleEngine.votes_required(self.state),
        )

        vote_tasks: list[tuple[str, asyncio.Task]] = []
        for voter in self.state.players:
            vote_agent = self.broker.agents.get(voter.player_id)
            if not vote_agent:
                continue
            vote_tasks.append((voter.player_id, asyncio.create_task(vote_agent.act(self.state, "vote"))))

        votes_cast = 0
        yes_votes = 0
        vote_details: dict[str, bool] = {}
        for voter_id, task in vote_tasks:
            try:
                action = await task
            except Exception:
                action = {"action": "vote", "decision": False}
            try:
                self.state, events = NominationManager.cast_vote(self.state, voter_id, bool(action.get("decision", False)), trace_id)
            except ValueError:
                continue
            votes_cast += 1
            decision = bool(action.get("decision", False))
            vote_details[voter_id] = decision
            yes_votes += 1 if decision else 0
            self._set_nomination_state(
                votes_cast=votes_cast,
                yes_votes=yes_votes,
                threshold=RuleEngine.votes_required(self.state),
                votes=vote_details,
            )
            self._log_storyteller(
                "vote_cast",
                voter=voter_id,
                decision=decision,
                nominee=nominee_id,
                yes_votes=yes_votes,
                votes_cast=votes_cast,
                trace_id=trace_id,
            )
            self._record_storyteller_judgement(
                "voting",
                decision="cast",
                voter=voter_id,
                nominee=nominee_id,
                vote=decision,
                yes_votes=yes_votes,
                votes_cast=votes_cast,
                trace_id=trace_id,
            )
            for event in events:
                await self.event_bus.publish(event)

        self.state, events = NominationManager.resolve_voting_round(self.state, trace_id)
        for event in events:
            await self.event_bus.publish(event)
        if events:
            result_payload = dict(events[0].payload)
            result_payload["target"] = nominee_id
            self._set_nomination_state(
                stage="resolved",
                result_phase="vote_resolved",
                last_result=result_payload,
                current_nominee=nominee_id,
                votes=vote_details,
                votes_cast=votes_cast,
                yes_votes=yes_votes,
                defense_text=defense_text,
            )
            self._append_nomination_history({
                "kind": "voting_resolved",
                "round": self.state.payload.get("nomination_state", {}).get("round"),
                "nominee": nominee_id,
                "passed": result_payload.get("passed"),
                "votes": result_payload.get("votes"),
                "needed": result_payload.get("needed"),
                "voters": vote_details,
                "trace_id": trace_id,
            })
            self._log_storyteller(
                "voting_resolved",
                nominee=nominee_id,
                passed=result_payload.get("passed"),
                votes=result_payload.get("votes"),
                needed=result_payload.get("needed"),
                trace_id=trace_id,
            )
            self._record_storyteller_judgement(
                "voting",
                decision="resolve",
                nominee=nominee_id,
                passed=result_payload.get("passed"),
                votes=result_payload.get("votes"),
                needed=result_payload.get("needed"),
                yes_votes=yes_votes,
                votes_cast=votes_cast,
                trace_id=trace_id,
            )

    def export_game_record(self, export_dir: str) -> None:
        """持久化输出事件日志和系统快照到外部文件系统，用于前端回放或调试"""
        import os
        import json
        
        os.makedirs(export_dir, exist_ok=True)
        # 导出快照
        snapshot_path = os.path.join(export_dir, "snapshots.json")
        with open(snapshot_path, "w", encoding="utf-8") as f:
            f.write(self.snapshot_manager.export_to_json())
            
        # 导出事件
        event_path = os.path.join(export_dir, "events.json")
        events_data = [e.model_dump(mode="json") for e in self.event_log.events]
        with open(event_path, "w", encoding="utf-8") as f:
            json.dump(events_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"游戏记录已持久化到目录: {export_dir}")
