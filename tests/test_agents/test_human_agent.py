"""Phase 4 - 人类代理测试"""

import pytest
import asyncio
import json
from src.agents.human_agent import HumanAgent
from src.state.game_state import GameState, GameEvent, GamePhase


@pytest.mark.asyncio
async def test_human_agent_act():
    messages = []
    
    async def mock_send(msg):
        messages.append(msg)
        
    agent = HumanAgent("p1", "Human", mock_send)
    state = GameState(phase=GamePhase.DAY_DISCUSSION, round_number=1)
    
    # 模拟后端请求 action，这会卡住等待前端回应
    act_task = asyncio.create_task(agent.act(state, "speak"))
    
    # 让出执行权，让 act 函数发消息
    await asyncio.sleep(0.01)
    
    # 验证是否发出了 action_request
    assert len(messages) == 1
    req = json.loads(messages[0])
    assert req["type"] == "action_request"
    assert req["action_type"] == "speak"
    
    # 模拟前端通过 WebSocket 发送回来
    response_msg = {
        "type": "action_response",
        "payload": {
            "action": "speak",
            "content": "大家好我是预言家"
        }
    }
    await agent.receive_client_message(json.dumps(response_msg))
    
    # 获取后端等到的动作
    result = await act_task
    assert result["content"] == "大家好我是预言家"


@pytest.mark.asyncio
async def test_human_agent_observe():
    messages = []
    async def mock_send(msg):
        messages.append(msg)
        
    agent = HumanAgent("p2", "Human", mock_send)
    state = GameState(phase=GamePhase.NIGHT, round_number=1)
    event = GameEvent(event_type="test_event", round_number=1, phase=GamePhase.NIGHT)
    
    await agent.observe_event(event, state)
    
    # 验证事件推送给了客户端
    assert len(messages) == 1
    req = json.loads(messages[0])
    assert req["type"] == "event_update"
    assert req["event"]["event_type"] == "test_event"
