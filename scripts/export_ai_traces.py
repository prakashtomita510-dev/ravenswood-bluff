from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.engine.data_collector import GameDataCollector


def main() -> int:
    parser = argparse.ArgumentParser(description="Export AI traces for a game_id")
    parser.add_argument("game_id", help="Target game_id")
    parser.add_argument("--base-dir", default="data/sessions", help="Trace storage directory")
    args = parser.parse_args()

    payload = GameDataCollector.export_ai_traces(args.game_id, base_dir=args.base_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
