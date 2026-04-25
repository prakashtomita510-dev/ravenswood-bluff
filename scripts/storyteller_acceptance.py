"""Alpha 0.3 storyteller acceptance runner."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run(repo_root: Path, args: list[str]) -> None:
    result = subprocess.run(
        [str(repo_root / ".venv" / "Scripts" / "python.exe"), *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    _run(
        repo_root,
        [
            "-m",
            "pytest",
            "tests/test_agents/test_storyteller_export.py",
            "tests/test_state/test_game_record.py",
            "tests/test_orchestrator/test_gameover_ui.py",
            "tests/test_orchestrator/test_storyteller_gameover_ui.py",
            "-k",
            (
                "normalizes_standard_fields "
                "or embeds_decision_context "
                "or exports_history_detail_with_storyteller_judgements "
                "or history_overlay_contract_is_wired "
                "or storyteller_console_fetches_settlement_and_history_contracts"
            ),
            "-q",
        ],
    )
    _run(
        repo_root,
        [
            str(repo_root / "scripts" / "storyteller_balance_acceptance.py"),
        ],
    )
    print("storyteller acceptance: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
