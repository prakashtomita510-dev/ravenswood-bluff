"""Phase 2 测试 - Agent AI 与 推理、对话测试"""

import pytest
from unittest.mock import AsyncMock, patch

from src.agents.ai_agent import AIAgent, Persona
from src.agents.reasoning.deduction import DeductionEngine
from src.agents.dialogue.dialogue_manager import DialogueManager
from src.agents.memory.social_graph import SocialGraph
from src.agents.memory.working_memory import Observation, WorkingMemory
import src.engine.roles.townsfolk  # noqa: F401
from src.llm.base_backend import LLMBackend, LLMResponse, Message
from src.state.game_state import ChatMessage, GameEvent, GamePhase, GameState, PlayerState, Team, Visibility


class DummyBackend(LLMBackend):
    async def generate(self, system_prompt: str, messages: list[Message], **kwargs) -> LLMResponse:
        return LLMResponse(content="这是一个假象的LLM回复", tool_calls=[])
        
    def get_model_name(self) -> str:
        return "dummy-model"


def _agent_ctx(agent: AIAgent, state: GameState):
    visible_state = agent._build_visible_state(state)
    legal_context = agent._build_legal_action_context(state, visible_state)
    return visible_state, legal_context


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
    
    visible_state, _ = _agent_ctx(dummy_agent, dummy_state)
    await dummy_agent.observe_event(event, visible_state)
    
    assert not dummy_agent.working_memory.is_empty
    obs = dummy_agent.working_memory.observations[0]
    assert "大家好我是好人" in obs.content
    assert "Bob" in obs.content


@pytest.mark.asyncio
async def test_agent_private_info_is_pinned_in_anchor_memory(dummy_agent):
    state = GameState(
        phase=GamePhase.NIGHT,
        round_number=2,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="undertaker", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="imp", team=Team.EVIL),
        ),
    )
    dummy_agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(dummy_agent, state)
    event = GameEvent(
        event_type="private_info_delivered",
        phase=GamePhase.NIGHT,
        round_number=2,
        target="p1",
        visibility=Visibility.PRIVATE,
        payload={
            "type": "undertaker_info",
            "title": "送葬者信息",
            "lines": ["今天被处决的玩家身份是：小恶魔。"],
            "role_seen": "imp",
        },
    )

    await dummy_agent.observe_event(event, visible_state)

    assert any("送葬者信息" in fact for fact in dummy_agent.working_memory.anchor_facts)
    assert any("小恶魔" in fact for fact in dummy_agent.working_memory.anchor_facts)
    assert dummy_agent.working_memory.get_private_memory_summaries("undertaker_info") == ["送葬者信息: 今天被处决的玩家身份是：小恶魔。"]


@pytest.mark.asyncio
async def test_agent_records_public_role_claim_as_anchor_fact(dummy_agent):
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=2,
        day_number=2,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="chef", team=Team.GOOD),
        ),
    )
    dummy_agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(dummy_agent, state)
    event = GameEvent(
        event_type="player_speaks",
        phase=GamePhase.DAY_DISCUSSION,
        round_number=2,
        actor="p2",
        visibility=Visibility.PUBLIC,
        payload={"content": "我跳预言家，昨晚验了两个人。"},
    )

    await dummy_agent.observe_event(event, visible_state)

    bob = dummy_agent.social_graph.get_profile("p2")
    assert bob is not None
    assert bob.claimed_role_id == "fortune_teller"
    assert any("Bob 公开跳身份为 预言家" in fact for fact in dummy_agent.working_memory.anchor_facts)


@pytest.mark.asyncio
async def test_agent_does_not_turn_denial_into_role_claim(dummy_agent):
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=2,
        day_number=2,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="chef", team=Team.GOOD),
        ),
    )
    dummy_agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(dummy_agent, state)
    event = GameEvent(
        event_type="player_speaks",
        phase=GamePhase.DAY_DISCUSSION,
        round_number=2,
        actor="p2",
        visibility=Visibility.PUBLIC,
        payload={"content": "我什么时候说我是士兵了？你是不是记错了？"},
    )

    await dummy_agent.observe_event(event, visible_state)

    bob = dummy_agent.social_graph.get_profile("p2")
    assert bob is not None
    assert bob.claimed_role_id is None
    assert bob.claim_history
    assert bob.claim_history[-1].claim_type == "denial"
    assert bob.claim_history[-1].role_id == "soldier"


@pytest.mark.asyncio
async def test_agent_self_claim_with_mentions_does_not_assign_role_to_others(dummy_agent):
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=3,
        day_number=2,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="h1", name="Human", role_id="investigator", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p3", name="Charlie", role_id="imp", team=Team.EVIL),
        ),
    )
    dummy_agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(dummy_agent, state)
    event = GameEvent(
        event_type="player_speaks",
        phase=GamePhase.DAY_DISCUSSION,
        round_number=3,
        actor="h1",
        visibility=Visibility.PUBLIC,
        payload={"content": "我跳调查员，我觉得 Bob 和 Charlie 里至少有一人很可疑。"},
    )

    await dummy_agent.observe_event(event, visible_state)

    human = dummy_agent.social_graph.get_profile("h1")
    bob = dummy_agent.social_graph.get_profile("p2")
    charlie = dummy_agent.social_graph.get_profile("p3")
    assert human is not None
    assert human.claimed_role_id == "investigator"
    assert bob is None or bob.claimed_role_id is None
    assert charlie is None or charlie.claimed_role_id is None


@pytest.mark.asyncio
async def test_agent_claim_history_records_conflict_when_player_changes_story(dummy_agent):
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=3,
        day_number=2,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="chef", team=Team.GOOD),
        ),
    )
    dummy_agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(dummy_agent, state)

    claim_event = GameEvent(
        event_type="player_speaks",
        phase=GamePhase.DAY_DISCUSSION,
        round_number=2,
        actor="p2",
        visibility=Visibility.PUBLIC,
        payload={"content": "我跳预言家。"},
    )
    deny_event = GameEvent(
        event_type="player_speaks",
        phase=GamePhase.DAY_DISCUSSION,
        round_number=3,
        actor="p2",
        visibility=Visibility.PUBLIC,
        payload={"content": "我什么时候说我是预言家了？"},
    )

    await dummy_agent.observe_event(claim_event, visible_state)
    await dummy_agent.observe_event(deny_event, visible_state)

    bob = dummy_agent.social_graph.get_profile("p2")
    assert bob is not None
    assert len(bob.claim_history) == 2
    assert bob.claim_history[0].claim_type == "self_claim"
    assert bob.claim_history[1].claim_type == "denial"
    summary = dummy_agent.social_graph.get_graph_summary()
    assert "身份发言记录" in summary
    assert "否认" in summary


@pytest.mark.asyncio
async def test_claim_conflict_increases_target_suspicion(dummy_agent):
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=3,
        day_number=2,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p3", name="Charlie", role_id="chef", team=Team.GOOD),
        ),
    )
    dummy_agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(dummy_agent, state)

    bob_claim = GameEvent(
        event_type="player_speaks",
        phase=GamePhase.DAY_DISCUSSION,
        round_number=1,
        actor="p2",
        visibility=Visibility.PUBLIC,
        payload={"content": "我跳预言家。"},
    )
    bob_deny = GameEvent(
        event_type="player_speaks",
        phase=GamePhase.DAY_DISCUSSION,
        round_number=2,
        actor="p2",
        visibility=Visibility.PUBLIC,
        payload={"content": "我什么时候说我是预言家了？"},
    )
    charlie_claim = GameEvent(
        event_type="player_speaks",
        phase=GamePhase.DAY_DISCUSSION,
        round_number=1,
        actor="p3",
        visibility=Visibility.PUBLIC,
        payload={"content": "我跳预言家。"},
    )

    await dummy_agent.observe_event(bob_claim, visible_state)
    await dummy_agent.observe_event(bob_deny, visible_state)
    await dummy_agent.observe_event(charlie_claim, visible_state)

    bob_score = dummy_agent._target_signal_score("p2", visible_state)
    charlie_score = dummy_agent._target_signal_score("p3", visible_state)
    assert bob_score > charlie_score


@pytest.mark.asyncio
async def test_confirmed_evil_teammate_private_info_reduces_suspicion_for_evil_agent():
    backend = DummyBackend()
    agent = AIAgent(
        player_id="p1",
        name="Minion Alice",
        backend=backend,
        persona=Persona(description="谨慎的爪牙", speaking_style="低调试探"),
    )
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=2,
        day_number=2,
        players=(
            PlayerState(player_id="p1", name="Minion Alice", role_id="poisoner", team=Team.EVIL),
            PlayerState(player_id="p2", name="Player 2", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p3", name="Charlie", role_id="chef", team=Team.GOOD),
        ),
    )
    agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(agent, state)

    private_info = GameEvent(
        event_type="private_info_delivered",
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        target="p1",
        visibility=Visibility.PRIVATE,
        payload={
            "type": "evil_team_info",
            "title": "邪恶阵营信息",
            "lines": ["你看到了邪恶队友。"],
            "teammates": ["Player 2"],
            "bluffs": ["washerwoman", "librarian", "investigator"],
        },
    )

    await agent.observe_event(private_info, visible_state)

    teammate_score = agent._target_signal_score("p2", visible_state)
    outsider_score = agent._target_signal_score("p3", visible_state)
    assert teammate_score < outsider_score
    assert agent.working_memory.get_objective_memory_summaries("evil_teammates") == ["你的邪恶队友是：Player 2"]
    assert agent.working_memory.get_objective_memory_summaries("evil_bluffs")


@pytest.mark.asyncio
async def test_fortune_teller_high_confidence_info_increases_suspicion_for_mentioned_targets():
    agent = AIAgent(
        player_id="p1",
        name="Alice",
        backend=DummyBackend(),
        persona=Persona(description="谨慎的信息位", speaking_style="平稳"),
    )
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=2,
        day_number=2,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="fortune_teller", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p3", name="Charlie", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p4", name="Daisy", role_id="washerwoman", team=Team.GOOD),
        ),
    )
    agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(agent, state)
    private_info = GameEvent(
        event_type="private_info_delivered",
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        target="p1",
        visibility=Visibility.PRIVATE,
        payload={
            "type": "fortune_teller_info",
            "title": "预言家信息",
            "lines": ["Bob 和 Charlie 中至少有一人是恶魔或红鲱鱼。"],
        },
    )

    await agent.observe_event(private_info, visible_state)

    bob_score = agent._target_signal_score("p2", visible_state)
    charlie_score = agent._target_signal_score("p3", visible_state)
    daisy_score = agent._target_signal_score("p4", visible_state)

    assert bob_score > daisy_score
    assert charlie_score > daisy_score


@pytest.mark.asyncio
async def test_ravenkeeper_revealed_role_creates_targeted_high_confidence_memory():
    agent = AIAgent(
        player_id="p1",
        name="Alice",
        backend=DummyBackend(),
        persona=Persona(description="谨慎的信息位", speaking_style="平稳"),
    )
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=2,
        day_number=2,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="ravenkeeper", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p3", name="Charlie", role_id="chef", team=Team.GOOD),
        ),
    )
    agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(agent, state)
    private_info = GameEvent(
        event_type="private_info_delivered",
        phase=GamePhase.NIGHT,
        round_number=2,
        target="p1",
        visibility=Visibility.PRIVATE,
        payload={
            "type": "ravenkeeper_info",
            "title": "守鸦人信息",
            "lines": ["你得知 Bob 的身份是：小恶魔。"],
            "player_id": "p2",
            "role_seen": "imp",
        },
    )

    await agent.observe_event(private_info, visible_state)

    revealed = agent.working_memory.get_private_memory_summaries("revealed_role")
    assert any("Bob 的身份被高可信信息指出为 小恶魔" in item for item in revealed)
    bob_score = agent._target_signal_score("p2", visible_state)
    charlie_score = agent._target_signal_score("p3", visible_state)
    assert bob_score > charlie_score


@pytest.mark.asyncio
async def test_investigator_candidate_and_conflicting_public_claim_raise_suspicion():
    agent = AIAgent(
        player_id="p1",
        name="Alice",
        backend=DummyBackend(),
        persona=Persona(description="谨慎的信息位", speaking_style="平稳"),
    )
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=2,
        day_number=2,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="investigator", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="poisoner", team=Team.EVIL),
            PlayerState(player_id="p3", name="Charlie", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p4", name="Daisy", role_id="washerwoman", team=Team.GOOD),
        ),
    )
    agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(agent, state)
    private_info = GameEvent(
        event_type="private_info_delivered",
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        target="p1",
        visibility=Visibility.PRIVATE,
        payload={
            "type": "investigator_info",
            "title": "调查员信息",
            "lines": ["Bob, Charlie 之中，有一人是 投毒者。"],
            "players": ["p2", "p3"],
            "role_seen": "poisoner",
        },
    )
    public_claim = GameEvent(
        event_type="player_speaks",
        phase=GamePhase.DAY_DISCUSSION,
        round_number=2,
        actor="p2",
        visibility=Visibility.PUBLIC,
        payload={"content": "我跳洗衣妇。"},
    )

    await agent.observe_event(private_info, visible_state)
    await agent.observe_event(public_claim, visible_state)

    bob_score = agent._target_signal_score("p2", visible_state)
    daisy_score = agent._target_signal_score("p4", visible_state)
    assert bob_score > daisy_score


@pytest.mark.asyncio
async def test_washerwoman_candidate_consistent_public_claim_reduces_suspicion():
    agent = AIAgent(
        player_id="p1",
        name="Alice",
        backend=DummyBackend(),
        persona=Persona(description="谨慎的信息位", speaking_style="平稳"),
    )
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=2,
        day_number=2,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p3", name="Charlie", role_id="librarian", team=Team.GOOD),
            PlayerState(player_id="p4", name="Daisy", role_id="imp", team=Team.EVIL),
        ),
    )
    agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(agent, state)
    private_info = GameEvent(
        event_type="private_info_delivered",
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        target="p1",
        visibility=Visibility.PRIVATE,
        payload={
            "type": "washerwoman_info",
            "title": "洗衣妇信息",
            "lines": ["Bob, Charlie 之中，有一人是 厨师。"],
            "players": ["p2", "p3"],
            "role_seen": "chef",
        },
    )
    public_claim = GameEvent(
        event_type="player_speaks",
        phase=GamePhase.DAY_DISCUSSION,
        round_number=2,
        actor="p2",
        visibility=Visibility.PUBLIC,
        payload={"content": "我跳厨师。"},
    )

    await agent.observe_event(private_info, visible_state)
    await agent.observe_event(public_claim, visible_state)

    bob_score = agent._target_signal_score("p2", visible_state)
    charlie_score = agent._target_signal_score("p3", visible_state)
    assert bob_score < charlie_score


@pytest.mark.asyncio
async def test_fortune_teller_info_is_stored_as_high_confidence_memory(dummy_agent):
    state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="fortune_teller", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p3", name="Charlie", role_id="imp", team=Team.EVIL),
        ),
    )
    dummy_agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(dummy_agent, state)
    event = GameEvent(
        event_type="private_info_delivered",
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        target="p1",
        visibility=Visibility.PRIVATE,
        payload={
            "type": "fortune_teller_info",
            "title": "预言家信息",
            "lines": ["Bob 和 Charlie 中至少有一人是恶魔或红鲱鱼。"],
        },
    )

    await dummy_agent.observe_event(event, visible_state)

    summaries = dummy_agent.working_memory.get_private_memory_summaries("fortune_teller_info")
    assert summaries == ["预言家信息: Bob 和 Charlie 中至少有一人是恶魔或红鲱鱼。"]


@pytest.mark.asyncio
async def test_investigator_info_is_stored_as_high_confidence_memory(dummy_agent):
    state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="investigator", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p3", name="Charlie", role_id="poisoner", team=Team.EVIL),
        ),
    )
    dummy_agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(dummy_agent, state)
    event = GameEvent(
        event_type="private_info_delivered",
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        target="p1",
        visibility=Visibility.PRIVATE,
        payload={
            "type": "investigator_info",
            "title": "调查员信息",
            "lines": ["Bob 和 Charlie 中有一名爪牙。"],
        },
    )

    await dummy_agent.observe_event(event, visible_state)

    summaries = dummy_agent.working_memory.get_private_memory_summaries("investigator_info")
    assert summaries == ["调查员信息: Bob 和 Charlie 中有一名爪牙。"]


@pytest.mark.asyncio
async def test_ravenkeeper_info_is_stored_as_high_confidence_memory(dummy_agent):
    state = GameState(
        phase=GamePhase.NIGHT,
        round_number=2,
        day_number=2,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="ravenkeeper", team=Team.GOOD, is_alive=False),
            PlayerState(player_id="p2", name="Bob", role_id="imp", team=Team.EVIL),
        ),
    )
    dummy_agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(dummy_agent, state)
    event = GameEvent(
        event_type="private_info_delivered",
        phase=GamePhase.NIGHT,
        round_number=2,
        target="p1",
        visibility=Visibility.PRIVATE,
        payload={
            "type": "ravenkeeper_info",
            "title": "守鸦人信息",
            "lines": ["Bob 的真实身份是：小恶魔。"],
        },
    )

    await dummy_agent.observe_event(event, visible_state)

    summaries = dummy_agent.working_memory.get_private_memory_summaries("ravenkeeper_info")
    assert summaries == ["守鸦人信息: Bob 的真实身份是：小恶魔。"]


@pytest.mark.asyncio
async def test_spy_book_is_stored_as_objective_memory(dummy_agent):
    state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="spy", team=Team.EVIL),
            PlayerState(player_id="p2", name="Bob", role_id="chef", team=Team.GOOD),
        ),
    )
    dummy_agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(dummy_agent, state)
    event = GameEvent(
        event_type="private_info_delivered",
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        target="p1",
        visibility=Visibility.PRIVATE,
        payload={
            "type": "spy_book",
            "title": "间谍魔典",
            "lines": ["Bob：厨师（存活）"],
        },
    )

    await dummy_agent.observe_event(event, visible_state)

    summaries = dummy_agent.working_memory.get_objective_memory_summaries("spy_book")
    assert summaries == ["间谍魔典: Bob：厨师（存活）"]


@pytest.mark.asyncio
async def test_washerwoman_info_is_stored_as_high_confidence_memory(dummy_agent):
    state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p3", name="Charlie", role_id="empath", team=Team.GOOD),
        ),
    )
    dummy_agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(dummy_agent, state)
    event = GameEvent(
        event_type="private_info_delivered",
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        target="p1",
        visibility=Visibility.PRIVATE,
        payload={
            "type": "washerwoman_info",
            "title": "洗衣妇信息",
            "lines": ["Bob 和 Charlie 中有一人是镇民。"],
        },
    )

    await dummy_agent.observe_event(event, visible_state)

    summaries = dummy_agent.working_memory.get_private_memory_summaries("washerwoman_info")
    assert summaries == ["洗衣妇信息: Bob 和 Charlie 中有一人是镇民。"]


@pytest.mark.asyncio
async def test_librarian_info_is_stored_as_high_confidence_memory(dummy_agent):
    state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="librarian", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="drunk", team=Team.GOOD),
            PlayerState(player_id="p3", name="Charlie", role_id="saint", team=Team.GOOD),
        ),
    )
    dummy_agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(dummy_agent, state)
    event = GameEvent(
        event_type="private_info_delivered",
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        target="p1",
        visibility=Visibility.PRIVATE,
        payload={
            "type": "librarian_info",
            "title": "图书馆员信息",
            "lines": ["Bob 和 Charlie 中有一名外来者。"],
        },
    )

    await dummy_agent.observe_event(event, visible_state)

    summaries = dummy_agent.working_memory.get_private_memory_summaries("librarian_info")
    assert summaries == ["图书馆员信息: Bob 和 Charlie 中有一名外来者。"]


@pytest.mark.asyncio
async def test_chef_info_is_stored_as_high_confidence_memory(dummy_agent):
    state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="poisoner", team=Team.EVIL),
            PlayerState(player_id="p3", name="Charlie", role_id="imp", team=Team.EVIL),
        ),
    )
    dummy_agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(dummy_agent, state)
    event = GameEvent(
        event_type="private_info_delivered",
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        target="p1",
        visibility=Visibility.PRIVATE,
        payload={
            "type": "chef_info",
            "title": "厨师信息",
            "lines": ["今晚你得知：有 1 对相邻邪恶玩家。"],
        },
    )

    await dummy_agent.observe_event(event, visible_state)

    summaries = dummy_agent.working_memory.get_private_memory_summaries("chef_info")
    assert summaries == ["厨师信息: 今晚你得知：有 1 对相邻邪恶玩家。"]


@pytest.mark.asyncio
async def test_empath_info_is_stored_as_high_confidence_memory(dummy_agent):
    state = GameState(
        phase=GamePhase.NIGHT,
        round_number=2,
        day_number=2,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="poisoner", team=Team.EVIL),
            PlayerState(player_id="p3", name="Charlie", role_id="chef", team=Team.GOOD),
        ),
    )
    dummy_agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(dummy_agent, state)
    event = GameEvent(
        event_type="private_info_delivered",
        phase=GamePhase.NIGHT,
        round_number=2,
        target="p1",
        visibility=Visibility.PRIVATE,
        payload={
            "type": "empath_info",
            "title": "共情者信息",
            "lines": ["你有 1 个邪恶邻座。"],
        },
    )

    await dummy_agent.observe_event(event, visible_state)

    summaries = dummy_agent.working_memory.get_private_memory_summaries("empath_info")
    assert summaries == ["共情者信息: 你有 1 个邪恶邻座。"]


@pytest.mark.asyncio
async def test_ai_agent_ignores_hidden_events_and_private_chats_in_prompt():
    class CapturingBackend(LLMBackend):
        def __init__(self) -> None:
            self.prompts: list[str] = []

        async def generate(self, system_prompt: str, messages: list[Message], **kwargs) -> LLMResponse:
            self.prompts.append(system_prompt)
            return LLMResponse(content='{"action":"speak","content":"ok","tone":"calm","reasoning":"ok"}', tool_calls=[])

        def get_model_name(self) -> str:
            return "capturing-model"

    backend = CapturingBackend()
    agent = AIAgent(
        player_id="p1",
        name="Alice",
        backend=backend,
        persona=Persona(description="谨慎观察者", speaking_style="先观察再表态"),
    )
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=1,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="imp", team=Team.EVIL),
        ),
        chat_history=(
            ChatMessage(
                speaker="p2",
                content="公开发言：我觉得现在还不能急着下结论",
                phase=GamePhase.DAY_DISCUSSION,
                round_number=1,
            ),
            ChatMessage(
                speaker="p2",
                content="只有邪恶队友能看到的私聊",
                phase=GamePhase.DAY_DISCUSSION,
                round_number=1,
                recipient_ids=("p2",),
            ),
        ),
        event_log=(
            GameEvent(
                event_type="player_death",
                phase=GamePhase.DAY_DISCUSSION,
                round_number=1,
                actor="p2",
                target="p2",
                visibility=Visibility.STORYTELLER_ONLY,
                payload={"reason": "should_not_leak"},
            ),
            GameEvent(
                event_type="player_speaks",
                phase=GamePhase.DAY_DISCUSSION,
                round_number=1,
                actor="p2",
                visibility=Visibility.PUBLIC,
                payload={"content": "公开事件内容"},
            ),
        ),
    )
    agent.synchronize_role(state.get_player("p1"))

    visible_state, legal_context = _agent_ctx(agent, state)
    await agent.observe_event(state.event_log[0], visible_state)
    assert agent.working_memory.is_empty

    await agent.observe_event(state.event_log[1], visible_state)
    assert not agent.working_memory.is_empty

    recent_texts = agent._recent_context_texts(agent._build_visible_state(state))
    assert "公开发言：我觉得现在还不能急着下结论" in "\n".join(recent_texts)
    assert "只有邪恶队友能看到的私聊" not in "\n".join(recent_texts)

    await agent.act(visible_state, "speak", legal_context=legal_context)
    prompt = backend.prompts[-1]
    assert "公开事件内容" in prompt
    assert "should_not_leak" not in prompt
    assert "STORYTELLER_ONLY" not in prompt

    visible_state = agent._build_visible_state(state)
    assert visible_state.self_view is not None
    assert not hasattr(visible_state.self_view, "true_role_id")
    assert len(visible_state.visible_event_log) == 1
    assert len(visible_state.public_chat_history) == 1


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

    visible_state, legal_context = _agent_ctx(agent, state)
    decision = await agent.act(visible_state, "nominate", legal_context=legal_context)
    assert decision["action"] in {"nominate", "none"}
    if decision["action"] == "nominate":
        assert decision["target"] in {"p2", "p3"}


@pytest.mark.asyncio
async def test_ai_agent_normalizes_nested_multi_target_night_action():
    class NestedTargetsBackend(DummyBackend):
        async def generate(self, system_prompt: str, messages: list[Message], **kwargs) -> LLMResponse:
            return LLMResponse(
                content='{"action":"night_action","target":[["p2","h1"]],"reasoning":"two targets"}',
                tool_calls=[],
            )

    agent = AIAgent(
        player_id="p1",
        name="Alice",
        backend=NestedTargetsBackend(),
        persona=Persona(description="安静的预言家", speaking_style="低调、克制"),
    )
    state = GameState(
        phase=GamePhase.NIGHT,
        round_number=1,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="fortune_teller", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="h1", name="Human", role_id="washerwoman", team=Team.GOOD),
        ),
    )
    agent.synchronize_role(state.get_player("p1"))

    visible_state, legal_context = _agent_ctx(agent, state)
    assert legal_context.required_targets == 2
    assert legal_context.can_target_self is True
    decision = await agent.act(visible_state, "night_action", legal_context=legal_context)

    assert decision["action"] == "night_action"
    assert decision["target"] in {"p2", "h1"}
    assert len(decision["targets"]) == 2
    assert set(decision["targets"]) == {"p2", "h1"}


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

    visible_state, legal_context = _agent_ctx(agent, state)
    decision = await agent.act(visible_state, "nomination_intent", legal_context=legal_context)
    assert decision["action"] == "none"
    assert decision.get("target") is None


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

    visible_state, legal_context = _agent_ctx(agent, state)
    decision = await agent.act(visible_state, "vote", legal_context=legal_context)
    assert decision["action"] == "vote"
    assert isinstance(decision["decision"], bool)


@pytest.mark.asyncio
async def test_ai_agent_archives_phase_memory_into_episodic_memory():
    agent = AIAgent(
        player_id="p1",
        name="Alice",
        backend=DummyBackend(),
        persona=Persona(description="谨慎村民", speaking_style="平稳"),
    )
    agent.synchronize_role(PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD))
    state = GameState(phase=GamePhase.DAY_DISCUSSION, round_number=2, day_number=3)

    agent.working_memory.add_observation(
        Observation(
            observation_id="evt-1",
            content="Bob 提名了 Charlie。",
            source_event=GameEvent(
                event_type="nomination_started",
                phase=GamePhase.NOMINATION,
                round_number=2,
                actor="p2",
                target="p3",
                visibility=Visibility.PUBLIC,
            ),
            phase=GamePhase.DAY_DISCUSSION,
            round_number=2,
        )
    )
    agent.working_memory.add_thought("Bob 这手像是在带节奏。")
    agent.working_memory.add_impression("Bob 说话一直很急。")

    visible_state, _ = _agent_ctx(agent, state)
    await agent.archive_phase_memory(visible_state)

    assert len(agent.episodic_memory.episodes) == 1
    episode = agent.episodic_memory.episodes[0]
    assert episode.phase == GamePhase.DAY_DISCUSSION
    assert "Bob 提名了 Charlie" in episode.summary
    assert "nomination_started" in episode.key_events
    assert agent.working_memory.impressions == ["Bob 说话一直很急。"]
    assert agent.working_memory.is_empty


@pytest.mark.asyncio
async def test_high_confidence_private_info_survives_phase_archive_and_public_noise():
    agent = AIAgent(
        player_id="p1",
        name="Alice",
        backend=DummyBackend(),
        persona=Persona(description="谨慎的信息位", speaking_style="平稳"),
    )
    state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="fortune_teller", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p3", name="Charlie", role_id="imp", team=Team.EVIL),
        ),
    )
    agent.synchronize_role(state.get_player("p1"))
    visible_state, _ = _agent_ctx(agent, state)

    private_event = GameEvent(
        event_type="private_info_delivered",
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        target="p1",
        visibility=Visibility.PRIVATE,
        payload={
            "type": "fortune_teller_info",
            "title": "占卜师信息",
            "lines": ["昨晚查验结果：Bob 和 Charlie 中至少一人可能是恶魔。"],
            "players": ["p2", "p3"],
            "result": True,
        },
    )
    await agent.observe_event(private_event, visible_state)

    day_state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=2,
        day_number=2,
        players=state.players,
        chat_history=(
            ChatMessage(speaker="p2", content="我跳士兵，昨天谁都别信。", phase=GamePhase.DAY_DISCUSSION, round_number=2),
        ),
    )
    visible_day_state, _ = _agent_ctx(agent, day_state)
    public_event = GameEvent(
        event_type="player_speaks",
        phase=GamePhase.DAY_DISCUSSION,
        round_number=2,
        actor="p2",
        visibility=Visibility.PUBLIC,
        payload={"content": "我跳士兵，昨天谁都别信。"},
    )
    await agent.observe_event(public_event, visible_day_state)
    await agent.archive_phase_memory(visible_day_state)

    context = agent.working_memory.get_recent_context()
    assert "你确认掌握的高可信私密信息" in context
    assert "占卜师信息: 昨晚查验结果：Bob 和 Charlie 中至少一人可能是恶魔。" in context
    assert "公开场上的普通信息" in context
    assert "Bob 公开跳身份为 士兵" in context
