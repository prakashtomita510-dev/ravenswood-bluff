"""
阶段状态机 (Phase Manager)

管理血染钟楼游戏的阶段转移，确保状态转换的合法性。
"""

from __future__ import annotations

import logging
from typing import Optional

from src.state.game_state import GamePhase

logger = logging.getLogger(__name__)

# 合法的阶段转移表
VALID_TRANSITIONS: dict[GamePhase, list[GamePhase]] = {
    GamePhase.SETUP: [GamePhase.SETUP, GamePhase.FIRST_NIGHT, GamePhase.GAME_OVER],
    GamePhase.FIRST_NIGHT: [GamePhase.DAY_DISCUSSION],
    GamePhase.DAY_DISCUSSION: [GamePhase.NOMINATION, GamePhase.GAME_OVER],
    GamePhase.NOMINATION: [GamePhase.VOTING, GamePhase.EXECUTION, GamePhase.NIGHT, GamePhase.GAME_OVER],
    GamePhase.VOTING: [GamePhase.NOMINATION, GamePhase.EXECUTION, GamePhase.GAME_OVER],
    GamePhase.EXECUTION: [GamePhase.NIGHT, GamePhase.GAME_OVER],
    GamePhase.NIGHT: [GamePhase.DAY_DISCUSSION, GamePhase.GAME_OVER],
    GamePhase.GAME_OVER: [],  # 终态
}


class PhaseManager:
    """
    阶段管理器 — 维护游戏阶段状态机

    职责:
    - 管理当前游戏阶段
    - 验证阶段转移的合法性
    - 追踪轮次和天数
    """

    def __init__(self) -> None:
        self._current_phase: GamePhase = GamePhase.SETUP
        self._round_number: int = 0
        self._day_number: int = 0
        self._phase_history: list[tuple[GamePhase, int, int]] = []  # (phase, round, day)

    @property
    def current_phase(self) -> GamePhase:
        return self._current_phase

    @property
    def round_number(self) -> int:
        return self._round_number

    @property
    def day_number(self) -> int:
        return self._day_number

    @property
    def is_game_over(self) -> bool:
        return self._current_phase == GamePhase.GAME_OVER

    @property
    def phase_history(self) -> list[tuple[GamePhase, int, int]]:
        return list(self._phase_history)

    def can_transition_to(self, target: GamePhase | str) -> bool:
        """检查是否可以转移到目标阶段"""
        # 强制转为 Enum 比较
        if isinstance(target, str):
            try:
                target = GamePhase(target)
            except ValueError:
                return False
        
        # 确保当前阶段也是 Enum
        current = self._current_phase
        if isinstance(current, str):
            current = GamePhase(current)

        valid_targets = VALID_TRANSITIONS.get(current, [])
        # DEBUG PRINTS
        # print(f"DEBUG: Checking {current} -> {target}. Valid: {valid_targets}")
        # for v in valid_targets:
        #     if v == target: print(f"DEBUG: Found match! {v} == {target}")
        
        return target in valid_targets

    def get_valid_transitions(self) -> list[GamePhase]:
        """获取当前阶段可以转移到的所有合法阶段"""
        current = self._current_phase
        if isinstance(current, str):
            current = GamePhase(current)
        return list(VALID_TRANSITIONS.get(current, []))

    def transition_to(self, target: GamePhase | str) -> None:
        """
        执行阶段转移

        Raises:
            ValueError: 如果转移不合法
        """
        # 统一转为 Enum 成员
        if isinstance(target, str):
            try:
                target = GamePhase(target)
            except ValueError:
                raise ValueError(f"无效的阶段名称: {target}")

        if not self.can_transition_to(target):
            valid = self.get_valid_transitions()
            raise ValueError(
                f"非法阶段转移: {self._current_phase} -> {target}. "
                f"允许的后续阶段为: {[p.value for p in valid]}"
            )

        old_phase = self._current_phase
        self._current_phase = target

        # 更新轮次和天数
        if target == GamePhase.FIRST_NIGHT:
            self._round_number = 1
            self._day_number = 0 # 首夜通常认为是第0天或还没到第1天
        elif target == GamePhase.DAY_DISCUSSION:
            self._day_number += 1
        elif target == GamePhase.NIGHT:
            self._round_number += 1

        self._phase_history.append((target, self._round_number, self._day_number))

        logger.info(
            f"阶段转移: {old_phase.value} -> {target.value} "
            f"(轮次={self._round_number}, 天数={self._day_number})"
        )

    def reset(self) -> None:
        """重置状态机"""
        self._current_phase = GamePhase.SETUP
        self._round_number = 0
        self._day_number = 0
        self._phase_history.clear()

    def __repr__(self) -> str:
        return (
            f"PhaseManager(phase={self._current_phase.value}, "
            f"round={self._round_number}, day={self._day_number})"
        )
