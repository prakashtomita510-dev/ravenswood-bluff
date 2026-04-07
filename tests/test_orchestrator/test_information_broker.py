"""Phase 3 测试 - 信息代理"""

import pytest
from src.orchestrator.information_broker import InformationBroker
from src.state.game_state import GameState, PlayerState, GameEvent, GamePhase, Team, Visibility
from src.agents.base_agent import BaseAgent


class DummyAgent(BaseAgent):
    def __init__(self, pid: str, team: Team):
        super().__init__(player_id=pid, name=f"Agent_{pid}")
        self._team = team
        self.observed_events = []
    
    def synchronize_role(self, state):
        self.team = self._team.value

    async def act(self, game_state, action_type, **kwargs):
        return {}

    async def observe_event(self, event, game_state):
        self.observed_events.append(event)
        
    async def think(self, prompt, game_state):
        pass


@pytest.mark.asyncio
async def test_information_broker_visibility():
    broker = InformationBroker()
    
    a1 = DummyAgent("p1", Team.GOOD)
    a2 = DummyAgent("p2", Team.GOOD)
    a3 = DummyAgent("p3", Team.EVIL)
    
    broker.register_agent(a1)
    broker.register_agent(a2)
    broker.register_agent(a3)

    state = GameState(
        players=(
            PlayerState(player_id="p1", name="A1", role_id="r1", team=Team.GOOD),
            PlayerState(player_id="p2", name="A2", role_id="r2", team=Team.GOOD),
            PlayerState(player_id="p3", name="A3", role_id="r3", team=Team.EVIL),
        )
    )
    
    # 1. 公开事件
    e_pub = GameEvent(event_type="test", round_number=1, phase=GamePhase.DAY_DISCUSSION, visibility=Visibility.PUBLIC)
    await broker.broadcast_event(e_pub, state)
    assert e_pub in a1.observed_events
    assert e_pub in a2.observed_events
    assert e_pub in a3.observed_events
    
    # 2. 邪恶阵营事件
    e_evil = GameEvent(event_type="test", round_number=1, phase=GamePhase.NIGHT, visibility=Visibility.TEAM_EVIL)
    await broker.broadcast_event(e_evil, state)
    assert e_evil not in a1.observed_events
    assert e_evil not in a2.observed_events
    assert e_evil in a3.observed_events
    
    # 3. 私人事件 (发给 p2)
    e_priv = GameEvent(event_type="test", round_number=1, phase=GamePhase.NIGHT, target="p2", visibility=Visibility.PRIVATE)
    await broker.broadcast_event(e_priv, state)
    assert e_priv not in a1.observed_events
    assert e_priv in a2.observed_events
    assert e_priv not in a3.observed_events
    
    # 4. 说书人事件
    e_story = GameEvent(event_type="test", round_number=1, phase=GamePhase.NIGHT, actor="p1", target="p3", visibility=Visibility.STORYTELLER_ONLY)
    await broker.broadcast_event(e_story, state)
    # 参与者应该知道
    assert e_story in a1.observed_events
    assert e_story in a3.observed_events
    # 未参与者不知道
    assert e_story not in a2.observed_events
