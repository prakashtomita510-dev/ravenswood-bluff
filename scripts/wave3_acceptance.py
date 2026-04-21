"""Wave 3 aggregate acceptance runner."""

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


def main() -> int:
    run_script("long_loop_memory_acceptance.py")
    run_script("long_game_ai_acceptance.py")
    run_script("player_knowledge_acceptance.py")
    run_script("persona_divergence_test.py")
    run_script("ai_eval_acceptance.py")
    print("wave3 acceptance: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
