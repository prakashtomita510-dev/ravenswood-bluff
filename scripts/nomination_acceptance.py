"""Backend acceptance checks for the nomination / voting / execution lifecycle."""

from __future__ import annotations

import asyncio
import importlib
import os
from types import SimpleNamespace

from src.agents.base_agent import BaseAgent
from src.api.server import build_nomination_state
from src.orchestrator.game_loop import GameOrchestrator
from src.state.game_state import GameConfig, GamePhase, GameState, PlayerState, Team


class DummyStoryteller:
    async def decide_drunk_role(self, script, role_ids):
        return "washerwoman"

    async def build_night_order(self, game_state, phase):
        return []

    def role_receives_storyteller_info(self, role_id):
        return True

    async def decide_night_info(self, game_state, player_id, role_id):
        return {}

    async def narrate_phase(self, game_state):
        return ""


class ScriptedAgent(BaseAgent):
    def __init__(self, pid: str, name: str, actions: dict[str, list[dict]]):
        super().__init__(pid, name)
        self.actions = actions
        self.counters: dict[str, int] = {}

    async def act(self, game_state, action_type, **kwargs):
        index = self.counters.get(action_type, 0)
        queue = self.actions.get(action_type, [])
        if index < len(queue):
            self.counters[action_type] = index + 1
            return queue[index]
        return {"action": "none"}

    async def observe_event(self, event, game_state):
        return None

    async def think(self, prompt, game_state):
        return ""


async def run_multi_round_execution_scenario() -> None:
    state = GameState(
        phase=GamePhase.NOMINATION,
        round_number=1,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="One", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Two", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="p3", name="Three", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p4", name="Four", role_id="chef", team=Team.GOOD),
        ),
        seat_order=("p1", "p2", "p3", "p4"),
        config=GameConfig(
            player_count=4,
            human_mode="none",
            human_player_ids=[],
            is_human_participant=False,
            discussion_rounds=1,
            max_nomination_rounds=3,
        ),
    )
    orch = GameOrchestrator(state)
    orch.storyteller_agent = DummyStoryteller()
    orch.register_agent(ScriptedAgent("p1", "One", {
        "nomination_intent": [{"action": "nominate", "target": "p3"}, {"action": "none"}],
        "vote": [{"action": "vote", "decision": True}, {"action": "vote", "decision": True}],
        "defense_speech": [{"action": "defense_speech", "content": "No comment."}],
    }))
    orch.register_agent(ScriptedAgent("p2", "Two", {
        "nomination_intent": [{"action": "none"}, {"action": "nominate", "target": "p4"}],
        "vote": [{"action": "vote", "decision": False}, {"action": "vote", "decision": True}],
        "defense_speech": [{"action": "defense_speech", "content": "Second round."}],
    }))
    orch.register_agent(ScriptedAgent("p3", "Three", {
        "nomination_intent": [{"action": "none"}, {"action": "none"}],
        "vote": [{"action": "vote", "decision": True}, {"action": "vote", "decision": False}],
        "defense_speech": [{"action": "defense_speech", "content": "I am innocent."}],
    }))
    orch.register_agent(ScriptedAgent("p4", "Four", {
        "nomination_intent": [{"action": "none"}, {"action": "none"}],
        "vote": [{"action": "vote", "decision": False}, {"action": "vote", "decision": True}],
        "defense_speech": [{"action": "defense_speech", "content": "Please spare me."}],
    }))

    await orch._run_nomination_phase()

    nomination_events = [e for e in orch.event_log.events if e.event_type == "nomination_started"]
    execution_events = [e for e in orch.event_log.events if e.event_type == "execution_resolved"]
    assert len(nomination_events) == 2
    assert execution_events[-1].payload["executed"] == "p4"
    assert orch.state.payload["nomination_state"]["current_nominator"] is None
    assert orch.state.payload["nomination_state"]["current_nominee"] is None
    assert len(orch.state.payload["nomination_history"]) >= 4


async def run_no_nomination_scenario() -> None:
    state = GameState(
        phase=GamePhase.NOMINATION,
        round_number=1,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="One", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Two", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="p3", name="Three", role_id="imp", team=Team.EVIL),
        ),
        seat_order=("p1", "p2", "p3"),
        config=GameConfig(
            player_count=3,
            human_mode="none",
            human_player_ids=[],
            is_human_participant=False,
            discussion_rounds=1,
            max_nomination_rounds=1,
        ),
    )
    orch = GameOrchestrator(state)
    orch.storyteller_agent = DummyStoryteller()
    orch.register_agent(ScriptedAgent("p1", "One", {"nomination_intent": [{"action": "none"}]}))
    orch.register_agent(ScriptedAgent("p2", "Two", {"nomination_intent": [{"action": "none"}]}))
    orch.register_agent(ScriptedAgent("p3", "Three", {"nomination_intent": [{"action": "none"}]}))

    await orch._run_nomination_phase()

    nomination_state = orch.state.payload["nomination_state"]
    assert nomination_state["last_result"]["reason"] == "no_nomination"
    assert nomination_state["current_nominator"] is None
    assert nomination_state["current_nominee"] is None


def run_game_over_contract_scenario() -> None:
    os.environ["BOTC_BACKEND"] = "mock"
    import src.api.server as server_module

    server_module = importlib.reload(server_module)
    orch = server_module.build_fresh_orchestrator("mock")
    orch.state = GameState(
        phase=GamePhase.GAME_OVER,
        players=(
            PlayerState(player_id="p1", name="One", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Two", role_id="imp", team=Team.EVIL, is_alive=False),
        ),
        payload={
            "nomination_state": {
                "stage": "idle",
                "result_phase": "game_over",
                "current_nominator": None,
                "current_nominee": None,
                "votes_cast": 0,
                "yes_votes": 0,
                "votes": {},
                "last_result": None,
            },
            "nomination_history": [
                {"kind": "nomination_started", "round": 1, "nominator": "p1", "nominee": "p2"},
                {"kind": "execution_resolved", "round": 1, "executed": "p2", "votes": 2},
            ],
        },
    )

    nomination_state = build_nomination_state(SimpleNamespace(state=orch.state))
    assert nomination_state["result_phase"] == "game_over"
    assert nomination_state["current_nominator"] is None
    assert nomination_state["current_nominee"] is None
    assert nomination_state["history"][-1]["kind"] == "execution_resolved"


def main() -> int:
    asyncio.run(run_multi_round_execution_scenario())
    asyncio.run(run_no_nomination_scenario())
    run_game_over_contract_scenario()
    print("nomination acceptance: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
