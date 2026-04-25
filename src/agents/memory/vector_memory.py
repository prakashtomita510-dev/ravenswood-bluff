"""
向量检索记忆 (Vector Memory)

利用向量数据库（此处使用 Faiss）存储长期的对局历史，支持语义检索。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

try:
    import numpy as np
except ImportError:
    np = None

try:
    import faiss
except ImportError:
    # 允许在没有 faiss 的环境下降级（虽然此环境中已有）
    faiss = None

from src.llm.base_backend import LLMBackend
from src.state.game_state import GameEvent, ChatMessage

logger = logging.getLogger(__name__)


class VectorMemory:
    """
    基于向量检索的长期记忆模块。
    """

    def __init__(self, backend: LLMBackend, dimension: int = 1536) -> None:
        self.backend = backend
        self.dimension = dimension
        self._last_query = ""
        self._last_hits_preview: list[str] = []
        
        # 初始化 Faiss 索引 (L2 距离)
        if faiss and np is not None:
            self.index = faiss.IndexFlatL2(dimension)
            self._local_disable_reason: Optional[str] = None
        else:
            self.index = None
            self._local_disable_reason = "missing_numpy_or_faiss"
            logger.warning("numpy/faiss-cpu is not installed, VectorMemory will be disabled.")
            
        # 存储原始数据和元数据
        self.metadata: list[dict[str, Any]] = []
        self._stats = {
            "enabled": bool(self.index),
            "indexed_items": 0,
            "text_ingests": 0,
            "event_ingests": 0,
            "message_ingests": 0,
            "search_count": 0,
            "search_hit_count": 0,
            "last_hit_count": 0,
        }

    def _get_runtime_status(self) -> tuple[str, Optional[str], bool]:
        """返回当前向量检索状态、原因与 embeddings 是否启用。"""
        if not self.index:
            return "disabled", self._local_disable_reason, False

        embeddings_disabled = bool(getattr(self.backend, "_embeddings_disabled", False))
        if embeddings_disabled:
            reason = getattr(self.backend, "_embeddings_disable_reason", None) or "embeddings_disabled"
            return "degraded", reason, False

        return "enabled", None, True

    async def add_text(self, text: str, metadata: dict[str, Any]) -> None:
        """将一段文本向量化并存入索引"""
        if not self.index:
            return
            
        try:
            embeddings = await self.backend.get_embeddings([text])
            if not embeddings:
                return
                
            vector = np.array(embeddings).astype('float32')
            self.index.add(vector)
            
            # 记录元数据
            self.metadata.append({
                "text": text,
                **metadata
            })
            self._stats["indexed_items"] = len(self.metadata)
            self._stats["text_ingests"] += 1
        except Exception as e:
            logger.error(f"Failed to add text to VectorMemory: {e}")

    async def add_event(self, event: GameEvent) -> None:
        """记录一个游戏事件"""
        content = f"事件: {event.event_type} | 参与者: {event.actor} | 目标: {event.target} | 详情: {event.payload}"
        self._stats["event_ingests"] += 1
        await self.add_text(content, {
            "type": "event",
            "event_type": event.event_type,
            "round": event.round_number,
            "phase": str(event.phase)
        })

    async def add_message(self, msg: ChatMessage) -> None:
        """记录一条聊天消息"""
        speaker = msg.speaker or "unknown"
        content = f"发言: {speaker} 说: \"{msg.content}\""
        self._stats["message_ingests"] += 1
        await self.add_text(content, {
            "type": "message",
            "speaker": speaker,
            "phase": str(msg.phase),
            "round": msg.round_number,
            "target_player": msg.target_player,
            "recipient_ids": list(msg.recipient_ids) if msg.recipient_ids else [],
            "tone": msg.tone,
        })

    async def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """执行语义搜索"""
        self._stats["search_count"] += 1
        self._last_query = query
        if not self.index or self.index.ntotal == 0:
            self._stats["last_hit_count"] = 0
            self._last_hits_preview = []
            return []
            
        try:
            query_embeddings = await self.backend.get_embeddings([query])
            if not query_embeddings:
                self._stats["last_hit_count"] = 0
                self._last_hits_preview = []
                return []
                
            query_vector = np.array(query_embeddings).astype('float32')
            distances, indices = self.index.search(query_vector, top_k)
            
            results = []
            for i, idx in enumerate(indices[0]):
                if idx != -1 and idx < len(self.metadata):
                    results.append(self.metadata[idx])
            self._stats["last_hit_count"] = len(results)
            self._stats["search_hit_count"] += len(results)
            self._last_hits_preview = [result.get("text", "") for result in results[:3]]
            return results
        except Exception as e:
            logger.error(f"VectorMemory search failed: {e}")
            self._stats["last_hit_count"] = 0
            self._last_hits_preview = []
            return []

    def get_stats(self) -> dict[str, Any]:
        """返回轻量检索/摄入统计，用于快照与调试。"""
        status, disable_reason, embeddings_enabled = self._get_runtime_status()
        stats = dict(self._stats)
        stats.update(
            {
                "status": status,
                "disable_reason": disable_reason,
                "index_enabled": bool(self.index),
                "embeddings_enabled": embeddings_enabled,
                "dimension": self.dimension,
                "embedding_base_url": getattr(self.backend, "_embedding_base_url", None),
                "embedding_model": getattr(self.backend, "_embedding_model", None),
                "last_query": self._last_query,
                "last_hits_preview": list(self._last_hits_preview),
            }
        )
        return stats

    def clear(self) -> None:
        """清空索引"""
        if self.index:
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata.clear()
            self._stats["indexed_items"] = 0
            self._stats["last_hit_count"] = 0
            self._last_query = ""
            self._last_hits_preview = []
