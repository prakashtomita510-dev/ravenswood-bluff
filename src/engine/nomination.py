"""
提名与投票系统 (Nomination Manager)

管理白天阶段的提名、投票和处决逻辑。
"""

from __future__ import annotations

import logging
from typing import Optional

from src.state.game_state import GameEvent, GamePhase, GameState, Visibility
from src.engine.rule_engine import RuleEngine

logger = logging.getLogger(__name__)


class NominationManager:
    """
    负责处理提名、投票流程和处决决算。
    这是无状态的管理器，接受 GameState 并返回新的 GameState 和事件。
    """

    @staticmethod
    def nominate(
        game_state: GameState,
        nominator_id: str,
        nominee_id: str,
    ) -> tuple[GameState, list[GameEvent]]:
        """发起提名"""
        is_legal, reason = RuleEngine.can_nominate(game_state, nominator_id, nominee_id)
        if not is_legal:
            raise ValueError(f"提名无效: {reason}")

        # 记录今天已经被提名和发起提名的人
        new_nominations_today = tuple(list(game_state.nominations_today) + [nominator_id])
        new_nominees_today = tuple(list(game_state.nominees_today) + [nominee_id])
        
        new_state = game_state.with_update(
            current_nominator=nominator_id,
            current_nominee=nominee_id,
            nominations_today=new_nominations_today,
            nominees_today=new_nominees_today,
            votes_today={},  # 清空本次投票记录
        )
        
        event = GameEvent(
            event_type="nomination",
            phase=GamePhase.NOMINATION,
            round_number=game_state.round_number,
            actor=nominator_id,
            target=nominee_id,
            visibility=Visibility.PUBLIC,
        )
        
        return new_state.with_event(event), [event]

    @staticmethod
    def cast_vote(
        game_state: GameState,
        voter_id: str,
        vote: bool,
    ) -> tuple[GameState, list[GameEvent]]:
        """投出一票"""
        is_legal, reason = RuleEngine.can_vote(game_state, voter_id)
        if not is_legal:
            raise ValueError(f"投票无效: {reason}")

        votes = dict(game_state.votes_today)
        votes[voter_id] = vote

        new_state = game_state.with_update(votes_today=votes)
        
        event = GameEvent(
            event_type="vote",
            phase=GamePhase.VOTING,
            round_number=game_state.round_number,
            actor=voter_id,
            target=game_state.current_nominee,
            payload={"vote": vote},
            visibility=Visibility.PUBLIC,
        )

        return new_state.with_event(event), [event]

    @staticmethod
    def resolve_voting_round(
        game_state: GameState,
    ) -> tuple[GameState, list[GameEvent]]:
        """
        结束当前的单人投票轮。
        检查票数是否足够将该玩家送上处决台，并返回提名阶段。
        这不会立即处决，因为一天可以有多次提名。
        """
        if game_state.phase != GamePhase.VOTING:
            return game_state, []

        nominee_id = game_state.current_nominee
        if not nominee_id:
            return game_state, []

        # 计算票数
        yes_votes = sum(1 for v in game_state.votes_today.values() if v is True)
        
        # 必须大于等于存活人数的一半才能上处决台
        votes_needed = max(1, game_state.alive_count // 2)
        
        # 血染钟楼的一天：可能有多个人上处决台，最终票数最高（且满足半数）的被处决
        # 我们需要在 GameState 中记录 "即将被处决的人及其票数"
        # 暂时将其存在 votes_today 或需要扩展的状态里
        # 这里简化：扩展一个状态逻辑 (需要改GameState，我们暂用 payload 事件记录)

        event = GameEvent(
            event_type="voting_result",
            phase=GamePhase.VOTING,
            round_number=game_state.round_number,
            target=nominee_id,
            payload={
                "yes_votes": yes_votes,
                "needed": votes_needed,
                "passed": yes_votes >= votes_needed
            },
            visibility=Visibility.PUBLIC,
        )

        # 消耗死者的选票
        new_state = game_state
        for voter_id, vote_val in game_state.votes_today.items():
            if vote_val is True:
                player = new_state.get_player(voter_id)
                if player and not player.is_alive and player.ghost_votes_remaining > 0:
                    new_state = new_state.with_player_update(
                        voter_id, 
                        ghost_votes_remaining=player.ghost_votes_remaining - 1,
                        has_used_dead_vote=True
                    )

        # 结束投票回到白天讨论阶段 (主要由 Orchestrator 的状态机控制切换)
        new_state = new_state.with_update(
            current_nominator=None,
            current_nominee=None,
        )
        new_state = new_state.with_event(event)

        return new_state, [event]
