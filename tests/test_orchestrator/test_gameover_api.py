import importlib

import pytest
from fastapi.testclient import TestClient

from src.state.game_state import GameConfig, GamePhase, GameState, PlayerState, Team


def _memory_db_uri(name: str) -> str:
    return f"file:{name}?mode=memory&cache=shared"


def test_settlement_endpoint_returns_report_when_game_over(monkeypatch):
    monkeypatch.setenv("BOTC_BACKEND", "mock")
    import src.api.server as server_module

    server_module = importlib.reload(server_module)
    orchestrator = server_module.build_fresh_orchestrator("mock")
    orchestrator.state = GameState(
        game_id="settlement-test",
        phase=GamePhase.GAME_OVER,
        round_number=4,
        day_number=2,
        winning_team=Team.GOOD,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="imp", team=Team.EVIL, is_alive=False),
        ),
    )
    orchestrator.winner = Team.GOOD
    orchestrator.settlement_report = {
        "game_id": "settlement-test",
        "winning_team": "good",
        "victory_reason": "demon_executed",
        "duration_rounds": 4,
        "days_played": 2,
        "players": [],
        "timeline": [],
        "statistics": {
            "total_nominations": 1,
            "total_executions": 1,
            "total_votes": 2,
            "total_deaths": 1,
            "days_played": 2,
            "player_count": 2,
        },
    }
    with TestClient(server_module.app) as client:
        server_module.global_orchestrator = orchestrator
        response = client.get("/api/game/settlement")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["game_id"] == "settlement-test"
        assert payload["winning_team"] == "good"
        assert payload["victory_reason"] == "demon_executed"


@pytest.mark.asyncio
async def test_history_endpoints_read_persisted_games(monkeypatch):
    monkeypatch.setenv("BOTC_BACKEND", "mock")
    import src.state.game_record as game_record_module
    import src.api.server as server_module

    db_uri = _memory_db_uri("api_game_record_test")
    original_init = game_record_module.GameRecordStore.__init__

    def patched_init(self, db_path_arg: str = "data/games.db"):
        return original_init(self, db_uri)

    monkeypatch.setattr(game_record_module.GameRecordStore, "__init__", patched_init)
    server_module = importlib.reload(server_module)

    store = game_record_module.GameRecordStore()
    state = GameState(
        game_id="history-test",
        phase=GamePhase.GAME_OVER,
        round_number=3,
        day_number=2,
        winning_team=Team.GOOD,
        players=(
            PlayerState(
                player_id="p1",
                name="Alice",
                role_id="washerwoman",
                true_role_id="washerwoman",
                perceived_role_id="washerwoman",
                team=Team.GOOD,
                current_team=Team.GOOD,
            ),
            PlayerState(
                player_id="p2",
                name="Bob",
                role_id="imp",
                true_role_id="imp",
                perceived_role_id="chef",
                team=Team.EVIL,
                current_team=Team.EVIL,
                is_alive=False,
            ),
        ),
    )
    settlement = {
        "game_id": "history-test",
        "winning_team": "good",
        "victory_reason": "demon_executed",
        "duration_rounds": 3,
        "days_played": 2,
        "players": [],
        "timeline": [],
        "statistics": {
            "total_nominations": 1,
            "total_executions": 1,
            "total_votes": 2,
            "total_deaths": 1,
            "days_played": 2,
            "player_count": 2,
        },
    }
    try:
        await store.save_game("history-test", state, settlement)

        with TestClient(server_module.app) as client:
            list_response = client.get("/api/game/history")
            assert list_response.status_code == 200
            list_payload = list_response.json()
            assert list_payload["status"] == "ok"
            assert any(item["game_id"] == "history-test" for item in list_payload["games"])

            detail_response = client.get("/api/game/history/history-test")
            assert detail_response.status_code == 200
            detail_payload = detail_response.json()
            assert detail_payload["status"] == "ok"
            assert detail_payload["game_id"] == "history-test"
            assert detail_payload["winning_team"] == "good"
            assert detail_payload["storyteller_judgements"]["game_id"] == "history-test"
            assert detail_payload["storyteller_judgements"]["judgement_count"] == 0

            player_response = client.get("/api/game/history/player/Alice")
            assert player_response.status_code == 200
            player_payload = player_response.json()
            assert player_payload["status"] == "ok"
            assert player_payload["player_name"] == "Alice"
            assert any(item["game_id"] == "history-test" for item in player_payload["games"])
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_export_endpoint_returns_history_traces_and_judgement_summary(monkeypatch):
    monkeypatch.setenv("BOTC_BACKEND", "mock")
    import src.state.game_record as game_record_module
    import src.engine.data_collector as data_collector_module
    import src.api.server as server_module

    db_uri = _memory_db_uri("api_game_export_test")
    original_init = game_record_module.GameRecordStore.__init__

    def patched_init(self, db_path_arg: str = "data/games.db"):
        return original_init(self, db_uri)

    monkeypatch.setattr(game_record_module.GameRecordStore, "__init__", patched_init)
    monkeypatch.setattr(data_collector_module.GameDataCollector, "export_ai_traces", classmethod(lambda cls, game_id, base_dir="data/sessions": {
        "version": "a3-data-export-v1",
        "game_id": game_id,
        "entries": [{"record_type": "thought_trace", "game_id": game_id}],
        "files": [],
        "stats": {
            "file_count": 0,
            "entry_count": 1,
            "thought_trace_count": 1,
            "snapshot_count": 0,
            "parse_error_count": 0,
        },
    }))

    server_module = importlib.reload(server_module)

    store = game_record_module.GameRecordStore()
    state = GameState(
        game_id="export-test",
        phase=GamePhase.GAME_OVER,
        round_number=3,
        day_number=2,
        winning_team=Team.GOOD,
        players=(
            PlayerState(
                player_id="p1",
                name="Alice",
                role_id="washerwoman",
                true_role_id="washerwoman",
                perceived_role_id="washerwoman",
                team=Team.GOOD,
                current_team=Team.GOOD,
            ),
            PlayerState(
                player_id="p2",
                name="Bob",
                role_id="imp",
                true_role_id="imp",
                perceived_role_id="chef",
                team=Team.EVIL,
                current_team=Team.EVIL,
                is_alive=False,
            ),
        ),
    )
    settlement = {
        "game_id": "export-test",
        "winning_team": "good",
        "victory_reason": "demon_executed",
        "duration_rounds": 3,
        "days_played": 2,
        "players": [],
        "timeline": [],
        "statistics": {
            "total_nominations": 1,
            "total_executions": 1,
            "total_votes": 2,
            "total_deaths": 1,
            "days_played": 2,
            "player_count": 2,
        },
        "judgement_summary": [
            {"category": "night_info", "decision": "deliver", "reason": "sample", "summary": "player_id=p1"}
        ],
    }

    try:
        await store.save_game("export-test", state, settlement)

        with TestClient(server_module.app) as client:
            response = client.get("/api/game/export/export-test")
            assert response.status_code == 200
            payload = response.json()
            assert payload["status"] == "ok"
            assert payload["game_id"] == "export-test"
            assert payload["game_history"]["game_id"] == "export-test"
            assert payload["storyteller_judgements"]["game_id"] == "export-test"
            assert payload["storyteller_judgements"]["judgement_count"] == 1
            assert payload["ai_traces"]["game_id"] == "export-test"
            assert payload["ai_traces"]["stats"]["entry_count"] == 1
    finally:
        await store.close()


def test_rematch_endpoint_restarts_game_with_same_config(monkeypatch):
    monkeypatch.setenv("BOTC_BACKEND", "mock")
    import src.api.server as server_module

    server_module = importlib.reload(server_module)
    orchestrator = server_module.build_fresh_orchestrator("mock")
    orchestrator.state = GameState(
        game_id="finished-game",
        phase=GamePhase.GAME_OVER,
        round_number=4,
        day_number=2,
        winning_team=Team.GOOD,
        players=(
            PlayerState(player_id="h1", name="Host", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="imp", team=Team.EVIL, is_alive=False),
        ),
        config=GameConfig(
            player_count=5,
            human_mode="player",
            human_client_id="h1",
            storyteller_client_id=None,
            backend_mode="mock",
        ),
    )

    with TestClient(server_module.app) as client:
        server_module.global_orchestrator = orchestrator
        response = client.post("/api/game/rematch")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["player_count"] == 5
        assert payload["new_game_id"] != "finished-game"
        assert server_module.global_orchestrator is not None
        assert server_module.global_orchestrator.state.game_id == payload["new_game_id"]
        assert server_module.global_orchestrator.state.phase != GamePhase.GAME_OVER


def test_game_state_marks_configured_setup_as_not_requiring_setup(monkeypatch):
    monkeypatch.setenv("BOTC_BACKEND", "mock")
    import src.api.server as server_module

    server_module = importlib.reload(server_module)
    orchestrator = server_module.build_fresh_orchestrator("mock")
    orchestrator.state = GameState(
        game_id="configured-setup",
        phase=GamePhase.SETUP,
        round_number=0,
        day_number=0,
        players=(
            PlayerState(player_id="h1", name="Human Player", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Player 2", role_id="imp", team=Team.EVIL),
        ),
        seat_order=("h1", "p2"),
        config=GameConfig(
            player_count=2,
            human_mode="player",
            human_client_id="h1",
            storyteller_client_id=None,
            backend_mode="mock",
        ),
    )

    with TestClient(server_module.app) as client:
        server_module.global_orchestrator = orchestrator
        response = client.get("/api/game/state?player_id=h1")
        assert response.status_code == 200
        payload = response.json()
        assert payload["phase"] == "setup"
        assert payload["setup_configured"] is True
        assert payload["setup_required"] is False
