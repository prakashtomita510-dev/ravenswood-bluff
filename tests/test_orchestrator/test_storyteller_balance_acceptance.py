from __future__ import annotations

import subprocess
from pathlib import Path


def test_storyteller_balance_acceptance_script_runs() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            str(repo_root / ".venv" / "Scripts" / "python.exe"),
            str(repo_root / "scripts" / "storyteller_balance_acceptance.py"),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "storyteller balance acceptance: ok" in result.stdout
    assert "night_info=" in result.stdout
    assert "suppressed=" in result.stdout
    assert "distorted=" in result.stdout
    assert "legacy_fallback=" in result.stdout
