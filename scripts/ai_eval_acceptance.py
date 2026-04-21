"""Wave 3 AI intelligence evaluation acceptance runner."""

from __future__ import annotations

import subprocess
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    python = repo_root / ".venv" / "Scripts" / "python.exe"
    result = subprocess.run(
        [
            str(python),
            "-m",
            "pytest",
            "tests/test_agents/test_ai_persona.py",
            "tests/test_agents/test_agent_reasoning.py",
            "-q",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout)
    eval_result = subprocess.run(
        [str(python), str(repo_root / "scripts" / "ai_evaluation.py")],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if eval_result.returncode != 0:
        raise SystemExit(eval_result.stderr or eval_result.stdout)
    print("ai eval acceptance: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
