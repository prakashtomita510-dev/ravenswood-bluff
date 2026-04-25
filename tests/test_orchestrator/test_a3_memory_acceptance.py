from __future__ import annotations

import subprocess
from pathlib import Path


def test_a3_memory_acceptance_script_passes():
    repo_root = Path(__file__).resolve().parents[2]
    python = repo_root / ".venv" / "Scripts" / "python.exe"
    result = subprocess.run(
        [str(python), "scripts/a3_memory_acceptance.py"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "a3 memory acceptance: ok" in result.stdout
