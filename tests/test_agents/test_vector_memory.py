import sys
import types

import pytest


class _FakeArray:
    def __init__(self, values):
        self.values = values

    def astype(self, _dtype: str):
        return self.values


class _FakeIndexFlatL2:
    def __init__(self, dimension: int):
        self.dimension = dimension
        self._vectors: list[list[float]] = []

    @property
    def ntotal(self) -> int:
        return len(self._vectors)

    def add(self, vectors):
        self._vectors.extend(vectors)

    def search(self, query_vector, top_k: int):
        top_indices = list(range(min(top_k, len(self._vectors))))
        while len(top_indices) < top_k:
            top_indices.append(-1)
        return [[0.0] * top_k], [top_indices]


sys.modules.setdefault(
    "numpy",
    types.SimpleNamespace(array=lambda values: _FakeArray(values)),
)
sys.modules.setdefault(
    "faiss",
    types.SimpleNamespace(IndexFlatL2=_FakeIndexFlatL2),
)

from src.agents.memory.vector_memory import VectorMemory
from src.llm.base_backend import LLMBackend, LLMResponse, Message
from src.state.game_state import ChatMessage, GamePhase


class DummyEmbeddingBackend(LLMBackend):
    async def generate(self, system_prompt: str, messages: list[Message], **kwargs) -> LLMResponse:
        return LLMResponse(content="unused", model="dummy")

    def get_model_name(self) -> str:
        return "dummy-embedding"

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            base = float(len(text))
            vectors.append([base, base / 2.0, base / 3.0])
        return vectors


@pytest.mark.asyncio
async def test_add_message_uses_chatmessage_speaker_and_metadata() -> None:
    memory = VectorMemory(backend=DummyEmbeddingBackend(), dimension=3)
    message = ChatMessage(
        speaker="p2",
        content="我跳调查员，并点名 p3 和 h1。",
        phase=GamePhase.DAY_DISCUSSION,
        round_number=2,
        target_player="p3",
        recipient_ids=("p1", "p4"),
    )

    await memory.add_message(message)

    assert len(memory.metadata) == 1
    stored = memory.metadata[0]
    assert stored["text"] == '发言: p2 说: "我跳调查员，并点名 p3 和 h1。"'
    assert stored["speaker"] == "p2"
    assert stored["phase"] == str(GamePhase.DAY_DISCUSSION)
    assert stored["round"] == 2
    assert stored["target_player"] == "p3"
    assert stored["recipient_ids"] == ["p1", "p4"]


@pytest.mark.asyncio
async def test_add_message_can_be_retrieved_via_search() -> None:
    memory = VectorMemory(backend=DummyEmbeddingBackend(), dimension=3)
    message = ChatMessage(
        speaker="storyteller",
        content="今晚没有人死亡。",
        phase=GamePhase.NIGHT,
        round_number=3,
    )

    await memory.add_message(message)
    results = await memory.search("今晚没有人死亡", top_k=1)

    assert len(results) == 1
    assert results[0]["type"] == "message"
    assert results[0]["speaker"] == "storyteller"
    stats = memory.get_stats()
    assert stats["message_ingests"] == 1
    assert stats["text_ingests"] == 1
    assert stats["search_count"] == 1
    assert stats["last_hit_count"] == 1
    assert stats["search_hit_count"] == 1
