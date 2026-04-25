"""
对局数据收集器 (Game Data Collector)

负责收集并持久化对局中的 AI 思维链、决策轨迹和环境快照，用于后续分析和训练。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class GameDataCollector:
    """
    负责收集对局数据并写入本地存储。
    """

    def __init__(self, base_dir: str = "data/sessions") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.current_game_id: str | None = None
        self._log_file: Path | None = None

    def start_game(self, game_id: str) -> None:
        """开始新对局的数据记录"""
        self.current_game_id = game_id
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._log_file = self.base_dir / f"{game_id}_{timestamp}.jsonl"
        logger.info(f"Data collection started for game {game_id}, saving to {self._log_file}")

    def record_thought_trace(
        self,
        player_id: str,
        role_id: str,
        phase: str,
        round_number: int,
        thought: str,
        action: dict[str, Any],
        context: dict[str, Any]
    ) -> None:
        """记录一条 AI 的思维和决策轨迹"""
        if not self._log_file:
            return

        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "thought_trace",
            "game_id": self.current_game_id,
            "player_id": player_id,
            "role_id": role_id,
            "phase": phase,
            "round": round_number,
            "round_number": round_number,
            "thought": thought,
            "action": action,
            "context_summary": context,
        }

        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write thought trace: {e}")

    def record_snapshot(self, snapshot: dict[str, Any]) -> None:
        """记录全场快照。

        最小约定：
        - 顶层至少包含 phase/day_number/round_number
        - 用 summary 承载轻量摘要，避免把完整状态直接落盘
        """
        if not self._log_file:
            return
            
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "snapshot",
            "game_id": self.current_game_id,
            "data": snapshot
        }
        
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write snapshot: {e}")

    @classmethod
    @staticmethod
    def _normalize_trace_entry(raw_entry: dict[str, Any]) -> dict[str, Any]:
        """将 jsonl 原始记录转换为稳定导出结构。"""
        record_type = raw_entry.get("type") or "thought_trace"
        if record_type == "snapshot":
            snapshot = raw_entry.get("data") or {}
            summary = snapshot.get("summary") or {}
            return {
                "record_type": "snapshot",
                "timestamp": raw_entry.get("timestamp"),
                "game_id": raw_entry.get("game_id"),
                "phase": snapshot.get("phase"),
                "day_number": snapshot.get("day_number"),
                "round_number": snapshot.get("round_number"),
                "stage": snapshot.get("stage"),
                "summary": summary,
                "retrieval_summary": summary.get("retrieval_summary") or {},
                "raw": snapshot,
            }

        return {
            "record_type": "thought_trace",
            "timestamp": raw_entry.get("timestamp"),
            "game_id": raw_entry.get("game_id"),
            "player_id": raw_entry.get("player_id"),
            "role_id": raw_entry.get("role_id"),
            "phase": raw_entry.get("phase"),
            "day_number": raw_entry.get("day_number"),
            "round_number": raw_entry.get("round_number", raw_entry.get("round")),
            "thought": raw_entry.get("thought"),
            "action": raw_entry.get("action") or {},
            "context_summary": raw_entry.get("context_summary") or {},
            "raw": raw_entry,
        }

    @classmethod
    def export_ai_traces(cls, game_id: str, base_dir: str = "data/sessions") -> dict[str, Any]:
        """
        [A3-DATA-4] 按 game_id 导出 AI 的行为轨迹。
        会扫描 base_dir 下对应 game_id 的 jsonl 文件并返回统一导出结构。
        """
        dir_path = Path(base_dir)
        if not dir_path.exists():
            return {
                "version": "a3-data-export-v1",
                "game_id": game_id,
                "entries": [],
                "files": [],
                "stats": {
                    "file_count": 0,
                    "entry_count": 0,
                    "thought_trace_count": 0,
                    "snapshot_count": 0,
                    "parse_error_count": 0,
                },
            }

        normalized_entries: list[dict[str, Any]] = []
        file_paths = sorted(dir_path.glob(f"{game_id}_*.jsonl"))
        parse_error_count = 0
        for file_path in file_paths:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        normalized_entries.append(
                            cls._normalize_trace_entry(json.loads(line))
                        )
                    except Exception as e:
                        parse_error_count += 1
                        logger.warning(f"Error parsing trace line in {file_path}: {e}")

        normalized_entries.sort(
            key=lambda entry: (
                entry.get("timestamp") or "",
                entry.get("round_number") or -1,
                entry.get("record_type") or "",
            )
        )

        thought_trace_count = sum(
            1 for entry in normalized_entries if entry["record_type"] == "thought_trace"
        )
        snapshot_count = sum(
            1 for entry in normalized_entries if entry["record_type"] == "snapshot"
        )
        snapshot_stage_counts: dict[str, int] = {}
        retrieval_snapshot_count = 0
        degraded_retrieval_snapshot_count = 0
        embeddings_disabled_snapshot_count = 0
        for entry in normalized_entries:
            if entry["record_type"] != "snapshot":
                continue
            stage = entry.get("stage")
            if stage:
                snapshot_stage_counts[stage] = snapshot_stage_counts.get(stage, 0) + 1
            retrieval_summary = entry.get("retrieval_summary") or {}
            if retrieval_summary:
                retrieval_snapshot_count += 1
                for player_summary in retrieval_summary.values():
                    if not isinstance(player_summary, dict):
                        continue
                    if player_summary.get("status") == "degraded":
                        degraded_retrieval_snapshot_count += 1
                    if player_summary.get("embeddings_enabled") is False:
                        embeddings_disabled_snapshot_count += 1
        return {
            "version": "a3-data-export-v1",
            "game_id": game_id,
            "files": [str(path) for path in file_paths],
            "entries": normalized_entries,
            "stats": {
                "file_count": len(file_paths),
                "entry_count": len(normalized_entries),
                "thought_trace_count": thought_trace_count,
                "snapshot_count": snapshot_count,
                "parse_error_count": parse_error_count,
                "snapshot_stage_counts": snapshot_stage_counts,
                "retrieval_snapshot_count": retrieval_snapshot_count,
                "degraded_retrieval_snapshot_count": degraded_retrieval_snapshot_count,
                "embeddings_disabled_snapshot_count": embeddings_disabled_snapshot_count,
            },
        }
