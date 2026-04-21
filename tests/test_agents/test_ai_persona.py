"""AI 玩家 persona 个性化测试。"""

from __future__ import annotations

import pytest

from src.agents.ai_agent import AIAgent, Persona
from src.llm.base_backend import LLMBackend, LLMResponse, Message
from src.state.game_state import ChatMessage, GameEvent, GameState, GamePhase, PlayerState, Team


class CapturingBackend(LLMBackend):
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[str] = []

    async def generate(self, system_prompt: str, messages: list[Message], **kwargs) -> LLMResponse:
        self.calls.append(system_prompt)
        return LLMResponse(content=self.content, tool_calls=[])

    def get_model_name(self) -> str:
        return "capturing-model"


def _agent_ctx(agent: AIAgent, state: GameState):
    visible_state = agent._build_visible_state(state)
    legal_context = agent._build_legal_action_context(state, visible_state)
    return visible_state, legal_context


def _build_state() -> GameState:
    players = (
        PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD),
        PlayerState(player_id="p2", name="Bob", role_id="imp", team=Team.EVIL),
        PlayerState(player_id="p3", name="Cathy", role_id="chef", team=Team.GOOD),
    )
    return GameState(
        players=players,
        phase=GamePhase.DAY_DISCUSSION,
        round_number=1,
        day_number=1,
    )


def _build_signal_state() -> GameState:
    players = (
        PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD),
        PlayerState(player_id="p2", name="Bob", role_id="imp", team=Team.EVIL),
        PlayerState(player_id="p3", name="Cathy", role_id="chef", team=Team.GOOD),
    )
    chat_history = (
        ChatMessage(speaker="p3", content="我觉得 Bob 的解释有点怪", phase=GamePhase.DAY_DISCUSSION, round_number=1),
        ChatMessage(speaker="p1", content="Bob 这边我还是有点怀疑", phase=GamePhase.DAY_DISCUSSION, round_number=1),
        ChatMessage(speaker="p3", content="Bob 需要再解释一下", phase=GamePhase.DAY_DISCUSSION, round_number=1),
    )
    event_log = (
        GameEvent(
            event_type="nomination_started",
            phase=GamePhase.NOMINATION,
            round_number=1,
            actor="p3",
            target="p2",
            payload={"vote": True},
        ),
    )
    return GameState(
        players=players,
        phase=GamePhase.NOMINATION,
        round_number=1,
        day_number=2,
        current_nominee=None,
        current_nominator=None,
        nominees_today=(),
        nominations_today=(),
        chat_history=chat_history,
        event_log=event_log,
    )


@pytest.mark.asyncio
async def test_ai_persona_prompt_includes_stable_role_hint_and_action_guidance():
    backend = CapturingBackend('{"action":"speak","content":"我先听听大家怎么说","tone":"calm","reasoning":"ok"}')
    agent = AIAgent(
        player_id="p1",
        name="Alice",
        backend=backend,
        persona=Persona(description="谨慎观察者", speaking_style="短句，先观察再表态"),
    )
    state = _build_state()
    agent.synchronize_role(state.get_player("p1"))

    visible_state, legal_context = _agent_ctx(agent, state)
    await agent.act(visible_state, "speak", legal_context=legal_context)

    assert backend.calls, "backend 应该收到系统提示词"
    prompt = backend.calls[-1]
    assert "谨慎确认信息" in prompt
    assert "短句，先观察再表态" in prompt
    assert "人格签名" in prompt
    assert "当前动作风格" in prompt
    assert "保持同一个稳定的人设" in prompt
    assert agent.persona_signature
    assert agent.persona_profile["voice_anchor"]
    assert agent.persona_profile["decision_style"]


@pytest.mark.asyncio
async def test_ai_persona_profile_differs_by_player_id():
    backend_a = CapturingBackend('{"action":"speak","content":"A","tone":"calm","reasoning":"ok"}')
    backend_b = CapturingBackend('{"action":"speak","content":"B","tone":"calm","reasoning":"ok"}')

    agent_a = AIAgent(
        player_id="p1",
        name="Alice",
        backend=backend_a,
        persona=Persona(description="同一套性格", speaking_style="同一套说法"),
    )
    agent_b = AIAgent(
        player_id="p2",
        name="Alice",
        backend=backend_b,
        persona=Persona(description="同一套性格", speaking_style="同一套说法"),
    )
    state = _build_state()
    agent_a.synchronize_role(state.get_player("p1"))
    agent_b.synchronize_role(state.get_player("p2"))

    visible_state_a, legal_context_a = _agent_ctx(agent_a, state)
    visible_state_b, legal_context_b = _agent_ctx(agent_b, state)
    await agent_a.act(visible_state_a, "speak", legal_context=legal_context_a)
    await agent_b.act(visible_state_b, "speak", legal_context=legal_context_b)

    assert agent_a.persona_signature != agent_b.persona_signature
    assert agent_a.persona_profile != agent_b.persona_profile
    assert backend_a.calls[-1] != backend_b.calls[-1]


@pytest.mark.asyncio
async def test_ai_persona_nomination_skips_when_signal_is_weak():
    class BrokenBackend(CapturingBackend):
        async def generate(self, system_prompt: str, messages: list[Message], **kwargs) -> LLMResponse:
            self.calls.append(system_prompt)
            return LLMResponse(content="not-json", tool_calls=[])

    backend = BrokenBackend("not-json")
    agent = AIAgent(
        player_id="p1",
        name="Alice",
        backend=backend,
        persona=Persona(
            description="果断但不冲动",
            speaking_style="先看局面再说",
            decision_style="谨慎推进，只有在证据够强时才主动出手。",
        ),
    )
    state = _build_state()
    agent.synchronize_role(state.get_player("p1"))

    visible_state, legal_context = _agent_ctx(agent, state)
    decision = await agent.act(visible_state, "nominate", legal_context=legal_context)

    assert decision["action"] in {"none", "nominate"}
    assert decision["action"] == "none"
    assert decision["target"] is None


@pytest.mark.asyncio
async def test_ai_persona_nomination_fires_when_signal_is_strong():
    class BrokenBackend(CapturingBackend):
        async def generate(self, system_prompt: str, messages: list[Message], **kwargs) -> LLMResponse:
            self.calls.append(system_prompt)
            return LLMResponse(content="not-json", tool_calls=[])

    agent = AIAgent(
        player_id="p1",
        name="Alice",
        backend=BrokenBackend("not-json"),
        persona=Persona(
            description="强势带节奏者",
            speaking_style="直接、喜欢推动局面",
            decision_style="谨慎推进，只有在证据够强时才主动出手。",
        ),
    )
    state = _build_signal_state()
    agent.synchronize_role(state.get_player("p1"))
    agent.social_graph.init_player("p2", "Bob")
    agent.social_graph.update_trust("p2", -0.9)

    visible_state, legal_context = _agent_ctx(agent, state)
    decision = await agent.act(visible_state, "nominate", legal_context=legal_context)

    assert decision["action"] == "nominate"
    assert decision["target"] == "p2"
    assert "怀疑度" in decision["reasoning"]
    assert "阈值" in decision["reasoning"]


@pytest.mark.asyncio
async def test_ai_persona_vote_respects_suspicion_threshold():
    class BrokenBackend(CapturingBackend):
        async def generate(self, system_prompt: str, messages: list[Message], **kwargs) -> LLMResponse:
            self.calls.append(system_prompt)
            return LLMResponse(content="not-json", tool_calls=[])

    agent = AIAgent(
        player_id="p1",
        name="Alice",
        backend=BrokenBackend("not-json"),
        persona=Persona(
            description="会先看风险再行动",
            speaking_style="克制",
            decision_style="谨慎推进，只有在证据够强时才主动出手。",
        ),
    )
    state = GameState(
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="imp", team=Team.EVIL),
        ),
        phase=GamePhase.VOTING,
        round_number=3,
        day_number=1,
        current_nominee="p2",
        chat_history=(
            ChatMessage(speaker="p1", content="Bob 现在看起来不太对", phase=GamePhase.VOTING, round_number=3),
        ),
    )
    agent.synchronize_role(state.get_player("p1"))

    visible_state, legal_context = _agent_ctx(agent, state)
    decision = await agent.act(visible_state, "vote", legal_context=legal_context)

    assert decision["action"] == "vote"
    assert isinstance(decision["decision"], bool)
    assert decision["decision"] is False
    assert "怀疑度" in decision["reasoning"]
