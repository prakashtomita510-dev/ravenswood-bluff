"""
外来者角色 (Outsiders)

实现惹事生非(Trouble Brewing)剧本中的外来者角色。
"""

from __future__ import annotations

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


@register_role("butler")
class ButlerRole(BaseRole):
    """管家: 你每晚选择一名玩家。明天，你只能在他们投票时投票"""

    requires_night_target = True

    @classmethod
    def binding_payload_key(cls) -> str:
        return "butler_bindings"

    @classmethod
    def set_binding(cls, game_state: GameState, butler_id: str, target_id: str) -> GameState:
        bindings = dict(game_state.payload.get(cls.binding_payload_key(), {}))
        bindings[butler_id] = {
            "target_id": target_id,
            "applies_on_day": game_state.day_number,
        }
        payload = dict(game_state.payload)
        payload[cls.binding_payload_key()] = bindings
        return game_state.with_update(payload=payload)

    @classmethod
    def get_active_binding(cls, game_state: GameState, butler_id: str) -> Optional[dict[str, Any]]:
        binding = game_state.payload.get(cls.binding_payload_key(), {}).get(butler_id)
        if not binding:
            return None
        if binding.get("applies_on_day") != game_state.day_number:
            return None
        return binding

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="butler",
            name="管家",
            name_en="Butler",
            team=Team.GOOD,
            role_type=RoleType.OUTSIDER,
            ability=Ability(
                trigger=AbilityTrigger.EACH_NIGHT,
                action_type=AbilityType.PASSIVE_EFFECT,
                description="每晚选择一名玩家。明天，除非该玩家投票，否则你不能投票",
                night_order=70,
            ),
        )

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        if not target:
            raise ValueError("管家必须选择一名玩家")
        target_player = game_state.get_player(target)
        if not target_player:
            raise ValueError("目标不存在")

        new_state = self.set_binding(game_state, actor.player_id, target)
        event = GameEvent(
            event_type="butler_binding",
            phase=game_state.phase,
            round_number=game_state.round_number,
            actor=actor.player_id,
            target=target,
            visibility=Visibility.STORYTELLER_ONLY,
            payload={
                "target_id": target,
                "applies_on_day": game_state.day_number,
            },
        )
        return new_state.with_event(event), [event]


@register_role("drunken")
class DrunkenRole(BaseRole):
    """酒鬼: 你以为你是某个村民，但其实你是个酒鬼（能力失效且会得到错误信息）"""

    fixed_info_role = False

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="drunken",
            name="酒鬼",
            name_en="Drunken",
            team=Team.GOOD,
            role_type=RoleType.OUTSIDER,
            drunk_behavior="false_info",
            ability=Ability(
                trigger=AbilityTrigger.PASSIVE,
                action_type=AbilityType.PASSIVE_EFFECT,
                description="你以为你是某个村民角色，但其实你不是。你的能力会失效或得到错误信息",
                night_order=0,
            ),
        )

    @classmethod
    def should_receive_false_info(cls) -> bool:
        return True

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        return game_state, []


@register_role("recluse")
class RecluseRole(BaseRole):
    """隐士: 你可能被当作邪恶阵营、爪牙或恶魔"""

    fixed_info_role = False

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="recluse",
            name="隐士",
            name_en="Recluse",
            team=Team.GOOD,
            role_type=RoleType.OUTSIDER,
            drunk_behavior="misread_as_evil",
            ability=Ability(
                trigger=AbilityTrigger.PASSIVE,
                action_type=AbilityType.PASSIVE_EFFECT,
                description="即使你属于正义阵营且是外来者，你也可能被当作邪恶阵营角色、爪牙或恶魔",
                night_order=0,
            ),
        )

    def registers_as_team(self, game_state: GameState, actor: PlayerState) -> Team:
        # 允许说书人调整其表现出的阵营
        key = f"misregistration:team:{actor.player_id}"
        if key in game_state.payload:
            return Team(game_state.payload[key])
        return super().registers_as_team(game_state, actor)

    def registers_as_role_type(self, game_state: GameState, actor: PlayerState) -> RoleType:
        key = f"misregistration:type:{actor.player_id}"
        if key in game_state.payload:
            return RoleType(game_state.payload[key])
        return super().registers_as_role_type(game_state, actor)

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        return game_state, []


@register_role("saint")
class SaintRole(BaseRole):
    """圣徒: 如果你被处决，你的阵营失败"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="saint",
            name="圣徒",
            name_en="Saint",
            team=Team.GOOD,
            role_type=RoleType.OUTSIDER,
            ability=Ability(
                trigger=AbilityTrigger.PASSIVE,
                action_type=AbilityType.PASSIVE_EFFECT,
                description="如果你被处决，你的阵营立即输掉游戏",
                night_order=0,
            ),
        )

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        return game_state, []
