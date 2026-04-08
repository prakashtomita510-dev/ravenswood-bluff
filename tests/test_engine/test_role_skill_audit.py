"""Trouble Brewing 角色技能审计与首批回归测试。"""

from __future__ import annotations

import pytest

import src.engine.roles.demons  # noqa: F401
import src.engine.roles.minions  # noqa: F401
import src.engine.roles.outsiders  # noqa: F401
import src.engine.roles.townsfolk  # noqa: F401
from src.engine.roles.base_role import get_role_class
from src.state.game_state import GameEvent, GamePhase, GameState, PlayerState, PlayerStatus, Team, Visibility


def make_player(player_id: str, name: str, role_id: str, team: Team, **kwargs) -> PlayerState:
    return PlayerState(player_id=player_id, name=name, role_id=role_id, team=team, **kwargs)


@pytest.mark.parametrize(
    "role_id",
    [
        "washerwoman",
        "librarian",
        "investigator",
        "chef",
        "empath",
        "undertaker",
        "spy",
    ],
)
def test_fixed_info_roles_are_classified(role_id: str) -> None:
    role_cls = get_role_class(role_id)
    assert role_cls is not None
    assert role_cls.is_fixed_info_role() is True
    assert role_cls.needs_night_target() is False


@pytest.mark.parametrize(
    "role_id",
    [
        "fortune_teller",
        "monk",
        "poisoner",
        "imp",
    ],
)
def test_targeted_roles_are_classified(role_id: str) -> None:
    role_cls = get_role_class(role_id)
    assert role_cls is not None
    assert role_cls.needs_night_target() is True


def test_washerwoman_reveals_townsfolk_pair() -> None:
    role = get_role_class("washerwoman")()
    state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        players=(
            make_player("w", "Wash", "washerwoman", Team.GOOD),
            make_player("c", "Chef", "chef", Team.GOOD),
            make_player("b", "Butler", "butler", Team.GOOD),
            make_player("d", "Demon", "imp", Team.EVIL),
        ),
    )

    info = role.get_night_info(state, state.get_player("w"))

    assert info is not None
    assert info["type"] == "washerwoman_info"
    assert info["role_seen"] == "chef"
    assert len(info["players"]) == 2
    assert "c" in info["players"]


def test_librarian_reports_specific_outsider_or_none() -> None:
    role = get_role_class("librarian")()
    with_outsider = GameState(
        phase=GamePhase.FIRST_NIGHT,
        players=(
            make_player("l", "Lib", "librarian", Team.GOOD),
            make_player("o", "Outsider", "butler", Team.GOOD),
            make_player("g", "Good", "chef", Team.GOOD),
        ),
    )
    without_outsider = GameState(
        phase=GamePhase.FIRST_NIGHT,
        players=(
            make_player("l", "Lib", "librarian", Team.GOOD),
            make_player("g1", "Good1", "chef", Team.GOOD),
            make_player("g2", "Good2", "empath", Team.GOOD),
        ),
    )

    info = role.get_night_info(with_outsider, with_outsider.get_player("l"))
    assert info is not None
    assert info["type"] == "librarian_info"
    assert info["has_outsider"] is True
    assert info["role_seen"] == "butler"
    assert "o" in info["players"]

    no_info = role.get_night_info(without_outsider, without_outsider.get_player("l"))
    assert no_info == {"type": "librarian_info", "has_outsider": False}


def test_investigator_reveals_minion_pair() -> None:
    role = get_role_class("investigator")()
    state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        players=(
            make_player("i", "Inv", "investigator", Team.GOOD),
            make_player("m", "Minion", "poisoner", Team.EVIL),
            make_player("g", "Good", "chef", Team.GOOD),
        ),
    )

    info = role.get_night_info(state, state.get_player("i"))

    assert info is not None
    assert info["type"] == "investigator_info"
    assert info["role_seen"] == "poisoner"
    assert "m" in info["players"]


def test_chef_counts_adjacent_evil_pairs() -> None:
    role = get_role_class("chef")()
    state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            make_player("p1", "Imp", "imp", Team.EVIL),
            make_player("p2", "Poisoner", "poisoner", Team.EVIL),
            make_player("p3", "Chef", "chef", Team.GOOD),
            make_player("p4", "Empath", "empath", Team.GOOD),
        ),
    )

    info = role.get_night_info(state, state.get_player("p3"))

    assert info == {"type": "chef_info", "pairs": 1}


def test_empath_counts_alive_evil_neighbors() -> None:
    role = get_role_class("empath")()
    state = GameState(
        phase=GamePhase.NIGHT,
        seat_order=("p1", "p2", "p3", "p4", "p5"),
        players=(
            make_player("p1", "Good1", "chef", Team.GOOD),
            make_player("p2", "EvilL", "imp", Team.EVIL),
            make_player("p3", "Empath", "empath", Team.GOOD),
            make_player("p4", "EvilR", "poisoner", Team.EVIL),
            make_player("p5", "Good2", "librarian", Team.GOOD),
        ),
    )

    info = role.get_night_info(state, state.get_player("p3"))

    assert info == {"type": "empath_info", "evil_count": 2}


def test_undertaker_reads_executed_role() -> None:
    role = get_role_class("undertaker")()
    state = GameState(
        phase=GamePhase.NIGHT,
        players=(
            make_player("u", "Under", "undertaker", Team.GOOD),
            make_player("x", "Executed", "imp", Team.EVIL),
        ),
        event_log=(
            GameEvent(
                event_type="execution_resolved",
                phase=GamePhase.EXECUTION,
                round_number=1,
                payload={"executed": "x"},
                visibility=Visibility.PUBLIC,
            ),
        ),
    )

    info = role.get_night_info(state, state.get_player("u"))

    assert info == {"type": "undertaker_info", "role_seen": "imp"}


@pytest.mark.parametrize(
    "targets, red_herring, expected",
    [
        (["g1", "d1"], None, True),
        (["g1", "g2"], "g2", True),
    ],
)
def test_fortune_teller_detects_demon_or_red_herring(targets, red_herring, expected) -> None:
    role = get_role_class("fortune_teller")()
    state = GameState(
        phase=GamePhase.NIGHT,
        players=(
            make_player("f", "Fortune", "fortune_teller", Team.GOOD),
            make_player("g1", "Good1", "chef", Team.GOOD),
            make_player("g2", "Good2", "empath", Team.GOOD),
            make_player("d1", "Demon", "imp", Team.EVIL),
        ),
        payload={"fortune_teller_red_herring": red_herring},
        event_log=(
            GameEvent(
                event_type="night_action_resolved",
                phase=GamePhase.NIGHT,
                round_number=1,
                actor="f",
                payload={"targets": targets},
                visibility=Visibility.STORYTELLER_ONLY,
            ),
        ),
    )

    info = role.get_night_info(state, state.get_player("f"))

    assert info == {"type": "fortune_teller_info", "has_demon": expected}


def test_spy_returns_full_book() -> None:
    role = get_role_class("spy")()
    state = GameState(
        phase=GamePhase.NIGHT,
        players=(
            make_player("s", "Spy", "spy", Team.EVIL),
            make_player("g", "Good", "chef", Team.GOOD),
            make_player("d", "Dead", "imp", Team.EVIL, is_alive=False),
        ),
    )

    info = role.get_night_info(state, state.get_player("s"))

    assert info is not None
    assert info["type"] == "spy_book"
    assert len(info["book"]) == 3
    assert info["book"][0]["role_id"] == "spy"
    assert info["book"][2]["is_alive"] is False


def test_monk_rejects_self_target_and_protects_other() -> None:
    role = get_role_class("monk")()
    state = GameState(
        phase=GamePhase.NIGHT,
        players=(
            make_player("m", "Monk", "monk", Team.GOOD),
            make_player("t", "Target", "chef", Team.GOOD),
        ),
    )

    same_state, same_events = role.execute_ability(state, state.get_player("m"), "m")
    assert same_state == state
    assert same_events == []

    new_state, events = role.execute_ability(state, state.get_player("m"), "t")
    assert new_state.get_player("t").is_poisoned is False
    assert PlayerStatus.PROTECTED in new_state.get_player("t").statuses
    assert len(events) == 1
    assert events[0].event_type == "protection"


@pytest.mark.parametrize(
    "target_kwargs",
    [
        {"statuses": (PlayerStatus.ALIVE, PlayerStatus.PROTECTED)},
        {"role_id": "soldier", "team": Team.GOOD},
    ],
)
def test_imp_respects_protection_and_soldier_immunity(target_kwargs) -> None:
    role = get_role_class("imp")()
    target_fields = {
        "player_id": "t",
        "name": "Target",
        "role_id": "chef",
        "team": Team.GOOD,
        **target_kwargs,
    }
    state = GameState(
        phase=GamePhase.NIGHT,
        players=(
            make_player("i", "Imp", "imp", Team.EVIL),
            PlayerState(**target_fields),
        ),
    )

    new_state, events = role.execute_ability(state, state.get_player("i"), "t")

    assert new_state.get_player("t").is_alive is True
    assert events == []


def test_ravenkeeper_reveals_target_role_on_death_trigger() -> None:
    role = get_role_class("ravenkeeper")()
    state = GameState(
        phase=GamePhase.NIGHT,
        players=(
            make_player("r", "Raven", "ravenkeeper", Team.GOOD),
            make_player("t", "Target", "poisoner", Team.EVIL),
        ),
    )

    new_state, events = role.execute_ability(state, state.get_player("r"), "t")

    assert len(new_state.event_log) == len(state.event_log) + 1
    assert len(events) == 1
    assert events[0].event_type == "night_info"
    assert events[0].target == "r"
    assert events[0].visibility == Visibility.PRIVATE
    assert events[0].payload["role_seen"] == "poisoner"
