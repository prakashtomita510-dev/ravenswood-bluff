"""Wave 2 role consistency acceptance runner."""

from __future__ import annotations

import subprocess
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            str(repo_root / ".venv" / "Scripts" / "python.exe"),
            "-m",
            "pytest",
            "tests/test_engine/test_high_risk_roles.py",
            "tests/test_engine/test_role_skill_audit.py",
            "-q",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout)
    print("role acceptance: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
