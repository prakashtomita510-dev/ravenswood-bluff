"""
LLM 后端抽象接口

定义统一的 LLM 调用接口，支持多种模型提供商。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    """LLM 消息"""
    role: str              # "system" / "user" / "assistant" / "tool"
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[list[dict]] = None


class ToolDef(BaseModel):
    """工具定义（用于 LLM tool calling）"""
    name: str
    description: str
    parameters: dict = Field(default_factory=dict)


class ToolCall(BaseModel):
    """LLM 返回的工具调用"""
    tool_call_id: str
    function_name: str
    arguments: dict = Field(default_factory=dict)


class LLMResponse(BaseModel):
    """LLM 响应"""
    content: Optional[str] = None           # 文本响应
    tool_calls: list[ToolCall] = Field(default_factory=list)
    model: str = ""
    usage: dict = Field(default_factory=dict)  # token 用量


class LLMBackend(ABC):
    """
    LLM 后端统一抽象接口

    所有 LLM 提供商（OpenAI、Anthropic、Gemini 等）都需要实现此接口。
    Agent 通过此接口与 LLM 交互，实现模型无关性。
    """

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        messages: list[Message],
        tools: Optional[list[ToolDef]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """
        向 LLM 发送请求并获取响应。

        Args:
            system_prompt: 系统提示词
            messages: 对话消息历史
            tools: 可选的工具定义列表
            temperature: 生成温度
            max_tokens: 最大生成 token 数

        Returns:
            LLMResponse: LLM 的响应结果
        """
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        """获取当前使用的模型名称"""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.get_model_name()})"
