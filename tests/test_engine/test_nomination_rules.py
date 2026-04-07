"""Phase 1 测试 — 规则引擎 & 提名投票系统"""

import pytest
from src.engine.rule_engine import RuleEngine
from src.engine.nomination import NominationManager
from src.state.game_state import GamePhase, GameState, PlayerState, Team


def make_test_state(phase: GamePhase = GamePhase.NOMINATION, **kwargs) -> GameState:
    players = (
        PlayerState(player_id="p1", name="A", role_id="imp", team=Team.EVIL),
        PlayerState(player_id="p2", name="B", role_id="washerwoman", team=Team.GOOD),
        PlayerState(player_id="p3", name="C", role_id="empath", team=Team.GOOD, is_alive=False),
        PlayerState(player_id="p4", name="D", role_id="poisoner", team=Team.EVIL, is_alive=False, has_used_dead_vote=True),
    )
    defaults = {"players": players, "phase": phase}
    defaults.update(kwargs)
    return GameState(**defaults)


class TestRuleEngine:
    def test_can_nominate_wrong_phase(self):
        state = make_test_state(phase=GamePhase.DAY_DISCUSSION)
        can, reason = RuleEngine.can_nominate(state, "p1", "p2")
        assert can is False
        assert "当前不是提名阶段" in reason

    def test_can_nominate_dead_nominator(self):
        state = make_test_state()
        can, reason = RuleEngine.can_nominate(state, "p3", "p1")
        assert can is False
        assert "死亡玩家不能发起提名" in reason

    def test_can_nominate_already_nominated_today(self):
        state = make_test_state(nominations_today=("p1",))
        can, reason = RuleEngine.can_nominate(state, "p1", "p2")
        assert can is False
        assert "每天只能发起一次提名" in reason

    def test_can_nominate_success(self):
        state = make_test_state()
        can, reason = RuleEngine.can_nominate(state, "p1", "p2")
        assert can is True
        assert reason == ""

    def test_can_vote(self):
        state = make_test_state(phase=GamePhase.VOTING, current_nominee="p2")
        # 活人投票
        can, _ = RuleEngine.can_vote(state, "p1")
        assert can is True
        # 死人第一次投票
        can, _ = RuleEngine.can_vote(state, "p3")
        assert can is True
        # 死人没票了
        can, reason = RuleEngine.can_vote(state, "p4")
        assert can is False
        assert "耗尽" in reason


class TestNominationManager:
    def test_nominate_success(self):
        state = make_test_state()
        new_state, events = NominationManager.nominate(state, "p1", "p2")
        
        assert new_state.phase == GamePhase.VOTING
        assert new_state.current_nominator == "p1"
        assert new_state.current_nominee == "p2"
        assert "p1" in new_state.nominations_today
        assert len(events) == 1
        assert events[0].event_type == "nomination"

    def test_nominate_fail(self):
        state = make_test_state(phase=GamePhase.DAY_DISCUSSION)
        with pytest.raises(ValueError, match="提名无效"):
            NominationManager.nominate(state, "p1", "p2")

    def test_cast_vote(self):
        state = make_test_state(phase=GamePhase.VOTING, current_nominee="p2")
        new_state, events = NominationManager.cast_vote(state, "p1", True)
        
        assert new_state.votes_today["p1"] is True
        assert len(events) == 1

    def test_resolve_voting_passed(self):
        # 4人局，存活2人，需要1票过半 (2//2=1)。死人p3投票。
        state = make_test_state(phase=GamePhase.VOTING, current_nominee="p2", votes_today={"p3": True})
        new_state, events = NominationManager.resolve_voting_round(state)
        
        assert new_state.phase == GamePhase.DAY_DISCUSSION
        assert new_state.current_nominee is None
        
        ev = events[0]
        assert ev.event_type == "voting_result"
        assert ev.payload["passed"] is True
        assert ev.payload["yes_votes"] == 1
        
        # 验证p3的死人票被扣除
        p3_new = new_state.get_player("p3")
        assert p3_new.has_used_dead_vote is True
        assert p3_new.ghost_votes_remaining == 0
