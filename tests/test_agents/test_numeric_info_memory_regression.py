import pytest

from src.agents.ai_agent import AIAgent, Persona
from src.llm.base_backend import LLMBackend, LLMResponse, Message
from src.state.game_state import ChatMessage, GameEvent, GamePhase, GameState, PlayerState, Team, Visibility


class DummyBackend(LLMBackend):
    async def generate(self, system_prompt: str, messages: list[Message], **kwargs) -> LLMResponse:
        return LLMResponse(content="{}", tool_calls=[])

    def get_model_name(self) -> str:
        return "dummy"


def _agent_ctx(agent: AIAgent, state: GameState):
    visible_state = agent._build_visible_state(state)
    legal_context = agent._build_legal_action_context(state, visible_state)
    return visible_state, legal_context


@pytest.mark.asyncio
async def test_empath_info_survives_phase_archive_and_enters_context():
    agent = AIAgent("p2", "Empath", DummyBackend(), Persona("谨慎信息位", "平稳"))
    state = GameState(
        phase=GamePhase.NIGHT,
        round_number=2,
        day_number=2,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            PlayerState(player_id="p1", name="Left", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p2", name="Empath", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="p3", name="Right", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p4", name="Far", role_id="chef", team=Team.GOOD),
        ),
    )
    agent.synchronize_role(state.get_player("p2"))
    visible_state, _ = _agent_ctx(agent, state)
    await agent.observe_event(
        GameEvent(
            event_type="private_info_delivered",
            phase=GamePhase.NIGHT,
            round_number=2,
            target="p2",
            visibility=Visibility.PRIVATE,
            payload={"type": "empath_info", "title": "共情者信息", "lines": ["你存活的邻座中，邪恶玩家数量：1。"]},
        ),
        visible_state,
    )
    await agent.archive_phase_memory(visible_state)
    context = agent.working_memory.get_recent_context()
    assert "你确认掌握的高可信私密信息" in context
    assert "共情者信息: 你存活的邻座中，邪恶玩家数量：1。" in context


@pytest.mark.asyncio
async def test_chef_info_can_create_verifiable_scoring_difference():
    agent = AIAgent("p1", "Chef", DummyBackend(), Persona("谨慎信息位", "平稳"))
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=2,
        day_number=2,
        players=(
            PlayerState(player_id="p1", name="Chef", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p3", name="Charlie", role_id="imp", team=Team.EVIL),
        ),
        chat_history=(
            ChatMessage(speaker="p2", content="Charlie 很可疑。", phase=GamePhase.DAY_DISCUSSION, round_number=2),
        ),
    )
    agent.synchronize_role(state.get_player("p1"))
    visible_state, legal_context = _agent_ctx(agent, state)
    await agent.observe_event(
        GameEvent(
            event_type="private_info_delivered",
            phase=GamePhase.FIRST_NIGHT,
            round_number=1,
            target="p1",
            visibility=Visibility.PRIVATE,
            payload={"type": "chef_info", "title": "厨师信息", "lines": ["相邻的邪恶玩家对数：1。"]},
        ),
        visible_state,
    )
    context = agent._build_action_context(visible_state, legal_context, "speak")
    assert "作为厨师，你的高可信首夜结果是" in context
    assert "相邻的邪恶玩家对数：1。" in context


@pytest.mark.asyncio
async def test_high_confidence_numeric_info_is_not_overwritten_by_public_noise():
    agent = AIAgent("p2", "Empath", DummyBackend(), Persona("谨慎信息位", "平稳"))
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=2,
        day_number=2,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            PlayerState(player_id="p1", name="Left", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p2", name="Empath", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="p3", name="Right", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p4", name="Far", role_id="chef", team=Team.GOOD),
        ),
        chat_history=(
            ChatMessage(speaker="p4", content="我觉得 Left 是好人。", phase=GamePhase.DAY_DISCUSSION, round_number=2),
        ),
    )
    agent.synchronize_role(state.get_player("p2"))
    visible_state, _ = _agent_ctx(agent, state)
    await agent.observe_event(
        GameEvent(
            event_type="private_info_delivered",
            phase=GamePhase.NIGHT,
            round_number=2,
            target="p2",
            visibility=Visibility.PRIVATE,
            payload={"type": "empath_info", "title": "共情者信息", "lines": ["你存活的邻座中，邪恶玩家数量：2。"]},
        ),
        visible_state,
    )
    await agent.observe_event(
        GameEvent(
            event_type="player_speaks",
            phase=GamePhase.DAY_DISCUSSION,
            round_number=2,
            actor="p4",
            visibility=Visibility.PUBLIC,
            payload={"content": "我觉得 Left 是好人。"},
        ),
        visible_state,
    )
    await agent.archive_phase_memory(visible_state)
    context = agent.working_memory.get_recent_context()
    assert "你存活的邻座中，邪恶玩家数量：2。" in context
    assert "公开场上的普通信息" in context
