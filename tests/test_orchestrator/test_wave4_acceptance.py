from __future__ import annotations

import subprocess
from pathlib import Path


def test_wave4_acceptance_script_runs_cleanly():
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [str(repo_root / ".venv" / "Scripts" / "python.exe"), "scripts/wave4_acceptance.py"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "wave4 acceptance: ok" in result.stdout
