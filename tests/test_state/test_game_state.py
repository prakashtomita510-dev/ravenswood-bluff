"""Phase 0 测试 — 核心数据模型"""

import pytest
from src.state.game_state import (
    Ability,
    AbilityTrigger,
    AbilityType,
    ChatMessage,
    GameConfig,
    GameEvent,
    GamePhase,
    GameState,
    PlayerState,
    PlayerStatus,
    RoleDefinition,
    RoleType,
    ScriptConfig,
    Team,
    Visibility,
    PrivatePlayerView,
)


# ============================================================
# PlayerState Tests
# ============================================================

class TestPlayerState:
    def test_create_player(self):
        player = PlayerState(
            player_id="p1",
            name="张三",
            role_id="washerwoman",
            team=Team.GOOD,
        )
        assert player.player_id == "p1"
        assert player.name == "张三"
        assert player.is_alive is True
        assert player.can_vote is True
        assert player.true_role_id == "washerwoman"
        assert player.perceived_role_id == "washerwoman"

    def test_player_immutability(self):
        player = PlayerState(
            player_id="p1", name="张三",
            role_id="washerwoman", team=Team.GOOD,
        )
        with pytest.raises(Exception):
            player.is_alive = False  # type: ignore

    def test_with_update(self):
        player = PlayerState(
            player_id="p1", name="张三",
            role_id="washerwoman", team=Team.GOOD,
        )
        dead_player = player.with_update(is_alive=False)
        assert player.is_alive is True    # 原对象不变
        assert dead_player.is_alive is False
        assert dead_player.name == "张三"   # 其他字段保留

    def test_is_poisoned(self):
        player = PlayerState(
            player_id="p1", name="张三",
            role_id="washerwoman", team=Team.GOOD,
            statuses=(PlayerStatus.ALIVE, PlayerStatus.POISONED),
        )
        assert player.is_poisoned is True

    def test_dead_vote(self):
        player = PlayerState(
            player_id="p1", name="张三",
            role_id="washerwoman", team=Team.GOOD,
            is_alive=False,
            has_used_dead_vote=False,
        )
        assert player.can_vote is True

        player_voted = player.with_update(has_used_dead_vote=True, ghost_votes_remaining=0)
        assert player_voted.can_vote is False


# ============================================================
# GameState Tests
# ============================================================

class TestGameState:
    def _make_players(self) -> tuple[PlayerState, ...]:
        return (
            PlayerState(player_id="p1", name="张三", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="李四", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p3", name="王五", role_id="empath", team=Team.GOOD),
        )

    def test_create_game_state(self):
        state = GameState(players=self._make_players())
        assert state.phase == GamePhase.SETUP
        assert state.player_count == 3
        assert state.alive_count == 3

    def test_immutability(self):
        state = GameState(players=self._make_players())
        with pytest.raises(Exception):
            state.phase = GamePhase.NIGHT  # type: ignore

    def test_get_player(self):
        state = GameState(players=self._make_players())
        player = state.get_player("p2")
        assert player is not None
        assert player.name == "李四"

    def test_get_player_by_name(self):
        state = GameState(players=self._make_players())
        player = state.get_player_by_name("王五")
        assert player is not None
        assert player.player_id == "p3"

    def test_get_player_not_found(self):
        state = GameState(players=self._make_players())
        assert state.get_player("nonexistent") is None

    def test_with_update(self):
        state = GameState(players=self._make_players())
        new_state = state.with_update(phase=GamePhase.FIRST_NIGHT, round_number=1)
        assert state.phase == GamePhase.SETUP       # 原对象不变
        assert new_state.phase == GamePhase.FIRST_NIGHT
        assert new_state.round_number == 1
        assert new_state.player_count == 3           # 玩家保留

    def test_with_player_update(self):
        state = GameState(players=self._make_players())
        new_state = state.with_player_update("p1", is_alive=False)
        assert state.get_player("p1").is_alive is True    # 原对象不变
        assert new_state.get_player("p1").is_alive is False

    def test_with_event(self):
        state = GameState(players=self._make_players())
        event = GameEvent(
            event_type="player_death",
            phase=GamePhase.NIGHT,
            round_number=1,
            actor="p2",
            target="p1",
        )
        new_state = state.with_event(event)
        assert len(state.event_log) == 0       # 原对象不变
        assert len(new_state.event_log) == 1
        assert new_state.event_log[0].event_type == "player_death"

    def test_with_message(self):
        state = GameState(players=self._make_players())
        msg = ChatMessage(
            speaker="p1",
            content="我是洗衣妇！",
            phase=GamePhase.DAY_DISCUSSION,
            round_number=1,
        )
        new_state = state.with_message(msg)
        assert len(new_state.chat_history) == 1

    def test_alive_players(self):
        players = (
            PlayerState(player_id="p1", name="A", role_id="r1", team=Team.GOOD),
            PlayerState(player_id="p2", name="B", role_id="r2", team=Team.EVIL, is_alive=False),
            PlayerState(player_id="p3", name="C", role_id="r3", team=Team.GOOD),
        )
        state = GameState(players=players)
        alive = state.get_alive_players()
        dead = state.get_dead_players()
        assert len(alive) == 2
        assert len(dead) == 1
        assert dead[0].name == "B"


# ============================================================
# GameEvent Tests
# ============================================================

class TestGameEvent:
    def test_create_event(self):
        event = GameEvent(
            event_type="night_kill",
            phase=GamePhase.NIGHT,
            round_number=2,
            actor="p1",
            target="p2",
            visibility=Visibility.STORYTELLER_ONLY,
            payload={"kill_type": "demon"},
        )
        assert event.event_type == "night_kill"
        assert event.visibility == Visibility.STORYTELLER_ONLY
        assert event.payload["kill_type"] == "demon"
        assert event.event_id  # 自动生成

    def test_public_event(self):
        event = GameEvent(
            event_type="player_speaks",
            phase=GamePhase.DAY_DISCUSSION,
            round_number=1,
        )
        assert event.visibility == Visibility.PUBLIC  # 默认公开


# ============================================================
# RoleDefinition Tests
# ============================================================

class TestRoleDefinition:
    def test_create_role(self):
        role = RoleDefinition(
            role_id="washerwoman",
            name="洗衣妇",
            name_en="Washerwoman",
            team=Team.GOOD,
            role_type=RoleType.TOWNSFOLK,
            ability=Ability(
                trigger=AbilityTrigger.FIRST_NIGHT,
                action_type=AbilityType.INFO_GATHER,
                description="你会得知两位玩家中有一位是某个特定的村民角色",
            ),
        )
        assert role.team == Team.GOOD
        assert role.role_type == RoleType.TOWNSFOLK
        assert role.ability.trigger == AbilityTrigger.FIRST_NIGHT


# ============================================================
# GameConfig Tests
# ============================================================

class TestGameConfig:
    def test_create_config(self):
        config = GameConfig(
            player_count=7,
            script=ScriptConfig(
                script_id="trouble_brewing",
                name="惹事生非",
                roles=["washerwoman", "librarian", "imp"],
            ),
        )
        assert config.player_count == 7
        assert config.storyteller_mode == "auto"
        assert config.script is not None
        assert len(config.script.roles) == 3


class TestPrivatePlayerView:
    def test_private_view_shape(self):
        view = PrivatePlayerView(
            player_id="p1",
            name="张三",
            true_role_id="drunken",
            perceived_role_id="washerwoman",
            current_team=Team.GOOD,
            is_drunk=True,
        )
        assert view.true_role_id == "drunken"
        assert view.perceived_role_id == "washerwoman"
