"""
规则引擎 (Rule Engine)

负责校验游戏中行动的合法性。
"""

from __future__ import annotations

import logging
from typing import Optional

from src.state.game_state import GamePhase, GameState, PlayerState

logger = logging.getLogger(__name__)


class RuleEngine:
    """
    负责游戏中各项行为的合法性检查
    """

    @staticmethod
    def can_nominate(
        game_state: GameState,
        nominator_id: str,
        nominee_id: str,
    ) -> tuple[bool, str]:
        """
        检查提名合法性

        Args:
            game_state: 当前游戏状态
            nominator_id: 提名者
            nominee_id: 被提名者

        Returns:
            (是否合法, 错误/拒绝原因)
        """
        # 1. 阶段检查
        if game_state.phase != GamePhase.NOMINATION:
            return False, f"当前不是提名阶段 ({game_state.phase.value})"

        nominator = game_state.get_player(nominator_id)
        nominee = game_state.get_player(nominee_id)

        if not nominator:
            return False, "提名者不存在"
        if not nominee:
            return False, "被提名者不存在"

        # 2. 存活检查
        if not nominator.is_alive:
            return False, "死亡玩家不能发起提名"
        
        if not nominee.is_alive:
            # 允许提名死人（有些特殊情况下或村规，但默认情况通常不能被处决，不过机制上一般不严格限制提名死人，
            # 官方规则通常允许提名死玩家，但死玩家不能被再次处决，这里默认死亡玩家不能被提名以简化）
            return False, "不能提名已死亡的玩家"

        # 3. 每日限制检查
        if nominator_id in game_state.nominations_today:
            return False, "每位玩家每天只能发起一次提名"
        
        # 被提名者每天只能被提名一次（默认规则）
        if nominee_id == game_state.current_nominee:
            return False, f"玩家 {nominee.name} 正在被提名中"
            
        # 检查今天是否已经被提名过（需要在game_state中记录，暂时假设这里只查记录）
        # 血染规则：每个人每天可以被提名一次，每次可以提名一个人
        if hasattr(game_state, "nominees_today") and nominee_id in getattr(game_state, "nominees_today", []):
            return False, f"玩家 {nominee.name} 今天已经被提名过了"

        return True, ""

    @staticmethod
    def can_vote(
        game_state: GameState,
        voter_id: str,
    ) -> tuple[bool, str]:
        """
        检查投票合法性
        """
        if game_state.phase != GamePhase.VOTING:
            return False, f"当前不是投票阶段 ({game_state.phase.value})"
            
        if not game_state.current_nominee:
            return False, "当前没有正在进行的提名"

        voter = game_state.get_player(voter_id)
        if not voter:
            return False, "投票者不存在"

        if not voter.can_vote:
            return False, "该玩家已耗尽选票（死亡且使用了最后一次投票权）"

        return True, ""

    @staticmethod
    def can_speak(
        game_state: GameState,
        speaker_id: str,
    ) -> tuple[bool, str]:
        """
        检查发言合法性 (白天讨论阶段等)
        """
        if game_state.phase not in (GamePhase.DAY_DISCUSSION, GamePhase.NOMINATION, GamePhase.VOTING):
            return False, "当前阶段不可公开发言"
            
        speaker = game_state.get_player(speaker_id)
        if not speaker:
            return False, "发言者不存在"
            
        # 官方规则：死亡玩家可以一直说话（只是不能提名，只能投一次票）
        return True, ""
