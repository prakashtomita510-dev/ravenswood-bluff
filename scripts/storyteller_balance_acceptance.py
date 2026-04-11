"""Wave 2 storyteller balance acceptance runner."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(repo_root: Path, args: list[str]) -> None:
    result = subprocess.run(
        [str(repo_root / ".venv" / "Scripts" / "python.exe"), *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout)


def _check_balance_index(repo_root: Path) -> dict:
    index_path = repo_root / "storyteller_eval_samples" / "sample_index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    summary = payload.get("aggregate_balance_summary", {})
    full_games = payload.get("full_games", [])
    if payload.get("curated_node_count", 0) < 3:
        raise SystemExit("storyteller balance acceptance failed: curated node coverage is too small")
    if summary.get("night_info_judgement_count", 0) < 1:
        raise SystemExit("storyteller balance acceptance failed: missing night_info judgements")
    if summary.get("suppressed_info_count", 0) < 1:
        raise SystemExit("storyteller balance acceptance failed: missing suppressed storyteller samples")
    if summary.get("distorted_info_count", 0) < 1:
        raise SystemExit("storyteller balance acceptance failed: missing distorted storyteller samples")
    if summary.get("legacy_fallback_count", 0) < 1:
        raise SystemExit("storyteller balance acceptance failed: missing legacy fallback samples")
    if "judgement_category_counts" not in summary or not summary["judgement_category_counts"]:
        raise SystemExit("storyteller balance acceptance failed: missing judgement category distribution")
    if "event_type_counts" not in summary or not summary["event_type_counts"]:
        raise SystemExit("storyteller balance acceptance failed: missing event type distribution")
    if not full_games:
        raise SystemExit("storyteller balance acceptance failed: missing full game samples")
    if not any(item.get("source") == "mock_full_game" for item in full_games):
        raise SystemExit("storyteller balance acceptance failed: missing mock full-game trace")

    combined_categories: set[str] = set()
    combined_suppressed = 0
    combined_distorted = 0
    combined_legacy = 0
    for game in full_games:
        game_summary = game.get("aggregate_balance_summary", {})
        if game_summary.get("event_node_fallback_count", 999) > 0:
            raise SystemExit("storyteller balance acceptance failed: full-game nodes still rely on event-node fallback")
        combined_categories.update((game_summary.get("judgement_category_counts") or {}).keys())
        combined_suppressed += int(game_summary.get("suppressed_info_count", 0))
        combined_distorted += int(game_summary.get("distorted_info_count", 0))
        combined_legacy += int(game_summary.get("legacy_fallback_count", 0))
        game_dir = repo_root / "storyteller_eval_samples" / "full_game_nodes" / game["game_id"]
        game_index = json.loads((game_dir / "sample_index.json").read_text(encoding="utf-8"))
        if game_index.get("node_count") != game.get("node_count"):
            raise SystemExit("storyteller balance acceptance failed: per-game node index is inconsistent")

    required_categories = {"night_info", "night_action", "nomination_started", "voting_resolution", "execution"}
    missing = sorted(required_categories - combined_categories)
    if missing:
        raise SystemExit(
            "storyteller balance acceptance failed: full-game judgement coverage missing categories: "
            + ", ".join(missing)
        )
    if combined_suppressed < 1:
        raise SystemExit("storyteller balance acceptance failed: full-game traces missing suppressed cases")
    if combined_distorted < 1:
        raise SystemExit("storyteller balance acceptance failed: full-game traces missing distorted cases")
    if combined_legacy < 1:
        raise SystemExit("storyteller balance acceptance failed: full-game traces missing legacy fallback cases")
    return payload


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    _run(
        repo_root,
        [
            str(repo_root / "scripts" / "storyteller_balance_sample_export.py"),
            "--full-games",
            "1",
            "--timeout-seconds",
            "8",
            "--max-node-samples",
            "16",
        ],
    )
    _run(
        repo_root,
        [
            "-m",
            "pytest",
            "tests/test_orchestrator/test_storyteller_balance_sample_export.py",
            "-q",
        ],
    )
    payload = _check_balance_index(repo_root)
    summary = payload["aggregate_balance_summary"]
    print(
        "storyteller balance acceptance: ok "
        f"(curated_nodes={payload['curated_node_count']}, "
        f"full_game_nodes={payload['full_game_node_count']}, "
        f"night_info={summary['night_info_judgement_count']}, "
        f"suppressed={summary['suppressed_info_count']}, "
        f"distorted={summary['distorted_info_count']}, "
        f"legacy_fallback={summary['legacy_fallback_count']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
