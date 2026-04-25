from __future__ import annotations

import pytest
import aiosqlite

from src.state.game_record import GameRecordStore
from src.state.game_state import GamePhase, GameState, PlayerState, Team


def _state(game_id: str, *, round_number: int = 3, winning_team: Team | None = Team.GOOD) -> GameState:
    return GameState(
        game_id=game_id,
        phase=GamePhase.GAME_OVER,
        round_number=round_number,
        day_number=2,
        winning_team=winning_team,
        players=(
            PlayerState(
                player_id="p1",
                name="Alice",
                role_id="washerwoman",
                true_role_id="washerwoman",
                perceived_role_id="washerwoman",
                team=Team.GOOD,
                current_team=Team.GOOD,
                is_alive=True,
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
        seat_order=("p1", "p2"),
    )


def _settlement(game_id: str, winning_team: str = "good") -> dict:
    return {
        "game_id": game_id,
        "winning_team": winning_team,
        "victory_reason": "demon_executed" if winning_team == "good" else "last_two_alive",
        "duration_rounds": 3,
        "days_played": 2,
        "players": [
            {
                "player_id": "p1",
                "name": "Alice",
                "true_role_id": "washerwoman",
                "perceived_role_id": "washerwoman",
                "team": "good",
                "is_alive": True,
                "stats": {"nominations_made": 1, "times_nominated": 0, "votes_cast": 2, "votes_yes": 2},
            },
            {
                "player_id": "p2",
                "name": "Bob",
                "true_role_id": "imp",
                "perceived_role_id": "chef",
                "team": "evil",
                "is_alive": False,
                "stats": {"nominations_made": 0, "times_nominated": 1, "votes_cast": 1, "votes_yes": 0},
            },
        ],
        "timeline": [],
        "statistics": {"total_nominations": 1, "total_executions": 1, "total_votes": 3, "total_deaths": 1, "days_played": 2, "player_count": 2},
    }

def _memory_db_uri(name: str) -> str:
    return f"file:{name}?mode=memory&cache=shared"


@pytest.mark.asyncio
async def test_game_record_store_save_get_list_and_player_history():
    store = GameRecordStore(_memory_db_uri("game_record_store_test"))
    try:
        state_one = _state("game-1")
        state_two = _state("game-2", round_number=5, winning_team=Team.EVIL)
        settlement_one = _settlement("game-1", "good")
        settlement_two = _settlement("game-2", "evil")

        await store.save_game("game-1", state_one, settlement_one)
        await store.save_game("game-2", state_two, settlement_two)

        record = await store.get_game("game-1")
        assert record is not None
        assert record["game_id"] == "game-1"
        assert record["winning_team"] == "good"
        assert record["settlement"]["victory_reason"] == "demon_executed"
        assert len(record["players"]) == 2
        assert {player["player_name"] for player in record["players"]} == {"Alice", "Bob"}

        games = await store.list_games(limit=10, offset=0)
        assert len(games) == 2
        assert {game["game_id"] for game in games} == {"game-1", "game-2"}

        alice_history = await store.get_player_history("Alice")
        assert len(alice_history) == 2
        assert {entry["game_id"] for entry in alice_history} == {"game-1", "game-2"}
        assert all(entry["player_name"] == "Alice" for entry in alice_history)

        bob_history = await store.get_player_history("Bob")
        assert len(bob_history) == 2
        assert {entry["true_role_id"] for entry in bob_history} == {"imp"}
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_game_record_store_recovers_from_disk_io_error(monkeypatch):
    store = GameRecordStore("data/_json_fallback_game_record.db")

    async def always_fail_schema():
        raise aiosqlite.OperationalError("disk I/O error")

    async def fake_recover(*, include_primary_db: bool):
        return None

    monkeypatch.setattr(store, "_ensure_schema", always_fail_schema)
    monkeypatch.setattr(store, "_recover_disk_store", fake_recover)

    try:
        await store.initialize()
        assert store._using_json_fallback()

        await store.save_game("fallback-game", _state("fallback-game"), _settlement("fallback-game"))
        record = await store.get_game("fallback-game")
        assert record is not None
        assert record["game_id"] == "fallback-game"
        assert record["winning_team"] == "good"
        history = await store.list_games(limit=5, offset=0)
        assert history and history[0]["game_id"] == "fallback-game"
    finally:
        await store.close()
        fallback_path = store._json_fallback_path
        if fallback_path.exists():
            try:
                fallback_path.unlink()
            except PermissionError:
                pass


@pytest.mark.asyncio
async def test_game_record_store_exports_history_and_storyteller_judgements_by_game_id():
    from src.agents.storyteller_agent import StorytellerAgent

    store = GameRecordStore(_memory_db_uri("game_record_export_test"))
    try:
        game_id = "game-export-1"
        state = _state(game_id)
        settlement = _settlement(game_id, "good")
        storyteller = StorytellerAgent()
        storyteller.record_judgement(
            "night_info",
            decision="deliver",
            phase="night",
            round_number=2,
            bucket="night_info.storyteller_info",
            player_id="p1",
        )

        await store.save_game(game_id, state, settlement)
        payload = await store.export_game_assets(game_id, storyteller)

        assert payload is not None
        assert payload["game_id"] == game_id
        assert payload["game_history"]["game_id"] == game_id
        assert payload["storyteller_judgements"]["game_id"] == game_id
        assert payload["storyteller_judgements"]["judgement_count"] == 1
        assert payload["storyteller_judgements"]["judgements"][0]["game_id"] == game_id
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_game_record_store_exports_settlement_judgement_summary_without_live_storyteller():
    store = GameRecordStore(_memory_db_uri("game_record_export_summary_test"))
    try:
        game_id = "game-export-summary"
        state = _state(game_id)
        settlement = _settlement(game_id, "good")
        settlement["judgement_summary"] = [
            {
                "category": "night_info",
                "decision": "deliver",
                "reason": "fortune_teller_result",
                "summary": "player_id=p1",
            }
        ]

        await store.save_game(game_id, state, settlement)
        payload = await store.export_game_assets(game_id, storyteller_agent=None)

        assert payload is not None
        assert payload["storyteller_judgements"]["game_id"] == game_id
        assert payload["storyteller_judgements"]["judgement_count"] == 1
        assert payload["storyteller_judgements"]["recent_summary"][0]["category"] == "night_info"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_game_record_store_exports_history_detail_with_storyteller_judgements():
    store = GameRecordStore(_memory_db_uri("game_record_history_detail_test"))
    try:
        game_id = "history-detail-export"
        state = _state(game_id)
        settlement = _settlement(game_id, "good")
        settlement["judgement_summary"] = [
            {
                "category": "night_info",
                "bucket": "night_info.fixed_info",
                "decision": "deliver",
                "reason": "chef_info",
                "phase": "first_night",
                "day_number": 1,
                "round_number": 1,
                "summary": "player_id=p1",
            }
        ]

        await store.save_game(game_id, state, settlement)
        detail = await store.export_history_detail(game_id, storyteller_agent=None)

        assert detail is not None
        assert detail["game_id"] == game_id
        assert detail["storyteller_judgements"]["game_id"] == game_id
        assert detail["storyteller_judgements"]["judgement_count"] == 1
        assert detail["storyteller_judgements"]["recent_summary"][0]["bucket"] == "night_info.fixed_info"
    finally:
        await store.close()
