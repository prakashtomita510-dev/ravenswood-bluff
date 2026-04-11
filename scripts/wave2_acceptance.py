"""Wave 2 aggregate acceptance runner."""

from __future__ import annotations

import subprocess
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
    run_script("storyteller_acceptance.py")
    run_script("storyteller_balance_acceptance.py")
    run_script("role_acceptance.py")
    print("wave2 acceptance: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
