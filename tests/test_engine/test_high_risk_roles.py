"""高风险角色的最小真实行为回归。"""

from __future__ import annotations

import pytest
import random as py_random

import src.engine.scripts as scripts_module
import src.engine.roles.demons  # noqa: F401
import src.engine.roles.minions  # noqa: F401
import src.engine.roles.outsiders  # noqa: F401
import src.engine.roles.townsfolk  # noqa: F401
from src.engine.roles.base_role import get_role_class
from src.engine.rule_engine import RuleEngine
from src.state.game_state import GameEvent, GamePhase, GameState, PlayerState, Team, Visibility


def make_player(player_id: str, name: str, role_id: str, team: Team, **kwargs) -> PlayerState:
    return PlayerState(player_id=player_id, name=name, role_id=role_id, team=team, **kwargs)


def test_drunken_marks_false_info_behavior() -> None:
    role_cls = get_role_class("drunken")
    assert role_cls is not None

    definition = role_cls.get_definition()

    assert definition.drunk_behavior == "false_info"
    assert role_cls.should_receive_false_info() is True


def test_recluse_marks_evil_misread_behavior() -> None:
    role_cls = get_role_class("recluse")
    assert role_cls is not None

    definition = role_cls.get_definition()

    assert definition.drunk_behavior == "misread_as_evil"
    assert role_cls.can_be_misread_as_evil() is True
    assert role_cls.misread_as_role_types() == ("evil", "minion", "demon")


def test_baron_exposes_extra_outsider_contract() -> None:
    role_cls = get_role_class("baron")
    assert role_cls is not None

    definition = role_cls.get_definition()

    assert definition.setup_influence == "add_2_outsiders"
    assert role_cls.outsider_bonus() == 2


def test_baron_distribution_uses_helper_bonus(monkeypatch) -> None:
    def fake_sample(population, k):
        items = list(population)
        if "baron" in items:
            return ["baron"][:k]
        return items[:k]

    monkeypatch.setattr(py_random, "sample", fake_sample)
    monkeypatch.setattr(py_random, "shuffle", lambda seq: None)

    roles, bluffs = scripts_module.distribute_roles(scripts_module.TROUBLE_BREWING, 7)

    counts = {"townsfolk": 0, "outsider": 0, "minion": 0, "demon": 0}
    for rid in roles:
        role_cls = get_role_class(rid)
        assert role_cls is not None
        counts[role_cls.get_definition().role_type.value] += 1

    assert "baron" in roles
    assert counts["demon"] == 1
    assert counts["minion"] == 1
    assert counts["outsider"] == 2
    assert counts["townsfolk"] == 3
    assert len(bluffs) <= 3


def test_imp_self_kill_transfers_to_scarlet_woman_when_threshold_met() -> None:
    role = get_role_class("imp")()
    state = GameState(
        phase=GamePhase.NIGHT,
        players=(
            make_player("i", "Imp", "imp", Team.EVIL),
            make_player("s", "Scarlet", "scarlet_woman", Team.EVIL),
            make_player("m", "Minion", "poisoner", Team.EVIL),
            make_player("g1", "Good1", "chef", Team.GOOD),
            make_player("g2", "Good2", "empath", Team.GOOD),
        ),
    )

    new_state, events = role.execute_ability(state, state.get_player("i"), "i")

    transformed = new_state.get_player("s")
    assert new_state.get_player("i").is_alive is False
    assert transformed is not None
    assert transformed.role_id == "imp"
    assert transformed.true_role_id == "imp"
    assert transformed.perceived_role_id == "imp"
    assert transformed.current_team == Team.EVIL
    assert len(events) == 2
    assert events[0].event_type == "night_kill"
    assert events[1].event_type == "role_transfer"
    assert events[1].payload["reason"] == "scarlet_woman_trigger"


def test_imp_self_kill_falls_back_to_minion_when_scarlet_woman_threshold_not_met() -> None:
    role = get_role_class("imp")()
    state = GameState(
        phase=GamePhase.NIGHT,
        players=(
            make_player("i", "Imp", "imp", Team.EVIL),
            make_player("s", "Scarlet", "scarlet_woman", Team.EVIL),
            make_player("m", "Minion", "poisoner", Team.EVIL),
            make_player("g1", "Good1", "chef", Team.GOOD),
        ),
    )

    new_state, events = role.execute_ability(state, state.get_player("i"), "i")

    transformed = new_state.get_player("m")
    assert new_state.get_player("i").is_alive is False
    assert new_state.get_player("s").role_id == "scarlet_woman"
    assert transformed is not None
    assert transformed.role_id == "imp"
    assert transformed.true_role_id == "imp"
    assert transformed.current_team == Team.EVIL
    assert len(events) == 2
    assert events[1].event_type == "role_transfer"
    assert events[1].payload["reason"] == "imp_suicide"


def test_butler_binds_target_and_limits_vote_on_following_day() -> None:
    role = get_role_class("butler")()
    state = GameState(
        phase=GamePhase.NIGHT,
        day_number=0,
        players=(
            make_player("b", "Butler", "butler", Team.GOOD),
            make_player("t", "Target", "chef", Team.GOOD),
            make_player("o", "Other", "empath", Team.GOOD),
        ),
    )

    new_state, events = role.execute_ability(state, state.get_player("b"), "t")

    assert len(events) == 1
    assert events[0].event_type == "butler_binding"
    assert new_state.payload["butler_bindings"]["b"]["target_id"] == "t"
    assert new_state.payload["butler_bindings"]["b"]["applies_on_day"] == 1

    voting_state = new_state.with_update(phase=GamePhase.VOTING, current_nominee="o", day_number=1)
    can_vote, reason = RuleEngine.can_vote(voting_state, "b")
    assert can_vote is True
    assert reason == ""


def test_butler_rejects_vote_when_bound_player_cannot_vote() -> None:
    role = get_role_class("butler")()
    state = GameState(
        phase=GamePhase.NIGHT,
        day_number=0,
        players=(
            make_player("b", "Butler", "butler", Team.GOOD),
            make_player("t", "Target", "chef", Team.GOOD, is_alive=False, ghost_votes_remaining=0, has_used_dead_vote=True),
            make_player("o", "Other", "empath", Team.GOOD),
        ),
    )

    new_state, _ = role.execute_ability(state, state.get_player("b"), "t")
    voting_state = new_state.with_update(phase=GamePhase.VOTING, current_nominee="o", day_number=1)
    can_vote, reason = RuleEngine.can_vote(voting_state, "b")
    assert can_vote is False
    assert "管家只能在其选择的玩家能够投票时投票" in reason


def test_slayer_consumes_shot_and_hits_demon() -> None:
    role = get_role_class("slayer")()
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        players=(
            make_player("s", "Slayer", "slayer", Team.GOOD),
            make_player("d", "Demon", "imp", Team.EVIL),
            make_player("g", "Good", "chef", Team.GOOD),
        ),
    )

    new_state, events = role.execute_ability(state, state.get_player("s"), "d")

    assert "slayer_used" in new_state.get_player("s").storyteller_notes
    assert new_state.get_player("d").is_alive is False
    assert len(events) == 2
    assert events[0].event_type == "slayer_shot"
    assert events[0].payload["success"] is True
    assert events[1].event_type == "player_death"
    assert events[1].payload["reason"] == "slayer_shot"

    with pytest.raises(ValueError, match="已经使用过能力"):
        role.execute_ability(new_state, new_state.get_player("s"), "d")


def test_slayer_miss_consumes_shot_without_kill() -> None:
    role = get_role_class("slayer")()
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        players=(
            make_player("s", "Slayer", "slayer", Team.GOOD),
            make_player("g", "Good", "chef", Team.GOOD),
            make_player("d", "Demon", "imp", Team.EVIL),
        ),
    )

    new_state, events = role.execute_ability(state, state.get_player("s"), "g")

    assert "slayer_used" in new_state.get_player("s").storyteller_notes
    assert new_state.get_player("g").is_alive is True
    assert len(events) == 1
    assert events[0].event_type == "slayer_shot"
    assert events[0].payload["success"] is False


def test_mayor_night_kill_redirects_to_another_alive_player() -> None:
    role = get_role_class("imp")()
    state = GameState(
        phase=GamePhase.NIGHT,
        players=(
            make_player("i", "Imp", "imp", Team.EVIL),
            make_player("m", "Mayor", "mayor", Team.GOOD),
            make_player("g1", "Good1", "chef", Team.GOOD),
            make_player("g2", "Good2", "empath", Team.GOOD),
        ),
    )

    new_state, events = role.execute_ability(state, state.get_player("i"), "m")

    assert new_state.get_player("m").is_alive is True
    assert new_state.get_player("g1").is_alive is False
    assert len(events) == 1
    assert events[0].event_type == "night_kill"
    assert events[0].payload["redirected_from"] == "m"
    assert events[0].payload["resolved_target_role"] == "chef"


def test_mayor_redirection_prefers_non_mayor_non_killer_alive_player() -> None:
    role = get_role_class("imp")()
    state = GameState(
        phase=GamePhase.NIGHT,
        players=(
            make_player("i", "Imp", "imp", Team.EVIL),
            make_player("m", "Mayor", "mayor", Team.GOOD),
            make_player("g1", "Good1", "chef", Team.GOOD),
            make_player("g2", "Good2", "empath", Team.GOOD),
        ),
    )

    target = get_role_class("mayor").choose_redirection_target(state, mayor_player_id="m", killer_id="i")

    assert target == "g1"


def test_recluse_registers_as_demon_for_fortune_teller() -> None:
    role = get_role_class("fortune_teller")()
    state = GameState(
        phase=GamePhase.NIGHT,
        players=(
            make_player("f", "Fortune", "fortune_teller", Team.GOOD),
            make_player("r", "Recluse", "recluse", Team.GOOD),
            make_player("g", "Good", "chef", Team.GOOD),
        ),
        event_log=(
            GameEvent(
                event_type="night_action_resolved",
                phase=GamePhase.NIGHT,
                round_number=1,
                actor="f",
                payload={"targets": ["r", "g"]},
                visibility=Visibility.STORYTELLER_ONLY,
            ),
        ),
    )

    info = role.get_night_info(state, state.get_player("f"))

    assert info == {"type": "fortune_teller_info", "has_demon": True}


def test_ravenkeeper_reads_true_role_on_death_trigger() -> None:
    role = get_role_class("ravenkeeper")()
    state = GameState(
        phase=GamePhase.NIGHT,
        players=(
            make_player("r", "Raven", "ravenkeeper", Team.GOOD),
            make_player("t", "Target", "butler", Team.GOOD, true_role_id="poisoner", perceived_role_id="butler"),
        ),
    )

    new_state, events = role.execute_ability(state, state.get_player("r"), "t")

    assert len(events) == 1
    assert events[0].event_type == "night_info"
    assert events[0].payload["role_seen"] == "poisoner"
