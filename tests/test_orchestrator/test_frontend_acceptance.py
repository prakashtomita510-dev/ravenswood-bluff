"""Frontend-facing acceptance checks for the player and storyteller views."""

from __future__ import annotations

import importlib
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from src.api.server import build_nomination_state
from src.state.game_state import GameState, PlayerState, Team


def make_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("BOTC_BACKEND", "mock")
    import src.api.server as server_module

    server_module = importlib.reload(server_module)
    return TestClient(server_module.app)


def wait_for_nomination_prompt(client: TestClient, player_id: str = "h1") -> dict:
    state: dict = {}
    for _ in range(30):
        time.sleep(0.1)
        state = client.get("/api/game/state", params={"player_id": player_id}).json()
        metrics = client.get("/api/game/metrics").json()
        if metrics.get("nomination_prompt_count", 0) > 0 or state.get("phase") in {"nomination", "voting", "night", "game_over"}:
            break
    return state


def test_player_frontend_contract_shows_private_info_and_nomination_state(monkeypatch):
    with make_client(monkeypatch) as client:
        setup = client.post(
            "/api/game/setup",
            json={
                "player_count": 5,
                "host_id": "h1",
                "human_mode": "player",
                "human_client_id": "h1",
                "discussion_rounds": 1,
                "audit_mode": True,
                "max_nomination_rounds": 3,
            },
        )
        assert setup.status_code == 200
        assert setup.json()["status"] == "ok"

        state = wait_for_nomination_prompt(client)

        assert state["viewer_mode"] == "player"
        assert state["human_mode"] == "player"
        assert state["can_view_grimoire"] is False
        assert isinstance(state["players"], list) and state["players"]
        assert isinstance(state["private_info"], list)
        assert "nomination_state" in state
        assert "stage" in state["nomination_state"]
        assert "threshold" in state["nomination_state"]
        assert "result_phase" in state["nomination_state"]

        grimoire = client.get("/api/game/grimoire", params={"player_id": "h1"})
        assert grimoire.status_code == 403


def test_storyteller_frontend_contract_exposes_grimoire_and_full_state(monkeypatch):
    with make_client(monkeypatch) as client:
        setup = client.post(
            "/api/game/setup",
            json={
                "player_count": 5,
                "host_id": "h1",
                "human_mode": "storyteller",
                "storyteller_client_id": "h1",
                "discussion_rounds": 1,
                "audit_mode": True,
                "max_nomination_rounds": 3,
            },
        )
        assert setup.status_code == 200
        assert setup.json()["status"] == "ok"

        state = wait_for_nomination_prompt(client, "h1")

        assert state["viewer_mode"] == "storyteller"
        assert state["human_mode"] == "storyteller"
        assert state["can_view_grimoire"] is True
        assert any("true_role_id" in player for player in state["players"])
        assert state["private_info"] == []

        grimoire = client.get("/api/game/grimoire", params={"player_id": "h1"})
        assert grimoire.status_code == 200
        payload = grimoire.json()
        assert "players" in payload
        assert payload["players"]


def test_frontend_contract_reset_clears_session_artifacts(monkeypatch):
    with make_client(monkeypatch) as client:
        setup = client.post(
            "/api/game/setup",
            json={
                "player_count": 5,
                "host_id": "h1",
                "human_mode": "player",
                "human_client_id": "h1",
                "discussion_rounds": 1,
                "audit_mode": True,
                "max_nomination_rounds": 3,
            },
        )
        assert setup.status_code == 200
        assert setup.json()["status"] == "ok"

        state_before = wait_for_nomination_prompt(client)
        assert state_before["game_id"]

        reset = client.post("/api/game/reset", json={"backend_mode": "mock"})
        assert reset.status_code == 200

        state_after = client.get("/api/game/state", params={"player_id": "h1"}).json()
        assert state_after["phase"] == "setup"
        assert state_after["game_id"] != state_before["game_id"]
        assert state_after["private_info"] == []
        assert state_after["nomination_state"]["stage"] == "idle"
        assert state_after["nomination_state"]["history"] == []
        assert state_after["nomination_state"]["has_current_round"] is False


def test_nomination_state_contract_keeps_pending_resolution_details():
    state = GameState(
        players=(
            PlayerState(player_id="p1", name="One", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Two", role_id="imp", team=Team.EVIL),
        ),
        payload={
            "nomination_state": {
                "stage": "resolved",
                "round": 2,
                "last_result": {"votes": 3, "needed": 3, "passed": True, "target": "p2"},
            }
        },
    )
    nomination_state = build_nomination_state(SimpleNamespace(state=state))

    assert nomination_state["game_id"] == state.game_id
    assert nomination_state["stage"] == "resolved"
    assert nomination_state["result_phase"] == "vote_resolved"
    assert nomination_state["last_result"]["passed"] is True
    assert nomination_state["last_result"]["target"] == "p2"
    assert nomination_state["threshold"] == 2
