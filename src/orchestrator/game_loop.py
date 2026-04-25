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
from src.engine.data_collector import GameDataCollector
from src.orchestrator.event_bus import EventBus
from src.orchestrator.information_broker import InformationBroker
from src.state.event_log import EventLog
from src.state.game_state import (
    AgentActionLegalContext,
    AgentVisibleState,
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
from src.state.game_record import GameRecordStore
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
        self.settlement_report: dict[str, Any] | None = None
        self.record_store = GameRecordStore()
        self.data_collector = GameDataCollector()
        self._setup_done: asyncio.Future | None = None
        self._setup_started = False
        self._pending_night_action: dict[str, Any] | None = None  # { "player_id": str, "action_type": str, "legal_context": dict }
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

    def _should_storyteller_auto_act(self) -> bool:
        """检查说书人是否应由 AI 自动执行逻辑。"""
        if not self.storyteller_agent:
            return False
        # 如果模式是自动，或者人类模式下选择了托管
        return (
            self.storyteller_agent.mode == "auto" 
            or getattr(self.storyteller_agent, "delegated", False)
        )

    def _log_storyteller(self, event: str, **fields: Any) -> None:
        parts = [f"{key}={value}" for key, value in fields.items() if value is not None]
        storyteller_logger.info("[%s] %s", event, " ".join(parts) if parts else "")

    def _record_storyteller_judgement(self, category: str, decision: str, reason: str | None = None, **fields: Any) -> None:
        fields.setdefault("phase", self.state.phase.value)
        fields.setdefault("day_number", self.state.day_number)
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
            seen_role = get_role_name(payload.get("role_seen", "unknown"))
            seen_player = self._player_label(payload.get("player_id")) if payload.get("player_id") else "今天被处决的玩家"
            lines = [f"{seen_player} 的身份是：{seen_role}。"]
        elif info_type == "fortune_teller_info":
            title = title or f"{get_role_name(role_id)}信息"
            pair = ", ".join(self._player_label(pid) for pid in payload.get("players", [])) or "这两人"
            result = "至少有一人是恶魔" if payload.get("has_demon") else "这两人都不是恶魔"
            lines = [f"{pair}：{result}。"]
        elif info_type == "ravenkeeper_info":
            title = title or f"{get_role_name(role_id)}信息"
            seen_role = get_role_name(payload.get("role_seen", "unknown"))
            seen_player = self._player_label(payload.get("player_id")) if payload.get("player_id") else "该玩家"
            lines = [f"你得知 {seen_player} 的身份是：{seen_role}。"]
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

    def _record_data_snapshot(self, stage: str, **extra_summary: Any) -> None:
        last_event = self.state.event_log[-1].event_type if self.state.event_log else None
        nomination_state = self.state.payload.get("nomination_state", {})
        ai_snapshot = self._build_ai_data_snapshot_summary()
        snapshot = {
            "game_id": self.state.game_id,
            "stage": stage,
            "phase": self.state.phase.value,
            "day_number": self.state.day_number,
            "round_number": self.state.round_number,
            "summary": {
                "alive_count": self.state.alive_count,
                "dead_count": self.state.player_count - self.state.alive_count,
                "player_count": self.state.player_count,
                "chat_messages": len(self.state.chat_history),
                "last_event_type": last_event,
                "nomination_stage": nomination_state.get("stage"),
                "visible_state_summary": {
                    "alive_players": [player.name for player in self.state.get_alive_players()],
                    "dead_players": [player.name for player in self.state.players if not player.is_alive],
                    "current_nominee": self._player_label(self.state.current_nominee) if self.state.current_nominee else None,
                    "current_nominator": self._player_label(self.state.current_nominator) if self.state.current_nominator else None,
                },
                "working_memory_summary": ai_snapshot["working_memory_summary"],
                "social_graph_summary": ai_snapshot["social_graph_summary"],
                "claim_history_summary": ai_snapshot["claim_history_summary"],
                "retrieval_summary": ai_snapshot["retrieval_summary"],
                **extra_summary,
            },
        }
        self.data_collector.record_snapshot(snapshot)

    def _build_ai_data_snapshot_summary(self) -> dict[str, Any]:
        summary = {
            "working_memory_summary": {},
            "social_graph_summary": {},
            "claim_history_summary": {},
            "retrieval_summary": {},
        }
        for player_id, agent in self.broker.agents.items():
            if not hasattr(agent, "build_data_snapshot_summary"):
                continue
            try:
                agent_summary = agent.build_data_snapshot_summary()
            except Exception as exc:
                logger.warning("build_data_snapshot_summary failed for %s: %s", player_id, exc)
                continue
            summary["working_memory_summary"][player_id] = agent_summary.get("working_memory_summary", {})
            summary["social_graph_summary"][player_id] = agent_summary.get("social_graph_summary", "")
            summary["claim_history_summary"][player_id] = agent_summary.get("claim_history_summary", {})
            summary["retrieval_summary"][player_id] = agent_summary.get("retrieval_summary", {})
        return summary

    async def _publish_event(self, event: GameEvent) -> None:
        # 确保事件携带最新的天数信息，便于前端展示
        try:
            # 由于 GameEvent 是 frozen 的，我们需要 model_copy 来更新
            if getattr(event, 'day_number', 1) == 1 and self.state.day_number != 1:
                event = event.model_copy(update={"day_number": self.state.day_number})
        except Exception:
            pass
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

    def _get_agent_visible_state(self, player_id: str) -> AgentVisibleState | None:
        return self.broker.get_visible_state(player_id, self.state)

    def _get_agent_legal_context(
        self,
        player_id: str,
        visible_state: AgentVisibleState | None = None,
    ) -> AgentActionLegalContext:
        return self.broker.get_action_legal_context(player_id, self.state, visible_state)

    def _ensure_player_alive(self, player_id: str, context: str = "action") -> PlayerState:
        """[GAME-1.2] 统一存活检查。若玩家不存在或已死亡则抛出 ValueError。"""
        player = self.state.get_player(player_id)
        if not player:
            raise ValueError(f"[{context}] 玩家 {player_id} 不存在")
        if not player.is_alive:
            raise ValueError(f"[{context}] 玩家 {player_id} ({player.name}) 已死亡，无法执行操作")
        return player

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
        storyteller_delegated: bool = False,
    ) -> None:
        logger.info(f"[run_setup_with_options] Starting setup for {player_count} players. host_id={host_id} mode={human_mode}")
        if self._setup_started or self.phase_manager.current_phase != GamePhase.SETUP:
            logger.warning("[run_setup_with_options] Setup already started or not in SETUP phase. phase=%s", self.phase_manager.current_phase)
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
                fake_role = await self.storyteller_agent.decide_drunk_role(script, role_ids) if self._should_storyteller_auto_act() else "washerwoman"
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
                storyteller_delegated=storyteller_delegated,
                backend_mode=backend_mode,
                audit_mode=audit_mode,
                discussion_rounds=discussion_rounds or 3,
                max_nomination_rounds=max_nomination_rounds,
            ),
        )
        if self.storyteller_agent:
            new_mode = self.state.config.storyteller_mode
            logger.info(f"[run_setup_with_options] Updating storyteller_agent mode to {new_mode}, delegated={storyteller_delegated}")
            self.storyteller_agent.mode = new_mode
            if hasattr(self.storyteller_agent, "delegated"):
                self.storyteller_agent.delegated = storyteller_delegated
        self._update_payload(nomination_state={"stage": "idle"}, nomination_history=[])
        self._update_grimoire()

        from src.agents.ai_agent import AIAgent, Persona
        from src.agents.persona_registry import ARCHETYPES
        from src.llm.openai_backend import OpenAIBackend

        backend = self.default_agent_backend or (getattr(self.storyteller_agent, "backend", None)) or OpenAIBackend()
        player_count = len(self.state.players)
        archetype_keys = list(ARCHETYPES.keys())

        self.data_collector.start_game(self.state.game_id)
        for i, player in enumerate(self.state.players):
            if player.player_id not in self.broker.agents:
                # 轮询分配不同的性格原型
                arch_key = archetype_keys[i % len(archetype_keys)]
                arch = ARCHETYPES[arch_key]
                persona = Persona(
                    description=arch.description,
                    speaking_style=arch.speaking_style,
                    archetype=arch_key
                )
                
                self.register_agent(AIAgent(
                    player.player_id, 
                    player.name, 
                    backend, 
                    persona, 
                    player_count=player_count,
                    data_collector=self.data_collector
                ))

        logger.info("[run_setup_with_options] Syncing all agents")
        self._sync_all_agents("BOTC-FLOW-SETUP")
        if not self._setup_done:
            self._setup_done = asyncio.get_running_loop().create_future()
        if not self._setup_done.done():
            logger.info("[run_setup_with_options] Setting _setup_done result to True")
            self._setup_done.set_result(True)
        logger.info("[run_setup_with_options] Setup completed successfully")

    async def run_game_loop(self) -> Team | None:
        if not self._setup_done:
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
                logger.info("[run_game_loop] Waiting for _setup_done...")
                await self._setup_done
                logger.info("[run_game_loop] _setup_done received. Transitioning to FIRST_NIGHT")
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
        if target_phase != self.phase_manager.current_phase:
            await self._archive_agent_phase_memories()
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
            # 结算报告生成与持久化
            self.settlement_report = self._build_settlement_report()
            self.state = self.state.with_update(winning_team=self.winner)
            await self._publish_event(GameEvent(
                event_type="game_settlement",
                phase=GamePhase.GAME_OVER,
                round_number=self.phase_manager.round_number,
                trace_id=self._make_trace_id("BOTC-SETTLEMENT"),
                visibility=Visibility.PUBLIC,
                payload=self.settlement_report,
            ))
            try:
                await self.record_store.save_game(
                    self.state.game_id, self.state, self.settlement_report
                )
            except Exception as exc:
                logger.error("Failed to persist game record: %s", exc)
            self._record_data_snapshot(
                "game_settlement_ready",
                winning_team=self.winner.value if self.winner else None,
                timeline_items=len(self.settlement_report.get("timeline", [])) if self.settlement_report else 0,
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

        if self._should_storyteller_auto_act():
            narration = await self.storyteller_agent.narrate_phase(self.state)
            if narration:
                self.state = self.state.with_message(ChatMessage(
                    speaker="storyteller",
                    content=narration,
                    phase=target_phase,
                    round_number=self.phase_manager.round_number,
                ))

        # [A3-ST-6] 如果开启了 AI 说书人自动动作，在每个阶段开始时进行局势分析
        if self.storyteller_agent and self._should_storyteller_auto_act():
            try:
                await self.storyteller_agent.analyze_game_situation(self.state)
            except Exception as exc:
                logger.warning("Storyteller analysis failed: %s", exc)

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

    async def _archive_agent_phase_memories(self) -> None:
        for player_id, agent in self.broker.agents.items():
            try:
                visible_state = self._get_agent_visible_state(player_id)
                if visible_state:
                    await agent.archive_phase_memory(visible_state)
            except Exception as exc:
                logger.warning("archive_phase_memory failed for %s: %s", agent.player_id, exc)

    # --------------- 结算报告 ---------------

    def _build_settlement_report(self) -> dict[str, Any]:
        """组装完整的结算报告数据"""
        state = self.state
        events = list(state.event_log)

        # 胜负判定
        winning_team = self.winner.value if self.winner else "unknown"
        victory_reason = self._determine_victory_reason()

        # 玩家统计
        player_stats: dict[str, dict[str, int]] = {}
        for p in state.players:
            player_stats[p.player_id] = {
                "nominations_made": 0,
                "times_nominated": 0,
                "votes_cast": 0,
                "votes_yes": 0,
            }

        for event in events:
            if event.event_type == "nomination_started":
                if event.actor and event.actor in player_stats:
                    player_stats[event.actor]["nominations_made"] += 1
                if event.target and event.target in player_stats:
                    player_stats[event.target]["times_nominated"] += 1
            elif event.event_type == "vote_cast":
                if event.actor and event.actor in player_stats:
                    player_stats[event.actor]["votes_cast"] += 1
                    if event.payload.get("vote"):
                        player_stats[event.actor]["votes_yes"] += 1

        # 角色揭示
        human_ids = set()
        if state.config and state.config.human_player_ids:
            human_ids = set(state.config.human_player_ids)

        players_reveal = []
        for p in state.players:
            players_reveal.append({
                "player_id": p.player_id,
                "name": p.name,
                "true_role_id": p.true_role_id or p.role_id,
                "perceived_role_id": p.perceived_role_id,
                "team": (p.current_team or p.team).value,
                "is_alive": p.is_alive,
                "is_human": p.player_id in human_ids,
                "stats": player_stats.get(p.player_id, {}),
            })

        # 关键事件时间线
        key_event_types = {
            "nomination_started", "voting_resolved", "execution_resolved",
            "player_death", "phase_changed",
        }
        timeline = []
        for event in events:
            if event.event_type not in key_event_types:
                continue
            summary = self._summarize_event(event)
            if not summary:
                continue
            timeline.append({
                "round": event.round_number,
                "phase": event.phase.value,
                "event_type": event.event_type,
                "actor": event.actor,
                "target": event.target,
                "summary": summary,
                "timestamp": event.timestamp.isoformat(),
            })

        # 总体统计
        total_nominations = sum(1 for e in events if e.event_type == "nomination_started")
        total_executions = sum(1 for e in events if e.event_type == "execution_resolved" and e.payload.get("executed"))
        total_votes = sum(1 for e in events if e.event_type == "vote_cast")
        total_deaths = sum(1 for e in events if e.event_type == "player_death")
        judgement_summary: list[dict[str, Any]] = []
        if self.storyteller_agent and hasattr(self.storyteller_agent, "summarize_recent_judgements"):
            try:
                judgement_summary = list(self.storyteller_agent.summarize_recent_judgements(20))
            except Exception as exc:
                logger.warning("Failed to summarize storyteller judgements for settlement: %s", exc)

        return {
            "game_id": state.game_id,
            "winning_team": winning_team,
            "victory_reason": victory_reason,
            "duration_rounds": state.round_number,
            "days_played": state.day_number,
            "players": players_reveal,
            "timeline": timeline,
            "statistics": {
                "total_nominations": total_nominations,
                "total_executions": total_executions,
                "total_votes": total_votes,
                "total_deaths": total_deaths,
                "days_played": state.day_number,
                "player_count": len(state.players),
            },
            "judgement_summary": judgement_summary,
        }

    def _determine_victory_reason(self) -> str:
        """推断胜利原因"""
        if not self.winner:
            return "unknown"
        events = list(self.state.event_log)
        if self.winner == Team.GOOD:
            # 检查是否恶魔被处决
            for event in reversed(events):
                if event.event_type == "execution_resolved" and event.payload.get("executed"):
                    return "demon_executed"
                if event.event_type == "player_death":
                    return "demon_killed"
            return "demon_killed"
        else:
            # 邪恶获胜 = 只剩2人且恶魔存活
            return "last_two_alive"

    def _summarize_event(self, event: GameEvent) -> str:
        """将事件转为人可读的摘要"""
        actor = self._player_label(event.actor) if event.actor else ""
        target = self._player_label(event.target) if event.target else ""

        if event.event_type == "phase_changed":
            day = event.payload.get("day_number", "?")
            phase_names = {
                "first_night": "第一夜",
                "day_discussion": f"第{day}天 白天讨论",
                "nomination": f"第{day}天 提名阶段",
                "night": f"第{day}天 夜晚",
                "game_over": "游戏结束",
            }
            return phase_names.get(event.phase.value, f"阶段: {event.phase.value}")

        if event.event_type == "nomination_started":
            return f"{actor} 提名了 {target}"

        if event.event_type == "voting_resolved":
            passed = event.payload.get("passed", False)
            votes = event.payload.get("votes", 0)
            needed = event.payload.get("needed", 0)
            result = "通过" if passed else "未通过"
            return f"投票{result} ({votes}/{needed}票) - {target}"

        if event.event_type == "execution_resolved":
            executed = event.payload.get("executed")
            if executed:
                return f"{self._player_label(executed)} 被处决"
            return "今天无人被处决"

        if event.event_type == "player_death":
            reason = event.payload.get("reason", "night")
            if reason == "night":
                return f"{target} 在夜晚死亡"
            return f"{target} 死亡"

        return ""

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
        # 在首夜开始时，由说书人决定一些初始配置（如酒鬼是谁，以及洗衣妇等人的信息内容）
        if self._should_storyteller_auto_act():
            self.state = await self.storyteller_agent.decide_initial_setup_info(self.state)

        await self._execute_night_actions(GamePhase.FIRST_NIGHT)
        await self._distribute_night_info(GamePhase.FIRST_NIGHT)
        self._sync_all_agents("BOTC-FLOW-NIGHT")
        self._update_grimoire()
        self._record_data_snapshot(
            "first_night_complete",
            private_info_events=sum(1 for e in self.state.event_log if e.event_type == "private_info_delivered"),
        )

    def get_grimoire_info(self) -> GrimoireInfo:
        """生成当前的魔典快照（实时计算）。"""
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
        
        # 收集夜晚行动记录
        night_actions = tuple(
            {"event_type": event.event_type, "actor": event.actor, "target": event.target, "payload": event.payload, "trace_id": event.trace_id}
            for event in self.state.event_log
            if event.event_type in {"night_action_requested", "night_action_resolved", "private_info_delivered", "role_transfer"}
        )
        return GrimoireInfo(
            players=tuple(grimoire_players), 
            night_actions=night_actions,
            reminders=tuple(self.state.payload.get("reminders", []))
        )

    def _update_grimoire(self) -> None:
        """更新状态中的魔典快照（用于存档和持久化）。"""
        grimoire = self.get_grimoire_info()
        self.state = self.state.with_update(grimoire=grimoire)
        self._log_storyteller(
            "grimoire_update",
            players=len(grimoire.players),
            night_actions=len(grimoire.night_actions),
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
        # 在每晚行动开始前，说书人可以做出一些全局性决策（如间谍/隐士是否误报）
        if self._should_storyteller_auto_act():
            self.state = await self.storyteller_agent.decide_misregistration(self.state)

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
                visible_state = self._get_agent_visible_state(player.player_id)
                if not visible_state:
                    continue
                legal_context = self._get_agent_legal_context(player.player_id, visible_state)
                action = await agent.act(visible_state, "death_trigger", legal_context=legal_context)
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

    async def _execute_slayer_shot(self, actor_id: str, target_id: str) -> None:
        """执行猎手技能"""
        try:
            actor = self._ensure_player_alive(actor_id, "slayer_shot_actor")
            target = self._ensure_player_alive(target_id, "slayer_shot_target")
        except ValueError as e:
            logger.warning("猎手技能校验失败: %s", e)
            return

        from src.engine.roles.townsfolk import SlayerRole
        role = SlayerRole()
        
        trace_id = self._make_trace_id("BOTC-FLOW-SLAYER")
        await self._publish_event(GameEvent(
            event_type="slayer_shot_announced",
            phase=self.phase_manager.current_phase,
            round_number=self.state.round_number,
            trace_id=trace_id,
            actor=actor_id,
            target=target_id,
            visibility=Visibility.PUBLIC,
            payload={"message": f"{actor.name} 对 {target.name} 发动了猎手技能！"}
        ))
        
        # 执行技能
        try:
            self.state, events = role.execute_ability(self.state, actor, target_id)
            for event in events:
                # 确保 trace_id 一致
                event_dict = event.model_dump()
                event_dict["trace_id"] = trace_id
                #重新封装以通过 event_bus
                new_event = GameEvent(**event_dict)
                await self._publish_event(new_event)
                
            self._record_storyteller_judgement(
                "slayer_shot",
                decision="execute",
                actor=actor_id,
                target=target_id,
                trace_id=trace_id,
            )
        except Exception as e:
            logger.error(f"Slayer shot execution failed: {e}")

    async def _execute_night_actions(self, phase: GamePhase) -> None:
        steps = await self.storyteller_agent.build_night_order(self.state, phase) if self._should_storyteller_auto_act() else []
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
            
            # [FIX] 夜晚行动顺序校验：如果玩家已死亡且不是守鸦人（ON_DEATH 触发），则跳过
            if not player.is_alive:
                role_cls = get_role_class(player.true_role_id or player.role_id)
                if role_cls:
                    role_def = role_cls.get_definition()
                    # 守鸦人等 ON_DEATH 角色允许在当晚死后行动一次
                    if role_def.ability.trigger != AbilityTrigger.ON_DEATH:
                        logger.info(f"BOTC-FLOW-NIGHT: 跳过已死亡玩家 {player.player_id} ({player.role_id}) 的行动")
                        continue
                else:
                    continue
            trace_id = self._make_trace_id("BOTC-ST-ACT")
            
            visible_state = self._get_agent_visible_state(player.player_id)
            if not visible_state:
                continue
            legal_context = self._get_agent_legal_context(player.player_id, visible_state)

            # 持久化当前待办动作，供 API 查询
            self._pending_night_action = {
                "player_id": player.player_id,
                "action_type": "night_action",
                "legal_context": legal_context.model_dump(mode="json"),
                "role_id": player.true_role_id or player.role_id,
            }

            trying_empty = False
            retry_count = 0
            last_error = None
            while True:
                retry_count += 1
                reminder_msg = ""
                if trying_empty:
                    reminder_msg = "请选择目标后再提交，不可空跳。"
                elif last_error:
                    reminder_msg = f"操作失败: {last_error}。由于规则或格式限制，请修正后重新提交。"

                await self._publish_event(GameEvent(
                    event_type="night_action_requested",
                    phase=phase,
                    round_number=self.state.round_number,
                    trace_id=trace_id,
                    actor=player.player_id,
                    visibility=Visibility.STORYTELLER_ONLY,
                    payload={
                        "role_id": player.true_role_id or player.role_id, 
                        "requires_choice": True,
                        "required_targets": legal_context.required_targets,
                        "can_target_self": legal_context.can_target_self,
                        "reminder": reminder_msg if reminder_msg else None
                    },
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

                action = await agent.act(
                    visible_state,
                    "night_action",
                    legal_context=legal_context,
                    reminder=reminder_msg if reminder_msg else None,
                    retry_count=retry_count,
                    last_error=last_error,
                )

                if (
                    player
                    and (player.current_team or player.team) == Team.EVIL
                    and hasattr(agent, "build_evil_night_coordination_message")
                ):
                    try:
                        coordination_msg = agent.build_evil_night_coordination_message(action, visible_state, legal_context)
                    except Exception:
                        coordination_msg = ""
                    if coordination_msg:
                        await self.handle_chat(player.player_id, coordination_msg, is_private=True)

                role_cls = get_role_class(player.true_role_id or player.role_id)
                
                # 鲁棒性：解析 targets 并处理可能的嵌套列表
                raw_targets = action.get("targets") or ([action["target"]] if action.get("target") else [])
                
                def flatten_targets(items):
                    """递归展平列表并过滤非字符串"""
                    res = []
                    if isinstance(items, (list, tuple)):
                        for item in items:
                            res.extend(flatten_targets(item))
                    elif isinstance(items, str):
                        res.append(items)
                    return res
                
                targets = flatten_targets(raw_targets)
                
                # 校验：如果不允许空选（required_targets > 0）但玩家空选了，则重试
                if legal_context.required_targets > 0 and not targets:
                    logger.warning(f"[GameLoop] 玩家 {player.player_id} ({player.role_id}) 尝试空选，重新请求。")
                    trying_empty = True
                    last_error = "必须选择目标"
                    continue

                if role_cls and action.get("action") == "night_action":
                    try:
                        primary_target = targets[0] if targets else None
                        self.state, events = role_cls().execute_ability(
                            self.state,
                            player,
                            target=primary_target,
                            targets=targets,
                        )
                        
                        # 成功执行，发布事件并记录
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
                        break  # 执行成功，跳出重试循环
                    except Exception as exc:
                        logger.warning("夜晚行动无效: actor=%s role=%s targets=%s error=%s. 重新请求。", 
                                       player.player_id, player.true_role_id or player.role_id, targets, exc)
                        last_error = str(exc)
                        # 执行失败（如校验不通过），继续循环重试
                        continue
                else:
                    # 如果不是目标行动或解析失败，也认为需要重试（或根据逻辑跳过，但这里我们偏向严格）
                    break

            # 清除待办
            self._pending_night_action = None

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
            info = await self.storyteller_agent.decide_night_info(self.state, player.player_id, role_id) if self._should_storyteller_auto_act() else {}
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
        """清理夜晚开始时的瞬时状态（如僧侣保护、中毒、醉酒等）"""
        players = []
        for player in self.state.players:
            # 清理状态列表
            # 只清理 POISONED 和 PROTECTED。
            # 注意：DRUNK (醉酒) 通常是持久的 (如酒鬼角色)，不应在每晚结束时自动清除。
            statuses = tuple(status for status in player.statuses if status not in {PlayerStatus.PROTECTED, PlayerStatus.POISONED})
            if not statuses:
                statuses = (PlayerStatus.ALIVE,) if player.is_alive else (PlayerStatus.DEAD,)
            
            # botc 标准逻辑：中毒通常持续一个昼夜 cycle。
            # 这里我们简单清理，后续可根据具体角色技能持续时间细化。
            players.append(player.with_update(statuses=statuses))
        
        self.state = self.state.with_update(players=tuple(players))
        self._log_storyteller("transient_statuses_cleared")

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
                visible_state = self._get_agent_visible_state(player.player_id)
                if not visible_state:
                    continue
                legal_context = self._get_agent_legal_context(player.player_id, visible_state)
                action = await agent.act(visible_state, "speak", legal_context=legal_context)
                if action.get("action") == "skip_discussion":
                    self._record_data_snapshot(
                        "day_discussion_complete",
                        discussion_round=discussion_round,
                    )
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
                
                # [FIX] 猎手技能发动逻辑
                if action.get("action") == "slayer_shot":
                    target_id = action.get("target")
                    if target_id:
                        await self._execute_slayer_shot(player.player_id, target_id)
        self._record_data_snapshot(
            "day_discussion_complete",
            discussion_round=rounds,
        )

    async def handle_chat(self, sender_id: str, content: str, is_private: bool = False) -> None:
        sender = self.state.get_player(sender_id)
        # 允许说书人发消息，即使他不在玩家列表中
        is_storyteller = sender_id in ["h1", "storyteller", "admin"] or (self.state.config and sender_id == self.state.config.storyteller_client_id)
        
        if not sender and not is_storyteller:
            return

        current_phase = self.state.phase if self.state.phase != GamePhase.SETUP else self.phase_manager.current_phase
        private_window_open = current_phase in {GamePhase.FIRST_NIGHT, GamePhase.NIGHT}
        can_use_evil_chat = is_private and private_window_open and sender and (sender.current_team or sender.team) == Team.EVIL
        visibility = Visibility.TEAM_EVIL if can_use_evil_chat else Visibility.PUBLIC
        recipient_ids = tuple(p.player_id for p in self.state.players if (p.current_team or p.team) == Team.EVIL) if visibility == Visibility.TEAM_EVIL else None
        self.state = self.state.with_message(ChatMessage(
            speaker=sender_id,
            content=content,
            phase=current_phase,
            round_number=self.state.round_number or self.phase_manager.round_number,
            recipient_ids=recipient_ids,
        ))
        await self._publish_event(GameEvent(
            event_type="player_speaks",
            phase=current_phase,
            round_number=self.state.round_number or self.phase_manager.round_number,
            trace_id=self._make_trace_id("BOTC-FLOW-CHAT"),
            actor=sender_id,
            visibility=visibility,
            payload={"content": content, "is_private": can_use_evil_chat},
        ))

    async def _run_nomination_phase(self) -> None:
        # [A3-DATA-2] 提名前快照
        self._record_data_snapshot("before_nomination")

        self._set_nomination_state(
            stage="window_open",
            result_phase="window_open",
            current_nominator=None,
            current_nominee=None,
            votes_cast=0,
            yes_votes=0,
        )
        self._record_data_snapshot(
            "nomination_window_open",
            threshold=RuleEngine.votes_required(self.state),
        )
        max_rounds = self.state.config.max_nomination_rounds if self.state.config and self.state.config.max_nomination_rounds else max(1, self.state.alive_count)
        nomination_round = 0
        had_any_nomination = False
        self._log_storyteller("nomination_phase_open", max_rounds=max_rounds, alive=self.state.alive_count)
        self._record_storyteller_judgement(
            "nomination_started",
            decision="open",
            max_rounds=max_rounds,
            alive=self.state.alive_count,
        )

        while nomination_round < max_rounds:
            nomination_round += 1
            intents = await self._collect_nomination_intents(nomination_round)
            
            # [FIX] 优先处理猎手技能发动
            for intent_pid, intent_data in intents.items():
                if intent_data.get("action") == "slayer_shot":
                    target_id = intent_data.get("target")
                    if target_id:
                        await self._execute_slayer_shot(intent_pid, target_id)

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
                self._ensure_player_alive(nominator_id, "nomination_actor")
                self._ensure_player_alive(target_id, "nomination_target")
                self.state, events = NominationManager.nominate(self.state, nominator_id, target_id, trace_id)
                # [FIX] 如果由于特殊技能（如圣女）导致了即时处决，处决事件会修改 phase 为非提名且非投票状态（如直接进入结算或回退讨论）
                if self.state.phase not in [GamePhase.NOMINATION, GamePhase.VOTING]:
                    logger.info("提名阶段被特殊技能(如圣女)中断，或已直接进入处决结算。")
                    break
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
        
        # [A3-DATA-2] 投票与处决后快照
        self._record_data_snapshot("after_execution")

    def _select_nomination_intent(self, intents: dict[str, dict[str, Any]]) -> tuple[str, str] | None:
        for player_id in self.state.seat_order or tuple(p.player_id for p in self.state.players):
            intent = intents.get(player_id)
            if not intent:
                continue
            target_id = intent.get("target")
            if intent.get("action") == "nominate" and target_id and target_id != "not_nominating":
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
            visible_state = self._get_agent_visible_state(player.player_id)
            if not visible_state:
                continue
            legal_context = self._get_agent_legal_context(player.player_id, visible_state)
            
            # 为人类玩家增加强制选择校验
            if player.player_id in human_ids:
                async def human_nomination_loop(v_state, a_type, l_ctx, a_agent):
                    trying_empty = False
                    retry_count = 0
                    while True:
                        retry_count += 1
                        # 发送请求并等待
                        act_res = await a_agent.act(
                            v_state,
                            a_type,
                            legal_context=l_ctx,
                            reminder="请做出选择（提名玩家或选择‘不提名’）。不可空选。" if trying_empty else None,
                            retry_count=retry_count,
                            last_error="必须明确选择提名对象或不提名" if trying_empty else None,
                        )
                        # 校验：必须有 target，且不得为空。合法的可以是 "not_nominating" 或 玩家 ID
                        tgt = act_res.get("target")
                        if tgt:
                            return act_res
                        logger.warning(f"[Nomination] 玩家 {player.player_id} 提交了空提名意图，重试。")
                        trying_empty = True
                tasks.append((player.player_id, asyncio.create_task(human_nomination_loop(visible_state, action_type, legal_context, agent))))
            else:
                tasks.append((player.player_id, asyncio.create_task(agent.act(visible_state, action_type, legal_context=legal_context))))

        results: dict[str, dict[str, Any]] = {}
        for player_id, task in tasks:
            trace_id = self._make_trace_id("BOTC-FLOW-NOMINTENT")
            try:
                action = await task
            except Exception as exc:
                action = {"action": "none", "reasoning": f"nomination_intent_error:{type(exc).__name__}"}
            
            # 统一处理结果：如果结果依然为空（AI 异常等），给予默认值，防止卡死
            if not action.get("target"):
                action["target"] = "not_nominating"
                action["action"] = "not_nominating"

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
        # [GAME-1.2] 二次存活检查：防范提名发起后、进入防御前目标死亡（如特殊技能或圣女导致被提名人离场）
        nominee_player = self.state.get_player(nominee_id)
        if not nominee_player or not nominee_player.is_alive:
            logger.info("被提名人 %s 已死亡，取消防御和投票阶段", nominee_id)
            self._set_nomination_state(stage="resolved", result_phase="nominee_dead_abort")
            return

        agent = self.broker.agents.get(nominee_id)
        defense_text = "我无告可陈。"
        if agent:
            self._record_storyteller_judgement(
                "defense",
                decision="request",
                nominee=nominee_id,
                trace_id=trace_id,
            )
            visible_state = self._get_agent_visible_state(nominee_id)
            if not visible_state:
                visible_state = self.broker.get_visible_state(nominee_id, self.state)
            legal_context = self._get_agent_legal_context(nominee_id, visible_state) if visible_state else AgentActionLegalContext()
            defense = await agent.act(visible_state, "defense_speech", legal_context=legal_context) if visible_state else {"action": "speak", "content": defense_text}
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
            "voting_resolution",
            decision="open",
            nominee=nominee_id,
            trace_id=trace_id,
            defense_text=defense_text,
            threshold=RuleEngine.votes_required(self.state),
        )

        vote_details: dict[str, bool] = {}
        votes_cast = 0
        yes_votes = 0
        for voter in self.state.players:
            voter_id = voter.player_id
            vote_agent = self.broker.agents.get(voter_id)
            if not vote_agent:
                continue
            
            # W3-D: 串行投票，每个玩家在举手前能看到当前已有的票数
            try:
                visible_state = self._get_agent_visible_state(voter_id)
                if not visible_state:
                    continue
                legal_context = self._get_agent_legal_context(voter_id, visible_state)
                
                # 为人类玩家增加强制选择校验（必须明确 True 或 False）
                human_ids = set(self.state.config.human_player_ids if self.state.config else [])
                if voter_id in human_ids:
                    trying_empty = False
                    retry_count = 0
                    while True:
                        retry_count += 1
                        action = await vote_agent.act(
                            visible_state,
                            "vote",
                            legal_context=legal_context,
                            reminder="请做出明确选择（同意或不赞成）。不可直接跳过。" if trying_empty else None,
                            retry_count=retry_count,
                            last_error="必须明确选择同意或不赞成" if trying_empty else None,
                        )
                        if action.get("decision") is not None:
                            break
                        logger.warning(f"[Voting] 玩家 {voter_id} 提交了空投票意图，重试。")
                        trying_empty = True
                else:
                    action = await vote_agent.act(visible_state, "vote", legal_context=legal_context)
            except Exception as e:
                logger.error(f"Voter {voter_id} action error: {e}")
                action = {"action": "vote", "decision": False}
                
            decision = bool(action.get("decision", False))
            try:
                self.state, events = NominationManager.cast_vote(self.state, voter_id, decision, trace_id)
                for event in events:
                    await self.event_bus.publish(event)
            except ValueError:
                continue
            
            vote_details[voter_id] = decision
            votes_cast += 1
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
                "voting_resolution",
                decision="cast_vote",
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
                "voting_resolution",
                decision="resolve",
                nominee=nominee_id,
                passed=result_payload.get("passed"),
                votes=result_payload.get("votes"),
                needed=result_payload.get("needed"),
                yes_votes=yes_votes,
                votes_cast=votes_cast,
                trace_id=trace_id,
            )
            self._record_data_snapshot(
                "voting_resolved",
                nominee=nominee_id,
                passed=result_payload.get("passed"),
                votes=result_payload.get("votes"),
                needed=result_payload.get("needed"),
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
