"""Phase 0 测试 — LLM 后端抽象接口"""

import pytest
from src.llm.base_backend import (
    LLMBackend,
    LLMResponse,
    Message,
    ToolCall,
    ToolDef,
)


class MockLLMBackend(LLMBackend):
    """用于测试的 Mock LLM 后端"""

    def __init__(self, response_content: str = "mock response"):
        self._response_content = response_content
        self._call_count = 0
        self._last_system_prompt = None
        self._last_messages = None
        self._last_tools = None

    async def generate(
        self,
        system_prompt: str,
        messages: list[Message],
        tools=None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        self._call_count += 1
        self._last_system_prompt = system_prompt
        self._last_messages = messages
        self._last_tools = tools
        return LLMResponse(
            content=self._response_content,
            model="mock-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

    def get_model_name(self) -> str:
        return "mock-model"


class TestLLMModels:
    def test_message_creation(self):
        msg = Message(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"

    def test_tool_def(self):
        tool = ToolDef(
            name="speak",
            description="发言",
            parameters={"type": "object", "properties": {"content": {"type": "string"}}},
        )
        assert tool.name == "speak"

    def test_tool_call(self):
        tc = ToolCall(
            tool_call_id="tc_1",
            function_name="nominate",
            arguments={"nominee": "张三"},
        )
        assert tc.function_name == "nominate"
        assert tc.arguments["nominee"] == "张三"

    def test_llm_response(self):
        resp = LLMResponse(content="hello", model="gpt-4o")
        assert resp.content == "hello"
        assert resp.tool_calls == []


class TestMockBackend:
    @pytest.mark.asyncio
    async def test_generate(self):
        backend = MockLLMBackend("你好世界")
        messages = [Message(role="user", content="请自我介绍")]
        response = await backend.generate(
            system_prompt="你是一个村民",
            messages=messages,
        )
        assert response.content == "你好世界"
        assert response.model == "mock-model"
        assert backend._call_count == 1

    @pytest.mark.asyncio
    async def test_records_inputs(self):
        backend = MockLLMBackend()
        messages = [Message(role="user", content="test")]
        tools = [ToolDef(name="t1", description="d1")]
        await backend.generate("sys", messages, tools=tools)

        assert backend._last_system_prompt == "sys"
        assert len(backend._last_messages) == 1
        assert len(backend._last_tools) == 1

    def test_get_model_name(self):
        backend = MockLLMBackend()
        assert backend.get_model_name() == "mock-model"

    def test_repr(self):
        backend = MockLLMBackend()
        assert "MockLLMBackend" in repr(backend)
