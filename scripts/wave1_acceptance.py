"""Aggregated Wave 1 backend acceptance runner."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_script(script_name: str) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [str(repo_root / ".venv" / "Scripts" / "python.exe"), str(repo_root / "scripts" / script_name)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout)
    print(result.stdout.strip())


def main() -> int:
    run_script("frontend_acceptance.py")
    run_script("nomination_acceptance.py")
    run_script("night_info_acceptance.py")
    print("wave1 acceptance: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
