from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_long_loop_memory_acceptance_script_runs_and_reports_accumulation():
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [str(repo_root / ".venv" / "Scripts" / "python.exe"), "scripts/long_loop_memory_acceptance.py"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines[-1] == "long loop memory acceptance: ok"
    payload = json.loads("\n".join(lines[:-1]))
    assert payload["episode_count"] >= 5
    assert payload["episode_counts_progression"] == [1, 2, 3, 4, 5]
    assert payload["bob_trust_scores"][0] > payload["bob_trust_scores"][-1]
    assert payload["cathy_trust_scores"][0] < payload["cathy_trust_scores"][-1]
    assert payload["bob_notes_count"] >= 4
    assert payload["cathy_notes_count"] >= 4
    assert payload["working_memory_empty"] is True
    assert ">> 第1天 白天" in payload["episodic_summary"]
    assert ">> 第2天 白天" in payload["episodic_summary"]
