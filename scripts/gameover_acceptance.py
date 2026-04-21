"""Wave 4-A game settlement and persistence acceptance runner."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    python = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    try:
        result = subprocess.run(
            [
                str(python),
                "-m",
                "pytest",
                "tests/test_state/test_game_record.py",
                "tests/test_orchestrator/test_gameover_api.py",
                "tests/test_orchestrator/test_gameover_ui.py",
                "-q",
            ],
            cwd=REPO_ROOT,
            text=True,
            check=False,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(f"gameover acceptance timed out after {exc.timeout}s")
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout or "gameover acceptance failed")
    print("gameover acceptance: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
