"""Phase 2 测试 - Agent AI 与 推理、对话测试"""

import pytest
from unittest.mock import AsyncMock, patch

from src.agents.ai_agent import AIAgent, Persona
from src.agents.reasoning.deduction import DeductionEngine
from src.agents.dialogue.dialogue_manager import DialogueManager
from src.agents.memory.social_graph import SocialGraph
from src.agents.memory.working_memory import WorkingMemory
from src.llm.base_backend import LLMBackend, LLMResponse, Message
from src.state.game_state import ChatMessage, GameState, PlayerState, GameEvent, GamePhase, Team


class DummyBackend(LLMBackend):
    async def generate(self, system_prompt: str, messages: list[Message], **kwargs) -> LLMResponse:
        return LLMResponse(content="这是一个假象的LLM回复", tool_calls=[])
        
    def get_model_name(self) -> str:
        return "dummy-model"


@pytest.fixture
def dummy_agent():
    backend = DummyBackend()
    persona = Persona(description="村子的酒鬼", speaking_style="说话大舌头，含糊不清")
    agent = AIAgent(player_id="p1", name="Alice", backend=backend, persona=persona)
    return agent


@pytest.fixture
def dummy_state():
    players = (
        PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD),
        PlayerState(player_id="p2", name="Bob", role_id="imp", team=Team.EVIL),
    )
    return GameState(players=players, phase=GamePhase.DAY_DISCUSSION, round_number=1)


@pytest.mark.asyncio
async def test_agent_observe(dummy_agent, dummy_state):
    event = GameEvent(
        event_type="player_speaks",
        phase=GamePhase.DAY_DISCUSSION,
        round_number=1,
        actor="p2",
        payload={"content": "大家好我是好人"}
    )
    
    await dummy_agent.observe_event(event, dummy_state)
    
    assert not dummy_agent.working_memory.is_empty
    obs = dummy_agent.working_memory.observations[0]
    assert "大家好我是好人" in obs.content
    assert "Bob" in obs.content


@pytest.mark.asyncio
async def test_deduction_engine():
    # 测试推理引擎格式化Prompt与处理响应
    class MockBackendDeduction(DummyBackend):
        async def generate(self, system_prompt: str, messages: list[Message], **kwargs) -> LLMResponse:
            assert "washerwoman" in system_prompt
            assert "这是你的私人思考时刻" in system_prompt
            assert "day_discussion" in messages[0].content
            return LLMResponse(content="我觉得我是好人，Bob也像好人", tool_calls=[])

    engine = DeductionEngine(backend=MockBackendDeduction())
    
    wm = WorkingMemory()
    sg = SocialGraph(my_player_id="p1")
    
    me = PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD)
    state = GameState(phase=GamePhase.DAY_DISCUSSION, round_number=1, players=(me,))
    
    result = await engine.analyze_situation(
        game_state=state,
        me=me,
        working_memory=wm,
        episodic_summary="无历史",
        social_graph_summary=sg.get_graph_summary(),
        persona_desc="普通村民"
    )
    
    assert "我觉得我是好人" in result


@pytest.mark.asyncio
async def test_dialogue_manager():
    # 模拟LLM调用工具返回格式不兼容的问题或正常的工具调用
    class MockBackendDialogue(DummyBackend):
        async def generate(self, system_prompt: str, messages: list[Message], **kwargs) -> LLMResponse:
            # 必须验证传递了工具结构
            assert "tools" in kwargs
            tools = kwargs["tools"]
            assert len(tools) == 1
            assert tools[0].name == "speak"
            
            # 手工构造一个假的 ToolCall
            from src.llm.base_backend import ToolCall
            dummy_tc = ToolCall(function_name="speak", tool_call_id="call_123", arguments={"content": "我同意大家的看法", "tone": "calm", "target_player": "Bob"})
                
            return LLMResponse(content="", tool_calls=[dummy_tc])

    manager = DialogueManager(backend=MockBackendDialogue())
    wm = WorkingMemory()
    
    me = PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD)
    state = GameState(phase=GamePhase.DAY_DISCUSSION, round_number=1, players=(me,))
    
    res = await manager.generate_speech(
        game_state=state,
        me=me,
        working_memory=wm,
        social_graph_summary="",
        current_strategy="假装没用技能",
        persona={"description": "普通", "speaking_style": "随便"}
    )
    
    assert res["action"] == "speak"
    assert res["content"] == "我同意大家的看法"
    assert res["target_player"] == "Bob"


@pytest.mark.asyncio
async def test_ai_agent_fallback_nomination_returns_legal_target():
    class BrokenBackend(DummyBackend):
        async def generate(self, system_prompt: str, messages: list[Message], **kwargs) -> LLMResponse:
            return LLMResponse(content='{"action":"nominate","target":"nobody"}', tool_calls=[])

    agent = AIAgent(
        player_id="p1",
        name="Alice",
        backend=BrokenBackend(),
        persona=Persona(description="强势带节奏者", speaking_style="直接、喜欢推动局面"),
    )
    state = GameState(
        phase=GamePhase.NOMINATION,
        round_number=1,
        day_number=2,
        current_nominee=None,
        current_nominator=None,
        nominees_today=(),
        nominations_today=(),
        chat_history=(
            ChatMessage(speaker="p3", content="Bob 的解释有点怪", phase=GamePhase.DAY_DISCUSSION, round_number=1),
            ChatMessage(speaker="p1", content="Bob 这边我还是有点怀疑", phase=GamePhase.DAY_DISCUSSION, round_number=1),
            ChatMessage(speaker="p3", content="Bob 需要再解释一下", phase=GamePhase.DAY_DISCUSSION, round_number=1),
        ),
        event_log=(
            GameEvent(
                event_type="nomination_started",
                phase=GamePhase.NOMINATION,
                round_number=1,
                actor="p3",
                target="p2",
            ),
        ),
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p3", name="Charlie", role_id="chef", team=Team.GOOD),
        ),
    )

    decision = await agent.act(state, "nominate")
    assert decision["action"] == "nominate"
    assert decision["target"] == "p2"
    assert "怀疑度" in decision["reasoning"]


@pytest.mark.asyncio
async def test_ai_agent_nomination_intent_can_proactively_nominate():
    class PassiveBackend(DummyBackend):
        async def generate(self, system_prompt: str, messages: list[Message], **kwargs) -> LLMResponse:
            return LLMResponse(content='{"action":"none"}', tool_calls=[])

    agent = AIAgent(
        player_id="p1",
        name="Alice",
        backend=PassiveBackend(),
        persona=Persona(description="强势带节奏者", speaking_style="直接、喜欢推动局面"),
    )
    state = GameState(
        phase=GamePhase.NOMINATION,
        round_number=2,
        day_number=2,
        current_nominee=None,
        current_nominator=None,
        chat_history=(
            ChatMessage(speaker="p2", content="p3 的解释有点怪，我有点怀疑 p3。", phase=GamePhase.DAY_DISCUSSION, round_number=1),
            ChatMessage(speaker="p3", content="我还是觉得 p2 更可疑。", phase=GamePhase.DAY_DISCUSSION, round_number=1),
            ChatMessage(speaker="p1", content="我也觉得 p3 需要被提名。", phase=GamePhase.DAY_DISCUSSION, round_number=1),
            ChatMessage(speaker="p1", content="p3 真的很可疑，应该提名。", phase=GamePhase.DAY_DISCUSSION, round_number=1),
        ),
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="chef", team=Team.GOOD, is_alive=False),
            PlayerState(player_id="p3", name="Charlie", role_id="imp", team=Team.EVIL),
        ),
        nominations_today=(),
        nominees_today=(),
    )

    decision = await agent.act(state, "nomination_intent")
    assert decision["action"] == "nominate"
    assert decision["target"] == "p3"


@pytest.mark.asyncio
async def test_ai_agent_fallback_vote_remains_structured():
    class BrokenBackend(DummyBackend):
        async def generate(self, system_prompt: str, messages: list[Message], **kwargs) -> LLMResponse:
            return LLMResponse(content='{"action":"speak","content":"随便"}', tool_calls=[])

    agent = AIAgent(
        player_id="p1",
        name="Alice",
        backend=BrokenBackend(),
        persona=Persona(description="冷静村民", speaking_style="平稳"),
    )
    state = GameState(
        phase=GamePhase.VOTING,
        round_number=1,
        current_nominee="p2",
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="imp", team=Team.EVIL),
        ),
    )

    decision = await agent.act(state, "vote")
    assert decision["action"] == "vote"
    assert isinstance(decision["decision"], bool)
