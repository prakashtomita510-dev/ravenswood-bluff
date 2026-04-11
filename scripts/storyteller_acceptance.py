"""Wave 2 storyteller consistency acceptance runner."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            str(repo_root / ".venv" / "Scripts" / "python.exe"),
            "-m",
            "pytest",
            "tests/test_orchestrator/test_storyteller_judgement_logging.py",
            "-q",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout)
    print("storyteller acceptance: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
