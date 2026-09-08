#!/usr/bin/env python3
"""Documentation health gate for the ``docs/`` corpus.

Checks every Markdown file under the docs root (recursively), except the
directories / files explicitly EXEMPT:

  1. Frontmatter presence and completeness (required fields).
  2. Controlled vocabulary for ``role`` / ``category`` / ``status``
     (per ``.codebuddy/skills/doc-governance``).
  3. Internal links: dead relative links are HARD failures; absolute /
     non-portable link targets are WARNINGS (use ``--strict`` to fail on
     them too).
  4. Index registration: documents not referenced anywhere in
     ``docs/README.md`` ("ghost documents") are HARD failures.
  5. Document size: files over ``MAX_DOC_LINES`` (500) lines are WARNINGS;
     ``--strict`` escalates them to failures.

Exits non-zero when any HARD violation is found, so it can gate CI.

Usage:
    python scripts/check_doc_health.py [--root PATH] [--strict]
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# --- Controlled vocabulary (from .codebuddy/skills/doc-governance) ----------
REQUIRED_FM = ["doc_id", "title", "category", "role", "status", "date", "author"]
VALID_ROLES = {"[State]", "[Delta]", "[Cold]"}
VALID_CATEGORIES = {
    "architecture",
    "planning",
    "review",
    "release",
    "report",
    "reference",
    "api",
    "template",
    "spec",
}
VALID_STATUS = {"draft", "review", "published", "archived", "superseded"}

# Directories (relative to docs root) whose contents are auto-generated
# (e.g. acceptance evidence) and exempt from frontmatter governance.
EXEMPT_DIRS = {"alpha-1.1-evidence"}

# Governance thresholds (doc-governance anti-patterns).
MAX_DOC_LINES = 500  # 巨型单文件: split or mark archived
INDEX_NAME = "README.md"  # corpus index every doc must be registered in

FRONTMATTER_RE = re.compile(r"^---\s*$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
ABS_TARGET_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|file://|//|/)")


def parse_frontmatter(text: str):
    """Return (fields dict, error str|None).

    ``fields`` maps frontmatter key -> raw value (quotes stripped).
    ``error`` is non-None when frontmatter is missing or malformed.
    """
    lines = text.splitlines()
    if not lines or not FRONTMATTER_RE.match(lines[0]):
        return {}, "missing frontmatter (file must start with '---')"
    fields: dict[str, str] = {}
    for i in range(1, len(lines)):
        line = lines[i]
        if FRONTMATTER_RE.match(line):
            return fields, None  # closing delimiter found
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            value = value[1:-1]
        if key:
            fields[key] = value
    return fields, "unterminated frontmatter (no closing '---')"


def check_frontmatter(path: Path, violations: list[str]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        violations.append(f"{path}:0 cannot decode as UTF-8")
        return
    fields, err = parse_frontmatter(text)
    if err:
        violations.append(f"{path}:1 {err}")
        return
    for key in REQUIRED_FM:
        if key not in fields or not fields[key]:
            violations.append(f"{path}:1 frontmatter missing required field '{key}'")
    role = fields.get("role")
    if role and role not in VALID_ROLES:
        violations.append(f"{path}:1 role '{role}' not in {sorted(VALID_ROLES)}")
    category = fields.get("category")
    if category and category not in VALID_CATEGORIES:
        violations.append(f"{path}:1 category '{category}' not in controlled vocabulary")
    status = fields.get("status")
    if status and status not in VALID_STATUS:
        violations.append(f"{path}:1 status '{status}' not in {sorted(VALID_STATUS)}")


def check_links(path: Path, violations: list[str], warnings: list[str], strict: bool) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return  # already reported by frontmatter check
    base = path.parent
    for m in LINK_RE.finditer(text):
        target = m.group(1).strip()
        if not target:
            continue
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        if target.startswith("#"):
            continue
        if ABS_TARGET_RE.match(target):
            msg = f"{path}:{text[: m.start()].count(chr(10)) + 1} absolute/non-portable link -> {target}"
            (violations if strict else warnings).append(msg)
            continue
        clean = target.split("#", 1)[0].split("?", 1)[0]
        if not clean:
            continue
        if not (base / clean).resolve().exists():
            line_no = text[: m.start()].count("\n") + 1
            violations.append(f"{path}:{line_no} dead link -> {target}")


def check_index_registration(
    root: Path, path: Path, index_text: str, violations: list[str]
) -> None:
    """Ghost-document check: every doc must be referenced in the index."""
    rel = path.relative_to(root).as_posix()
    if rel == INDEX_NAME:
        return
    if rel not in index_text:
        violations.append(f"{path}:1 ghost document - not registered in {INDEX_NAME} index")


def check_doc_size(
    path: Path, violations: list[str], warnings: list[str], strict: bool
) -> None:
    """Oversized-file check: > MAX_DOC_LINES lines is an anti-pattern."""
    try:
        lines = len(path.read_text(encoding="utf-8").splitlines())
    except (UnicodeDecodeError, OSError):
        return  # unreadable files are already reported elsewhere
    if lines <= MAX_DOC_LINES:
        return
    msg = (
        f"{path}:1 oversized document ({lines} lines > {MAX_DOC_LINES})"
        " - split it or mark status: archived"
    )
    (violations if strict else warnings).append(msg)


def iter_docs(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        if set(rel_dir.parts) & EXEMPT_DIRS:
            dirnames[:] = []
            continue
        for fn in filenames:
            if fn.lower().endswith(".md"):
                yield Path(dirpath) / fn


def main() -> int:
    parser = argparse.ArgumentParser(description="Check docs/ frontmatter and links.")
    default_root = Path(__file__).resolve().parent.parent / "docs"
    parser.add_argument(
        "--root", type=Path, default=default_root, help="docs corpus root (default: <repo>/docs)"
    )
    parser.add_argument(
        "--strict", action="store_true", help="also fail on absolute/non-portable link targets"
    )
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        print(f"ERROR: docs root not found: {root}", file=sys.stderr)
        return 2

    index_path = root / INDEX_NAME
    index_text = ""
    if index_path.is_file():
        try:
            index_text = index_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"WARNING: cannot decode index {index_path}", file=sys.stderr)
    else:
        print(f"WARNING: index {index_path} not found - skipping ghost check", file=sys.stderr)

    violations: list[str] = []
    warnings: list[str] = []
    scanned = 0
    for path in iter_docs(root):
        scanned += 1
        check_frontmatter(path, violations)
        check_links(path, violations, warnings, args.strict)
        if index_text:
            check_index_registration(root, path, index_text, violations)
        check_doc_size(path, violations, warnings, args.strict)

    print(f"Scanned {scanned} markdown file(s) under {root}")
    if warnings:
        print(f"\n{len(warnings)} warning(s) (non-portable links / oversized documents):")
        for w in warnings:
            print(f"  ! {w}")
    if violations:
        print(f"\nFound {len(violations)} violation(s):\n")
        for v in violations:
            print(f"  - {v}")
        print("\nDoc health check FAILED.")
        return 1
    print("Doc health check PASSED (frontmatter complete, links valid, index registered).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
