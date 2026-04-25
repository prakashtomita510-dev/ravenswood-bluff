from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.agents.storyteller_agent import StorytellerAgent
from src.llm.mock_backend import MockBackend
from src.orchestrator.storyteller_balance import (
    aggregate_storyteller_node_samples,
    build_storyteller_adjudication_sample,
    build_storyteller_node_samples,
    export_storyteller_adjudication_sample,
)
from src.state.game_state import GameConfig, GameEvent, GamePhase, GameState, PlayerState, Team, Visibility


def _config() -> GameConfig:
    return GameConfig(
        player_count=4,
        script_id="trouble_brewing",
        human_mode="none",
        storyteller_mode="auto",
        backend_mode="mock",
        audit_mode=True,
    )


def _fortune_teller_state() -> GameState:
    return GameState(
        phase=GamePhase.NIGHT,
        round_number=2,
        day_number=1,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            PlayerState(player_id="p1", name="FT", role_id="fortune_teller", team=Team.GOOD),
            PlayerState(player_id="p2", name="Imp", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p3", name="Town", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p4", name="Chef", role_id="chef", team=Team.GOOD),
        ),
        event_log=(
            GameEvent(
                event_type="night_action_resolved",
                phase=GamePhase.NIGHT,
                round_number=2,
                actor="p1",
                payload={"targets": ["p2", "p3"]},
                visibility=Visibility.STORYTELLER_ONLY,
            ),
        ),
        payload={"fortune_teller_red_herring": "p4", "nomination_history": [{"kind": "no_nomination", "day_number": 1}]},
        config=_config(),
    )


def _daytime_trace_state() -> GameState:
    return GameState(
        phase=GamePhase.EXECUTION,
        round_number=2,
        day_number=1,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            PlayerState(player_id="p1", name="A", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="B", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p3", name="C", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p4", name="D", role_id="spy", team=Team.EVIL, is_alive=False),
        ),
        event_log=(
            GameEvent(
                event_type="nomination_started",
                phase=GamePhase.NOMINATION,
                round_number=2,
                trace_id="trace-day-01",
                actor="p1",
                target="p3",
                payload={"threshold": 2},
                visibility=Visibility.PUBLIC,
            ),
            GameEvent(
                event_type="voting_resolved",
                phase=GamePhase.VOTING,
                round_number=2,
                trace_id="trace-day-01",
                actor="p1",
                target="p3",
                payload={"passed": True, "votes": 3, "needed": 2},
                visibility=Visibility.PUBLIC,
            ),
            GameEvent(
                event_type="execution_resolved",
                phase=GamePhase.EXECUTION,
                round_number=2,
                trace_id="trace-day-02",
                target="p3",
                payload={"executed": "p3", "votes": 3},
                visibility=Visibility.PUBLIC,
            ),
        ),
        config=_config(),
    )


@pytest.mark.asyncio
async def test_storyteller_balance_sample_contains_truth_context_and_judgement():
    agent = StorytellerAgent(MockBackend())
    state = _fortune_teller_state()
    info = await agent.decide_night_info(state, "p1", "fortune_teller")
    enriched_state = state.with_event(
        GameEvent(
            event_type="private_info_delivered",
            phase=state.phase,
            round_number=state.round_number,
            actor="storyteller",
            target="p1",
            payload=info,
            visibility=Visibility.PRIVATE,
        )
    )

    sample = build_storyteller_adjudication_sample(enriched_state, storyteller_agent=agent, seed="ft-sample")

    assert sample.script_id == "trouble_brewing"
    assert sample.seed == "ft-sample"
    assert sample.chosen_adjudication is not None
    assert sample.chosen_adjudication["category"] == "night_info"
    assert sample.storyteller_context["fortune_teller_red_herring"] == "p4"
    assert sample.players_private_delivery_history["p1"][0]["payload"]["type"] == "fortune_teller_info"
    assert sample.balance_signals.good_alive == 3
    assert sample.balance_signals.evil_alive == 1
    assert sample.balance_signals.reached_final_4 is True
    assert sample.balance_signals.storyteller_judgement_count >= 1
    assert sample.balance_signals.distorted_info_count == 0

    output_dir = Path(__file__).resolve().parents[1] / "test_runs" / "_storyteller_balance"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = export_storyteller_adjudication_sample(sample, output_dir / "ft_sample.json")
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["chosen_adjudication"]["category"] == "night_info"
    assert payload["balance_signals"]["good_alive"] == 3


def test_storyteller_balance_sample_detects_hard_lock_risk():
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=3,
        day_number=3,
        seat_order=("p1", "p2", "p3", "p4", "p5"),
        players=(
            PlayerState(player_id="p1", name="A", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="B", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p3", name="C", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p4", name="D", role_id="librarian", team=Team.GOOD, is_alive=False),
            PlayerState(player_id="p5", name="E", role_id="spy", team=Team.EVIL, is_alive=False),
        ),
        payload={
            "nomination_history": [
                {"kind": "no_nomination", "day_number": 2},
                {"kind": "no_nomination", "day_number": 3},
            ]
        },
        config=_config(),
    )

    sample = build_storyteller_adjudication_sample(state)

    assert sample.balance_signals.hard_lock_risk is True
    assert sample.balance_signals.alive_total == 3
    assert sample.balance_signals.no_nomination_count == 2
    assert sample.balance_signals.no_nomination_count == 2
    assert sample.balance_signals.early_end_pressure is True


def test_storyteller_balance_builds_full_game_node_samples_from_event_log():
    state = GameState(
        phase=GamePhase.GAME_OVER,
        round_number=2,
        day_number=1,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            PlayerState(player_id="p1", name="FT", role_id="fortune_teller", team=Team.GOOD),
            PlayerState(player_id="p2", name="Imp", role_id="imp", team=Team.EVIL, is_alive=False),
            PlayerState(player_id="p3", name="Town", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p4", name="Spy", role_id="spy", team=Team.EVIL),
        ),
        event_log=(
            GameEvent(
                event_type="private_info_delivered",
                phase=GamePhase.NIGHT,
                round_number=2,
                trace_id="trace-night-info",
                actor="storyteller",
                target="p1",
                payload={"type": "fortune_teller_info", "has_demon": True},
                visibility=Visibility.PRIVATE,
            ),
            GameEvent(
                event_type="execution_resolved",
                phase=GamePhase.EXECUTION,
                round_number=2,
                trace_id="trace-exec",
                target="p2",
                payload={"executed": "p2", "votes": 3},
                visibility=Visibility.PUBLIC,
            ),
        ),
        payload={"fortune_teller_red_herring": "p3"},
        config=_config(),
    )

    samples = build_storyteller_node_samples(state, seed="full-game-node-test")

    assert len(samples) == 2
    assert samples[0].event_log_so_far[-1]["event_type"] == "private_info_delivered"
    assert samples[0].chosen_adjudication["decision"] == "private_info_delivered"
    assert samples[1].event_log_so_far[-1]["event_type"] == "execution_resolved"
    assert samples[1].chosen_adjudication["decision"] == "execution_resolved"
    assert samples[0].balance_signals.private_info_delivery_count == 1


@pytest.mark.asyncio
async def test_storyteller_balance_matches_private_delivery_to_night_info_judgement():
    agent = StorytellerAgent(MockBackend())
    state = _fortune_teller_state()
    info = await agent.decide_night_info(state, "p1", "fortune_teller")
    enriched_state = state.with_event(
        GameEvent(
            event_type="private_info_delivered",
            phase=state.phase,
            round_number=state.round_number,
            actor="storyteller",
            target="p1",
            payload=info,
            visibility=Visibility.PRIVATE,
        )
    )

    samples = build_storyteller_node_samples(
        enriched_state,
        storyteller_agent=agent,
        seed="night-info-match-test",
    )

    assert len(samples) == 2
    private_sample = samples[-1]
    assert private_sample.event_log_so_far[-1]["event_type"] == "private_info_delivered"
    assert private_sample.chosen_adjudication["category"] == "night_info"
    assert private_sample.chosen_adjudication["player_id"] == "p1"
    assert private_sample.chosen_adjudication["info_type"] == info["type"]


def test_storyteller_balance_sample_tracks_delivery_and_execution_counts():
    state = GameState(
        phase=GamePhase.GAME_OVER,
        round_number=2,
        day_number=1,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            PlayerState(player_id="p1", name="FT", role_id="fortune_teller", team=Team.GOOD),
            PlayerState(player_id="p2", name="Imp", role_id="imp", team=Team.EVIL, is_alive=False),
            PlayerState(player_id="p3", name="Town", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p4", name="Spy", role_id="spy", team=Team.EVIL),
        ),
        event_log=(
            GameEvent(
                event_type="private_info_delivered",
                phase=GamePhase.FIRST_NIGHT,
                round_number=1,
                trace_id="trace-private",
                actor="storyteller",
                target="p1",
                payload={"type": "fortune_teller_info", "has_demon": True},
                visibility=Visibility.PRIVATE,
            ),
            GameEvent(
                event_type="night_action_resolved",
                phase=GamePhase.NIGHT,
                round_number=2,
                trace_id="trace-night",
                actor="p2",
                target="p3",
                payload={"action": "kill"},
                visibility=Visibility.STORYTELLER_ONLY,
            ),
            GameEvent(
                event_type="execution_resolved",
                phase=GamePhase.EXECUTION,
                round_number=2,
                trace_id="trace-exec",
                target="p2",
                payload={"executed": "p2", "votes": 3},
                visibility=Visibility.PUBLIC,
            ),
        ),
        config=_config(),
    )

    sample = build_storyteller_adjudication_sample(state)

    assert sample.balance_signals.private_info_delivery_count == 1
    assert sample.balance_signals.night_action_resolution_count == 1
    assert sample.balance_signals.execution_count == 1


def test_storyteller_balance_aggregates_node_sample_metrics():
    state = GameState(
        phase=GamePhase.GAME_OVER,
        round_number=2,
        day_number=1,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            PlayerState(player_id="p1", name="FT", role_id="fortune_teller", team=Team.GOOD),
            PlayerState(player_id="p2", name="Imp", role_id="imp", team=Team.EVIL, is_alive=False),
            PlayerState(player_id="p3", name="Town", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p4", name="Spy", role_id="spy", team=Team.EVIL),
        ),
        event_log=(
            GameEvent(
                event_type="private_info_delivered",
                phase=GamePhase.NIGHT,
                round_number=2,
                trace_id="trace-night-info",
                actor="storyteller",
                target="p1",
                payload={"type": "fortune_teller_info", "has_demon": True},
                visibility=Visibility.PRIVATE,
            ),
            GameEvent(
                event_type="execution_resolved",
                phase=GamePhase.EXECUTION,
                round_number=2,
                trace_id="trace-exec",
                target="p2",
                payload={"executed": "p2", "votes": 3},
                visibility=Visibility.PUBLIC,
            ),
        ),
        payload={"fortune_teller_red_herring": "p3"},
        config=_config(),
    )

    samples = build_storyteller_node_samples(state, seed="aggregate-node-test")
    summary = aggregate_storyteller_node_samples(samples)

    assert summary["node_count"] == 2
    assert summary["private_info_delivery_node_count"] == 1
    assert summary["execution_resolved_node_count"] == 1
    assert summary["event_node_fallback_count"] == 2
    assert summary["event_type_counts"]["private_info_delivered"] == 1
    assert summary["event_type_counts"]["execution_resolved"] == 1


def test_storyteller_balance_matches_daytime_nodes_to_judgements():
    agent = StorytellerAgent(MockBackend())
    state = _daytime_trace_state()
    agent.record_judgement(
        "nomination_started",
        decision="start",
        phase=GamePhase.NOMINATION.value,
        round_number=2,
        trace_id="trace-day-01",
        nominator="p1",
        nominee="p3",
        threshold=2,
    )
    agent.record_judgement(
        "voting",
        decision="resolve",
        phase=GamePhase.VOTING.value,
        round_number=2,
        trace_id="trace-day-01",
        nominee="p3",
        passed=True,
        votes=3,
        needed=2,
    )
    agent.record_judgement(
        "execution",
        decision="finalize",
        phase=GamePhase.EXECUTION.value,
        round_number=2,
        trace_id="trace-day-02",
        executed="p3",
        votes=3,
    )

    samples = build_storyteller_node_samples(
        state,
        storyteller_agent=agent,
        seed="daytime-judgement-match",
    )

    assert len(samples) == 3
    assert samples[0].chosen_adjudication["category"] == "nomination_started"
    assert samples[1].chosen_adjudication["category"] == "voting"
    assert samples[2].chosen_adjudication["category"] == "execution"
    summary = aggregate_storyteller_node_samples(samples)
    assert summary["judgement_category_counts"]["nomination_started"] == 1
    assert summary["judgement_category_counts"]["voting"] == 1
    assert summary["judgement_category_counts"]["execution"] == 1


def test_storyteller_balance_uses_full_decision_ledger_for_node_matching():
    agent = StorytellerAgent(MockBackend())
    state = GameState(
        phase=GamePhase.NIGHT,
        round_number=1,
        day_number=0,
        seat_order=("p1", "p2"),
        players=(
            PlayerState(player_id="p1", name="Spy", role_id="spy", team=Team.EVIL),
            PlayerState(player_id="p2", name="Chef", role_id="chef", team=Team.GOOD),
        ),
        event_log=(
            GameEvent(
                event_type="private_info_delivered",
                phase=GamePhase.FIRST_NIGHT,
                round_number=1,
                trace_id="trace-private-01",
                target="p2",
                payload={"type": "chef_info", "pairs": 1},
                visibility=Visibility.PRIVATE,
            ),
        ),
        config=_config(),
    )
    agent.record_judgement(
        "private_info",
        decision="deliver",
        phase=GamePhase.FIRST_NIGHT.value,
        round_number=1,
        target="p2",
        trace_id="trace-private-01",
        info_type="chef_info",
    )
    for idx in range(250):
        agent.record_judgement(
            "night_info",
            decision="skip",
            phase=GamePhase.NIGHT.value,
            round_number=idx + 2,
            player_id="p2",
            role_id="chef",
            source="empty",
            contract_mode="fixed_info",
        )

    samples = build_storyteller_node_samples(
        state,
        storyteller_agent=agent,
        seed="full-ledger-match",
    )

    assert len(samples) == 1
    assert samples[0].chosen_adjudication["category"] == "night_info"
    assert samples[0].chosen_adjudication["bucket"] == "night_info.fixed_info"
    assert samples[0].chosen_adjudication["trace_id"] == "trace-private-01"
