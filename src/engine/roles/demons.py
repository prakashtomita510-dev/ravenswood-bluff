"""
恶魔角色 (Demons)

实现核心的恶魔角色。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from src.engine.roles.base_role import BaseRole, register_role
from src.state.game_state import (
    Ability,
    AbilityTrigger,
    AbilityType,
    GameEvent,
    GamePhase,
    GameState,
    PlayerState,
    RoleDefinition,
    RoleType,
    Team,
    Visibility,
)

logger = logging.getLogger(__name__)


@register_role("imp")
class ImpRole(BaseRole):
    """小恶魔: 每个除第一夜外的夜晚可以通过选择死亡一名玩家。如果小恶魔自杀，一个爪牙将变成小恶魔"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="imp",
            name="小恶魔",
            name_en="Imp",
            team=Team.EVIL,
            role_type=RoleType.DEMON,
            ability=Ability(
                trigger=AbilityTrigger.EACH_NIGHT_EXCEPT_FIRST,
                action_type=AbilityType.KILL,
                description="除第一夜外，每晚你可以选择一名玩家使其死亡。如果你选择自杀，一个爪牙将变成小恶魔",
                night_order=24,
            ),
        )

    def execute_ability(
        self,
        game_state: GameState,
        actor: PlayerState,
        target: Optional[str] = None,
        **kwargs: Any,
    ) -> tuple[GameState, list[GameEvent]]:
        if not target:
            raise ValueError("小恶魔必须选择一个目标")

        target_player = game_state.get_player(target)
        if not target_player:
            raise ValueError("目标不存在")

        if not target_player.is_alive:
            # 鞭尸不会真正死亡
            return game_state, []

        events = []
        new_state = game_state.with_player_update(target, is_alive=False)

        kill_event = GameEvent(
            event_type="night_kill",
            phase=GamePhase.NIGHT,
            round_number=game_state.round_number,
            actor=actor.player_id,
            target=target,
            visibility=Visibility.STORYTELLER_ONLY,
            payload={"killer_role": "imp"}
        )
        events.append(kill_event)
        new_state = new_state.with_event(kill_event)

        # 检查是否自杀传递小恶魔
        if target == actor.player_id:
            # 找到一个存活的爪牙并变成小恶魔
            from src.engine.roles.base_role import get_role_class
            minions = []
            for p in game_state.get_alive_players():
                if p.player_id != actor.player_id:
                    cls = get_role_class(p.role_id)
                    if cls and cls.get_definition().role_type == RoleType.MINION:
                        minions.append(p)
            
            if minions:
                new_imp = minions[0]  # 这里简单取第一个，如果有多个，由于没有其他输入，先这么处理
                new_state = new_state.with_player_update(new_imp.player_id, role_id="imp")
                transfer_event = GameEvent(
                    event_type="role_transfer",
                    phase=GamePhase.NIGHT,
                    round_number=game_state.round_number,
                    target=new_imp.player_id,
                    visibility=Visibility.STORYTELLER_ONLY,
                    payload={"new_role": "imp", "reason": "imp_suicide"}
                )
                events.append(transfer_event)
                new_state = new_state.with_event(transfer_event)

        return new_state, events
