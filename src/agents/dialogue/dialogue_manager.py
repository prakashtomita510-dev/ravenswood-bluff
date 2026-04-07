"""
对话模块 (Dialogue Manager)

处理Agent的公开发言、说服和欺骗逻辑。
"""

from __future__ import annotations

import json
import logging

from src.agents.memory.working_memory import WorkingMemory
from src.llm.base_backend import LLMBackend, Message, ToolDef
from src.state.game_state import GameState, PlayerState

logger = logging.getLogger(__name__)


class DialogueManager:
    """对话生成管理器"""

    def __init__(self, backend: LLMBackend):
        self.backend = backend

    async def generate_speech(
        self,
        game_state: GameState,
        me: PlayerState,
        working_memory: WorkingMemory,
        social_graph_summary: str,
        current_strategy: str,
        persona: dict,
    ) -> dict:
        """
        生成公开发言，强制LLM调用 speak 工具。
        """
        system_prompt = self._build_system_prompt(me, persona)
        
        context = []
        context.append(f"【当前阶段】 第{game_state.round_number}轮 白天讨论")
        if game_state.current_nominee:
            nominee = game_state.get_player(game_state.current_nominee)
            context.append(f"⚠️ 当前正在进行针对 {nominee.name if nominee else ''} 的处决投票环节。")
            
        context.append("\n" + social_graph_summary)
        context.append("\n" + working_memory.get_recent_context(limit=10))
        context.append(f"\n【你的内心策略】\n{current_strategy}")
        
        user_prompt = (
            f"结合当前局势和你的内心策略，轮到你发言了。\n"
            f"{chr(10).join(context)}\n\n"
            f"请通过调用 `speak` 工具进行发言。一定要符合你的人格特点和说话风格！"
            f"{'作为邪恶阵营，如果你需要报假身份，请编造得自然一些。' if me.team.value == 'evil' else ''}"
        )

        messages = [Message(role="user", content=user_prompt)]
        
        tools = [
            ToolDef(
                name="speak",
                description="在白天讨论环节向所有人发出一段语音留言或文本发言",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "你的发言内容，应自然、像人类口语，不要太长"
                        },
                        "tone": {
                            "type": "string",
                            "enum": ["calm", "passionate", "accusatory", "defensive", "hesitant"],
                            "description": "发言时的语气情绪"
                        },
                        "target_player": {
                            "type": ["string", "null"],
                            "description": "如果你这番话主要是对某个人说的（例如质问他），填他的名字。否则填 null"
                        }
                    },
                    "required": ["content", "tone"]
                }
            )
        ]

        try:
            resp = await self.backend.generate(system_prompt, messages, tools=tools, temperature=0.8)
            
            # 解析工具调用
            if resp.tool_calls:
                for tc in resp.tool_calls:
                    if tc.function_name == "speak":
                        return {
                            "action": "speak",
                            "content": tc.arguments.get("content", "嗯...我没什么想说的。"),
                            "tone": tc.arguments.get("tone", "calm"),
                            "target_player": tc.arguments.get("target_player")
                        }
            
            # Fallback
            return {"action": "speak", "content": "（陷入了沉默）", "tone": "calm"}
            
        except Exception as e:
            logger.error(f"对话生成异常: {e}")
            return {"action": "speak", "content": "（头痛欲裂，无法说话）", "tone": "hesitant"}

    def _build_system_prompt(self, me: PlayerState, persona: dict) -> str:
        return (
            f"你正在玩桌游《血染钟楼》。\n"
            f"你的公开表现必须符合你的人格设定：\n"
            f"描述: {persona.get('description', '普通镇民')}\n"
            f"说话风格: {persona.get('speaking_style', '平淡')}\n\n"
            f"你的真实身份是 {me.role_id}（{me.team.value}阵营），这是你心中的机密。在别人面前你可能正在假扮其他角色。"
        )
