"""
村民角色 (Townsfolk)

实现惹事生非(Trouble Brewing)剧本中的核心村民角色。
"""

from __future__ import annotations

import random
from typing import Any, Optional

from src.engine.roles.base_role import BaseRole, register_role
from src.state.game_state import (
    Ability,
    AbilityTrigger,
    AbilityType,
    GameEvent,
    GameState,
    PlayerState,
    RoleDefinition,
    RoleType,
    Team,
)


@register_role("washerwoman")
class WasherwomanRole(BaseRole):
    """洗衣妇: 你会得知两位玩家中有一位是某个特定的村民角色"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="washerwoman",
            name="洗衣妇",
            name_en="Washerwoman",
            team=Team.GOOD,
            role_type=RoleType.TOWNSFOLK,
            ability=Ability(
                trigger=AbilityTrigger.FIRST_NIGHT,
                action_type=AbilityType.INFO_GATHER,
                description="你会得知两位玩家中有一位是某个特定的村民角色",
                night_order=32,
            ),
        )

    def execute_ability(
        self,
        game_state: GameState,
        actor: PlayerState,
        target: Optional[str] = None,
        **kwargs: Any,
    ) -> tuple[GameState, list[GameEvent]]:
        # 在AI系统中，信息获取能力通常表现为其 get_night_info 被说书人/引擎调用。
        # 实际修改游戏状态的"主动技能"才需要在此处实现复杂逻辑。
        # 记录使用了技能。
        return game_state, []

    def get_night_info(
        self,
        game_state: GameState,
        actor: PlayerState,
    ) -> Optional[dict]:
        """为洗衣妇生成夜晚信息（由编排器或自动说书人调用）"""
        # 如果中毒，可能会获得假信息（这通常由编排器决定，这里只提供基础真实逻辑）
        # 1. 找到在场的所有其他村民
        townsfolks = [
            p for p in game_state.players 
            if p.player_id != actor.player_id 
            and p.role_id != "washerwoman"
            and self._is_townsfolk_role(p.role_id)
        ]
        
        if not townsfolks:
            return None
            
        # 2. 随机选一个真实的
        target_player = random.choice(townsfolks)
        target_role_id = target_player.role_id
        
        # 3. 随机选一个其他人干扰
        others = [p for p in game_state.players 
                  if p.player_id not in (actor.player_id, target_player.player_id)]
        decoy = random.choice(others) if others else target_player
        
        # 打乱顺序
        pair = [target_player.player_id, decoy.player_id]
        random.shuffle(pair)
        
        return {
            "type": "washerwoman_info",
            "players": pair,
            "role_seen": target_role_id
        }

    def _is_townsfolk_role(self, role_id: str) -> bool:
        from src.engine.roles.base_role import get_role_class
        cls = get_role_class(role_id)
        if cls:
            return cls.get_definition().role_type == RoleType.TOWNSFOLK
        return False


@register_role("empath")
class EmpathRole(BaseRole):
    """共情者: 每晚你会得知你的两个活着的邻居中有几个是邪恶的"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="empath",
            name="共情者",
            name_en="Empath",
            team=Team.GOOD,
            role_type=RoleType.TOWNSFOLK,
            ability=Ability(
                trigger=AbilityTrigger.EACH_NIGHT,
                action_type=AbilityType.INFO_GATHER,
                description="每晚你会得知你的两个活着的邻居中有几个是邪恶的",
                night_order=50,
            ),
        )

    def execute_ability(
        self,
        game_state: GameState,
        actor: PlayerState,
        target: Optional[str] = None,
        **kwargs: Any,
    ) -> tuple[GameState, list[GameEvent]]:
        return game_state, []

    def get_night_info(
        self,
        game_state: GameState,
        actor: PlayerState,
    ) -> Optional[dict]:
        seat_order = game_state.seat_order
        if not seat_order or actor.player_id not in seat_order:
            return None

        my_idx = seat_order.index(actor.player_id)
        n = len(seat_order)
        
        # 找左边最近的活人
        left_idx = (my_idx - 1) % n
        while not game_state.get_player(seat_order[left_idx]).is_alive:
            left_idx = (left_idx - 1) % n
            if left_idx == my_idx: break # 大家都死了
            
        # 找右边最近的活人
        right_idx = (my_idx + 1) % n
        while not game_state.get_player(seat_order[right_idx]).is_alive:
            right_idx = (right_idx + 1) % n
            if right_idx == my_idx: break

        evil_count = 0
        left_player = game_state.get_player(seat_order[left_idx])
        if left_player and left_player.team == Team.EVIL:
            evil_count += 1
            
        right_player = game_state.get_player(seat_order[right_idx])
        # 如果只剩两个人（自己和另一个活人），不重复计算
        if left_idx != right_idx and right_player and right_player.team == Team.EVIL:
            evil_count += 1

        return {
            "type": "empath_info",
            "evil_count": evil_count
        }


@register_role("undertaker")
class UndertakerRole(BaseRole):
    """送葬者: 每个夜晚*，得知今天白天被处决的玩家角色"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="undertaker",
            name="送葬者",
            name_en="Undertaker",
            team=Team.GOOD,
            role_type=RoleType.TOWNSFOLK,
            ability=Ability(
                trigger=AbilityTrigger.EACH_NIGHT,
                action_type=AbilityType.INFO_GATHER,
                description="得知今天白天被处决的玩家角色",
                night_order=52,
            ),
        )

    def execute_ability(
        self, game_state: GameState, actor: PlayerState, target: Optional[str] = None, **kwargs: Any
    ) -> tuple[GameState, list[GameEvent]]:
        return game_state, []

    def get_night_info(self, game_state: GameState, actor: PlayerState) -> Optional[dict]:
        if actor.is_drunk() or actor.is_poisoned():
            return {"type": "undertaker_info", "role_seen": "drunk_fake_role"}
            
        # Simplified: Check if anyone died by execution today.
        return {"type": "undertaker_info", "role_seen": "unknown_due_to_simple_impl"}
