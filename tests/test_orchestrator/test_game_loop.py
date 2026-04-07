"""Phase 3 测试 - 完整游戏循环"""

import pytest
from unittest.mock import AsyncMock

from src.orchestrator.game_loop import GameOrchestrator
from src.state.game_state import GameState, PlayerState, Team, GamePhase
from src.agents.base_agent import BaseAgent
from src.engine.roles.base_role import get_all_role_ids


# 简单的占位Agent，用于在测试中配合游戏循环
class ScriptedAgent(BaseAgent):
    def __init__(self, pid, name, actions):
        super().__init__(pid, name)
        self.actions = actions  # type -> index 取动作
        self.counters = {}
        
    async def act(self, game_state, action_type, **kwargs):
        c = self.counters.get(action_type, 0)
        lst = self.actions.get(action_type, [])
        if c < len(lst):
            self.counters[action_type] = c + 1
            return lst[c]
        return {"action": action_type}

    async def observe_event(self, event, game_state):
        pass

    async def think(self, prompt, game_state):
        return ""


@pytest.mark.asyncio
async def test_game_orchestrator_initialization():
    initial_state = GameState(
        players=(
            PlayerState(player_id="a1", name="Alice", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="a2", name="Bob", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="a3", name="Charlie", role_id="washerwoman", team=Team.GOOD),
        )
    )
    orch = GameOrchestrator(initial_state)
    assert orch.state.phase == GamePhase.SETUP
    
    agent1 = ScriptedAgent("a1", "Alice", {})
    orch.register_agent(agent1)
    
    assert agent1.role_id == "imp"
    assert agent1.team == Team.EVIL.value
    assert "a1" in orch.broker.agents


@pytest.mark.asyncio
async def test_game_loop_auto_execute_until_end():
    """测试完整运转游戏主循环一次（基于胜负判定机制直接让游戏结束）"""
    initial_state = GameState(
        players=(
            PlayerState(player_id="a1", name="A", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="a2", name="B", role_id="washerwoman", team=Team.GOOD),
        )
    )
    orch = GameOrchestrator(initial_state)
    
    # 注册 Agent
    # 恶魔每晚刀人
    a1 = ScriptedAgent("a1", "A", {
        "night_action": [{"action": "night_action", "target": "a2"}], # 第一晚无刀，但是没关系我们会跳过
        "speak": [{"action": "speak", "content": "hello"}],
    })
    
    a2 = ScriptedAgent("a2", "B", {})
    
    orch.register_agent(a1)
    orch.register_agent(a2)
    
    # 因为 2人存活 有一个是恶魔，测试胜负判定是否在一开始就触发
    winner = await orch.run_game_loop()
    
    # The VictoryChecker triggers EVIL win on <=2 players
    assert winner == Team.EVIL
    
    # 测试有日志
    assert len(orch.event_log.events) > 0
    
    # 测试快照已经落盘 (内存中)
    assert orch.snapshot_manager.count > 0
