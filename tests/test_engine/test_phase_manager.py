"""Phase 1 测试 — 阶段状态机"""

import pytest
from src.engine.phase_manager import PhaseManager
from src.state.game_state import GamePhase


class TestPhaseManager:
    def test_initial_state(self):
        pm = PhaseManager()
        assert pm.current_phase == GamePhase.SETUP
        assert pm.round_number == 0
        assert pm.day_number == 0

    def test_valid_transitions(self):
        pm = PhaseManager()
        
        # SETUP -> FIRST_NIGHT
        assert pm.can_transition_to(GamePhase.FIRST_NIGHT)
        pm.transition_to(GamePhase.FIRST_NIGHT)
        assert pm.current_phase == GamePhase.FIRST_NIGHT
        assert pm.round_number == 1
        assert pm.day_number == 0

        # FIRST_NIGHT -> DAY_DISCUSSION
        assert pm.can_transition_to(GamePhase.DAY_DISCUSSION)
        pm.transition_to(GamePhase.DAY_DISCUSSION)
        assert pm.current_phase == GamePhase.DAY_DISCUSSION
        assert pm.day_number == 1
        
        # DAY_DISCUSSION -> NOMINATION
        pm.transition_to(GamePhase.NOMINATION)
        assert pm.current_phase == GamePhase.NOMINATION

        # NOMINATION -> VOTING
        pm.transition_to(GamePhase.VOTING)
        assert pm.current_phase == GamePhase.VOTING

        # VOTING -> EXECUTION
        pm.transition_to(GamePhase.EXECUTION)
        
        # EXECUTION -> NIGHT
        pm.transition_to(GamePhase.NIGHT)
        assert pm.current_phase == GamePhase.NIGHT
        assert pm.round_number == 2

    def test_invalid_transitions(self):
        pm = PhaseManager()
        with pytest.raises(ValueError, match="非法阶段转移"):
            pm.transition_to(GamePhase.DAY_DISCUSSION)

    def test_reset(self):
        pm = PhaseManager()
        pm.transition_to(GamePhase.FIRST_NIGHT)
        pm.transition_to(GamePhase.DAY_DISCUSSION)
        
        pm.reset()
        assert pm.current_phase == GamePhase.SETUP
        assert pm.round_number == 0
        assert pm.day_number == 0
        assert len(pm.phase_history) == 0

    def test_phase_history(self):
        pm = PhaseManager()
        pm.transition_to(GamePhase.FIRST_NIGHT)
        
        history = pm.phase_history
        assert len(history) == 1
        assert history[0] == (GamePhase.FIRST_NIGHT, 1, 0)
