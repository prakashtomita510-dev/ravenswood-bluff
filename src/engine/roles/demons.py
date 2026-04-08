"""
恶魔角色 (Demons)

实现核心的恶魔角色。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from src.engine.roles.base_role import BaseRole, get_role_class, register_role
from src.state.game_state import (
    Ability,
    AbilityTrigger,
    AbilityType,
    GameEvent,
    GamePhase,
    GameState,
    PlayerState,
    PlayerStatus,
    RoleDefinition,
    RoleType,
    Team,
    Visibility,
)

logger = logging.getLogger(__name__)


@register_role("imp")
class ImpRole(BaseRole):
    """小恶魔: 每个除第一夜外的夜晚可以通过选择死亡一名玩家。如果小恶魔自杀，一个爪牙将变成小恶魔"""

    requires_night_target = True

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

    def _find_scarlet_woman(self, game_state: GameState) -> Optional[PlayerState]:
        """寻找当前存活且满足接管条件的绯红女郎。"""
        role_cls = get_role_class("scarlet_woman")
        if not role_cls:
            return None
        if not role_cls.should_trigger_on_demon_death(game_state):
            return None
        for player in game_state.get_alive_players():
            if role_cls.is_eligible_replacement(game_state, player):
                return player
        return None

    def _find_minion_replacement(self, game_state: GameState, exclude_player_id: str) -> Optional[PlayerState]:
        """在没有绯红女郎时，选择一个存活爪牙接管。"""
        for player in game_state.get_alive_players():
            if player.player_id == exclude_player_id:
                continue
            if (player.true_role_id or player.role_id) == "scarlet_woman":
                continue
            role_cls = get_role_class(player.true_role_id or player.role_id)
            if role_cls and role_cls.get_definition().role_type == RoleType.MINION:
                return player
        return None

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
            return game_state, []

        events = []
        protected = PlayerStatus.PROTECTED in target_player.statuses
        soldier_cls = get_role_class("soldier")
        soldier_safe = bool(soldier_cls and soldier_cls.is_immune_to_demon(target_player))
        if target != actor.player_id and (protected or soldier_safe):
            return game_state, []

        actual_target = target
        mayor_cls = get_role_class("mayor")
        redirected_from = None
        if mayor_cls and mayor_cls.should_redirect_night_death(game_state, target_player) and target != actor.player_id:
            redirected_target = mayor_cls.choose_redirection_target(game_state, mayor_player_id=target_player.player_id, killer_id=actor.player_id)
            if redirected_target:
                actual_target = redirected_target
                redirected_from = target
                target_player = game_state.get_player(actual_target)

        new_state = game_state.with_player_update(actual_target, is_alive=False)

        kill_event = GameEvent(
            event_type="night_kill",
            phase=GamePhase.NIGHT,
            round_number=game_state.round_number,
            actor=actor.player_id,
            target=actual_target,
            visibility=Visibility.STORYTELLER_ONLY,
            payload={
                "killer_role": "imp",
                "resolved_target_role": target_player.true_role_id or target_player.role_id,
                "redirected_from": redirected_from,
            },
        )
        events.append(kill_event)
        new_state = new_state.with_event(kill_event)

        # 检查是否自杀传递小恶魔
        if actual_target == actor.player_id:
            replacement = self._find_scarlet_woman(game_state)
            replacement_reason = "scarlet_woman_trigger"
            if not replacement:
                replacement = self._find_minion_replacement(game_state, exclude_player_id=actor.player_id)
                replacement_reason = "imp_suicide"

            if replacement:
                new_state = new_state.with_player_update(
                    replacement.player_id,
                    role_id="imp",
                    team=Team.EVIL,
                    true_role_id="imp",
                    perceived_role_id="imp",
                    current_team=Team.EVIL,
                    storyteller_notes=replacement.storyteller_notes + ("role_transferred_to_imp",),
                )
                transfer_event = GameEvent(
                    event_type="role_transfer",
                    phase=GamePhase.NIGHT,
                    round_number=game_state.round_number,
                    actor=actor.player_id,
                    target=replacement.player_id,
                    visibility=Visibility.STORYTELLER_ONLY,
                    payload={"new_role": "imp", "reason": replacement_reason},
                )
                events.append(transfer_event)
                new_state = new_state.with_event(transfer_event)

        return new_state, events
