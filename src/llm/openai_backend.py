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
        import os
        from dotenv import load_dotenv
        
        load_dotenv() # Load variables from .env if present
        
        self._model = os.getenv("DEFAULT_MODEL") or model
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self._embedding_api_key = os.getenv("EMBEDDING_API_KEY") or self._api_key
        self._embedding_base_url = os.getenv("EMBEDDING_BASE_URL") or self._base_url
        self._embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self._client = None
        self._embedding_client = None
        self._embeddings_disabled = False
        self._embeddings_disable_reason: Optional[str] = None

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
            self._client = AsyncOpenAI(**kwargs, timeout=60.0)
        return self._client

    def _get_embedding_client(self):
        """懒加载 Embeddings 客户端，允许与聊天模型分离配置。"""
        if self._embedding_client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError(
                    "openai package is required. Install with: pip install openai"
                )
            kwargs = {}
            if self._embedding_api_key:
                kwargs["api_key"] = self._embedding_api_key
            if self._embedding_base_url:
                kwargs["base_url"] = self._embedding_base_url
            self._embedding_client = AsyncOpenAI(**kwargs)
        return self._embedding_client

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
        logger.info(f"Sending LLM request to {self._model} (base_url: {self._base_url})")
        try:
            response = await client.chat.completions.create(**kwargs, timeout=30.0)
            logger.info("Received LLM response successfully.")
        except Exception as e:
            logger.error(f"OpenAI API error: {type(e).__name__}: {e}")
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

    @staticmethod
    def _is_embedding_unsupported_error(error: Exception) -> bool:
        status_code = getattr(error, "status_code", None)
        if status_code == 404:
            return True

        message = str(error).lower()
        unsupported_markers = (
            "404",
            "not found",
            "embeddings",
            "does not exist",
            "unsupported",
        )
        return "embedding" in message and any(marker in message for marker in unsupported_markers)

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """通过 OpenAI API 获取向量嵌入"""
        if not texts:
            return []

        if self._embeddings_disabled:
            return []
        
        client = self._get_embedding_client()
        logger.info(
            "Generating embeddings for %s texts using %s (base_url=%s)",
            len(texts),
            self._embedding_model,
            self._embedding_base_url,
        )
        try:
            response = await client.embeddings.create(
                model=self._embedding_model,
                input=texts,
                timeout=15.0
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            if self._is_embedding_unsupported_error(e):
                self._embeddings_disabled = True
                self._embeddings_disable_reason = str(e)
                logger.warning(
                    "Embeddings endpoint/model is unavailable for base_url=%s model=%s; "
                    "disabling embeddings and continuing without vector retrieval. reason=%s",
                    self._embedding_base_url,
                    self._embedding_model,
                    e,
                )
                return []

            logger.error(f"OpenAI Embeddings API error: {e}")
            return []

    def get_embedding_status(self) -> dict[str, object]:
        """返回 embeddings 通道的轻量状态，供数据快照与调试使用。"""
        return {
            "enabled": not self._embeddings_disabled,
            "model": self._embedding_model,
            "base_url": self._embedding_base_url,
            "disabled_reason": self._embeddings_disable_reason,
        }
