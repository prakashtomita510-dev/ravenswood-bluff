"""说书人裁定与日志回归测试。"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

import pytest

from src.agents.base_agent import BaseAgent
from src.agents import storyteller_agent as storyteller_module
from src.llm.mock_backend import MockBackend
from src.engine.roles.base_role import get_role_class
from src.engine.roles.minions import SpyRole
from src.engine.roles.townsfolk import (
    ChefRole,
    EmpathRole,
    FortuneTellerRole,
    InvestigatorRole,
    LibrarianRole,
    UndertakerRole,
    WasherwomanRole,
)
from src.orchestrator.game_loop import GameOrchestrator
from src.state.game_state import GameConfig, GameEvent, GamePhase, GameState, PlayerState, PlayerStatus, RoleType, Team, Visibility


class ScriptedAgent(BaseAgent):
    def __init__(self, player_id: str, name: str, actions: dict[str, list[dict]]):
        super().__init__(player_id, name)
        self.actions = actions
        self.counters: dict[str, int] = {}

    async def act(self, visible_state, action_type, legal_context=None, **kwargs):
        index = self.counters.get(action_type, 0)
        choices = self.actions.get(action_type, [])
        if index < len(choices):
            self.counters[action_type] = index + 1
            return choices[index]
        if action_type == "vote":
            return {"action": "vote", "decision": False}
        if action_type == "defense_speech":
            return {"action": "defense_speech", "content": "我无可辩解。"}
        if action_type in {"nomination_intent", "nominate"}:
            return {"action": "none"}
        return {"action": action_type}

    async def observe_event(self, event, visible_state):
        return None

    async def think(self, prompt, visible_state):
        return ""


def _flush_storyteller_logger() -> None:
    for handler in logging.getLogger("storyteller").handlers:
        if hasattr(handler, "flush"):
            handler.flush()


def _close_workspace_handlers(workspace: Path) -> None:
    logger = logging.getLogger("storyteller")
    for handler in list(logger.handlers):
        base_filename = getattr(handler, "baseFilename", "")
        if base_filename and Path(base_filename).parent == workspace:
            handler.close()
            logger.removeHandler(handler)


def _state_for_washerwoman() -> GameState:
    return GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            PlayerState(player_id="p1", name="One", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Two", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="p3", name="Three", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p4", name="Four", role_id="chef", team=Team.GOOD),
        ),
    )


def _state_for_empath() -> GameState:
    return GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            PlayerState(player_id="p1", name="Left", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p2", name="Self", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="p3", name="Right", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p4", name="Far", role_id="spy", team=Team.EVIL),
        ),
    )


def _state_for_chef() -> GameState:
    return GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            PlayerState(player_id="p1", name="Chef", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p2", name="Imp", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p3", name="Poisoner", role_id="poisoner", team=Team.EVIL),
            PlayerState(player_id="p4", name="Town", role_id="washerwoman", team=Team.GOOD),
        ),
    )


def _state_for_librarian() -> GameState:
    return GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            PlayerState(player_id="p1", name="Lib", role_id="librarian", team=Team.GOOD),
            PlayerState(player_id="p2", name="Out", role_id="butler", team=Team.GOOD),
            PlayerState(player_id="p3", name="Town", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p4", name="Evil", role_id="imp", team=Team.EVIL),
        ),
    )


def _state_for_investigator() -> GameState:
    return GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            PlayerState(player_id="p1", name="Inv", role_id="investigator", team=Team.GOOD),
            PlayerState(player_id="p2", name="Minion", role_id="spy", team=Team.EVIL),
            PlayerState(player_id="p3", name="Town", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p4", name="Imp", role_id="imp", team=Team.EVIL),
        ),
    )


def _state_for_spy() -> GameState:
    return GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            PlayerState(player_id="p1", name="Town", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Spy", role_id="spy", team=Team.EVIL),
            PlayerState(player_id="p3", name="Imp", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p4", name="Lib", role_id="librarian", team=Team.GOOD),
        ),
    )


def _state_for_fortune_teller(*, suppressed: bool = False) -> GameState:
    statuses = (PlayerStatus.ALIVE, PlayerStatus.DRUNK) if suppressed else (PlayerStatus.ALIVE,)
    return GameState(
        phase=GamePhase.NIGHT,
        round_number=2,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            PlayerState(player_id="p1", name="FT", role_id="fortune_teller", team=Team.GOOD, statuses=statuses),
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
        payload={"fortune_teller_red_herring": "p4"},
    )


def _state_for_undertaker() -> GameState:
    return GameState(
        phase=GamePhase.NIGHT,
        round_number=2,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            PlayerState(player_id="p1", name="Under", role_id="undertaker", team=Team.GOOD),
            PlayerState(player_id="p2", name="Victim", role_id="empath", team=Team.GOOD, is_alive=False),
            PlayerState(player_id="p3", name="Imp", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p4", name="Spy", role_id="spy", team=Team.EVIL),
        ),
        event_log=(
            GameEvent(
                event_type="execution_resolved",
                phase=GamePhase.EXECUTION,
                round_number=1,
                target="p2",
                payload={"executed": "p2"},
                visibility=Visibility.PUBLIC,
            ),
        ),
    )


@pytest.mark.asyncio
async def test_storyteller_agent_records_judgement_summary_and_log(monkeypatch):
    workspace = Path(__file__).parent.parent / "test_runs" / "_storyteller_judgement_workspace"
    workspace.mkdir(exist_ok=True)
    monkeypatch.chdir(workspace)
    module = importlib.reload(storyteller_module)
    agent = module.StorytellerAgent(MockBackend())

    state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="poisoner", team=Team.EVIL),
            PlayerState(player_id="p3", name="Charlie", role_id="imp", team=Team.EVIL),
        ),
        seat_order=("p1", "p2", "p3"),
    )

    narration = await agent.narrate_phase(state)
    night_order = await agent.build_night_order(state, GamePhase.FIRST_NIGHT)
    night_info = await agent.decide_night_info(state, "p1", "empath")
    human_step = await agent.get_human_storyteller_step(state, GamePhase.FIRST_NIGHT)

    _flush_storyteller_logger()

    log_path = Path("storyteller_run.log")
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "[judgement][narration]" in content
    assert "[judgement][night_order]" in content
    assert "[judgement][night_info]" in content
    assert "[judgement][human_step]" in content
    assert narration
    assert night_order
    assert night_info
    assert human_step["recent_judgements"]
    assert human_step["phase"] == GamePhase.FIRST_NIGHT.value

    recent = agent.get_recent_judgements(10)
    categories = {entry["category"] for entry in recent}
    assert {"narration", "night_order", "night_info", "human_step"} <= categories

    summary = agent.summarize_recent_judgements(4)
    assert summary
    assert any(item["category"] == "human_step" for item in summary)
    assert any("phase=" in item["summary"] for item in summary)
    _close_workspace_handlers(workspace)


@pytest.mark.asyncio
async def test_nomination_and_voting_emit_storyteller_judgements(monkeypatch):
    workspace = Path.cwd() / "_storyteller_judgement_workspace"
    workspace.mkdir(exist_ok=True)
    monkeypatch.chdir(workspace)
    module = importlib.reload(storyteller_module)
    storyteller = module.StorytellerAgent(MockBackend())

    state = GameState(
        phase=GamePhase.NOMINATION,
        round_number=1,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="p3", name="Charlie", role_id="imp", team=Team.EVIL),
        ),
        seat_order=("p1", "p2", "p3"),
        config=GameConfig(
            player_count=3,
            script_id="trouble_brewing",
            human_client_id=None,
            human_mode="none",
            storyteller_client_id=None,
            human_player_ids=[],
            is_human_participant=False,
            storyteller_mode="auto",
            backend_mode="mock",
            audit_mode=True,
            discussion_rounds=1,
            max_nomination_rounds=1,
        ),
    )
    orch = GameOrchestrator(state)
    orch.storyteller_agent = storyteller

    orch.register_agent(
        ScriptedAgent(
            "p1",
            "Alice",
            {
                "nomination_intent": [{"action": "none"}],
                "vote": [{"action": "vote", "decision": True}],
            },
        )
    )
    orch.register_agent(
        ScriptedAgent(
            "p2",
            "Bob",
            {
                "nomination_intent": [{"action": "nominate", "target": "p3"}],
                "vote": [{"action": "vote", "decision": True}],
            },
        )
    )
    orch.register_agent(
        ScriptedAgent(
            "p3",
            "Charlie",
            {
                "nomination_intent": [{"action": "none"}],
                "vote": [{"action": "vote", "decision": False}],
                "defense_speech": [{"action": "defense_speech", "content": "我只是普通村民。"}],
            },
        )
    )

    await orch._run_nomination_phase()
    _flush_storyteller_logger()

    log_path = Path("storyteller_run.log")
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "[judgement][nomination_window]" in content
    assert "[judgement][nomination_choice]" in content
    assert "[judgement][nomination_started]" in content
    assert "[judgement][defense]" in content
    assert "[judgement][voting]" in content
    assert "[judgement][execution]" in content

    recent = storyteller.get_recent_judgements(20)
    categories = [entry["category"] for entry in recent]
    assert "nomination_window" in categories
    assert "nomination_started" in categories
    assert "defense" in categories
    assert "voting" in categories
    assert "execution" in categories

    summary = storyteller.summarize_recent_judgements(10)
    assert any(item["category"] == "voting" for item in summary)
    assert any("yes_votes=" in item["summary"] or "votes_cast=" in item["summary"] for item in summary)
    assert orch.state.payload.get("nomination_state", {}).get("stage") == "executed"
    _close_workspace_handlers(workspace)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role_cls,role_id,state_factory,actor_id,expected_type",
    [
        (WasherwomanRole, "washerwoman", _state_for_washerwoman, "p1", "washerwoman_info"),
        (EmpathRole, "empath", _state_for_empath, "p2", "empath_info"),
        (ChefRole, "chef", _state_for_chef, "p1", "chef_info"),
        (LibrarianRole, "librarian", _state_for_librarian, "p1", "librarian_info"),
        (InvestigatorRole, "investigator", _state_for_investigator, "p1", "investigator_info"),
        (UndertakerRole, "undertaker", _state_for_undertaker, "p1", "undertaker_info"),
        (SpyRole, "spy", _state_for_spy, "p2", "spy_book"),
    ],
)
async def test_fixed_info_roles_flow_through_storyteller_build_contract(
    monkeypatch,
    role_cls,
    role_id,
    state_factory,
    actor_id,
    expected_type,
):
    workspace = Path.cwd() / "_storyteller_judgement_workspace"
    workspace.mkdir(exist_ok=True)
    monkeypatch.chdir(workspace)
    module = importlib.reload(storyteller_module)
    agent = module.StorytellerAgent(MockBackend())

    def _fail_get_night_info(self, *args, **kwargs):
        raise AssertionError("get_night_info should not be used for storyteller adjudication")

    monkeypatch.setattr(role_cls, "get_night_info", _fail_get_night_info, raising=False)
    state = state_factory()

    info = await agent.decide_night_info(state, actor_id, role_id)
    _flush_storyteller_logger()

    assert info["type"] == expected_type
    recent = agent.get_recent_judgements(5)
    assert recent
    assert recent[-1]["category"] == "night_info"
    assert recent[-1]["decision"] == "deliver"
    assert recent[-1]["source"] == "build_storyteller_info"
    assert recent[-1]["bucket"] == "night_info.fixed_info"
    assert recent[-1]["contract_mode"] == "fixed_info"
    assert recent[-1]["adjudication_path"] == "fixed_info.adjudicated"
    assert recent[-1]["distortion_strategy"] == "none"
    content = Path("storyteller_run.log").read_text(encoding="utf-8")
    assert "[judgement][night_info]" in content
    _close_workspace_handlers(workspace)


@pytest.mark.asyncio
async def test_storyteller_marks_suppressed_fixed_info_as_distorted_bucket(monkeypatch):
    workspace = Path.cwd() / "_storyteller_judgement_workspace"
    workspace.mkdir(exist_ok=True)
    monkeypatch.chdir(workspace)
    module = importlib.reload(storyteller_module)
    agent = module.StorytellerAgent(MockBackend())

    state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        players=(
            PlayerState(
                player_id="p1",
                name="Empath",
                role_id="empath",
                team=Team.GOOD,
                statuses=(PlayerStatus.ALIVE, PlayerStatus.DRUNK),
            ),
            PlayerState(player_id="p2", name="Imp", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p3", name="Town", role_id="washerwoman", team=Team.GOOD),
        ),
        seat_order=("p1", "p2", "p3"),
    )

    info = await agent.decide_night_info(state, "p1", "empath")

    recent = agent.get_recent_judgements(5)
    assert info
    assert recent[-1]["category"] == "night_info"
    assert recent[-1]["decision"] == "suppressed"
    assert recent[-1]["bucket"] == "night_info.fixed_info.suppressed"
    assert recent[-1]["scope"] == "fixed_info.suppressed"
    assert recent[-1]["contract_mode"] == "fixed_info"
    assert recent[-1]["adjudication_path"] == "fixed_info.adjudicated"
    assert recent[-1]["distortion_strategy"] == "empath_binary_flip"
    _close_workspace_handlers(workspace)


@pytest.mark.asyncio
async def test_storyteller_marks_suppressed_investigator_as_consistent_false_info(monkeypatch):
    workspace = Path.cwd() / "_storyteller_judgement_workspace"
    workspace.mkdir(exist_ok=True)
    monkeypatch.chdir(workspace)
    module = importlib.reload(storyteller_module)
    agent = module.StorytellerAgent(MockBackend())

    state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            PlayerState(
                player_id="p1",
                name="Inv",
                role_id="investigator",
                team=Team.GOOD,
                statuses=(PlayerStatus.ALIVE, PlayerStatus.DRUNK),
            ),
            PlayerState(player_id="p2", name="Minion", role_id="spy", team=Team.EVIL),
            PlayerState(player_id="p3", name="Town", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p4", name="Imp", role_id="imp", team=Team.EVIL),
        ),
    )

    info = await agent.decide_night_info(state, "p1", "investigator")

    recent = agent.get_recent_judgements(5)
    assert info["type"] == "investigator_info"
    assert recent[-1]["category"] == "night_info"
    assert recent[-1]["decision"] == "suppressed"
    assert recent[-1]["bucket"] == "night_info.fixed_info.suppressed"
    assert recent[-1]["adjudication_path"] == "fixed_info.adjudicated"
    assert recent[-1]["distortion_strategy"] == "investigator_pair_role_seen_distortion"
    asserted_roles = {
        (state.get_player(pid).true_role_id or state.get_player(pid).role_id)
        for pid in info["players"]
        if state.get_player(pid)
    }
    assert len(info["players"]) == 2
    assert "p1" not in info["players"]
    assert info["role_seen"] in asserted_roles
    seen_role_cls = get_role_class(info["role_seen"])
    assert seen_role_cls is not None
    assert seen_role_cls.get_definition().role_type == RoleType.MINION
    _close_workspace_handlers(workspace)


@pytest.mark.asyncio
async def test_storyteller_distorts_investigator_role_seen_when_suppressed(monkeypatch):
    workspace = Path.cwd() / "_storyteller_judgement_workspace"
    workspace.mkdir(exist_ok=True)
    monkeypatch.chdir(workspace)
    module = importlib.reload(storyteller_module)
    agent = module.StorytellerAgent(MockBackend())

    state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        players=(
            PlayerState(
                player_id="p1",
                name="Investigator",
                role_id="investigator",
                team=Team.GOOD,
                statuses=(PlayerStatus.ALIVE, PlayerStatus.POISONED),
            ),
            PlayerState(player_id="p2", name="Minion", role_id="spy", team=Team.EVIL),
            PlayerState(player_id="p3", name="Town", role_id="washerwoman", team=Team.GOOD),
        ),
        seat_order=("p1", "p2", "p3"),
    )

    info = await agent.decide_night_info(state, "p1", "investigator")

    assert info["type"] == "investigator_info"
    assert len(info["players"]) == 2
    assert "p1" not in info["players"]
    role_map = {
        pid: (state.get_player(pid).true_role_id or state.get_player(pid).role_id)
        for pid in info["players"]
        if state.get_player(pid)
    }
    assert info["role_seen"] in role_map.values()
    seen_role_cls = get_role_class(info["role_seen"])
    assert seen_role_cls is not None
    assert seen_role_cls.get_definition().role_type == RoleType.MINION
    recent = agent.get_recent_judgements(5)
    assert recent[-1]["bucket"] == "night_info.fixed_info.suppressed"
    assert recent[-1]["distortion_strategy"] == "investigator_pair_role_seen_distortion"
    _close_workspace_handlers(workspace)


@pytest.mark.asyncio
async def test_storyteller_distorts_spy_book_when_suppressed(monkeypatch):
    workspace = Path.cwd() / "_storyteller_judgement_workspace"
    workspace.mkdir(exist_ok=True)
    monkeypatch.chdir(workspace)
    module = importlib.reload(storyteller_module)
    agent = module.StorytellerAgent(MockBackend())

    state = GameState(
        phase=GamePhase.NIGHT,
        round_number=2,
        players=(
            PlayerState(player_id="p1", name="Town", role_id="washerwoman", team=Team.GOOD),
            PlayerState(
                player_id="p2",
                name="Spy",
                role_id="spy",
                team=Team.EVIL,
                statuses=(PlayerStatus.ALIVE, PlayerStatus.DRUNK),
            ),
            PlayerState(player_id="p3", name="Imp", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p4", name="Lib", role_id="librarian", team=Team.GOOD),
        ),
        seat_order=("p1", "p2", "p3", "p4"),
    )

    info = await agent.decide_night_info(state, "p2", "spy")
    expected_book = SpyRole().build_storyteller_info(state, state.get_player("p2"))

    assert info["type"] == "spy_book"
    assert len(info["book"]) == len(expected_book["book"])
    assert any(
        original["role_id"] != changed["role_id"] or original["team"] != changed["team"]
        for original, changed in zip(expected_book["book"], info["book"])
    )
    recent = agent.get_recent_judgements(5)
    assert recent[-1]["bucket"] == "night_info.fixed_info.suppressed"
    assert recent[-1]["distortion_strategy"] == "spy_book_single_entry_distortion"
    _close_workspace_handlers(workspace)


@pytest.mark.asyncio
async def test_storyteller_marks_fortune_teller_as_storyteller_info_contract(monkeypatch):
    workspace = Path.cwd() / "_storyteller_judgement_workspace"
    workspace.mkdir(exist_ok=True)
    monkeypatch.chdir(workspace)
    module = importlib.reload(storyteller_module)
    agent = module.StorytellerAgent(MockBackend())

    state = _state_for_fortune_teller(suppressed=False)

    info = await agent.decide_night_info(state, "p1", "fortune_teller")

    assert info["type"] == "fortune_teller_info"
    assert info["has_demon"] is True
    recent = agent.get_recent_judgements(5)
    assert recent[-1]["bucket"] == "night_info.storyteller_info"
    assert recent[-1]["contract_mode"] == "storyteller_info"
    assert recent[-1]["adjudication_path"] == "storyteller_info.adjudicated"
    assert recent[-1]["distortion_strategy"] == "none"
    _close_workspace_handlers(workspace)


@pytest.mark.asyncio
async def test_storyteller_distorts_fortune_teller_when_suppressed(monkeypatch):
    workspace = Path.cwd() / "_storyteller_judgement_workspace"
    workspace.mkdir(exist_ok=True)
    monkeypatch.chdir(workspace)
    module = importlib.reload(storyteller_module)
    agent = module.StorytellerAgent(MockBackend())

    state = _state_for_fortune_teller(suppressed=True)

    info = await agent.decide_night_info(state, "p1", "fortune_teller")

    assert info["type"] == "fortune_teller_info"
    assert info["has_demon"] is False
    recent = agent.get_recent_judgements(5)
    assert recent[-1]["decision"] == "suppressed"
    assert recent[-1]["bucket"] == "night_info.storyteller_info.suppressed"
    assert recent[-1]["contract_mode"] == "storyteller_info"
    assert recent[-1]["adjudication_path"] == "storyteller_info.adjudicated"
    assert recent[-1]["distortion_strategy"] == "fortune_teller_boolean_flip"
    _close_workspace_handlers(workspace)


@pytest.mark.asyncio
async def test_storyteller_records_legacy_fallback_path_when_storyteller_info_uses_old_contract(monkeypatch):
    workspace = Path.cwd() / "_storyteller_judgement_workspace"
    workspace.mkdir(exist_ok=True)
    monkeypatch.chdir(workspace)
    module = importlib.reload(storyteller_module)
    agent = module.StorytellerAgent(MockBackend())

    state = _state_for_fortune_teller(suppressed=False)

    monkeypatch.setattr(FortuneTellerRole, "build_storyteller_info", lambda self, *_args, **_kwargs: None, raising=False)
    monkeypatch.setattr(
        FortuneTellerRole,
        "get_night_info",
        lambda self, *_args, **_kwargs: {"type": "fortune_teller_info", "has_demon": True},
        raising=False,
    )

    info = await agent.decide_night_info(state, "p1", "fortune_teller")

    assert info["type"] == "fortune_teller_info"
    recent = agent.get_recent_judgements(5)
    assert recent[-1]["source"] == "legacy_get_night_info"
    assert recent[-1]["contract_mode"] == "storyteller_info.legacy_fallback"
    assert recent[-1]["adjudication_path"] == "storyteller_info.legacy_fallback"
    assert recent[-1]["bucket"] == "night_info.storyteller_info"
    _close_workspace_handlers(workspace)
