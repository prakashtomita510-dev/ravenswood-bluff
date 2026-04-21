"""Phase 4 - 人类代理测试"""

import pytest
import asyncio
import json
from src.agents.human_agent import HumanAgent
from src.state.game_state import AgentActionLegalContext, AgentVisibleState, GameEvent, GamePhase


@pytest.mark.asyncio
async def test_human_agent_act():
    messages = []
    
    async def mock_send(msg):
        messages.append(msg)
        
    agent = HumanAgent("p1", "Human", mock_send)
    state = AgentVisibleState(game_id="g1", phase=GamePhase.DAY_DISCUSSION, round_number=1, day_number=1)
    legal_context = AgentActionLegalContext()
    
    # 模拟后端请求 action，这会卡住等待前端回应
    act_task = asyncio.create_task(agent.act(state, "speak", legal_context=legal_context))
    
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
async def test_human_agent_action_request_includes_retry_context():
    messages = []

    async def mock_send(msg):
        messages.append(msg)

    agent = HumanAgent("p1", "Human", mock_send)
    state = AgentVisibleState(game_id="g1", phase=GamePhase.NIGHT, round_number=1, day_number=1)
    legal_context = AgentActionLegalContext(required_targets=2, can_target_self=True)

    act_task = asyncio.create_task(
        agent.act(
            state,
            "night_action",
            legal_context=legal_context,
            reminder="请选择两个目标后再提交。",
            retry_count=2,
            last_error="目标数量不足",
        )
    )

    await asyncio.sleep(0.01)

    req = json.loads(messages[0])
    assert req["context"]["required_targets"] == 2
    assert req["context"]["can_target_self"] is True
    assert req["context"]["reminder"] == "请选择两个目标后再提交。"
    assert req["context"]["retry_count"] == 2
    assert req["context"]["last_error"] == "目标数量不足"

    await agent.receive_client_message(json.dumps({
        "type": "action_response",
        "payload": {"action": "night_action", "targets": ["p2", "p3"], "target": "p2"},
    }))
    result = await act_task
    assert result["targets"] == ["p2", "p3"]


@pytest.mark.asyncio
async def test_human_agent_observe():
    messages = []
    async def mock_send(msg):
        messages.append(msg)
        
    agent = HumanAgent("p2", "Human", mock_send)
    state = AgentVisibleState(game_id="g1", phase=GamePhase.NIGHT, round_number=1, day_number=1)
    event = GameEvent(event_type="test_event", round_number=1, phase=GamePhase.NIGHT)
    
    await agent.observe_event(event, state)
    
    # 验证事件推送给了客户端
    assert len(messages) == 1
    req = json.loads(messages[0])
    assert req["type"] == "event_update"
    assert req["event"]["event_type"] == "test_event"
