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


@register_role("spy")
class SpyRole(BaseRole):
    """间谍: 每晚你可以查看魔法书（所有玩家的角色和阵营）。你可能被当作正义阵营、村民或外来者"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="spy",
            name="间谍",
            name_en="Spy",
            team=Team.EVIL,
            role_type=RoleType.MINION,
            ability=Ability(
                trigger=AbilityTrigger.EACH_NIGHT,
                action_type=AbilityType.INFO_GATHER,
                description="每晚你可以查看魔法书：你会得知所有玩家的角色和阵营。你可能被当作正义阵营、村民或外来者",
                night_order=60,
            ),
        )

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        return game_state, []

    def get_night_info(self, game_state, actor):
        # 间谍能看到全场信息
        book = []
        for p in game_state.players:
            book.append({"player_id": p.player_id, "name": p.name, "role_id": p.role_id, "team": p.team})
        return {"type": "spy_book", "book": book}


@register_role("scarlet_woman")
class ScarletWomanRole(BaseRole):
    """绯红女郎: 如果恶魔死亡且场上有5名或更多存活玩家，你将成为新的恶魔"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="scarlet_woman",
            name="绯红女郎",
            name_en="Scarlet Woman",
            team=Team.EVIL,
            role_type=RoleType.MINION,
            ability=Ability(
                trigger=AbilityTrigger.PASSIVE,
                action_type=AbilityType.PASSIVE_EFFECT,
                description="如果恶魔死亡且场上有5名或更多存活玩家，你将立即成为新的恶魔",
                night_order=0,
            ),
        )

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        # 逻辑通常在死亡结算中触发
        return game_state, []


@register_role("baron")
class BaronRole(BaseRole):
    """男爵: 剧本中会额外多出两名外来者（减少两名村民）"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="baron",
            name="男爵",
            name_en="Baron",
            team=Team.EVIL,
            role_type=RoleType.MINION,
            ability=Ability(
                trigger=AbilityTrigger.PASSIVE,
                action_type=AbilityType.PASSIVE_EFFECT,
                description="由于你的加入，剧本中会额外包含两名外来者，而村民则相应减少",
                night_order=0,
            ),
            setup_influence="add_2_outsiders"
        )

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        return game_state, []
