import importlib
import logging
from types import SimpleNamespace

from src.state.game_state import GameEvent, GamePhase, GameState


def make_orchestrator(*, state_events=(), runtime_events=(), phase=GamePhase.NIGHT):
    state = GameState(phase=phase, event_log=tuple(state_events))
    event_log = SimpleNamespace(events=tuple(runtime_events))
    return SimpleNamespace(state=state, event_log=event_log)


def load_simulate_game():
    return importlib.import_module("simulate_game")


def cleanup_storyteller_logger():
    logger = logging.getLogger("storyteller")
    for handler in list(logger.handlers):
        if hasattr(handler, "flush"):
            handler.flush()
        if hasattr(handler, "close"):
            handler.close()
        logger.removeHandler(handler)


def test_should_stop_first_execution_from_state_event_log():
    simulate_game = load_simulate_game()
    orch = make_orchestrator(
        state_events=(
            GameEvent(
                event_type="execution_resolved",
                phase=GamePhase.EXECUTION,
                round_number=1,
                payload={"executed": "p1"},
            ),
        )
    )

    assert simulate_game.should_stop(orch, "first_execution") is True
    cleanup_storyteller_logger()


def test_should_stop_first_execution_from_runtime_event_log():
    simulate_game = load_simulate_game()
    orch = make_orchestrator(
        state_events=(),
        runtime_events=(
            GameEvent(
                event_type="execution_resolved",
                phase=GamePhase.EXECUTION,
                round_number=1,
                payload={"executed": "p1"},
            ),
        ),
    )

    assert simulate_game.should_stop(orch, "first_execution") is True
    cleanup_storyteller_logger()


def test_should_not_stop_on_no_execution():
    simulate_game = load_simulate_game()
    orch = make_orchestrator(
        runtime_events=(
            GameEvent(
                event_type="execution_resolved",
                phase=GamePhase.EXECUTION,
                round_number=1,
                payload={"executed": None},
            ),
        ),
    )

    assert simulate_game.should_stop(orch, "first_execution") is False
    cleanup_storyteller_logger()


def test_event_triggers_stop_only_on_executed_payload():
    simulate_game = load_simulate_game()
    resolved = GameEvent(
        event_type="execution_resolved",
        phase=GamePhase.EXECUTION,
        round_number=1,
        payload={"executed": "p1"},
    )
    unresolved = GameEvent(
        event_type="execution_resolved",
        phase=GamePhase.EXECUTION,
        round_number=1,
        payload={"executed": None},
    )

    assert simulate_game.event_triggers_stop(resolved, "first_execution") is True
    assert simulate_game.event_triggers_stop(unresolved, "first_execution") is False
    assert simulate_game.event_triggers_stop(resolved, "day_1") is False
    cleanup_storyteller_logger()


def test_collect_summary_counts_merged_events():
    simulate_game = load_simulate_game()
    orch = make_orchestrator(
        state_events=(
            GameEvent(
                event_type="execution_resolved",
                phase=GamePhase.EXECUTION,
                round_number=1,
                payload={"executed": "p1"},
            ),
        ),
        runtime_events=(
            GameEvent(
                event_type="nomination_started",
                phase=GamePhase.NOMINATION,
                round_number=1,
                actor="p2",
                target="p3",
            ),
        ),
    )

    summary = simulate_game.collect_summary(orch)

    assert summary["execution_count"] == 1
    assert summary["legal_nomination_count"] == 1
    cleanup_storyteller_logger()
