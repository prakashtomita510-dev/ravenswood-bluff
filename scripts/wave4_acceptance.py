"""Wave 4 aggregate acceptance runner."""

from __future__ import annotations

import subprocess
from pathlib import Path


def run_script(script_name: str) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    python = repo_root / ".venv" / "Scripts" / "python.exe"
    result = subprocess.run(
        [str(python), str(repo_root / "scripts" / script_name)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout)
    print(result.stdout.strip())


def run_pytest(test_path: str) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    python = repo_root / ".venv" / "Scripts" / "python.exe"
    result = subprocess.run(
        [str(python), "-m", "pytest", test_path, "-q"],
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
    run_script("gameover_acceptance.py")
    run_pytest("tests/test_orchestrator/test_storyteller_gameover_ui.py")
    print("wave4 acceptance: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
