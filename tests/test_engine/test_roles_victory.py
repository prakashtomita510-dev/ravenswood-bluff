"""Phase 1 测试 — 角色系统与胜负判定"""

import pytest
from src.engine.roles.base_role import get_role_class, get_all_role_ids
# ensure roles are registered
import src.engine.roles.townsfolk
import src.engine.roles.demons
import src.engine.roles.minions

from src.engine.victory_checker import VictoryChecker
from src.state.game_state import GamePhase, GameState, PlayerState, PlayerStatus, Team


def make_victory_state(alive_imp: bool = True, alive_good: int = 5) -> GameState:
    players = []
    
    # 添加一个恶魔
    players.append(PlayerState(
        player_id="demon", name="D", role_id="imp", team=Team.EVIL, is_alive=alive_imp
    ))
    
    # 添加好人
    for i in range(alive_good):
        players.append(PlayerState(
            player_id=f"g{i}", name=f"G{i}", role_id="washerwoman", team=Team.GOOD, is_alive=True
        ))
        
    # 添加死掉的好人凑数 (测试存活人数判定)
    players.append(PlayerState(
        player_id="dead_g", name="Dead", role_id="empath", team=Team.GOOD, is_alive=False
    ))
    
    return GameState(players=tuple(players))

class TestVictoryChecker:
    def test_no_winner_yet(self):
        state = make_victory_state(alive_imp=True, alive_good=5)
        winner = VictoryChecker.check_victory(state)
        assert winner is None
        
    def test_good_wins_demon_dead(self):
        state = make_victory_state(alive_imp=False, alive_good=5)
        winner = VictoryChecker.check_victory(state)
        assert winner == Team.GOOD

    def test_evil_wins_two_alive(self):
        # 恶魔 + 1个好人 = 2存活 -> 邪恶胜利
        state = make_victory_state(alive_imp=True, alive_good=1)
        winner = VictoryChecker.check_victory(state)
        assert winner == Team.EVIL

class TestRoles:
    def test_role_registration(self):
        ids = get_all_role_ids()
        assert "imp" in ids
        assert "washerwoman" in ids
        assert "empath" in ids
        assert "poisoner" in ids

    def test_washerwoman(self):
        cls = get_role_class("washerwoman")
        assert cls is not None
        df = cls.get_definition()
        assert df.name == "洗衣妇"
        
        # 测试 get_night_info
        role = cls()
        players = (
            PlayerState(player_id="w", name="W", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="t1", name="T1", role_id="empath", team=Team.GOOD),  # 村民
            PlayerState(player_id="e1", name="E1", role_id="imp", team=Team.EVIL),     # 不是村民
        )
        state = GameState(players=players)
        info = role.get_night_info(state, state.get_player("w"))
        assert info is not None
        assert info["type"] == "washerwoman_info"
        assert len(info["players"]) == 2
        assert "t1" in info["players"]
        assert info["role_seen"] == "empath"
        
    def test_imp_kill(self):
        cls = get_role_class("imp")
        role = cls()
        
        players = (
            PlayerState(player_id="imp", name="Imp", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="target", name="T", role_id="empath", team=Team.GOOD),
        )
        state = GameState(players=players)
        
        new_state, events = role.execute_ability(state, state.get_player("imp"), "target")
        assert new_state.get_player("target").is_alive is False
        assert len(events) == 1
        assert events[0].event_type == "night_kill"
        assert events[0].target == "target"

    def test_imp_suicide_transfer(self):
        cls = get_role_class("imp")
        role = cls()
        
        players = (
            PlayerState(player_id="imp", name="Imp", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="minion", name="M", role_id="poisoner", team=Team.EVIL),
        )
        state = GameState(players=players)
        
        # 自杀
        new_state, events = role.execute_ability(state, state.get_player("imp"), "imp")
        assert new_state.get_player("imp").is_alive is False
        # 转移
        assert new_state.get_player("minion").role_id == "imp"
        assert len(events) == 2  # kill, transfer
        assert events[1].event_type == "role_transfer"

    def test_poisoner(self):
        cls = get_role_class("poisoner")
        role = cls()
        
        players = (
            PlayerState(player_id="p", name="P", role_id="poisoner", team=Team.EVIL),
            PlayerState(player_id="target", name="T", role_id="empath", team=Team.GOOD),
        )
        state = GameState(players=players, phase=GamePhase.NIGHT)
        
        new_state, events = role.execute_ability(state, state.get_player("p"), "target")
        assert PlayerStatus.POISONED in new_state.get_player("target").statuses
        assert len(events) == 1
        assert events[0].event_type == "night_poison"
        assert events[0].phase == GamePhase.NIGHT
