"""
OpenAI LLM 后端实现

通过 OpenAI API（兼容 GPT-4o、GPT-4o-mini 等）调用 LLM。
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from src.llm.base_backend import (
    LLMBackend,
    LLMResponse,
    Message,
    ToolCall,
    ToolDef,
)

logger = logging.getLogger(__name__)


class OpenAIBackend(LLMBackend):
    """
    OpenAI API 后端

    使用 openai Python SDK 调用 GPT 系列模型。
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._client = None

    def _get_client(self):
        """懒加载 OpenAI 客户端"""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError(
                    "openai package is required. Install with: pip install openai"
                )
            kwargs = {}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def generate(
        self,
        system_prompt: str,
        messages: list[Message],
        tools: Optional[list[ToolDef]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """通过 OpenAI API 生成响应"""
        client = self._get_client()

        # 构建消息列表
        api_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            api_msg = {"role": msg.role, "content": msg.content}
            if msg.name:
                api_msg["name"] = msg.name
            if msg.tool_call_id:
                api_msg["tool_call_id"] = msg.tool_call_id
            api_messages.append(api_msg)

        # 构建 API 参数
        kwargs = {
            "model": self._model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # 构建工具定义
        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in tools
            ]

        # 调用 API
        try:
            response = await client.chat.completions.create(**kwargs)
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

        # 解析响应
        choice = response.choices[0]
        message = choice.message

        # 解析 tool calls
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    arguments = {"raw": tc.function.arguments}
                tool_calls.append(
                    ToolCall(
                        tool_call_id=tc.id,
                        function_name=tc.function.name,
                        arguments=arguments,
                    )
                )

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
        )

    def get_model_name(self) -> str:
        return self._model
