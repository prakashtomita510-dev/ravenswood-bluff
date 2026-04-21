"""
爪牙角色 (Minions)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from src.engine.roles.base_role import BaseRole, register_role


logger = logging.getLogger(__name__)
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

    requires_night_target = True

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
            payload={"effect": "poisoned_until_next_night"},
        )

        return new_state.with_event(event), [event]


@register_role("spy")
class SpyRole(BaseRole):
    """间谍: 每晚你可以查看魔法书（所有玩家的角色和阵营）。你可能被当作正义阵营、村民或外来者"""

    fixed_info_role = True
    storyteller_info_role = True

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
                night_order=70,
            ),
        )

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        return game_state, []

    def registers_as_team(self, game_state: GameState, actor: PlayerState) -> Team:
        key = f"misregistration:team:{actor.player_id}"
        if key in game_state.payload:
            return Team(game_state.payload[key])
        return super().registers_as_team(game_state, actor)

    def build_storyteller_info(self, game_state: GameState, actor: PlayerState) -> Optional[dict]:
        """间谍每晚查看魔法书：所有玩家的角色和阵营"""
        grimoire = []
        for p in game_state.players:
            grimoire.append({
                "player_id": p.player_id,
                "role_id": p.true_role_id or p.role_id,
                "team": p.current_team.value if p.current_team else p.team.value,
                "is_alive": p.is_alive
            })
        return {
            "type": "spy_grimoire",
            "grimoire": grimoire
        }

    def get_night_info(self, game_state, actor):
        return self.build_storyteller_info(game_state, actor)


@register_role("scarlet_woman")
class ScarletWomanRole(BaseRole):
    """绯红女郎: 如果恶魔死亡且场上有5名或更多存活玩家，你将成为新的恶魔"""

    @classmethod
    def can_replace_demon(cls, game_state: GameState) -> bool:
        """是否满足接管恶魔的基础条件。"""
        return game_state.alive_count >= 5

    @classmethod
    def is_eligible_replacement(cls, game_state: GameState, player: PlayerState) -> bool:
        """是否是当前可接管恶魔的绯红女郎。"""
        return (
            player.is_alive
            and (player.true_role_id or player.role_id) == "scarlet_woman"
            and cls.can_replace_demon(game_state)
        )

    @classmethod
    def should_trigger_on_demon_death(cls, game_state: GameState) -> bool:
        """恶魔死亡时是否应检查绯红女郎接管。"""
        return cls.can_replace_demon(game_state)

    @classmethod
    def check_and_transfer(
        cls,
        pre_death_state: GameState,
        post_death_state: GameState,
        dead_demon_id: str,
        trace_id: str,
    ) -> tuple[GameState, list[GameEvent]]:
        """检查绯红女郎接班。若符合条件，则接管为恶魔。"""
        if pre_death_state.alive_count < 5:
            return post_death_state, []
            
        for player in post_death_state.get_alive_players():
            if (player.true_role_id or player.role_id) == "scarlet_woman":
                demon_player = pre_death_state.get_player(dead_demon_id)
                if not demon_player:
                    continue
                new_demon_role = demon_player.true_role_id or demon_player.role_id
                
                new_state = post_death_state.with_player_update(
                    player.player_id,
                    role_id=new_demon_role,
                    team=Team.EVIL,
                    true_role_id=new_demon_role,
                    perceived_role_id=new_demon_role,
                    current_team=Team.EVIL,
                    storyteller_notes=player.storyteller_notes + (f"role_transferred_to_{new_demon_role}",)
                )
                transfer_event = GameEvent(
                    event_type="role_transfer",
                    phase=post_death_state.phase,
                    round_number=post_death_state.round_number,
                    trace_id=trace_id,
                    actor=dead_demon_id,
                    target=player.player_id,
                    visibility=Visibility.STORYTELLER_ONLY,
                    payload={"new_role": new_demon_role, "reason": "scarlet_woman_trigger"}
                )
                return new_state.with_event(transfer_event), [transfer_event]
                
        return post_death_state, []

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
                night_order=23,
            ),
        )

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        # 逻辑通常在死亡结算中触发
        return game_state, []


@register_role("baron")
class BaronRole(BaseRole):
    """男爵: 剧本中会额外多出两名外来者（减少两名村民）"""

    @classmethod
    def outsider_bonus(cls) -> int:
        """男爵带来的外来者增量。"""
        return 2

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
