"""Alpha 0.3 aggregate acceptance runner."""

from __future__ import annotations

import subprocess
from pathlib import Path


def run_command(*args: str) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    python = repo_root / ".venv" / "Scripts" / "python.exe"
    result = subprocess.run(
        [str(python), *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout)
    print(result.stdout.strip())


def main() -> int:
    run_command("scripts/a3_data_acceptance.py")
    run_command("scripts/a3_memory_acceptance.py")
    run_command("scripts/storyteller_acceptance.py")
    print("alpha3 acceptance: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
