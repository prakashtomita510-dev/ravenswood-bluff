"""
游戏记录持久化 (Game Record Store)

使用 SQLite 存储完整的对局记录，支持历史查询和复盘。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import shutil
import sqlite3
from datetime import datetime
from typing import Any, Optional

import aiosqlite

from src.state.game_state import GameState

logger = logging.getLogger(__name__)

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS game_records (
    game_id        TEXT PRIMARY KEY,
    started_at     TEXT NOT NULL,
    ended_at       TEXT NOT NULL,
    winning_team   TEXT NOT NULL,
    victory_reason TEXT,
    player_count   INTEGER NOT NULL,
    round_count    INTEGER NOT NULL,
    script_id      TEXT DEFAULT 'trouble_brewing',
    settlement     TEXT NOT NULL,
    config         TEXT
);

CREATE TABLE IF NOT EXISTS game_players (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id           TEXT NOT NULL REFERENCES game_records(game_id),
    player_id         TEXT NOT NULL,
    player_name       TEXT NOT NULL,
    true_role_id      TEXT NOT NULL,
    perceived_role_id TEXT,
    team              TEXT NOT NULL,
    is_alive          INTEGER NOT NULL DEFAULT 1,
    is_human          INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_game_players_game_id ON game_players(game_id);
CREATE INDEX IF NOT EXISTS idx_game_records_ended_at ON game_records(ended_at);
"""


class GameRecordStore:
    """SQLite 游戏记录存储"""

    _memory_keeper_connections: dict[str, aiosqlite.Connection] = {}
    _initialized_paths: set[str] = set()
    _path_locks: dict[str, asyncio.Lock] = {}

    def __init__(self, db_path: str = "data/games.db") -> None:
        self.db_path = db_path
        self._initialized = False
        self._storage_mode = "sqlite"

    @property
    def _use_uri(self) -> bool:
        return self.db_path.startswith("file:")

    @property
    def _use_shared_memory(self) -> bool:
        return self._use_uri and "mode=memory" in self.db_path

    def _connect(self):
        return aiosqlite.connect(self.db_path, uri=self._use_uri)

    @property
    def _json_fallback_path(self) -> Path:
        return Path(self.db_path).with_suffix(".records.json")

    @property
    def _path_key(self) -> str:
        return self.db_path

    def _get_path_lock(self) -> asyncio.Lock:
        lock = self._path_locks.get(self._path_key)
        if lock is None:
            lock = asyncio.Lock()
            self._path_locks[self._path_key] = lock
        return lock

    def _using_json_fallback(self) -> bool:
        return not self._use_uri and (
            self._storage_mode == "json" or self._json_fallback_path.exists()
        )

    def _build_record_payload(
        self,
        game_id: str,
        state: GameState,
        settlement: dict[str, Any],
    ) -> dict[str, Any]:
        winning_team = settlement.get("winning_team", "unknown")
        victory_reason = settlement.get("victory_reason", "")
        player_count = len(state.players)
        round_count = state.round_number
        script_id = state.config.script_id if state.config else "trouble_brewing"
        config_payload = state.config.model_dump(mode="json") if state.config else {}

        started_at = datetime.now().isoformat()
        if state.event_log:
            first_event = state.event_log[0]
            started_at = first_event.timestamp.isoformat()
        ended_at = datetime.now().isoformat()

        human_player_ids = set()
        if state.config and state.config.human_player_ids:
            human_player_ids = set(state.config.human_player_ids)

        players = []
        for player in state.players:
            players.append(
                {
                    "game_id": game_id,
                    "player_id": player.player_id,
                    "player_name": player.name,
                    "true_role_id": player.true_role_id or player.role_id,
                    "perceived_role_id": player.perceived_role_id,
                    "team": (player.current_team or player.team).value,
                    "is_alive": 1 if player.is_alive else 0,
                    "is_human": 1 if player.player_id in human_player_ids else 0,
                }
            )

        return {
            "game_id": game_id,
            "started_at": started_at,
            "ended_at": ended_at,
            "winning_team": winning_team,
            "victory_reason": victory_reason,
            "player_count": player_count,
            "round_count": round_count,
            "script_id": script_id,
            "settlement": settlement,
            "config": config_payload,
            "players": players,
        }

    def _load_json_records(self) -> dict[str, Any]:
        if not self._json_fallback_path.exists():
            return {"games": {}}
        return json.loads(self._json_fallback_path.read_text(encoding="utf-8"))

    def _save_json_records(self, payload: dict[str, Any]) -> None:
        self._json_fallback_path.parent.mkdir(parents=True, exist_ok=True)
        self._json_fallback_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def _initialize_json_fallback(self) -> None:
        self._storage_mode = "json"
        if not self._json_fallback_path.exists():
            self._save_json_records({"games": {}})
        logger.warning("GameRecordStore switched to JSON fallback: %s", self._json_fallback_path)

    async def _ensure_schema(self) -> None:
        async with self._connect() as db:
            await db.executescript(_CREATE_TABLES_SQL)
            await db.commit()

    def _file_sidecars(self) -> list[Path]:
        db_file = Path(self.db_path)
        return [
            db_file,
            Path(f"{self.db_path}-journal"),
            Path(f"{self.db_path}-wal"),
            Path(f"{self.db_path}-shm"),
        ]

    def _should_backup_primary_db(self, db_file: Path) -> bool:
        if not db_file.exists():
            return False
        try:
            conn = sqlite3.connect(db_file)
            try:
                tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            finally:
                conn.close()
            return not tables
        except sqlite3.DatabaseError:
            return True

    async def _move_path_with_retries(self, source: Path, backup: Path) -> None:
        last_error: PermissionError | None = None
        for attempt in range(5):
            try:
                shutil.move(str(source), str(backup))
                logger.warning("Recovered damaged game record file: %s -> %s", source, backup)
                return
            except PermissionError as exc:
                last_error = exc
                await asyncio.sleep(0.1 * (attempt + 1))
        if last_error:
            raise last_error

    async def _recover_disk_store(self, *, include_primary_db: bool) -> None:
        """在文件数据库出现 disk I/O error 时，备份损坏文件并重建。"""
        db_file = Path(self.db_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        should_backup_db = include_primary_db and self._should_backup_primary_db(db_file)

        for path in self._file_sidecars():
            if not path.exists():
                continue
            if path == db_file and not should_backup_db:
                continue
            backup = path.with_name(f"{path.name}.corrupt_{timestamp}")
            await self._move_path_with_retries(path, backup)

    async def close(self) -> None:
        """关闭当前 store 持有的共享内存 keeper 连接。"""
        if self._use_shared_memory:
            keeper = self._memory_keeper_connections.pop(self.db_path, None)
            if keeper is not None:
                await keeper.close()
            self._initialized_paths.discard(self._path_key)
        self._initialized = False
        if not self._use_uri and self._json_fallback_path.exists():
            self._storage_mode = "json"

    async def initialize(self) -> None:
        """创建数据库目录和表结构"""
        if self._using_json_fallback():
            self._initialize_json_fallback()
            self._initialized_paths.add(self._path_key)
            self._initialized = True
            return
        if self._initialized or self._path_key in self._initialized_paths:
            self._initialized = True
            return
        async with self._get_path_lock():
            if self._initialized or self._path_key in self._initialized_paths:
                self._initialized = True
                return
            if not self._use_uri:
                os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
            if self._use_shared_memory and self.db_path not in self._memory_keeper_connections:
                keeper = await aiosqlite.connect(self.db_path, uri=True)
                self._memory_keeper_connections[self.db_path] = keeper
            try:
                await self._ensure_schema()
            except aiosqlite.OperationalError as exc:
                if self._use_uri or "disk i/o error" not in str(exc).lower():
                    raise
                logger.warning(
                    "GameRecordStore initialize hit disk I/O error for %s; attempting sidecar recovery",
                    self.db_path,
                )
                try:
                    await self._recover_disk_store(include_primary_db=False)
                    await self._ensure_schema()
                except (aiosqlite.OperationalError, PermissionError) as retry_exc:
                    if not isinstance(retry_exc, PermissionError) and "disk i/o error" not in str(retry_exc).lower():
                        raise
                    logger.warning(
                        "GameRecordStore initialize still failing for %s; attempting primary-db recovery",
                        self.db_path,
                    )
                    try:
                        await self._recover_disk_store(include_primary_db=True)
                        await self._ensure_schema()
                    except (aiosqlite.OperationalError, PermissionError) as final_exc:
                        if "disk i/o error" not in str(final_exc).lower() and not isinstance(final_exc, PermissionError):
                            raise
                        logger.warning(
                            "GameRecordStore initialize could not recover SQLite file at %s; falling back to JSON storage",
                            self.db_path,
                        )
                        self._initialize_json_fallback()
            self._initialized = True
            self._initialized_paths.add(self._path_key)
            logger.info("GameRecordStore initialized: %s", self.db_path)

    async def save_game(
        self,
        game_id: str,
        state: GameState,
        settlement: dict[str, Any],
    ) -> None:
        """保存完整的对局记录"""
        await self.initialize()

        record = self._build_record_payload(game_id, state, settlement)

        if self._using_json_fallback():
            payload = self._load_json_records()
            payload.setdefault("games", {})[game_id] = record
            self._save_json_records(payload)
            logger.info(
                "Game record saved via JSON fallback: game_id=%s winner=%s rounds=%d",
                game_id,
                record["winning_team"],
                record["round_count"],
            )
            return

        async with self._connect() as db:
            await db.execute(
                """INSERT OR REPLACE INTO game_records
                   (game_id, started_at, ended_at, winning_team, victory_reason,
                    player_count, round_count, script_id, settlement, config)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record["game_id"],
                    record["started_at"],
                    record["ended_at"],
                    record["winning_team"],
                    record["victory_reason"],
                    record["player_count"],
                    record["round_count"],
                    record["script_id"],
                    json.dumps(record["settlement"], ensure_ascii=False, default=str),
                    json.dumps(record["config"], ensure_ascii=False, default=str),
                ),
            )

            # 删除旧的玩家记录（以支持 REPLACE 语义）
            await db.execute("DELETE FROM game_players WHERE game_id = ?", (game_id,))

            for player in record["players"]:
                await db.execute(
                    """INSERT INTO game_players
                       (game_id, player_id, player_name, true_role_id,
                        perceived_role_id, team, is_alive, is_human)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        player["game_id"],
                        player["player_id"],
                        player["player_name"],
                        player["true_role_id"],
                        player["perceived_role_id"],
                        player["team"],
                        player["is_alive"],
                        player["is_human"],
                    ),
                )

            await db.commit()

        logger.info(
            "Game record saved: game_id=%s winner=%s rounds=%d",
            game_id,
            record["winning_team"],
            record["round_count"],
        )

    async def get_game(self, game_id: str) -> Optional[dict[str, Any]]:
        """获取单局记录"""
        await self.initialize()
        if self._using_json_fallback():
            return self._load_json_records().get("games", {}).get(game_id)
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM game_records WHERE game_id = ?", (game_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return None

            record = dict(row)
            record["settlement"] = json.loads(record["settlement"])
            record["config"] = json.loads(record["config"]) if record["config"] else {}

            # 获取玩家列表
            cursor2 = await db.execute(
                "SELECT * FROM game_players WHERE game_id = ?", (game_id,)
            )
            players = [dict(r) for r in await cursor2.fetchall()]
            record["players"] = players

        return record

    async def export_game_history(self, game_id: str) -> Optional[dict[str, Any]]:
        """[A3-DATA-4] 导出完整对局历史数据（提供统一的导出接口命名）。"""
        return await self.get_game(game_id)

    async def export_storyteller_judgements(self, game_id: str, storyteller_agent: Any) -> Optional[dict[str, Any]]:
        """[A3-DATA-4] 导出与 game_id 对齐的说书人判决数据。"""
        history = await self.get_game(game_id)
        if history is None:
            return None
        if storyteller_agent is None:
            settlement = history.get("settlement", {}) if isinstance(history, dict) else {}
            summary = settlement.get("judgement_summary", []) if isinstance(settlement, dict) else []
            return {
                "game_id": game_id,
                "judgement_count": len(summary),
                "categories": sorted(
                    {str(item.get("category", "")) for item in summary if isinstance(item, dict) and item.get("category")}
                ),
                "buckets": [],
                "judgements": [],
                "recent_summary": list(summary),
            }
        if hasattr(storyteller_agent, "export_judgement_history"):
            return storyteller_agent.export_judgement_history(game_id)
        exported = storyteller_agent.export_judgements() if hasattr(storyteller_agent, "export_judgements") else []
        return {
            "game_id": game_id,
            "judgement_count": len(exported),
            "categories": sorted({str(item.get("category", "")) for item in exported if item.get("category")}),
            "buckets": sorted({str(item.get("bucket", "")) for item in exported if item.get("bucket")}),
            "judgements": [{"game_id": game_id, **item} for item in exported],
            "recent_summary": [],
        }

    async def export_game_assets(self, game_id: str, storyteller_agent: Any | None = None) -> Optional[dict[str, Any]]:
        """[A3-DATA-4] 最小统一导出接口：按 game_id 汇总对局历史与说书人判决。"""
        game_history = await self.export_game_history(game_id)
        if game_history is None:
            return None
        storyteller_judgements = await self.export_storyteller_judgements(game_id, storyteller_agent)
        return {
            "game_id": game_id,
            "game_history": game_history,
            "storyteller_judgements": storyteller_judgements,
        }

    async def export_history_detail(self, game_id: str, storyteller_agent: Any | None = None) -> Optional[dict[str, Any]]:
        """[A3-ST-4] 历史详情统一资产：结算详情 + 说书人裁量摘要。"""
        assets = await self.export_game_assets(game_id, storyteller_agent=storyteller_agent)
        if assets is None:
            return None
        game_history = assets["game_history"]
        storyteller_judgements = assets["storyteller_judgements"]
        return {
            **game_history,
            "storyteller_judgements": storyteller_judgements,
        }

    async def list_games(
        self, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        """分页获取历史对局列表（不含完整 settlement JSON）"""
        await self.initialize()
        if self._using_json_fallback():
            games = list(self._load_json_records().get("games", {}).values())
            games.sort(key=lambda item: item.get("ended_at", ""), reverse=True)
            sliced = games[offset : offset + limit]
            return [
                {
                    "game_id": item["game_id"],
                    "started_at": item["started_at"],
                    "ended_at": item["ended_at"],
                    "winning_team": item["winning_team"],
                    "victory_reason": item["victory_reason"],
                    "player_count": item["player_count"],
                    "round_count": item["round_count"],
                    "script_id": item["script_id"],
                }
                for item in sliced
            ]
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT game_id, started_at, ended_at, winning_team,
                          victory_reason, player_count, round_count, script_id
                   FROM game_records
                   ORDER BY ended_at DESC
                   LIMIT ? OFFSET ?""",
                (limit, offset),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_player_history(self, player_name: str) -> list[dict[str, Any]]:
        """按玩家名查询参与过的对局历史"""
        await self.initialize()
        if self._using_json_fallback():
            records = []
            for game in self._load_json_records().get("games", {}).values():
                for player in game.get("players", []):
                    if player.get("player_name") == player_name:
                        records.append(
                            {
                                "game_id": game["game_id"],
                                "started_at": game["started_at"],
                                "ended_at": game["ended_at"],
                                "winning_team": game["winning_team"],
                                "victory_reason": game["victory_reason"],
                                "player_count": game["player_count"],
                                "round_count": game["round_count"],
                                "script_id": game["script_id"],
                                **player,
                            }
                        )
            records.sort(key=lambda item: item.get("ended_at", ""), reverse=True)
            return records
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT
                    gr.game_id,
                    gr.started_at,
                    gr.ended_at,
                    gr.winning_team,
                    gr.victory_reason,
                    gr.player_count,
                    gr.round_count,
                    gr.script_id,
                    gp.player_id,
                    gp.player_name,
                    gp.true_role_id,
                    gp.perceived_role_id,
                    gp.team,
                    gp.is_alive,
                    gp.is_human
                FROM game_players gp
                JOIN game_records gr ON gr.game_id = gp.game_id
                WHERE gp.player_name = ?
                ORDER BY gr.ended_at DESC
                """,
                (player_name,),
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
