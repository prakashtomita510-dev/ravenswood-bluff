"""Phase 0 测试 — 状态快照"""

import json
import pytest
from src.state.snapshot import SnapshotManager
from src.state.game_state import GamePhase, GameState, PlayerState, Team


def make_state(**kwargs) -> GameState:
    defaults = {
        "players": (
            PlayerState(player_id="p1", name="A", role_id="r1", team=Team.GOOD),
        ),
    }
    defaults.update(kwargs)
    return GameState(**defaults)


class TestSnapshotManager:
    def test_take_snapshot(self):
        mgr = SnapshotManager()
        state = make_state()
        snap = mgr.take_snapshot(state, "初始状态")

        assert snap.snapshot_id == 0
        assert snap.description == "初始状态"
        assert snap.game_state.phase == GamePhase.SETUP

    def test_get_snapshot(self):
        mgr = SnapshotManager()
        mgr.take_snapshot(make_state(), "第一个")
        mgr.take_snapshot(
            make_state(phase=GamePhase.FIRST_NIGHT, round_number=1),
            "第二个",
        )

        snap = mgr.get_snapshot(1)
        assert snap is not None
        assert snap.description == "第二个"
        assert snap.game_state.phase == GamePhase.FIRST_NIGHT

    def test_get_latest(self):
        mgr = SnapshotManager()
        assert mgr.get_latest() is None

        mgr.take_snapshot(make_state(), "A")
        mgr.take_snapshot(make_state(), "B")
        assert mgr.get_latest().description == "B"

    def test_count(self):
        mgr = SnapshotManager()
        assert mgr.count == 0
        mgr.take_snapshot(make_state())
        mgr.take_snapshot(make_state())
        assert mgr.count == 2

    def test_export_to_json(self):
        mgr = SnapshotManager()
        mgr.take_snapshot(make_state(), "test")
        json_str = mgr.export_to_json()
        data = json.loads(json_str)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["description"] == "test"

    def test_repr(self):
        mgr = SnapshotManager()
        assert "SnapshotManager" in repr(mgr)
