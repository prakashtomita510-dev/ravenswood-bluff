import json
import logging
import importlib
import time
from pathlib import Path
import uuid

import pytest
from fastapi.testclient import TestClient
from src.state.game_state import GameEvent, GamePhase, GameState, PlayerState, Team


def make_client(monkeypatch):
    monkeypatch.setenv("BOTC_BACKEND", "mock")
    import src.api.server as server_module

    server_module = importlib.reload(server_module)
    return TestClient(server_module.app)


def test_game_start_is_idempotent(monkeypatch):
    with make_client(monkeypatch) as client:
        response = client.post("/api/game/start")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["already_running"] is True


def test_game_state_and_metrics_include_game_id_and_reset_changes_session(monkeypatch):
    with make_client(monkeypatch) as client:
        setup = client.post(
            "/api/game/setup",
            json={
                "player_count": 5,
                "host_id": "h1",
                "human_mode": "player",
                "human_client_id": "h1",
            },
        )
        assert setup.status_code == 200
        assert setup.json()["status"] == "ok"

        state_before = client.get("/api/game/state", params={"player_id": "h1"}).json()
        metrics_before = client.get("/api/game/metrics").json()
        assert state_before["game_id"]
        assert state_before["game_id"] == metrics_before["game_id"]

        reset = client.post("/api/game/reset", json={"backend_mode": "mock"})
        assert reset.status_code == 200

        state_after = client.get("/api/game/state", params={"player_id": "h1"}).json()
        metrics_after = client.get("/api/game/metrics").json()
        assert state_after["game_id"]
        assert state_after["game_id"] == metrics_after["game_id"]
        assert state_after["game_id"] != state_before["game_id"]


def test_metrics_expose_backend_and_nomination_flow(monkeypatch):
    with make_client(monkeypatch) as client:
        setup = client.post(
            "/api/game/setup",
            json={
                "player_count": 5,
                "host_id": "h1",
                "human_mode": "none",
                "discussion_rounds": 1,
                "audit_mode": True,
                "max_nomination_rounds": 1,
            },
        )
        assert setup.status_code == 200
        assert setup.json()["status"] == "ok"

        metrics = {}
        for _ in range(20):
            time.sleep(0.1)
            metrics = client.get("/api/game/metrics").json()
            if metrics.get("nomination_prompt_count", 0) > 0:
                break

        assert metrics["backend"]["type"] == "MockBackend"
        assert "phase" in metrics
        assert metrics["legal_nomination_count"] >= 1
        assert metrics["vote_count"] >= 1
        assert metrics["execution_count"] >= 1


def test_decorated_ws_message_includes_game_id(monkeypatch):
    monkeypatch.setenv("BOTC_BACKEND", "mock")
    import src.api.server as server_module

    server_module = importlib.reload(server_module)
    orchestrator = server_module.build_fresh_orchestrator("mock")
    message = json.dumps({"type": "event_update", "event": {"event_type": "phase_changed"}}, ensure_ascii=False)

    decorated = server_module.decorate_ws_message_with_game_id(message, orchestrator)
    payload = json.loads(decorated)

    assert payload["game_id"] == orchestrator.state.game_id
    assert payload["type"] == "event_update"
    assert payload["event"]["event_type"] == "phase_changed"


def test_player_mode_cannot_view_grimoire(monkeypatch):
    with make_client(monkeypatch) as client:
        setup = client.post(
            "/api/game/setup",
            json={
                "player_count": 5,
                "host_id": "h1",
                "human_mode": "player",
                "human_client_id": "h1",
            },
        )
        assert setup.status_code == 200
        assert setup.json()["status"] == "ok"

        state = client.get("/api/game/state", params={"player_id": "h1"})
        assert state.status_code == 200
        state_payload = state.json()
        assert state_payload["viewer_mode"] == "player"
        assert state_payload["can_view_grimoire"] is False

        grimoire = client.get("/api/game/grimoire", params={"player_id": "h1"})
        assert grimoire.status_code == 403


def test_storyteller_mode_can_view_grimoire(monkeypatch):
    with make_client(monkeypatch) as client:
        setup = client.post(
            "/api/game/setup",
            json={
                "player_count": 5,
                "host_id": "h1",
                "human_mode": "storyteller",
                "storyteller_client_id": "h1",
            },
        )
        assert setup.status_code == 200
        assert setup.json()["status"] == "ok"

        state = client.get("/api/game/state", params={"player_id": "h1"})
        assert state.status_code == 200
        state_payload = state.json()
        assert state_payload["viewer_mode"] == "storyteller"
        assert state_payload["can_view_grimoire"] is True

        grimoire = client.get("/api/game/grimoire", params={"player_id": "h1"})
        assert grimoire.status_code == 200
        payload = grimoire.json()
        assert "players" in payload


def test_build_nomination_state_preserves_payload_vote_details(monkeypatch):
    monkeypatch.setenv("BOTC_BACKEND", "mock")
    import src.api.server as server_module

    server_module = importlib.reload(server_module)
    orchestrator = server_module.build_fresh_orchestrator("mock")
    orchestrator.state = GameState(
        phase=GamePhase.NOMINATION,
        players=(
            PlayerState(player_id="p1", name="One", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Two", role_id="imp", team=Team.EVIL),
        ),
        payload={
            "nomination_state": {
                "stage": "resolved",
                "round": 2,
                "current_nominator": "p1",
                "current_nominee": "p2",
                "yes_votes": 1,
                "votes_cast": 2,
                "votes": {"p1": True, "p2": False},
                "defense_text": "I am not the demon.",
                "last_result": {"executed": None, "votes": 1},
            },
            "nomination_history": [
                {
                    "kind": "nomination_started",
                    "round": 2,
                    "nominator": "p1",
                    "nominee": "p2",
                },
                {
                    "kind": "voting_resolved",
                    "round": 2,
                    "nominee": "p2",
                    "votes": 1,
                    "needed": 2,
                    "passed": False,
                },
            ],
        },
    )

    nomination_state = server_module.build_nomination_state(orchestrator)

    assert nomination_state["stage"] == "resolved"
    assert nomination_state["round"] == 2
    assert nomination_state["current_nominator"] == "p1"
    assert nomination_state["current_nominee"] == "p2"
    assert nomination_state["votes"] == {"p1": True, "p2": False}
    assert nomination_state["votes_cast"] == 2
    assert nomination_state["yes_votes"] == 1
    assert nomination_state["defense_text"] == "I am not the demon."
    assert nomination_state["result_phase"] == "vote_resolved"
    assert nomination_state["history"][0]["kind"] == "nomination_started"
    assert nomination_state["history"][1]["kind"] == "voting_resolved"


def test_build_nomination_state_infers_history_from_event_log(monkeypatch):
    monkeypatch.setenv("BOTC_BACKEND", "mock")
    import src.api.server as server_module

    server_module = importlib.reload(server_module)
    orchestrator = server_module.build_fresh_orchestrator("mock")
    orchestrator.state = GameState(
        phase=GamePhase.EXECUTION,
        players=(
            PlayerState(player_id="p1", name="One", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Two", role_id="imp", team=Team.EVIL),
        ),
        event_log=(
            GameEvent(
                event_type="nomination_started",
                phase=GamePhase.NOMINATION,
                round_number=1,
                actor="p1",
                target="p2",
            ),
            GameEvent(
                event_type="voting_resolved",
                phase=GamePhase.VOTING,
                round_number=1,
                target="p2",
                payload={"votes": 2, "needed": 2, "passed": True},
            ),
            GameEvent(
                event_type="execution_resolved",
                phase=GamePhase.EXECUTION,
                round_number=1,
                target="p2",
                payload={"executed": "p2", "votes": 2},
            ),
        ),
        payload={"nomination_state": {"stage": "executed", "last_result": {"executed": "p2", "votes": 2}}},
    )

    nomination_state = server_module.build_nomination_state(orchestrator)

    assert [entry["kind"] for entry in nomination_state["history"]] == [
        "nomination_started",
        "voting_resolved",
        "execution_resolved",
    ]


@pytest.mark.asyncio
async def test_storyteller_log_is_written_without_api_leak(monkeypatch):
    monkeypatch.setenv("BOTC_BACKEND", "mock")
    for handler in list(logging.getLogger("storyteller").handlers):
        try:
            handler.flush()
        except Exception:
            pass
        try:
            handler.close()
        except Exception:
            pass
        logging.getLogger("storyteller").removeHandler(handler)

    test_dir = Path.cwd() / f"_storyteller_test_workspace_{uuid.uuid4().hex[:8]}"
    test_dir.mkdir(exist_ok=True)
    monkeypatch.chdir(test_dir)
    log_path = Path("storyteller_run.log")

    import src.api.server as server_module

    server_module = importlib.reload(server_module)
    orch = server_module.build_fresh_orchestrator("mock")

    narration = await orch.storyteller_agent.narrate_phase(orch.state)
    step = await orch.storyteller_agent.get_human_storyteller_step(orch.state, GamePhase.SETUP)

    for handler in logging.getLogger("storyteller").handlers:
        if hasattr(handler, "flush"):
            handler.flush()

    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "narrate_phase" in content
    assert "get_human_storyteller_step" in content
    assert narration
    assert step["phase"] == GamePhase.SETUP.value

    with TestClient(server_module.app) as client:
        state = client.get("/api/game/state", params={"player_id": "h1"})
        assert state.status_code == 200
        payload = state.json()
        body = json.dumps(payload, ensure_ascii=False)
        assert "storyteller_run.log" not in body
        assert "narrate_phase" not in body
