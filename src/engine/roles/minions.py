"""
爪牙角色 (Minions)
"""

from __future__ import annotations

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
    Visibility,
)


@register_role("poisoner")
class PoisonerRole(BaseRole):
    """投毒者: 每晚你可以选择一名玩家，他今晚和明天白天可能获得假信息或能力失效"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="poisoner",
            name="投毒者",
            name_en="Poisoner",
            team=Team.EVIL,
            role_type=RoleType.MINION,
            ability=Ability(
                trigger=AbilityTrigger.EACH_NIGHT,
                action_type=AbilityType.MANIPULATION,
                description="每晚你可以选择一名玩家，他今晚和明天白天中毒（可能获得假信息或能力失效）",
                night_order=15,
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
            raise ValueError("投毒者必须选择一个目标")

        target_player = game_state.get_player(target)
        if not target_player:
            raise ValueError("目标不存在")

        # 将目标存活玩家标记为中毒
        # 这里使用 statuses 加一个中毒标。我们在游戏状态中有 statuses=(PlayerStatus.ALIVE,)
        from src.state.game_state import PlayerStatus

        if PlayerStatus.POISONED not in target_player.statuses:
            new_statuses = tuple(list(target_player.statuses) + [PlayerStatus.POISONED])
        else:
            new_statuses = target_player.statuses

        new_state = game_state.with_player_update(target, statuses=new_statuses)

        event = GameEvent(
            event_type="night_poison",
            phase=game_state.phase,
            round_number=game_state.round_number,
            actor=actor.player_id,
            target=target,
            visibility=Visibility.STORYTELLER_ONLY,
        )
        
        # patch to fix phase
        event = event.model_copy(update={"phase": game_state.phase})

        return new_state.with_event(event), [event]
