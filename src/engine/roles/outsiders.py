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
    GameState,
    PlayerState,
    RoleDefinition,
    RoleType,
    Team,
)


@register_role("butler")
class ButlerRole(BaseRole):
    """管家: 你每晚选择一名玩家。明天，你只能在他们投票时投票"""

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
        # 记录追踪的目标，在投票逻辑中校验
        return game_state, []


@register_role("drunken")
class DrunkenRole(BaseRole):
    """酒鬼: 你以为你是某个村民，但其实你是个酒鬼（能力失效且会得到错误信息）"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="drunken",
            name="酒鬼",
            name_en="Drunken",
            team=Team.GOOD,
            role_type=RoleType.OUTSIDER,
            ability=Ability(
                trigger=AbilityTrigger.PASSIVE,
                action_type=AbilityType.PASSIVE_EFFECT,
                description="你以为你是某个村民角色，但其实你不是。你的能力会失效或得到错误信息",
                night_order=0,
            ),
        )

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        return game_state, []


@register_role("recluse")
class RecluseRole(BaseRole):
    """隐士: 你可能被当作邪恶阵营、爪牙或恶魔"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="recluse",
            name="隐士",
            name_en="Recluse",
            team=Team.GOOD,
            role_type=RoleType.OUTSIDER,
            ability=Ability(
                trigger=AbilityTrigger.PASSIVE,
                action_type=AbilityType.PASSIVE_EFFECT,
                description="即使你属于正义阵营且是外来者，你也可能被当作邪恶阵营角色、爪牙或恶魔",
                night_order=0,
            ),
        )

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
