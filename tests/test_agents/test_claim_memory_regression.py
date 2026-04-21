import pytest

from src.agents.ai_agent import AIAgent, Persona
from src.llm.base_backend import LLMBackend, LLMResponse, Message
from src.state.game_state import GameEvent, GamePhase, GameState, PlayerState, Team, Visibility


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
async def test_claim_history_tracks_self_claim_then_denial_across_multiple_days():
    agent = AIAgent("p1", "Alice", DummyBackend(), Persona("谨慎村民", "平稳"))
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=1,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="washerwoman", team=Team.GOOD),
        ),
    )
    visible_state, _ = _agent_ctx(agent, state)
    await agent.observe_event(
        GameEvent(
            event_type="player_speaks",
            phase=GamePhase.DAY_DISCUSSION,
            round_number=1,
            actor="p2",
            visibility=Visibility.PUBLIC,
            payload={"content": "我跳预言家。"},
        ),
        visible_state,
    )

    day2 = state.model_copy(update={"day_number": 2, "round_number": 2})
    visible_day2, _ = _agent_ctx(agent, day2)
    await agent.observe_event(
        GameEvent(
            event_type="player_speaks",
            phase=GamePhase.DAY_DISCUSSION,
            round_number=2,
            actor="p2",
            visibility=Visibility.PUBLIC,
            payload={"content": "我什么时候说我是预言家了？"},
        ),
        visible_day2,
    )

    bob = agent.social_graph.get_profile("p2")
    assert bob is not None
    assert len(bob.claim_history) == 2
    assert bob.claim_history[0].claim_type == "self_claim"
    assert bob.claim_history[1].claim_type == "denial"


@pytest.mark.asyncio
async def test_self_claim_with_named_players_does_not_assign_claimed_role_to_mentioned_players():
    agent = AIAgent("p1", "Alice", DummyBackend(), Persona("谨慎村民", "平稳"))
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=1,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="h1", name="Human", role_id="investigator", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p3", name="Charlie", role_id="librarian", team=Team.GOOD),
        ),
    )
    visible_state, _ = _agent_ctx(agent, state)
    await agent.observe_event(
        GameEvent(
            event_type="player_speaks",
            phase=GamePhase.DAY_DISCUSSION,
            round_number=1,
            actor="h1",
            visibility=Visibility.PUBLIC,
            payload={"content": "我跳调查员，我怀疑 Bob 和 Charlie 里有问题。"},
        ),
        visible_state,
    )

    human = agent.social_graph.get_profile("h1")
    bob = agent.social_graph.get_profile("p2")
    charlie = agent.social_graph.get_profile("p3")
    assert human is not None and human.claimed_role_id == "investigator"
    assert bob is None or bob.claimed_role_id is None
    assert charlie is None or charlie.claimed_role_id is None


@pytest.mark.asyncio
async def test_public_claim_remains_visible_in_summary_after_phase_archive():
    agent = AIAgent("p1", "Alice", DummyBackend(), Persona("谨慎村民", "平稳"))
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=1,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="fortune_teller", team=Team.GOOD),
        ),
    )
    visible_state, _ = _agent_ctx(agent, state)
    await agent.observe_event(
        GameEvent(
            event_type="player_speaks",
            phase=GamePhase.DAY_DISCUSSION,
            round_number=1,
            actor="p2",
            visibility=Visibility.PUBLIC,
            payload={"content": "我跳预言家。"},
        ),
        visible_state,
    )
    await agent.archive_phase_memory(visible_state)

    context = agent.working_memory.get_recent_context()
    assert "公开场上的普通信息" in context
    assert "Bob 公开跳身份为 预言家" in context
    assert "身份发言记录" in agent.social_graph.get_graph_summary()
