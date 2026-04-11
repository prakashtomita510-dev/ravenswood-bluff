"""Backend acceptance checks for night info and death-trigger flows."""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path

from src.agents.base_agent import BaseAgent
from src.agents.storyteller_agent import StorytellerAgent
from src.engine.roles.minions import SpyRole
from src.llm.mock_backend import MockBackend
from src.orchestrator.game_loop import GameOrchestrator
from src.state.game_state import GamePhase, GameState, PlayerState, PlayerStatus, Team


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


async def assert_evil_reveal_and_spy_refresh() -> None:
    initial_state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        players=(
            PlayerState(player_id="i1", name="Imp", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="s1", name="Spy", role_id="spy", team=Team.EVIL),
            PlayerState(player_id="g1", name="Empath", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="g2", name="Town", role_id="washerwoman", team=Team.GOOD),
        ),
        seat_order=("i1", "s1", "g1", "g2"),
        bluffs=("chef", "undertaker", "soldier"),
    )
    orch = GameOrchestrator(initial_state)
    orch.storyteller_agent = DummyStoryteller()

    await orch._run_first_night()
    await orch._distribute_night_info(GamePhase.NIGHT)

    evil_private = [
        event for event in orch.event_log.events
        if event.event_type == "private_info_delivered" and event.target in {"i1", "s1"}
    ]
    assert evil_private
    imp_payload = next(event.payload for event in evil_private if event.target == "i1" and event.payload.get("type") == "evil_reveal")
    spy_payload = next(event.payload for event in evil_private if event.target == "s1" and event.payload.get("type") == "evil_reveal")
    assert imp_payload["bluffs"] == ["chef", "undertaker", "soldier"]
    assert spy_payload["bluffs"] == ["chef", "undertaker", "soldier"]

    spy_books = [
        event.payload for event in orch.event_log.events
        if event.event_type == "private_info_delivered" and event.target == "s1" and event.payload.get("type") == "spy_book"
    ]
    assert len(spy_books) >= 2
    assert all(payload["book"] for payload in spy_books)


async def assert_ravenkeeper_death_trigger_flow() -> None:
    initial_state = GameState(
        phase=GamePhase.NIGHT,
        round_number=2,
        players=(
            PlayerState(player_id="r", name="Raven", role_id="ravenkeeper", team=Team.GOOD, is_alive=False),
            PlayerState(player_id="i", name="Imp", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="g", name="Good", role_id="chef", team=Team.GOOD),
        ),
        seat_order=("r", "i", "g"),
    )
    orch = GameOrchestrator(initial_state)
    orch.storyteller_agent = DummyStoryteller()
    orch.register_agent(ScriptedAgent("r", "Raven", {
        "death_trigger": [{"action": "death_trigger", "target": "i"}],
    }))

    await orch._resolve_on_death_triggers({"r", "i", "g"})

    private_infos = [
        event for event in orch.event_log.events
        if event.event_type == "private_info_delivered" and event.target == "r"
    ]
    assert private_infos
    assert private_infos[0].payload["type"] == "ravenkeeper_info"
    assert private_infos[0].payload["role_seen"] == "imp"


async def assert_storyteller_suppressed_information_is_traceable() -> None:
    workspace = Path.cwd() / "_storyteller_judgement_workspace"
    workspace.mkdir(exist_ok=True)
    import src.agents.storyteller_agent as storyteller_module

    module = importlib.reload(storyteller_module)
    agent = module.StorytellerAgent(MockBackend())

    state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        seat_order=("p1", "p2", "p3"),
        players=(
            PlayerState(
                player_id="p1",
                name="Investigator",
                role_id="investigator",
                team=Team.GOOD,
                statuses=(PlayerStatus.ALIVE, PlayerStatus.POISONED),
            ),
            PlayerState(player_id="p2", name="Spy", role_id="spy", team=Team.EVIL),
            PlayerState(player_id="p3", name="Town", role_id="washerwoman", team=Team.GOOD),
        ),
    )

    info = await agent.decide_night_info(state, "p1", "investigator")
    recent = agent.get_recent_judgements(5)

    assert info["type"] == "investigator_info"
    assert recent[-1]["decision"] == "suppressed"
    assert recent[-1]["bucket"] == "night_info.fixed_info.suppressed"


def main() -> int:
    asyncio.run(assert_evil_reveal_and_spy_refresh())
    asyncio.run(assert_ravenkeeper_death_trigger_flow())
    asyncio.run(assert_storyteller_suppressed_information_is_traceable())
    print("night info acceptance: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
