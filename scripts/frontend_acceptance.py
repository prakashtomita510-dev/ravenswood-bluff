"""Reusable frontend acceptance runner for the BOTC player/storyteller contract.

This script stays server-side and validates the state the browser depends on:
player vs storyteller permissions, private information delivery, and nomination
state visibility. For visual/browser verification, follow docs/frontend_acceptance.md
with Playwright/MCP.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
import time
from typing import Any

from fastapi.testclient import TestClient


def make_client(backend_mode: str) -> TestClient:
    os.environ["BOTC_BACKEND"] = backend_mode
    import src.api.server as server_module

    server_module = importlib.reload(server_module)
    return TestClient(server_module.app)


def wait_for_state(client: TestClient, player_id: str = "h1") -> dict[str, Any]:
    last_state: dict[str, Any] = {}
    for _ in range(30):
        time.sleep(0.1)
        last_state = client.get("/api/game/state", params={"player_id": player_id}).json()
        metrics = client.get("/api/game/metrics").json()
        if metrics.get("nomination_prompt_count", 0) > 0 or last_state.get("phase") in {"nomination", "voting", "night", "game_over"}:
            break
    return last_state


def assert_player_contract(client: TestClient) -> None:
    response = client.post(
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
    response.raise_for_status()
    state = wait_for_state(client, "h1")
    assert state["viewer_mode"] == "player"
    assert state["can_view_grimoire"] is False
    assert state["private_info"] is not None
    assert isinstance(state["nomination_state"], dict)
    assert "result_phase" in state["nomination_state"]
    assert client.get("/api/game/grimoire", params={"player_id": "h1"}).status_code == 403


def assert_storyteller_contract(client: TestClient) -> None:
    response = client.post(
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
    response.raise_for_status()
    state = wait_for_state(client, "h1")
    assert state["viewer_mode"] == "storyteller"
    assert state["can_view_grimoire"] is True
    assert state["private_info"] == []
    assert client.get("/api/game/grimoire", params={"player_id": "h1"}).status_code == 200


def main() -> int:
    parser = argparse.ArgumentParser(description="Run frontend acceptance checks.")
    parser.add_argument("--backend", default="mock", help="Backend mode to use (default: mock)")
    args = parser.parse_args()

    with make_client(args.backend) as client:
        assert_player_contract(client)
    with make_client(args.backend) as client:
        assert_storyteller_contract(client)

    print("frontend acceptance: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
