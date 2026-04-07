"""
人类玩家代理 (Human Agent)

负责将后端的事件和请求转发给 WebSocket 连接的人类客户端，
并在收到人类操作指令后将其转换为引擎可理解的行为。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

from src.agents.base_agent import BaseAgent
from src.state.game_state import GameEvent, GameState, PlayerState

logger = logging.getLogger(__name__)


class HumanAgent(BaseAgent):
    """
    人类代理
    
    使用 asyncio.Queue 或是回调机制异步等待前端传来的操作结果。
    """

    def __init__(self, player_id: str, name: str, send_message_callback: Callable):
        """
        Args:
            player_id: 玩家唯一标识
            name: 玩家昵称
            send_message_callback: 用于向前端发送消息的异步回调函数 `async def cb(msg_str)`
        """
        super().__init__(player_id, name)
        self.send_message = send_message_callback
        # 等待前端消息的队列。为了避免串联多个动作，每次 act() 会消耗一个指令
        self.pending_actions: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def observe_event(self, event: GameEvent, game_state: GameState) -> None:
        """事件通知。转发给前端"""
        obs_msg = {
            "type": "event_update",
            "event": event.model_dump(mode="json"),
            "round": game_state.round_number,
            "phase": game_state.phase.value
        }
        await self._send_to_client(obs_msg)

    async def act(self, game_state: GameState, action_type: str, **kwargs: Any) -> dict[str, Any]:
        """向客户端请求行动并阻塞等待反馈"""
        req_msg = {
            "type": "action_request",
            "action_type": action_type,
            "context": kwargs
        }
        await self._send_to_client(req_msg)
        
        logger.info(f"[HumanAgent {self.name}] 等待客户端响应 action_type: {action_type}...")
        
        # 阻塞等待客户端输入
        action_payload = await self.pending_actions.get()
        logger.info(f"[HumanAgent {self.name}] 获得客户端响应: {action_payload}")
        
        return action_payload

    async def think(self, prompt: str, game_state: GameState) -> str:
        """人类不需要被强制系统思考，但我们可以弹出一个UI提示"""
        msg = {
            "type": "thought_prompt",
            "prompt": prompt
        }
        await self._send_to_client(msg)
        return "Human continues playing"

    async def receive_client_message(self, message: str) -> None:
        """通过WebSocket收到客户端传来的消息后，处理并放入队列"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            if msg_type == "action_response":
                payload = data.get("payload", {})
                await self.pending_actions.put(payload)
            else:
                logger.warning(f"未知客户端消息类型: {msg_type}")
        except json.JSONDecodeError:
            logger.error(f"解析客户端消息失败: {message}")

    async def _send_to_client(self, message_dict: dict) -> None:
        """帮助封装发送逻辑"""
        try:
            await self.send_message(json.dumps(message_dict, ensure_ascii=False))
        except Exception as e:
            logger.error(f"发送消息到客户端失败 {self.name}: {e}")
