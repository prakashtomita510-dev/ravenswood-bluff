"""
说书人代理 (Storyteller Agent)

负责游戏的整体引导、信息分发决策（如分配哪两个玩家给洗衣妇）以及阶段叙事。
"""

import logging
from typing import Any, Optional
from src.state.game_state import GameState, GameEvent, GamePhase, Visibility, ChatMessage
from src.llm.openai_backend import OpenAIBackend

logger = logging.getLogger(__name__)

class StorytellerAgent:
    def __init__(self, backend: OpenAIBackend):
        self.backend = backend
        self.name = "Storyteller"
        self.player_id = "storyteller"

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """封装 LLM 调用"""
        from src.llm.base_backend import Message
        try:
            response = await self.backend.generate(
                system_prompt=system_prompt,
                messages=[Message(role="user", content=user_prompt)]
            )
            return response.content or ""
        except Exception as e:
            logger.error(f"Storyteller LLM error: {e}")
            return ""

    async def decide_drunk_role(self, script: Any, in_play_roles: list[str]) -> str:
        """为酒鬼决定一个假身份"""
        from src.engine.roles.base_role import get_role_class
        from src.state.game_state import RoleType
        
        townsfolk_pool = [r for r in script.roles if get_role_class(r).get_definition().role_type == RoleType.TOWNSFOLK and r not in in_play_roles]
        if not townsfolk_pool:
            return "washerwoman"
            
        prompt = f"""当前游戏在场角色: {', '.join(in_play_roles)}
候选的村民角色 (不在场): {', '.join(townsfolk_pool)}

请作为说书人，为“酒鬼”选择一个最能干扰正义阵营、平衡游戏局势的伪装身份。
直接返回角色 ID，不要有任何多余文字。"""
        
        res = await self._call_llm("你是一位精通血染钟楼平衡性的说书人。", prompt)
        res = res.strip().lower()
        if res in townsfolk_pool:
            return res
        return townsfolk_pool[0]

    async def decide_night_info(self, game_state: GameState, player_id: str, role_id: str) -> dict:
        """为特定角色决策首夜或夜晚信息"""
        import random
        players = list(game_state.players)
        
        # 基础提示词：让 LLM 决定目标
        system_prompt = "你是一位血染钟楼说书人，你的目标是通过分发信息来让游戏过程更加精彩和平衡。"
        
        if role_id == "washerwoman":
            # 洗衣妇：选一个村民，再选一个非该村民的人
            townsfolk = [p for p in players if p.role_id != "drunken" and p.team == "good" and p.player_id != player_id]
            if not townsfolk: return {}
            
            prompt = f"当前玩家列表: {', '.join([f'{p.name}({p.player_id})' for p in players])}。请为洗衣妇({player_id})选择一名村民作为提示目标，以及一名干扰目标。返回 JSON: {{\"target_id\": \"村民ID\", \"other_id\": \"干扰项目ID\"}}"
            res = await self._call_llm(system_prompt, prompt)
            try:
                import json
                data = json.loads(res.replace("```json", "").replace("```", ""))
                t1 = game_state.get_player(data["target_id"])
                t2 = game_state.get_player(data["other_id"])
                if t1 and t2:
                    return {"targets": [t1.name, t2.name], "role": t1.role_id}
            except: pass
            
            # Fallback
            target1 = random.choice(townsfolk)
            others = [p for p in players if p.player_id not in (player_id, target1.player_id)]
            target2 = random.choice(others) if others else target1
            return {"targets": [target1.name, target2.name], "role": target1.role_id}

        if role_id == "librarian":
            # 图书馆员：选一个外来者
            outsiders = [p for p in players if p.team == "good" and p.player_id != player_id] # 简化
            # ... 类似逻辑
            pass

        return {}

    async def narrate_phase(self, game_state: GameState) -> str:
        """为阶段切换提供叙事文本"""
        phase = game_state.phase
        day = game_state.day_number
        
        prompt = f"当前是血染钟楼游戏的 {phase.value} 阶段（第 {day} 天）。请作为说书人提供一段简短、神秘且有氛围感的开场白（中文，20-50字）。"
        
        res = await self._call_llm("你是一位充满神秘感的血染钟楼说书人。", prompt)
        return res if res else f"现在进入 {phase.value} 阶段。"
