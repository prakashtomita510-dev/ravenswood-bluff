from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


EXPECTED_SAMPLE_KEYS = {
    "game_id",
    "script_id",
    "seed",
    "round_number",
    "phase",
    "players_truth",
    "players_public_state",
    "event_log_so_far",
    "candidate_adjudications",
    "chosen_adjudication",
    "storyteller_context",
}

EXPECTED_INDEX_KEYS = {
    "sample_count",
    "files",
    "curated_node_count",
    "curated_node_files",
    "full_game_node_count",
    "full_game_node_files",
    "full_games",
    "aggregate_balance_summary",
}


def _find_sample_export_script(repo_root: Path) -> Path:
    candidates = [
        repo_root / "scripts" / "storyteller_balance_sample_export.py",
        repo_root / "scripts" / "storyteller_balance_export.py",
        repo_root / "scripts" / "storyteller_sample_export.py",
        repo_root / "scripts" / "storyteller_eval_samples.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    pytest.skip("storyteller balance sample export script is not implemented yet")


def _extract_json_payload(stdout: str) -> dict:
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            return json.loads(line)
    pytest.fail("sample export script did not emit a JSON object on stdout")


def test_storyteller_balance_sample_export_contains_schema_keys():
    repo_root = Path(__file__).resolve().parents[2]
    script = _find_sample_export_script(repo_root)
    result = subprocess.run(
        [
            str(repo_root / ".venv" / "Scripts" / "python.exe"),
            str(script),
            "--full-games",
            "0",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = _extract_json_payload(result.stdout)
    assert EXPECTED_SAMPLE_KEYS <= payload.keys()
    index_payload = json.loads((repo_root / "storyteller_eval_samples" / "sample_index.json").read_text(encoding="utf-8"))
    assert EXPECTED_INDEX_KEYS <= index_payload.keys()
    assert index_payload["curated_node_count"] >= 1
    assert len(index_payload["curated_node_files"]) >= 1
    assert len(index_payload["full_games"]) >= 1
    assert index_payload["full_game_node_count"] >= 1
    assert all(item.get("source") == "curated_full_game" for item in index_payload["full_games"])
    assert index_payload["aggregate_balance_summary"]["night_info_judgement_count"] >= 1
    assert index_payload["aggregate_balance_summary"]["suppressed_info_count"] >= 1
    assert index_payload["aggregate_balance_summary"]["distorted_info_count"] >= 1
    assert index_payload["aggregate_balance_summary"]["legacy_fallback_count"] >= 1
    assert "judgement_category_counts" in index_payload["aggregate_balance_summary"]
    assert "event_type_counts" in index_payload["aggregate_balance_summary"]


def test_storyteller_balance_sample_index_tracks_multiple_full_games():
    repo_root = Path(__file__).resolve().parents[2]
    script = _find_sample_export_script(repo_root)
    result = subprocess.run(
        [
            str(repo_root / ".venv" / "Scripts" / "python.exe"),
            str(script),
            "--full-games",
            "1",
            "--timeout-seconds",
            "8",
            "--max-node-samples",
            "16",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    index_path = repo_root / "storyteller_eval_samples" / "sample_index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert "full_games" in payload
    assert isinstance(payload["full_games"], list)
    assert len(payload["full_games"]) >= 1
    assert all("game_id" in item and "node_count" in item for item in payload["full_games"])
    assert any(item.get("source") == "mock_full_game" for item in payload["full_games"])
    assert any(
        item.get("source") == "mock_full_game"
        and item.get("aggregate_balance_summary", {}).get("night_info_judgement_count", 0) >= 1
        for item in payload["full_games"]
    )
    assert payload["aggregate_balance_summary"]["reached_final_4_count"] >= 0
    assert payload["aggregate_balance_summary"]["full_game_count"] >= 1
    assert payload["aggregate_balance_summary"]["node_count"] == (
        payload["full_game_node_count"] + payload["curated_node_count"]
    )
    assert "aggregate_balance_summary" in payload["full_games"][0]
    game_dir = repo_root / "storyteller_eval_samples" / "full_game_nodes" / payload["full_games"][0]["game_id"]
    game_index = json.loads((game_dir / "sample_index.json").read_text(encoding="utf-8"))
    assert game_index["game_id"] == payload["full_games"][0]["game_id"]
    assert game_index["node_count"] == payload["full_games"][0]["node_count"]
    assert "judgement_category_counts" in game_index["aggregate_balance_summary"]
