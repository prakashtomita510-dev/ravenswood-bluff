"""Alpha 0.3 / A3-MEM aggregate acceptance runner."""

from __future__ import annotations

import subprocess
from pathlib import Path


def run_pytest(*args: str) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    python = repo_root / ".venv" / "Scripts" / "python.exe"
    result = subprocess.run(
        [str(python), "-m", "pytest", *args, "-q"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout)
    print(result.stdout.strip())


def run_script(script_name: str) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    python = repo_root / ".venv" / "Scripts" / "python.exe"
    result = subprocess.run(
        [str(python), str(repo_root / "scripts" / script_name)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout)
    print(result.stdout.strip())


def main() -> int:
    run_pytest(
        "tests/test_agents/test_agent_reasoning.py::test_agent_does_not_turn_denial_into_role_claim",
        "tests/test_agents/test_agent_reasoning.py::test_high_confidence_private_info_survives_phase_archive_and_public_noise",
        "tests/test_agents/test_agent_reasoning.py::test_investigator_candidate_and_conflicting_public_claim_raise_suspicion",
    )
    run_script("long_loop_memory_acceptance.py")
    run_script("long_game_ai_acceptance.py")
    print("a3 memory acceptance: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
