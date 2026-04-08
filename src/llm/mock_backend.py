"""
Mock LLM 后端实现

用于在没有 API Key 的环境下进行逻辑模拟与自动化测试。
"""

from __future__ import annotations
import json
import random
import re
from typing import Optional

from src.llm.base_backend import (
    LLMBackend,
    LLMResponse,
    Message,
    ToolDef,
)

class MockBackend(LLMBackend):
    """
    Mock 后端
    根据 action_type 返回预定义的或随机的行为。
    """

    def _extract_player_ids(self, text: str) -> list[str]:
        matches = re.findall(r"\b([aph]\d+)\b", text.lower())
        seen: list[str] = []
        for match in matches:
            if match not in seen:
                seen.append(match)
        return seen

    def _extract_action_type(self, text: str) -> Optional[str]:
        match = re.search(r"当前需要执行的动作类型[:：]\s*([a-z_]+)", text.lower())
        return match.group(1) if match else None

    async def generate(
        self,
        system_prompt: str,
        messages: list[Message],
        tools: Optional[list[ToolDef]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        
        # 默认响应框架
        decision = {
            "action": "speak",
            "content": "我是一个 Mock AI。",
            "tone": "calm",
            "reasoning": "保持流程畅通。"
        }
        
        # 根据系统提示词中的关键词判定当前请求的行为类型
        prompt_lower = system_prompt.lower()
        player_ids = self._extract_player_ids(system_prompt)
        action_type = self._extract_action_type(system_prompt)

        if action_type == "night_action":
            decision["action"] = "night_action"
            decision["target"] = player_ids[1] if len(player_ids) > 1 else (player_ids[0] if player_ids else None)
            decision["reasoning"] = "夜晚行动模拟。"
        elif action_type in {"nominate", "nomination_intent"}:
            possible_targets = player_ids[1:] if len(player_ids) > 1 else player_ids
            if random.random() < 0.7 and possible_targets:
                decision["action"] = "nominate"
                decision["target"] = possible_targets[0]
                decision["reasoning"] = "我想推动一次有效提名。"
            else:
                decision["action"] = "none"
                decision["reasoning"] = "目前没有怀疑对象。"
        elif action_type == "defense_speech":
            decision["action"] = "speak"
            decision["content"] = "我是好人，请不要处决我！"
            decision["reasoning"] = "辩解中。"
        elif action_type == "vote":
            decision["action"] = "vote"
            decision["decision"] = True
            decision["reasoning"] = "赞成处决可疑人员。"
        elif action_type == "speak":
            decision["action"] = "speak"
            decision["content"] = "今天天气不错，大家有什么线索吗？"
        elif "night_action" in prompt_lower:
            decision["action"] = "night_action"
            decision["target"] = player_ids[1] if len(player_ids) > 1 else (player_ids[0] if player_ids else None)
            decision["reasoning"] = "夜晚行动模拟。"
            
        content = json.dumps(decision, ensure_ascii=False)

        return LLMResponse(
            content=content,
            tool_calls=[],
            model="mock-model",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        )

    def get_model_name(self) -> str:
        return "mock-model"
