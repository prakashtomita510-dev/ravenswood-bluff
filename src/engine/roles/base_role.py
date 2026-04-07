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

    def get_night_info(
        self,
        game_state: GameState,
        actor: PlayerState,
    ) -> Optional[dict]:
        """
        获取夜晚信息（对于信息收集型角色）

        Returns:
            信息字典，或 None（如果该角色不适用）
        """
        return None

    @classmethod
    def role_id(cls) -> str:
        return cls._role_id
