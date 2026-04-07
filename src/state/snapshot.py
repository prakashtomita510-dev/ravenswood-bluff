"""
状态快照与回放

支持游戏状态的快照保存和历史回放。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.state.game_state import GameState


class StateSnapshot(BaseModel):
    """状态快照"""
    snapshot_id: int
    timestamp: datetime = Field(default_factory=datetime.now)
    game_state: GameState
    description: str = ""    # 快照描述（如 "第2天 白天讨论开始"）


class SnapshotManager:
    """
    快照管理器

    在每个关键状态变更点保存快照，支持回放。
    """

    def __init__(self) -> None:
        self._snapshots: list[StateSnapshot] = []
        self._counter: int = 0

    def take_snapshot(self, game_state: GameState, description: str = "") -> StateSnapshot:
        """保存当前状态快照"""
        snapshot = StateSnapshot(
            snapshot_id=self._counter,
            game_state=game_state,
            description=description,
        )
        self._snapshots.append(snapshot)
        self._counter += 1
        return snapshot

    def get_snapshot(self, snapshot_id: int) -> Optional[StateSnapshot]:
        """根据 ID 获取快照"""
        for s in self._snapshots:
            if s.snapshot_id == snapshot_id:
                return s
        return None

    def get_latest(self) -> Optional[StateSnapshot]:
        """获取最新快照"""
        return self._snapshots[-1] if self._snapshots else None

    @property
    def snapshots(self) -> list[StateSnapshot]:
        """获取所有快照"""
        return list(self._snapshots)

    @property
    def count(self) -> int:
        return len(self._snapshots)

    def export_to_json(self) -> str:
        """导出所有快照为 JSON（用于保存游戏记录）"""
        data = [s.model_dump(mode="json") for s in self._snapshots]
        return json.dumps(data, ensure_ascii=False, indent=2)

    def __repr__(self) -> str:
        return f"SnapshotManager(snapshots={self.count})"
