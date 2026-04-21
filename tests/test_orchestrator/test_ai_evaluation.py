from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_ai_evaluation_script_runs_and_reports_metrics():
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [str(repo_root / ".venv" / "Scripts" / "python.exe"), "scripts/ai_evaluation.py"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines[-1] == "ai evaluation: ok"
    payload = json.loads("\n".join(lines[:-1]))
    assert payload["game_count"] >= 3
    assert payload["rounds_per_game"] >= 3
    assert payload["records_total"] >= payload["game_count"] * payload["rounds_per_game"]
    assert payload["ai_none_nomination_rate"] >= 0.3
    assert payload["ai_strong_nomination_rate"] >= 0.45
    assert payload["nomination_trend_monotonicity_rate"] >= 0.6
    assert payload["vote_trend_monotonicity_rate"] >= 0.6
    assert payload["persona_diversity_score"] >= 0.4
    assert payload["multi_game_stability_score"] >= 0.4
    assert payload["front_position_nomination_bias_rate"] <= 0.8
    assert payload["ambiguous_nomination_diversity_score"] >= 0.5
    assert payload["aggressive_vote_push_rate"] >= 0.65
    assert payload["silent_vote_restraint_rate"] >= 0.8
    assert payload["cooperative_follow_rate"] >= 0.75
    assert set(payload["level_breakdown"]["nomination"]) == {"weak", "medium", "strong"}
    assert set(payload["level_breakdown"]["vote"]) == {"weak", "medium", "strong"}
    assert "target_counts" in payload["ambiguous_nomination"]
    assert set(payload["archetype_vote_profiles"]) == {"logic", "aggressive", "cooperative", "chaos", "silent"}
