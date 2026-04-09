"""提名与投票系统 (Nomination Manager)。"""

from __future__ import annotations

import logging

from src.engine.rule_engine import RuleEngine
from src.state.game_state import ExecutionCandidate, GameEvent, GamePhase, GameState, Visibility

logger = logging.getLogger(__name__)


class NominationManager:
    """单一真相源：负责提名、投票、候选记录与当日处决决算。"""

    @staticmethod
    def nominate(
        game_state: GameState,
        nominator_id: str,
        nominee_id: str,
        trace_id: str = "",
    ) -> tuple[GameState, list[GameEvent]]:
        is_legal, reason = RuleEngine.can_nominate(game_state, nominator_id, nominee_id)
        if not is_legal:
            raise ValueError(f"提名无效: {reason}")

        new_state = game_state.with_update(
            phase=GamePhase.VOTING,
            current_nominator=nominator_id,
            current_nominee=nominee_id,
            nominations_today=game_state.nominations_today + (nominator_id,),
            nominees_today=game_state.nominees_today + (nominee_id,),
            votes_today={},
        )
        event = GameEvent(
            event_type="nomination_started",
            phase=GamePhase.NOMINATION,
            round_number=game_state.round_number,
            trace_id=trace_id,
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
        trace_id: str = "",
    ) -> tuple[GameState, list[GameEvent]]:
        is_legal, reason = RuleEngine.can_vote(game_state, voter_id)
        if not is_legal:
            raise ValueError(f"投票无效: {reason}")

        votes = dict(game_state.votes_today)
        votes[voter_id] = vote
        new_state = game_state.with_update(votes_today=votes)
        event = GameEvent(
            event_type="vote_cast",
            phase=GamePhase.VOTING,
            round_number=game_state.round_number,
            trace_id=trace_id,
            actor=voter_id,
            target=game_state.current_nominee,
            payload={"vote": vote},
            visibility=Visibility.PUBLIC,
        )
        return new_state.with_event(event), [event]

    @staticmethod
    def resolve_voting_round(
        game_state: GameState,
        trace_id: str = "",
    ) -> tuple[GameState, list[GameEvent]]:
        if game_state.phase != GamePhase.VOTING or not game_state.current_nominee:
            return game_state, []

        yes_votes = sum(1 for v in game_state.votes_today.values() if v is True)
        votes_needed = RuleEngine.votes_required(game_state)
        passed = yes_votes >= votes_needed

        new_state = game_state
        for voter_id, vote_val in game_state.votes_today.items():
            if not vote_val:
                continue
            player = new_state.get_player(voter_id)
            if player and not player.is_alive and player.ghost_votes_remaining > 0:
                new_state = new_state.with_player_update(
                    voter_id,
                    ghost_votes_remaining=player.ghost_votes_remaining - 1,
                    has_used_dead_vote=True,
                )

        candidate = ExecutionCandidate(
            nominee_id=game_state.current_nominee,
            votes=yes_votes,
            nominator_id=game_state.current_nominator or "",
            passed=passed,
            trace_id=trace_id,
        )
        new_state = new_state.with_update(
            phase=GamePhase.NOMINATION,
            current_nominator=None,
            current_nominee=None,
            votes_today={},
            execution_candidates=new_state.execution_candidates + (candidate,),
        )
        event = GameEvent(
            event_type="voting_resolved",
            phase=GamePhase.VOTING,
            round_number=game_state.round_number,
            trace_id=trace_id,
            target=candidate.nominee_id,
            payload={
                "votes": yes_votes,
                "needed": votes_needed,
                "passed": passed,
            },
            visibility=Visibility.PUBLIC,
        )
        return new_state.with_event(event), [event]

    @staticmethod
    def finalize_execution(
        game_state: GameState,
        trace_id: str = "",
    ) -> tuple[GameState, list[GameEvent]]:
        candidate = RuleEngine.get_execution_candidate(game_state)
        if not candidate:
            event = GameEvent(
                event_type="execution_resolved",
                phase=GamePhase.EXECUTION,
                round_number=game_state.round_number,
                trace_id=trace_id,
                payload={"executed": None},
                visibility=Visibility.PUBLIC,
            )
            new_state = game_state.with_update(
                phase=GamePhase.EXECUTION,
                current_nominator=None,
                current_nominee=None,
                votes_today={},
                execution_candidates=(),
            ).with_event(event)
            return new_state, [event]

        nominee = game_state.get_player(candidate.nominee_id)
        payload = {"executed": candidate.nominee_id, "votes": candidate.votes}
        new_state = game_state.with_update(
            phase=GamePhase.EXECUTION,
            current_nominator=None,
            current_nominee=None,
            votes_today={},
            execution_candidates=(),
        )
        if nominee:
            new_state = new_state.with_player_update(candidate.nominee_id, is_alive=False)
            if nominee.true_role_id == "saint":
                from src.state.game_state import Team
                new_state = new_state.with_update(winning_team=Team.EVIL)
                payload["saint_triggered"] = True

        events: list[GameEvent] = []
        if nominee:
            death_event = GameEvent(
                event_type="player_death",
                phase=GamePhase.EXECUTION,
                round_number=game_state.round_number,
                trace_id=trace_id,
                target=candidate.nominee_id,
                payload={"reason": "execution"},
                visibility=Visibility.PUBLIC,
            )
            new_state = new_state.with_event(death_event)
            events.append(death_event)

        event = GameEvent(
            event_type="execution_resolved",
            phase=GamePhase.EXECUTION,
            round_number=game_state.round_number,
            trace_id=trace_id,
            target=candidate.nominee_id,
            payload=payload,
            visibility=Visibility.PUBLIC,
        )
        new_state = new_state.with_event(event)
        events.append(event)
        return new_state, events
