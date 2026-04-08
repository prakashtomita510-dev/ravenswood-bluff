"""
基础角色类 (Base Role)

角色技能的基类和注册机制。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, TYPE_CHECKING

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

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# 全局角色注册表
_ROLE_REGISTRY: dict[str, type["BaseRole"]] = {}


def register_role(role_id: str):
    """角色注册装饰器"""
    def decorator(cls: type[BaseRole]):
        _ROLE_REGISTRY[role_id] = cls
        cls._role_id = role_id
        return cls
    return decorator


def get_role_class(role_id: str) -> Optional[type["BaseRole"]]:
    """根据角色ID获取角色类"""
    return _ROLE_REGISTRY.get(role_id)


def get_all_role_ids() -> list[str]:
    """获取所有已注册的角色ID"""
    return list(_ROLE_REGISTRY.keys())


class BaseRole(ABC):
    """
    角色基类

    每个角色需要实现:
    - get_definition(): 返回角色定义（静态信息）
    - execute_ability(): 执行角色技能
    """

    _role_id: str = ""
    fixed_info_role: bool = False
    storyteller_info_role: bool = False
    requires_night_target: bool = False

    @staticmethod
    @abstractmethod
    def get_definition() -> RoleDefinition:
        """获取角色静态定义"""
        ...

    @abstractmethod
    def execute_ability(
        self,
        game_state: GameState,
        actor: PlayerState,
        target: Optional[str] = None,
        **kwargs: Any,
    ) -> tuple[GameState, list[GameEvent]]:
        """
        执行角色技能

        Args:
            game_state: 当前游戏状态
            actor: 使用技能的玩家
            target: 技能目标 (player_id)
            **kwargs: 额外参数

        Returns:
            (新的 GameState, 产生的事件列表)
        """
        ...

    def can_act_at_phase(self, game_state: GameState, phase: GamePhase) -> bool:
        """
        检查角色在当前阶段是否应该行动
        """
        definition = self.get_definition()
        if not definition.ability:
            return False

        # 固定信息角色不进入通用 night_action 请求链。
        if definition.ability.action_type == AbilityType.INFO_GATHER and self.is_fixed_info_role():
            return False
        
        trigger = definition.ability.trigger
        
        if phase == GamePhase.FIRST_NIGHT:
            return trigger in (AbilityTrigger.FIRST_NIGHT, AbilityTrigger.EACH_NIGHT)
        
        if phase == GamePhase.NIGHT:
            # 除首夜(Round 1, Day 0)外的夜晚 (通常是 Round 2, Day 1 及以后)
            # 或者是针对 EACH_NIGHT_EXCEPT_FIRST 触发器
            if game_state.round_number > 1:
                return trigger in (AbilityTrigger.EACH_NIGHT, AbilityTrigger.EACH_NIGHT_EXCEPT_FIRST)
            # 首个夜晚(Round 1)已经用 FIRST_NIGHT 覆盖了，NIGHT 里的 EACH_NIGHT 也应在后续生效
            return trigger == AbilityTrigger.EACH_NIGHT
            
        return False

    @classmethod
    def is_fixed_info_role(cls) -> bool:
        """是否应由说书人直接发放固定信息，而不是请求玩家选择行动。"""
        return bool(getattr(cls, "fixed_info_role", False))

    @classmethod
    def needs_night_target(cls) -> bool:
        """是否需要在夜晚让玩家选择目标。"""
        return bool(getattr(cls, "requires_night_target", False))

    @classmethod
    def uses_storyteller_adjudication(cls) -> bool:
        """是否由说书人裁定并发放信息。"""
        return bool(getattr(cls, "storyteller_info_role", False))

    def build_storyteller_info(
        self,
        game_state: GameState,
        actor: PlayerState,
    ) -> Optional[dict]:
        """
        构建供说书人裁定的原始信息载荷。

        角色实现应返回事实型 payload，而不是最终展示文案。
        """
        return None

    def get_night_info(
        self,
        game_state: GameState,
        actor: PlayerState,
    ) -> Optional[dict]:
        """
        获取夜晚信息（兼容旧接口）。

        Returns:
            信息字典，或 None（如果该角色不适用）
        """
        return self.build_storyteller_info(game_state, actor)

    @classmethod
    def role_id(cls) -> str:
        return cls._role_id
