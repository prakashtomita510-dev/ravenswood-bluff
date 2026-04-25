from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.engine.data_collector import GameDataCollector
from src.state.game_record import GameRecordStore


async def _run(game_id: str, db_path: str, sessions_dir: str) -> dict:
    store = GameRecordStore(db_path)
    try:
        payload = await store.export_game_assets(game_id, storyteller_agent=None)
        if payload is None:
            return {"status": "error", "message": f"Game not found: {game_id}"}
        payload["ai_traces"] = GameDataCollector.export_ai_traces(game_id, base_dir=sessions_dir)
        return {"status": "ok", **payload}
    finally:
        await store.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Export game history + AI traces + storyteller judgements")
    parser.add_argument("game_id", help="Target game_id")
    parser.add_argument("--db-path", default="data/games.db", help="Game record database path")
    parser.add_argument("--sessions-dir", default="data/sessions", help="AI trace directory")
    args = parser.parse_args()

    payload = asyncio.run(_run(args.game_id, args.db_path, args.sessions_dir))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
