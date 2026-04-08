"""
信息代理 (Information Broker)

负责管理可见性，并在事件发生时向有权限看到的Agent进行广播和通知。
解决"恶魔在夜晚死人只有自己和说书人知道，但白天死人全村都知道"的问题。
"""

from __future__ import annotations

import logging
from typing import Optional

from src.agents.base_agent import BaseAgent
from src.state.game_state import GameEvent, GameState, PrivatePlayerView, Team, Visibility

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
            true_role_id=player.true_role_id or player.role_id,
            perceived_role_id=player.perceived_role_id or player.fake_role or player.role_id,
            public_claim_role_id=player.public_claim_role_id,
            current_team=player.current_team or player.team,
            fake_role=player.fake_role,
            is_alive=player.is_alive,
            is_poisoned=player.is_poisoned,
            is_drunk=player.is_drunk,
            storyteller_notes=player.storyteller_notes,
            ongoing_effects=player.ongoing_effects,
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
                await self.agents[pid].observe_event(event, game_state)
