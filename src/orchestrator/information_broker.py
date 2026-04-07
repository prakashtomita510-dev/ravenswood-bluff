"""
信息代理 (Information Broker)

负责管理可见性，并在事件发生时向有权限看到的Agent进行广播和通知。
解决"恶魔在夜晚死人只有自己和说书人知道，但白天死人全村都知道"的问题。
"""

from __future__ import annotations

import logging
from typing import Optional

from src.agents.base_agent import BaseAgent
from src.state.game_state import GameEvent, GameState, Team, Visibility

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

    async def broadcast_event(self, event: GameEvent, game_state: GameState) -> None:
        """根据事件可见性路由到对应的 Agent"""
        if event.visibility == Visibility.PUBLIC:
            # 所有人都能看见
            for agent in self.agents.values():
                await agent.observe_event(event, game_state)
                
        elif event.visibility == Visibility.STORYTELLER_ONLY:
            # 只有当事人（主动引发/被动承受）或说书人（系统）知道。
            # 这里简化为：参与者 (actor/target) 如果有 agent 则知道
            if event.actor and event.actor in self.agents:
                await self.agents[event.actor].observe_event(event, game_state)
            if event.target and event.target != event.actor and event.target in self.agents:
                await self.agents[event.target].observe_event(event, game_state)

        elif event.visibility == Visibility.PRIVATE:
            # 指定的目标知道，通常用于发信息。这里默认是 target 知道
            if event.target and event.target in self.agents:
                await self.agents[event.target].observe_event(event, game_state)

        elif event.visibility == Visibility.TEAM_EVIL:
            # 所有的邪恶阵营都能看见
            evil_player_ids = {
                p.player_id for p in game_state.players if p.team == Team.EVIL
            }
            for pid in evil_player_ids:
                if pid in self.agents:
                    await self.agents[pid].observe_event(event, game_state)

        elif event.visibility == Visibility.TEAM_GOOD:
            # 好人阵营可见（类似）
            good_player_ids = {
                p.player_id for p in game_state.players if p.team == Team.GOOD
            }
            for pid in good_player_ids:
                if pid in self.agents:
                    await self.agents[pid].observe_event(event, game_state)
