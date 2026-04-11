"""Export storyteller balance evaluation samples."""

from __future__ import annotations

import argparse
import asyncio
import json
import random
from contextlib import suppress
from pathlib import Path

from src.agents.storyteller_agent import StorytellerAgent
from src.llm.mock_backend import MockBackend
from src.orchestrator.game_loop import GameOrchestrator
from src.orchestrator.storyteller_balance import (
    aggregate_storyteller_node_samples,
    build_storyteller_adjudication_sample,
    build_storyteller_node_samples,
    export_storyteller_adjudication_sample,
)
from src.state.game_state import GameConfig, GameEvent, GamePhase, GameState, PlayerState, PlayerStatus, Team, Visibility


def _base_config(player_count: int = 5) -> GameConfig:
    return GameConfig(
        player_count=player_count,
        script_id="trouble_brewing",
        human_mode="none",
        storyteller_mode="auto",
        backend_mode="mock",
        audit_mode=True,
        discussion_rounds=1,
        max_nomination_rounds=2,
    )


def _empath_suppressed_state() -> GameState:
    return GameState(
        phase=GamePhase.NIGHT,
        round_number=2,
        day_number=1,
        seat_order=("p1", "p2", "p3", "p4", "p5"),
        config=_base_config(),
        payload={"seed": "storyteller-balance-empath"},
        players=(
            PlayerState(player_id="p1", name="Empath", role_id="empath", team=Team.GOOD, statuses=(PlayerStatus.ALIVE, PlayerStatus.DRUNK)),
            PlayerState(player_id="p2", name="Minion", role_id="poisoner", team=Team.EVIL),
            PlayerState(player_id="p3", name="Imp", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p4", name="Town", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p5", name="DeadTown", role_id="chef", team=Team.GOOD, is_alive=False, statuses=(PlayerStatus.DEAD,)),
        ),
        event_log=(
            GameEvent(
                event_type="execution_resolved",
                phase=GamePhase.EXECUTION,
                round_number=1,
                trace_id="balance-empath-exec",
                target="p5",
                payload={"executed": "p5", "votes": 3},
                visibility=Visibility.PUBLIC,
            ),
        ),
    )


def _fortune_teller_state() -> GameState:
    return GameState(
        phase=GamePhase.NIGHT,
        round_number=2,
        day_number=1,
        seat_order=("p1", "p2", "p3", "p4", "p5"),
        config=_base_config(),
        payload={
            "seed": "storyteller-balance-ft",
            "fortune_teller_red_herring": "p5",
        },
        players=(
            PlayerState(player_id="p1", name="Fortune Teller", role_id="fortune_teller", team=Team.GOOD),
            PlayerState(player_id="p2", name="Imp", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p3", name="Spy", role_id="spy", team=Team.EVIL),
            PlayerState(player_id="p4", name="Town", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p5", name="Chef", role_id="chef", team=Team.GOOD),
        ),
        event_log=(
            GameEvent(
                event_type="night_action_resolved",
                phase=GamePhase.NIGHT,
                round_number=2,
                trace_id="balance-ft-action",
                actor="p1",
                payload={"targets": ["p2", "p4"]},
                visibility=Visibility.STORYTELLER_ONLY,
            ),
        ),
    )


def _spy_book_state() -> GameState:
    return GameState(
        phase=GamePhase.NIGHT,
        round_number=3,
        day_number=2,
        seat_order=("p1", "p2", "p3", "p4", "p5"),
        config=_base_config(),
        payload={"seed": "storyteller-balance-spy"},
        bluffs=("chef", "monk", "slayer"),
        players=(
            PlayerState(player_id="p1", name="Spy", role_id="spy", team=Team.EVIL, statuses=(PlayerStatus.ALIVE, PlayerStatus.POISONED)),
            PlayerState(player_id="p2", name="Imp", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p3", name="Empath", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="p4", name="Virgin", role_id="virgin", team=Team.GOOD),
            PlayerState(player_id="p5", name="Saint", role_id="saint", team=Team.GOOD),
        ),
        event_log=(
            GameEvent(
                event_type="private_info_delivered",
                phase=GamePhase.FIRST_NIGHT,
                round_number=1,
                trace_id="balance-spy-evil-info",
                target="p1",
                payload={"type": "evil_reveal", "teammates": ["Imp"], "bluffs": ["chef", "monk", "slayer"]},
                visibility=Visibility.PRIVATE,
            ),
        ),
    )


def _undertaker_state() -> GameState:
    return GameState(
        phase=GamePhase.NIGHT,
        round_number=2,
        day_number=1,
        seat_order=("p1", "p2", "p3", "p4", "p5"),
        config=_base_config(),
        payload={"seed": "storyteller-balance-undertaker"},
        players=(
            PlayerState(player_id="p1", name="Undertaker", role_id="undertaker", team=Team.GOOD),
            PlayerState(player_id="p2", name="Imp", role_id="imp", team=Team.EVIL, is_alive=False),
            PlayerState(player_id="p3", name="Town", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p4", name="Spy", role_id="spy", team=Team.EVIL),
            PlayerState(player_id="p5", name="Chef", role_id="chef", team=Team.GOOD),
        ),
        event_log=(
            GameEvent(
                event_type="execution_resolved",
                phase=GamePhase.EXECUTION,
                round_number=1,
                trace_id="balance-undertaker-exec",
                target="p2",
                payload={"executed": "p2", "votes": 3},
                visibility=Visibility.PUBLIC,
            ),
        ),
    )


def _daytime_trace_state() -> GameState:
    return GameState(
        phase=GamePhase.EXECUTION,
        round_number=2,
        day_number=1,
        seat_order=("p1", "p2", "p3", "p4"),
        config=_base_config(4),
        players=(
            PlayerState(player_id="p1", name="Player 1", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Player 2", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p3", name="Player 3", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p4", name="Player 4", role_id="spy", team=Team.EVIL, is_alive=False),
        ),
        event_log=(
            GameEvent(
                event_type="nomination_started",
                phase=GamePhase.NOMINATION,
                round_number=2,
                trace_id="curated-day-trace-01",
                actor="p1",
                target="p3",
                payload={"threshold": 2},
                visibility=Visibility.PUBLIC,
            ),
            GameEvent(
                event_type="voting_resolved",
                phase=GamePhase.VOTING,
                round_number=2,
                trace_id="curated-day-trace-01",
                actor="p1",
                target="p3",
                payload={"passed": True, "votes": 3, "needed": 2},
                visibility=Visibility.PUBLIC,
            ),
            GameEvent(
                event_type="execution_resolved",
                phase=GamePhase.EXECUTION,
                round_number=2,
                trace_id="curated-day-trace-02",
                target="p3",
                payload={"executed": "p3", "votes": 3},
                visibility=Visibility.PUBLIC,
            ),
        ),
        payload={
            "nomination_history": [
                {"day_number": 1, "kind": "nomination_started", "round": 1, "nominator": "p1", "nominee": "p3", "trace_id": "curated-day-trace-01"},
                {"day_number": 1, "kind": "voting_resolved", "round": 1, "nominee": "p3", "passed": True, "votes": 3, "needed": 2, "trace_id": "curated-day-trace-01"},
                {"day_number": 1, "kind": "execution_resolved", "round": 1, "executed": "p3", "votes": 3, "trace_id": "curated-day-trace-02"},
            ]
        },
    )


def _record_daytime_resolution_judgements(
    agent: StorytellerAgent,
    *,
    nomination_trace: str,
    execution_trace: str,
    round_number: int,
    nominator: str,
    nominee: str,
    threshold: int,
    votes: int,
    needed: int,
) -> None:
    agent.record_judgement(
        "nomination_started",
        decision="start",
        phase=GamePhase.NOMINATION.value,
        round_number=round_number,
        trace_id=nomination_trace,
        nominator=nominator,
        nominee=nominee,
        threshold=threshold,
    )
    agent.record_judgement(
        "voting",
        decision="resolve",
        phase=GamePhase.VOTING.value,
        round_number=round_number,
        trace_id=nomination_trace,
        nominee=nominee,
        passed=True,
        votes=votes,
        needed=needed,
    )
    agent.record_judgement(
        "execution",
        decision="finalize",
        phase=GamePhase.EXECUTION.value,
        round_number=round_number,
        trace_id=execution_trace,
        executed=nominee,
        votes=votes,
    )


def _build_static_samples() -> list[dict]:
    agent = StorytellerAgent(MockBackend())
    scenarios = [
        ("empath", _empath_suppressed_state(), "p1", "empath"),
        ("fortune_teller", _fortune_teller_state(), "p1", "fortune_teller"),
        ("spy", _spy_book_state(), "p2", "spy"),
    ]
    samples: list[dict] = []
    for _name, state, player_id, role_id in scenarios:
        samples.append(agent.build_balance_sample(state, player_id, role_id))
    return samples


def _seed_rng(seed: str) -> None:
    random.seed(seed)


def _merge_summary_dicts(base: dict[str, int], incoming: dict[str, int]) -> None:
    for key, value in incoming.items():
        base[key] = int(base.get(key, 0)) + int(value)


def _merge_aggregate_summary(target: dict[str, object], source: dict[str, object]) -> None:
    for key, value in source.items():
        if isinstance(value, dict):
            bucket = target.setdefault(key, {})
            if isinstance(bucket, dict):
                _merge_summary_dicts(bucket, value)
        else:
            target[key] = int(target.get(key, 0)) + int(value)


async def _run_full_game_storyteller_trace(seed: str, timeout_seconds: int) -> tuple[GameOrchestrator, StorytellerAgent]:
    _seed_rng(seed)
    backend = MockBackend()
    storyteller = StorytellerAgent(backend)
    state = GameState(phase=GamePhase.SETUP, payload={"seed": seed})
    orchestrator = GameOrchestrator(state)
    orchestrator.storyteller_agent = storyteller
    orchestrator.default_agent_backend = backend

    loop_task = asyncio.create_task(orchestrator.run_game_loop())
    try:
        await asyncio.sleep(0.1)
        await orchestrator.run_setup_with_options(
            player_count=5,
            host_id="host",
            is_human=False,
            discussion_rounds=1,
            storyteller_mode="auto",
            audit_mode=True,
            max_nomination_rounds=2,
            backend_mode="mock",
        )
        await asyncio.wait_for(loop_task, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        if not loop_task.done():
            loop_task.cancel()
        with suppress(asyncio.CancelledError):
            await loop_task
    except asyncio.CancelledError:
        with suppress(asyncio.CancelledError):
            await loop_task
    return orchestrator, storyteller


async def _build_curated_node_samples() -> list[tuple[str, list]]:
    scenarios = [
        ("fortune_teller", _fortune_teller_state(), "p1", "fortune_teller"),
        ("empath_suppressed", _empath_suppressed_state(), "p1", "empath"),
    ]
    exported: list[tuple[str, list]] = []
    for name, state, player_id, role_id in scenarios:
        agent = StorytellerAgent(MockBackend())
        info = await agent.decide_night_info(state, player_id, role_id)
        enriched_state = state.with_event(
            GameEvent(
                event_type="private_info_delivered",
                phase=state.phase,
                round_number=state.round_number,
                actor="storyteller",
                target=player_id,
                payload=info,
                visibility=Visibility.PRIVATE,
            )
        )
        exported.append(
            (
                name,
                build_storyteller_node_samples(
                    enriched_state,
                    storyteller_agent=agent,
                    seed=f"curated-{name}",
                ),
            )
        )

    class _LegacyFallbackStorytellerAgent(StorytellerAgent):
        def _build_base_info(self, game_state, player_id, role_id):  # type: ignore[override]
            player = game_state.get_player(player_id)
            if not player:
                return {}, "missing_player", "unavailable"
            if role_id == "undertaker":
                return {"type": "undertaker_info", "role_seen": "imp"}, "legacy_get_night_info", "fixed_info.legacy_fallback"
            return super()._build_base_info(game_state, player_id, role_id)

    legacy_agent = _LegacyFallbackStorytellerAgent(MockBackend())
    legacy_state = _undertaker_state()
    legacy_info = await legacy_agent.decide_night_info(legacy_state, "p1", "undertaker")
    legacy_enriched_state = legacy_state.with_event(
        GameEvent(
            event_type="private_info_delivered",
            phase=legacy_state.phase,
            round_number=legacy_state.round_number,
            actor="storyteller",
            target="p1",
            payload=legacy_info,
            visibility=Visibility.PRIVATE,
        )
    )
    exported.append(
        (
            "legacy_fallback",
            build_storyteller_node_samples(
                legacy_enriched_state,
                storyteller_agent=legacy_agent,
                seed="curated-legacy-fallback",
            ),
        )
    )

    day_agent = StorytellerAgent(MockBackend())
    _record_daytime_resolution_judgements(
        day_agent,
        nomination_trace="curated-day-trace-01",
        execution_trace="curated-day-trace-02",
        round_number=2,
        nominator="p1",
        nominee="p3",
        threshold=2,
        votes=3,
        needed=2,
    )
    exported.append(
        (
            "daytime_resolution",
            build_storyteller_node_samples(
                _daytime_trace_state(),
                storyteller_agent=day_agent,
                seed="curated-daytime-resolution",
            ),
        )
    )
    return exported


async def _build_curated_full_game_samples() -> list[tuple[dict[str, object], list]]:
    exported: list[tuple[dict[str, object], list]] = []

    suppressed_agent = StorytellerAgent(MockBackend())
    suppressed_base = _empath_suppressed_state()
    suppressed_agent.record_judgement(
        "execution",
        decision="finalize",
        phase=GamePhase.EXECUTION.value,
        round_number=1,
        trace_id="balance-empath-exec",
        executed="p5",
        votes=3,
    )
    suppressed_info = await suppressed_agent.decide_night_info(suppressed_base, "p1", "empath")
    suppressed_trace = "curated-full-suppressed-info"
    suppressed_action_trace = "curated-full-suppressed-night"
    suppressed_nom_trace = "curated-full-suppressed-nom"
    suppressed_exec_trace = "curated-full-suppressed-exec"
    suppressed_agent.record_judgement(
        "night_action",
        decision="resolved",
        phase=GamePhase.NIGHT.value,
        round_number=2,
        trace_id=suppressed_action_trace,
        actor="p3",
        target="p4",
        role_id="imp",
    )
    _record_daytime_resolution_judgements(
        suppressed_agent,
        nomination_trace=suppressed_nom_trace,
        execution_trace=suppressed_exec_trace,
        round_number=2,
        nominator="p2",
        nominee="p3",
        threshold=3,
        votes=4,
        needed=3,
    )
    suppressed_final = GameState(
        phase=GamePhase.GAME_OVER,
        round_number=2,
        day_number=2,
        seat_order=suppressed_base.seat_order,
        config=suppressed_base.config,
        payload={"seed": "curated-full-game-suppressed"},
        players=suppressed_base.players,
        event_log=(
            *suppressed_base.event_log,
            GameEvent(
                event_type="private_info_delivered",
                phase=GamePhase.NIGHT,
                round_number=2,
                trace_id=suppressed_trace,
                actor="storyteller",
                target="p1",
                payload=suppressed_info,
                visibility=Visibility.PRIVATE,
            ),
            GameEvent(
                event_type="night_action_resolved",
                phase=GamePhase.NIGHT,
                round_number=2,
                trace_id=suppressed_action_trace,
                actor="p3",
                target="p4",
                payload={"action": "kill"},
                visibility=Visibility.STORYTELLER_ONLY,
            ),
            GameEvent(
                event_type="nomination_started",
                phase=GamePhase.NOMINATION,
                round_number=2,
                trace_id=suppressed_nom_trace,
                actor="p2",
                target="p3",
                payload={"threshold": 3},
                visibility=Visibility.PUBLIC,
            ),
            GameEvent(
                event_type="voting_resolved",
                phase=GamePhase.VOTING,
                round_number=2,
                trace_id=suppressed_nom_trace,
                actor="p2",
                target="p3",
                payload={"passed": True, "votes": 4, "needed": 3},
                visibility=Visibility.PUBLIC,
            ),
            GameEvent(
                event_type="execution_resolved",
                phase=GamePhase.EXECUTION,
                round_number=2,
                trace_id=suppressed_exec_trace,
                target="p3",
                payload={"executed": "p3", "votes": 4},
                visibility=Visibility.PUBLIC,
            ),
        ),
    )
    exported.append(
        (
            {
                "seed": "curated-full-game-suppressed",
                "source": "curated_full_game",
                "state": suppressed_final,
                "storyteller": suppressed_agent,
            },
            build_storyteller_node_samples(
                suppressed_final,
                storyteller_agent=suppressed_agent,
                seed="curated-full-game-suppressed",
            ),
        )
    )

    class _LegacyFallbackStorytellerAgent(StorytellerAgent):
        def _build_base_info(self, game_state, player_id, role_id):  # type: ignore[override]
            player = game_state.get_player(player_id)
            if not player:
                return {}, "missing_player", "unavailable"
            if role_id == "undertaker":
                return {"type": "undertaker_info", "role_seen": "imp"}, "legacy_get_night_info", "fixed_info.legacy_fallback"
            return super()._build_base_info(game_state, player_id, role_id)

    legacy_agent = _LegacyFallbackStorytellerAgent(MockBackend())
    legacy_base = _undertaker_state()
    legacy_agent.record_judgement(
        "execution",
        decision="finalize",
        phase=GamePhase.EXECUTION.value,
        round_number=1,
        trace_id="balance-undertaker-exec",
        executed="p2",
        votes=3,
    )
    legacy_info = await legacy_agent.decide_night_info(legacy_base, "p1", "undertaker")
    legacy_trace = "curated-full-legacy-info"
    legacy_action_trace = "curated-full-legacy-night"
    legacy_nom_trace = "curated-full-legacy-nom"
    legacy_exec_trace = "curated-full-legacy-exec"
    legacy_agent.record_judgement(
        "night_action",
        decision="resolved",
        phase=GamePhase.NIGHT.value,
        round_number=2,
        trace_id=legacy_action_trace,
        actor="p4",
        target="p1",
        role_id="spy",
    )
    _record_daytime_resolution_judgements(
        legacy_agent,
        nomination_trace=legacy_nom_trace,
        execution_trace=legacy_exec_trace,
        round_number=2,
        nominator="p3",
        nominee="p4",
        threshold=2,
        votes=3,
        needed=2,
    )
    legacy_final = GameState(
        phase=GamePhase.GAME_OVER,
        round_number=2,
        day_number=2,
        seat_order=legacy_base.seat_order,
        config=legacy_base.config,
        payload={"seed": "curated-full-game-legacy"},
        players=legacy_base.players,
        event_log=(
            *legacy_base.event_log,
            GameEvent(
                event_type="private_info_delivered",
                phase=GamePhase.NIGHT,
                round_number=2,
                trace_id=legacy_trace,
                actor="storyteller",
                target="p1",
                payload=legacy_info,
                visibility=Visibility.PRIVATE,
            ),
            GameEvent(
                event_type="night_action_resolved",
                phase=GamePhase.NIGHT,
                round_number=2,
                trace_id=legacy_action_trace,
                actor="p4",
                target="p1",
                payload={"action": "spy_book"},
                visibility=Visibility.STORYTELLER_ONLY,
            ),
            GameEvent(
                event_type="nomination_started",
                phase=GamePhase.NOMINATION,
                round_number=2,
                trace_id=legacy_nom_trace,
                actor="p3",
                target="p4",
                payload={"threshold": 2},
                visibility=Visibility.PUBLIC,
            ),
            GameEvent(
                event_type="voting_resolved",
                phase=GamePhase.VOTING,
                round_number=2,
                trace_id=legacy_nom_trace,
                actor="p3",
                target="p4",
                payload={"passed": True, "votes": 3, "needed": 2},
                visibility=Visibility.PUBLIC,
            ),
            GameEvent(
                event_type="execution_resolved",
                phase=GamePhase.EXECUTION,
                round_number=2,
                trace_id=legacy_exec_trace,
                target="p4",
                payload={"executed": "p4", "votes": 3},
                visibility=Visibility.PUBLIC,
            ),
        ),
    )
    exported.append(
        (
            {
                "seed": "curated-full-game-legacy",
                "source": "curated_full_game",
                "state": legacy_final,
                "storyteller": legacy_agent,
            },
            build_storyteller_node_samples(
                legacy_final,
                storyteller_agent=legacy_agent,
                seed="curated-full-game-legacy",
            ),
        )
    )

    storyteller_agent = StorytellerAgent(MockBackend())
    storyteller_base = _fortune_teller_state()
    storyteller_info = await storyteller_agent.decide_night_info(storyteller_base, "p1", "fortune_teller")
    storyteller_trace = "curated-full-storyteller-info"
    storyteller_action_trace = "curated-full-storyteller-night"
    storyteller_nom_trace = "curated-full-storyteller-nom"
    storyteller_exec_trace = "curated-full-storyteller-exec"
    storyteller_agent.record_judgement(
        "night_action",
        decision="resolved",
        phase=GamePhase.NIGHT.value,
        round_number=2,
        trace_id=storyteller_action_trace,
        actor="p2",
        target="p4",
        role_id="imp",
    )
    _record_daytime_resolution_judgements(
        storyteller_agent,
        nomination_trace=storyteller_nom_trace,
        execution_trace=storyteller_exec_trace,
        round_number=2,
        nominator="p4",
        nominee="p2",
        threshold=2,
        votes=3,
        needed=2,
    )
    storyteller_final = GameState(
        phase=GamePhase.GAME_OVER,
        round_number=2,
        day_number=2,
        seat_order=storyteller_base.seat_order,
        config=storyteller_base.config,
        payload=storyteller_base.payload | {"seed": "curated-full-game-storyteller"},
        players=storyteller_base.players,
        event_log=(
            *storyteller_base.event_log,
            GameEvent(
                event_type="private_info_delivered",
                phase=GamePhase.NIGHT,
                round_number=2,
                trace_id=storyteller_trace,
                actor="storyteller",
                target="p1",
                payload=storyteller_info,
                visibility=Visibility.PRIVATE,
            ),
            GameEvent(
                event_type="night_action_resolved",
                phase=GamePhase.NIGHT,
                round_number=2,
                trace_id=storyteller_action_trace,
                actor="p2",
                target="p4",
                payload={"action": "kill"},
                visibility=Visibility.STORYTELLER_ONLY,
            ),
            GameEvent(
                event_type="nomination_started",
                phase=GamePhase.NOMINATION,
                round_number=2,
                trace_id=storyteller_nom_trace,
                actor="p4",
                target="p2",
                payload={"threshold": 2},
                visibility=Visibility.PUBLIC,
            ),
            GameEvent(
                event_type="voting_resolved",
                phase=GamePhase.VOTING,
                round_number=2,
                trace_id=storyteller_nom_trace,
                actor="p4",
                target="p2",
                payload={"passed": True, "votes": 3, "needed": 2},
                visibility=Visibility.PUBLIC,
            ),
            GameEvent(
                event_type="execution_resolved",
                phase=GamePhase.EXECUTION,
                round_number=2,
                trace_id=storyteller_exec_trace,
                target="p2",
                payload={"executed": "p2", "votes": 3},
                visibility=Visibility.PUBLIC,
            ),
        ),
    )
    exported.append(
        (
            {
                "seed": "curated-full-game-storyteller",
                "source": "curated_full_game",
                "state": storyteller_final,
                "storyteller": storyteller_agent,
            },
            build_storyteller_node_samples(
                storyteller_final,
                storyteller_agent=storyteller_agent,
                seed="curated-full-game-storyteller",
            ),
        )
    )

    return exported


async def export_samples(
    output_dir: Path,
    full_games: int = 3,
    timeout_seconds: int = 20,
    max_node_samples: int | None = None,
) -> tuple[list[dict], list[Path], dict[str, int]]:
    output_dir.mkdir(parents=True, exist_ok=True)

    static_samples = _build_static_samples()
    static_files: list[str] = []
    for idx, sample in enumerate(static_samples, start=1):
        filename = f"sample_{idx:02d}_{sample['role_id']}.json"
        (output_dir / filename).write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
        static_files.append(filename)

    curated_node_paths: list[Path] = []
    curated_aggregate = {
        "node_count": 0,
        "judgement_entry_count": 0,
        "night_info_judgement_count": 0,
        "suppressed_info_count": 0,
        "distorted_info_count": 0,
        "legacy_fallback_count": 0,
        "human_storyteller_step_count": 0,
        "event_node_fallback_count": 0,
        "private_info_delivery_node_count": 0,
        "night_action_resolution_node_count": 0,
        "nomination_started_node_count": 0,
        "voting_resolved_node_count": 0,
        "execution_resolved_node_count": 0,
        "ended_before_day_3_count": 0,
        "reached_final_4_count": 0,
        "reached_final_3_count": 0,
        "single_side_runaway_risk_count": 0,
        "hard_lock_risk_count": 0,
        "judgement_category_counts": {},
        "judgement_bucket_counts": {},
        "distortion_strategy_counts": {},
        "adjudication_path_counts": {},
        "phase_counts": {},
        "event_type_counts": {},
    }
    curated_sets = await _build_curated_node_samples()
    for scenario_name, curated_samples in curated_sets:
        scenario_dir = output_dir / "curated_nodes" / scenario_name
        scenario_dir.mkdir(parents=True, exist_ok=True)
        scenario_summary = aggregate_storyteller_node_samples(curated_samples)
        for idx, sample in enumerate(curated_samples, start=1):
            chosen = sample.chosen_adjudication or {}
            event_type = chosen.get("decision", "node")
            safe_name = str(event_type).replace("/", "_")
            path = scenario_dir / f"node_{idx:02d}_{safe_name}.json"
            export_storyteller_adjudication_sample(sample, path)
            curated_node_paths.append(path)
        (scenario_dir / "sample_index.json").write_text(
            json.dumps(
                {
                    "scenario": scenario_name,
                    "node_count": len(curated_samples),
                    "files": [path.name for path in sorted(scenario_dir.glob("node_*.json"))],
                    "aggregate_balance_summary": scenario_summary,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        _merge_aggregate_summary(curated_aggregate, scenario_summary)

    game_summaries: list[dict[str, str | int | None | dict[str, int]]] = []
    node_files: list[Path] = []
    aggregate = {
        "full_game_count": 0,
        "curated_node_count": len(curated_node_paths),
        "node_count": 0,
        "judgement_entry_count": 0,
        "night_info_judgement_count": 0,
        "ended_before_day_3_count": 0,
        "reached_final_4_count": 0,
        "reached_final_3_count": 0,
        "single_side_runaway_risk_count": 0,
        "hard_lock_risk_count": 0,
        "suppressed_info_count": 0,
        "distorted_info_count": 0,
        "legacy_fallback_count": 0,
        "human_storyteller_step_count": 0,
        "event_node_fallback_count": 0,
        "private_info_delivery_node_count": 0,
        "night_action_resolution_node_count": 0,
        "nomination_started_node_count": 0,
        "voting_resolved_node_count": 0,
        "execution_resolved_node_count": 0,
        "judgement_category_counts": {},
        "judgement_bucket_counts": {},
        "distortion_strategy_counts": {},
        "adjudication_path_counts": {},
        "phase_counts": {},
        "event_type_counts": {},
    }
    aggregate["curated_node_count"] = len(curated_node_paths)
    curated_for_merge = {key: value for key, value in curated_aggregate.items()}
    _merge_aggregate_summary(aggregate, curated_for_merge)
    curated_full_games = await _build_curated_full_game_samples()
    for metadata, node_samples in curated_full_games:
        game_state = metadata["state"]
        seed = str(metadata["seed"])
        game_aggregate = aggregate_storyteller_node_samples(node_samples)
        node_dir = output_dir / "full_game_nodes" / game_state.game_id
        node_dir.mkdir(parents=True, exist_ok=True)
        local_paths: list[Path] = []
        for idx, sample in enumerate(node_samples, start=1):
            chosen = sample.chosen_adjudication or {}
            event_type = chosen.get("decision", "node")
            safe_name = str(event_type).replace("/", "_")
            path = node_dir / f"node_{idx:02d}_{safe_name}.json"
            export_storyteller_adjudication_sample(sample, path)
            node_files.append(path)
            local_paths.append(path)
        (node_dir / "sample_index.json").write_text(
            json.dumps(
                {
                    "seed": seed,
                    "game_id": game_state.game_id,
                    "winner": game_state.winning_team.value if game_state.winning_team else None,
                    "final_phase": game_state.phase.value,
                    "source": metadata.get("source", "curated_full_game"),
                    "node_count": len(node_samples),
                    "files": [path.name for path in sorted(local_paths)],
                    "aggregate_balance_summary": game_aggregate,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        _merge_aggregate_summary(aggregate, game_aggregate)
        aggregate["full_game_count"] += 1
        game_summaries.append(
            {
                "seed": seed,
                "game_id": game_state.game_id,
                "winner": game_state.winning_team.value if game_state.winning_team else None,
                "final_phase": game_state.phase.value,
                "source": metadata.get("source", "curated_full_game"),
                "node_count": len(node_samples),
                "aggregate_balance_summary": game_aggregate,
            }
        )
    for game_index in range(1, max(0, full_games) + 1):
        seed = f"storyteller-balance-full-game-{game_index:02d}"
        orchestrator, storyteller = await _run_full_game_storyteller_trace(seed, timeout_seconds)
        snapshots = [snapshot.game_state for snapshot in orchestrator.snapshot_manager.snapshots]
        node_samples = build_storyteller_node_samples(
            orchestrator.state,
            snapshots=snapshots,
            storyteller_agent=storyteller,
            seed=seed,
        )
        if max_node_samples is not None:
            node_samples = node_samples[:max(0, max_node_samples)]

        game_aggregate = aggregate_storyteller_node_samples(node_samples)

        node_dir = output_dir / "full_game_nodes" / orchestrator.state.game_id
        node_dir.mkdir(parents=True, exist_ok=True)
        for idx, sample in enumerate(node_samples, start=1):
            chosen = sample.chosen_adjudication or {}
            event_type = chosen.get("decision", "node")
            safe_name = str(event_type).replace("/", "_")
            path = node_dir / f"node_{idx:02d}_{safe_name}.json"
            export_storyteller_adjudication_sample(sample, path)
            node_files.append(path)
        (node_dir / "sample_index.json").write_text(
            json.dumps(
                {
                    "seed": seed,
                    "game_id": orchestrator.state.game_id,
                    "winner": orchestrator.winner.value if orchestrator.winner else None,
                    "final_phase": orchestrator.state.phase.value,
                    "source": "mock_full_game",
                    "node_count": len(node_samples),
                    "files": [path.name for path in sorted(node_dir.glob("node_*.json"))],
                    "aggregate_balance_summary": game_aggregate,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        _merge_aggregate_summary(aggregate, game_aggregate)
        aggregate["full_game_count"] += 1
        game_summaries.append(
            {
                "seed": seed,
                "game_id": orchestrator.state.game_id,
                "winner": orchestrator.winner.value if orchestrator.winner else None,
                "final_phase": orchestrator.state.phase.value,
                "source": "mock_full_game",
                "node_count": len(node_samples),
                "aggregate_balance_summary": game_aggregate,
            }
        )

    index_payload = {
        "sample_count": len(static_samples),
        "files": static_files,
        "curated_node_count": len(curated_node_paths),
        "curated_node_files": [str(path.relative_to(output_dir)) for path in curated_node_paths],
        "full_game_node_count": len(node_files),
        "full_game_node_files": [str(path.relative_to(output_dir)) for path in node_files],
        "full_games": game_summaries,
        "aggregate_balance_summary": aggregate,
    }
    (output_dir / "sample_index.json").write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return static_samples, [*curated_node_paths, *node_files], {
        "curated_node_count": len(curated_node_paths),
        "full_game_node_count": len(node_files),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default=str(Path("storyteller_eval_samples")),
        help="Directory to write storyteller balance samples into.",
    )
    parser.add_argument(
        "--full-games",
        type=int,
        default=1,
        help="How many full mock games to export storyteller node samples from.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=8,
        help="Per full mock game timeout in seconds.",
    )
    parser.add_argument(
        "--max-node-samples",
        type=int,
        default=24,
        help="Optional cap on exported full-game node samples per game.",
    )
    args = parser.parse_args()

    static_samples, exported_node_paths, export_counts = asyncio.run(
        export_samples(
            Path(args.output_dir),
            full_games=args.full_games,
            timeout_seconds=args.timeout_seconds,
            max_node_samples=args.max_node_samples,
        )
    )
    if exported_node_paths:
        payload = json.loads(exported_node_paths[0].read_text(encoding="utf-8"))
        print(json.dumps(payload, ensure_ascii=False))
    elif static_samples:
        print(json.dumps(static_samples[0], ensure_ascii=False))
    print(
        f"storyteller balance sample export: ok "
        f"(static={len(static_samples)}, curated_nodes={export_counts['curated_node_count']}, full_game_nodes={export_counts['full_game_node_count']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
