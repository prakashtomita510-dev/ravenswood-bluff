import sys
from types import SimpleNamespace

import pytest

from src.llm.openai_backend import OpenAIBackend


class _Embeddings404Error(Exception):
    def __init__(self, message: str = "404 Not Found"):
        super().__init__(message)
        self.status_code = 404


class _FailingEmbeddingsClient:
    def __init__(self) -> None:
        self.calls = 0
        self.embeddings = SimpleNamespace(create=self.create)

    async def create(self, **kwargs):
        self.calls += 1
        raise _Embeddings404Error()


class _SuccessEmbeddingsClient:
    def __init__(self) -> None:
        self.calls = 0
        self.embeddings = SimpleNamespace(create=self.create)

    async def create(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            data=[
                SimpleNamespace(embedding=[0.1, 0.2, 0.3]),
                SimpleNamespace(embedding=[0.4, 0.5, 0.6]),
            ]
        )


class _EchoAsyncOpenAI:
    instances = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.embeddings = SimpleNamespace(create=self.create)
        _EchoAsyncOpenAI.instances.append(self)

    async def create(self, **kwargs):
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])


@pytest.mark.asyncio
async def test_get_embeddings_disables_itself_after_unsupported_404() -> None:
    backend = OpenAIBackend(model="dummy")
    client = _FailingEmbeddingsClient()
    backend._embedding_client = client

    first = await backend.get_embeddings(["hello"])
    second = await backend.get_embeddings(["world"])

    assert first == []
    assert second == []
    assert backend._embeddings_disabled is True
    assert client.calls == 1


@pytest.mark.asyncio
async def test_get_embeddings_returns_vectors_when_supported() -> None:
    backend = OpenAIBackend(model="dummy")
    client = _SuccessEmbeddingsClient()
    backend._embedding_client = client

    embeddings = await backend.get_embeddings(["a", "b"])

    assert embeddings == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert backend._embeddings_disabled is False
    assert client.calls == 1


@pytest.mark.asyncio
async def test_get_embeddings_uses_dedicated_embedding_client_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_API_KEY", "embed-key")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1")
    monkeypatch.setenv("EMBEDDING_MODEL", "Pro/BAAI/bge-m3")

    _EchoAsyncOpenAI.instances.clear()
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=_EchoAsyncOpenAI))

    backend = OpenAIBackend(
        model="dummy-chat",
        api_key="chat-key",
        base_url="http://127.0.0.1:8045/v1",
    )

    embeddings = await backend.get_embeddings(["hello"])

    assert embeddings == [[0.1, 0.2, 0.3]]
    assert len(_EchoAsyncOpenAI.instances) == 1
    assert _EchoAsyncOpenAI.instances[0].kwargs["api_key"] == "embed-key"
    assert _EchoAsyncOpenAI.instances[0].kwargs["base_url"] == "https://api.siliconflow.cn/v1"


def test_get_embedding_status_reports_disable_state() -> None:
    backend = OpenAIBackend(model="dummy")
    backend._embedding_model = "Pro/BAAI/bge-m3"
    backend._embedding_base_url = "https://api.siliconflow.cn/v1"
    backend._embeddings_disabled = True
    backend._embeddings_disable_reason = "404"

    status = backend.get_embedding_status()

    assert status["enabled"] is False
    assert status["model"] == "Pro/BAAI/bge-m3"
    assert status["base_url"] == "https://api.siliconflow.cn/v1"
    assert status["disabled_reason"] == "404"
