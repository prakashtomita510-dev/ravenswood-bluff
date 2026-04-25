"""
信息代理 (Information Broker)

负责管理可见性，并在事件发生时向有权限看到的Agent进行广播和通知。
解决"恶魔在夜晚死人只有自己和说书人知道，但白天死人全村都知道"的问题。
"""

from __future__ import annotations

import logging
from typing import Optional

from src.agents.base_agent import BaseAgent
from src.engine.rule_engine import RuleEngine
from src.state.game_state import (
    AgentActionLegalContext,
    AgentVisibleState,
    GameEvent,
    GamePhase,
    GameState,
    PrivatePlayerView,
    Team,
    Visibility,
    VisiblePlayerInfo,
)

logger = logging.getLogger(__name__)


class InformationBroker:
    """
    基于 Visibility 的信息分发器。
    通常订阅 EventBus，或者由 Orchestrator 显式调用。
    """

    def __init__(self) -> None:
        # pid -> agent
        self.agents: dict[str, BaseAgent] = {}

    def register_agent(self, agent: BaseAgent) -> None:
        self.agents[agent.player_id] = agent

    def unregister_agent(self, player_id: str) -> None:
        if player_id in self.agents:
            del self.agents[player_id]

    def get_private_view(self, player_id: str, game_state: GameState) -> PrivatePlayerView | None:
        player = game_state.get_player(player_id)
        if not player:
            return None
        return PrivatePlayerView(
            player_id=player.player_id,
            name=player.name,
            perceived_role_id=player.perceived_role_id or player.fake_role or player.role_id,
            public_claim_role_id=player.public_claim_role_id,
            current_team=player.current_team or player.team,
            is_alive=player.is_alive,
            ghost_votes_remaining=player.ghost_votes_remaining,
        )

    def _is_event_visible_to_player(self, player_id: str, event: GameEvent, game_state: GameState) -> bool:
        player = game_state.get_player(player_id)
        if not player:
            return False
        team = (player.current_team or player.team).value
        if event.visibility == Visibility.PUBLIC:
            return True
        if event.visibility == Visibility.STORYTELLER_ONLY:
            storyteller_id = game_state.config.storyteller_client_id if game_state.config else None
            return player_id in {event.actor, event.target, storyteller_id}
        if event.visibility == Visibility.PRIVATE:
            storyteller_id = game_state.config.storyteller_client_id if game_state.config else None
            return player_id in {event.target, storyteller_id}
        if event.visibility == Visibility.TEAM_EVIL:
            return team == Team.EVIL.value
        if event.visibility == Visibility.TEAM_GOOD:
            return team == Team.GOOD.value
        return False

    def _is_chat_visible_to_player(self, player_id: str, message) -> bool:
        if message.speaker == player_id:
            return True
        recipients = getattr(message, "recipient_ids", None)
        if not recipients:
            return True
        return player_id in recipients

    def get_visible_state(self, player_id: str, game_state: GameState) -> AgentVisibleState | None:
        private_view = self.get_private_view(player_id, game_state)
        if not private_view:
            return None
        return AgentVisibleState(
            game_id=game_state.game_id,
            phase=game_state.phase,
            round_number=game_state.round_number,
            day_number=game_state.day_number,
            self_view=private_view,
            players=tuple(
                VisiblePlayerInfo(
                    player_id=player.player_id,
                    name=player.name,
                    is_alive=player.is_alive,
                )
                for player in game_state.players
            ),
            current_nominee=game_state.current_nominee,
            current_nominator=game_state.current_nominator,
            seat_order=game_state.seat_order or tuple(player.player_id for player in game_state.players),
            nominations_today=game_state.nominations_today,
            nominees_today=game_state.nominees_today,
            yes_votes=sum(1 for vote in game_state.votes_today.values() if vote is True),
            voted_player_ids=tuple(game_state.votes_today.keys()),
            public_chat_history=tuple(
                message for message in game_state.chat_history if self._is_chat_visible_to_player(player_id, message)
            ),
            visible_event_log=tuple(
                event for event in game_state.event_log if self._is_event_visible_to_player(player_id, event, game_state)
            ),
        )

    def get_action_legal_context(
        self,
        player_id: str,
        game_state: GameState,
        visible_state: AgentVisibleState | None = None,
    ) -> AgentActionLegalContext:
        visible_state = visible_state or self.get_visible_state(player_id, game_state)
        nomination_targets: list[str] = []
        for candidate in game_state.players:
            if candidate.player_id == player_id:
                continue
            allowed, _ = RuleEngine.can_nominate(game_state, player_id, candidate.player_id)
            if allowed:
                nomination_targets.append(candidate.player_id)
        
        # 始终为人类玩家展示“不提名”选项（只要该角色有提名权限）
        if nomination_targets:
            nomination_targets.append("not_nominating")
        night_targets = [
            player.player_id
            for player in game_state.get_alive_players()
            if player.player_id != player_id
        ]
        voters_so_far = set(game_state.votes_today.keys())
        seat_order = visible_state.seat_order if visible_state else (game_state.seat_order or tuple(p.player_id for p in game_state.players))
        remaining_voters = [pid for pid in seat_order if pid not in voters_so_far]

        # 动态获取角色行动要求
        required_targets = 1
        can_target_self = False
        can_slayer_shot = False
        from src.engine.roles.base_role import get_role_class
        from src.engine.roles.townsfolk import SlayerRole
        player = game_state.get_player(player_id)
        if player:
            role_cls = get_role_class(player.role_id)
            if role_cls:
                role_instance = role_cls()
                required_targets = role_instance.get_required_targets(game_state, game_state.phase)
                can_target_self = role_instance.can_target_self()
                
                # Slayer 特殊处理
                if player.role_id == "slayer":
                    if game_state.phase in (GamePhase.DAY_DISCUSSION, GamePhase.NOMINATION):
                        if not SlayerRole.has_used_shot(player):
                            can_slayer_shot = True

        return AgentActionLegalContext(
            legal_nomination_targets=tuple(nomination_targets),
            legal_night_targets=tuple(night_targets),
            votes_required=RuleEngine.votes_required(game_state),
            remaining_voters=tuple(remaining_voters),
            required_targets=required_targets,
            can_target_self=can_target_self,
            can_slayer_shot=can_slayer_shot,
        )

    async def broadcast_event(self, event: GameEvent, game_state: GameState) -> None:
        """根据事件可见性路由到对应的 Agent"""
        config = game_state.config
        st_id = config.storyteller_client_id if config else None
        
        # 2. 基础分发逻辑
        recipients = set()
        
        if event.visibility == Visibility.PUBLIC:
            recipients.update(self.agents.keys())
                
        elif event.visibility == Visibility.STORYTELLER_ONLY:
            # 只有当事人或说书人知道
            if event.actor: recipients.add(event.actor)
            if event.target: recipients.add(event.target)
            if st_id:
                recipients.add(st_id)

        elif event.visibility == Visibility.PRIVATE:
            # 仅当事人/目标知道，说书人也要知道
            if event.target: recipients.add(event.target)
            if st_id:
                recipients.add(st_id)

        elif event.visibility == Visibility.TEAM_EVIL:
            evil_player_ids = {p.player_id for p in game_state.players if (p.current_team or p.team) == Team.EVIL}
            recipients.update(evil_player_ids)
            if st_id:
                recipients.add(st_id)

        elif event.visibility == Visibility.TEAM_GOOD:
            good_player_ids = {p.player_id for p in game_state.players if (p.current_team or p.team) == Team.GOOD}
            recipients.update(good_player_ids)
            if st_id:
                recipients.add(st_id)

        # 执行分发
        for pid in recipients:
            if pid in self.agents:
                visible_state = self.get_visible_state(pid, game_state)
                if visible_state:
                    await self.agents[pid].observe_event(event, visible_state)
