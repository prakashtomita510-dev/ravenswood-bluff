"""Phase 3 测试 - 完整游戏循环"""

import pytest

from src.agents.storyteller_agent import StorytellerAgent
from src.orchestrator.game_loop import GameOrchestrator
from src.state.game_state import GameConfig, GameState, PlayerState, Team, GamePhase
from src.agents.base_agent import BaseAgent
from src.llm.mock_backend import MockBackend


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


class DummyStoryteller:
    async def decide_drunk_role(self, script, role_ids):
        return "washerwoman"

    async def build_night_order(self, game_state, phase):
        return []

    def role_receives_storyteller_info(self, role_id):
        return True

    async def decide_night_info(self, game_state, player_id, role_id):
        return {}

    async def narrate_phase(self, game_state):
        return ""


class TrackingAgent(BaseAgent):
    def __init__(self, pid, name, actions=None):
        super().__init__(pid, name)
        self.actions = actions or {}
        self.calls: list[str] = []

    async def act(self, game_state, action_type, **kwargs):
        self.calls.append(action_type)
        queue = self.actions.get(action_type, [])
        if queue:
            return queue.pop(0)
        return {"action": "none"}

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


@pytest.mark.asyncio
async def test_first_night_evil_private_info_contains_team_and_bluffs():
    initial_state = GameState(
        players=(
            PlayerState(player_id="a1", name="Imp", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="a2", name="Spy", role_id="spy", team=Team.EVIL),
            PlayerState(player_id="a3", name="Alice", role_id="washerwoman", team=Team.GOOD),
        ),
        bluffs=("chef", "empath", "monk"),
    )
    orch = GameOrchestrator(initial_state)
    orch.storyteller_agent = DummyStoryteller()

    await orch._run_first_night()

    evil_events = [
        event for event in orch.event_log.events
        if event.event_type == "private_info_delivered" and event.target == "a1"
    ]
    assert evil_events, "expected evil private info to be delivered"

    payload = evil_events[0].payload
    assert payload["title"] == "邪恶阵营互认"
    assert payload["teammates"] == ["Spy"]
    assert payload["bluffs"] == ["chef", "empath", "monk"]

    spy_events = [
        event for event in orch.event_log.events
        if event.event_type == "private_info_delivered" and event.target == "a2"
    ]
    assert spy_events, "expected spy to receive evil first-night reveal"
    assert spy_events[0].payload["bluffs"] == ["chef", "empath", "monk"]


@pytest.mark.asyncio
async def test_first_night_empath_receives_private_info():
    initial_state = GameState(
        players=(
            PlayerState(player_id="e1", name="Empath", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="e2", name="Minion", role_id="spy", team=Team.EVIL),
            PlayerState(player_id="e3", name="Townsfolk", role_id="washerwoman", team=Team.GOOD),
        ),
        seat_order=("e1", "e2", "e3"),
    )
    orch = GameOrchestrator(initial_state)
    orch.storyteller_agent = DummyStoryteller()

    await orch._run_first_night()

    empath_events = [
        event for event in orch.event_log.events
        if event.event_type == "private_info_delivered" and event.target == "e1"
    ]
    assert empath_events, "expected empath private info on first night"
    empath_payloads = [event.payload for event in empath_events if event.payload.get("type") == "empath_info"]
    assert empath_payloads, "expected empath-specific info payload"
    assert empath_payloads[0]["title"] == "共情者信息"
    assert empath_payloads[0]["lines"]


@pytest.mark.asyncio
async def test_spy_receives_spy_book_on_first_and_later_nights():
    initial_state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        seat_order=("s1", "g1", "g2"),
        players=(
            PlayerState(player_id="s1", name="Spy", role_id="spy", team=Team.EVIL),
            PlayerState(player_id="g1", name="Chef", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="g2", name="Town", role_id="washerwoman", team=Team.GOOD),
        ),
    )
    orch = GameOrchestrator(initial_state)
    orch.storyteller_agent = DummyStoryteller()

    await orch._distribute_night_info(GamePhase.FIRST_NIGHT)
    await orch._distribute_night_info(GamePhase.NIGHT)

    spy_events = [
        event
        for event in orch.event_log.events
        if event.event_type == "private_info_delivered" and event.target == "s1"
    ]
    spy_payloads = [event.payload for event in spy_events if event.payload.get("type") == "spy_book"]
    assert len(spy_payloads) >= 2
    assert all(payload["book"] for payload in spy_payloads)


@pytest.mark.asyncio
async def test_first_night_spy_receives_grimoire_and_refreshes_state():
    initial_state = GameState(
        players=(
            PlayerState(player_id="s1", name="Spy", role_id="spy", team=Team.EVIL),
            PlayerState(player_id="i1", name="Imp", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="g1", name="Town", role_id="washerwoman", team=Team.GOOD),
        ),
        bluffs=("chef", "empath", "monk"),
    )
    orch = GameOrchestrator(initial_state)
    orch.storyteller_agent = DummyStoryteller()

    await orch._run_first_night()

    spy_events = [
        event for event in orch.event_log.events
        if event.event_type == "private_info_delivered" and event.target == "s1"
    ]
    assert spy_events, "expected spy to receive private grimoire info"
    assert spy_events[-1].payload["type"] == "spy_book"
    assert orch.state.grimoire is not None
    assert orch.state.grimoire.night_actions
    assert any(
        action["event_type"] == "private_info_delivered" and action["payload"].get("type") == "spy_book"
        for action in orch.state.grimoire.night_actions
    )


@pytest.mark.asyncio
async def test_later_night_spy_receives_updated_grimoire_info():
    initial_state = GameState(
        phase=GamePhase.NIGHT,
        round_number=2,
        players=(
            PlayerState(player_id="s1", name="Spy", role_id="spy", team=Team.EVIL),
            PlayerState(player_id="g1", name="Town", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="g2", name="Chef", role_id="chef", team=Team.GOOD),
        ),
        seat_order=("s1", "g1", "g2"),
    )
    orch = GameOrchestrator(initial_state)
    orch.storyteller_agent = DummyStoryteller()

    await orch._distribute_night_info(GamePhase.NIGHT)
    orch._update_grimoire()

    spy_events = [
        event for event in orch.event_log.events
        if event.event_type == "private_info_delivered" and event.target == "s1"
    ]
    assert spy_events, "expected spy to receive nightly grimoire info"
    assert spy_events[-1].payload["type"] == "spy_book"
    assert orch.state.grimoire is not None
    assert any(
        action["event_type"] == "private_info_delivered" and action["payload"].get("type") == "spy_book"
        for action in orch.state.grimoire.night_actions
    )


@pytest.mark.asyncio
async def test_fixed_info_roles_do_not_receive_night_action_request():
    initial_state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        players=(
            PlayerState(player_id="w1", name="Washerwoman", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="e1", name="Empath", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="c1", name="Chef", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="i1", name="Imp", role_id="imp", team=Team.EVIL),
        ),
        seat_order=("w1", "e1", "c1", "i1"),
    )
    orch = GameOrchestrator(initial_state)
    orch.storyteller_agent = DummyStoryteller()
    for player in initial_state.players:
        orch.register_agent(ScriptedAgent(player.player_id, player.name, {
            "night_action": [{"action": "night_action", "target": "w1"}],
        }))

    await orch._execute_night_actions(GamePhase.FIRST_NIGHT)

    action_requests = [
        event for event in orch.event_log.events
        if event.event_type == "night_action_requested"
    ]
    requested_actors = {event.actor for event in action_requests}
    assert "w1" not in requested_actors
    assert "e1" not in requested_actors
    assert "c1" not in requested_actors


@pytest.mark.asyncio
async def test_storyteller_night_order_only_requests_targeted_roles():
    storyteller = StorytellerAgent(MockBackend())
    state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        players=(
            PlayerState(player_id="w1", name="Washerwoman", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="e1", name="Empath", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="f1", name="Fortune Teller", role_id="fortune_teller", team=Team.GOOD),
            PlayerState(player_id="p1", name="Poisoner", role_id="poisoner", team=Team.EVIL),
        ),
    )

    steps = await storyteller.build_night_order(state, GamePhase.FIRST_NIGHT)
    role_ids = [step["role_id"] for step in steps]

    assert "washerwoman" not in role_ids
    assert "empath" not in role_ids
    assert "fortune_teller" in role_ids
    assert "poisoner" in role_ids


@pytest.mark.asyncio
async def test_nomination_intents_choose_first_legal_by_seat_order():
    initial_state = GameState(
        phase=GamePhase.NOMINATION,
        players=(
            PlayerState(player_id="p1", name="One", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Two", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="p3", name="Three", role_id="imp", team=Team.EVIL),
        ),
        seat_order=("p1", "p2", "p3"),
        config={
            "player_count": 3,
            "human_mode": "none",
            "human_player_ids": [],
            "is_human_participant": False,
            "discussion_rounds": 1,
            "max_nomination_rounds": 1,
        },
    )
    orch = GameOrchestrator(initial_state)
    orch.storyteller_agent = DummyStoryteller()
    orch.register_agent(ScriptedAgent("p1", "One", {
        "nomination_intent": [{"action": "none"}],
        "vote": [{"action": "vote", "decision": True}],
        "defense_speech": [{"action": "defense_speech", "content": "No comment."}],
    }))
    orch.register_agent(ScriptedAgent("p2", "Two", {
        "nomination_intent": [{"action": "nominate", "target": "p3"}],
        "vote": [{"action": "vote", "decision": True}],
        "defense_speech": [{"action": "defense_speech", "content": "I object."}],
    }))
    orch.register_agent(ScriptedAgent("p3", "Three", {
        "nomination_intent": [{"action": "nominate", "target": "p1"}],
        "vote": [{"action": "vote", "decision": True}],
        "defense_speech": [{"action": "defense_speech", "content": "I am innocent."}],
    }))

    await orch._run_nomination_phase()

    nomination_events = [
        event for event in orch.event_log.events
        if event.event_type == "nomination_started"
    ]
    assert nomination_events
    assert nomination_events[0].actor == "p2"
    assert nomination_events[0].target == "p3"


@pytest.mark.asyncio
async def test_audit_mode_nomination_fallback_chooses_first_legal_pair():
    initial_state = GameState(
        phase=GamePhase.NOMINATION,
        players=(
            PlayerState(player_id="p1", name="One", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Two", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="p3", name="Three", role_id="imp", team=Team.EVIL),
        ),
        seat_order=("p1", "p2", "p3"),
        config=GameConfig(
            player_count=3,
            human_mode="none",
            human_player_ids=(),
            is_human_participant=False,
            discussion_rounds=1,
            max_nomination_rounds=1,
            audit_mode=True,
        ),
    )
    orch = GameOrchestrator(initial_state)
    orch.storyteller_agent = DummyStoryteller()
    orch.register_agent(ScriptedAgent("p1", "One", {"nomination_intent": [{"action": "none"}]}))
    orch.register_agent(ScriptedAgent("p2", "Two", {"nomination_intent": [{"action": "none"}]}))
    orch.register_agent(ScriptedAgent("p3", "Three", {"nomination_intent": [{"action": "none"}]}))

    chosen = orch._select_nomination_intent(
        {
            "p1": {"action": "none"},
            "p2": {"action": "none"},
            "p3": {"action": "none"},
        }
    )

    assert chosen == ("p1", "p2")


@pytest.mark.asyncio
async def test_ravenkeeper_death_trigger_delivers_private_info():
    initial_state = GameState(
        phase=GamePhase.NIGHT,
        round_number=2,
        players=(
            PlayerState(player_id="r", name="Raven", role_id="ravenkeeper", team=Team.GOOD, is_alive=False),
            PlayerState(player_id="i", name="Imp", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="g", name="Good", role_id="chef", team=Team.GOOD),
        ),
        seat_order=("r", "i", "g"),
    )
    orch = GameOrchestrator(initial_state)
    orch.storyteller_agent = DummyStoryteller()
    orch.register_agent(ScriptedAgent("r", "Raven", {
        "death_trigger": [{"action": "death_trigger", "target": "i"}],
    }))

    await orch._resolve_on_death_triggers({"r", "i", "g"})

    private_infos = [
        event for event in orch.event_log.events
        if event.event_type == "private_info_delivered" and event.target == "r"
    ]
    assert private_infos, "expected ravenkeeper to receive private info after death"
    payload = private_infos[0].payload
    assert payload["type"] == "ravenkeeper_info"
    assert payload["role_seen"] == "imp"


@pytest.mark.asyncio
async def test_nomination_phase_supports_multiple_rounds_before_night():
    initial_state = GameState(
        phase=GamePhase.NOMINATION,
        round_number=1,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="One", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Two", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="p3", name="Three", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p4", name="Four", role_id="chef", team=Team.GOOD),
        ),
        seat_order=("p1", "p2", "p3", "p4"),
        config=GameConfig(
            player_count=4,
            human_mode="none",
            human_player_ids=[],
            is_human_participant=False,
            discussion_rounds=1,
            max_nomination_rounds=3,
        ),
    )
    orch = GameOrchestrator(initial_state)
    orch.storyteller_agent = DummyStoryteller()
    orch.register_agent(ScriptedAgent("p1", "One", {
        "nomination_intent": [
            {"action": "nominate", "target": "p3"},
            {"action": "none"},
        ],
        "vote": [
            {"action": "vote", "decision": True},
            {"action": "vote", "decision": True},
        ],
        "defense_speech": [{"action": "defense_speech", "content": "No comment."}],
    }))
    orch.register_agent(ScriptedAgent("p2", "Two", {
        "nomination_intent": [
            {"action": "none"},
            {"action": "nominate", "target": "p4"},
        ],
        "vote": [
            {"action": "vote", "decision": False},
            {"action": "vote", "decision": True},
        ],
        "defense_speech": [{"action": "defense_speech", "content": "Second round."}],
    }))
    orch.register_agent(ScriptedAgent("p3", "Three", {
        "nomination_intent": [
            {"action": "none"},
            {"action": "none"},
        ],
        "vote": [
            {"action": "vote", "decision": True},
            {"action": "vote", "decision": False},
        ],
        "defense_speech": [{"action": "defense_speech", "content": "I am innocent."}],
    }))
    orch.register_agent(ScriptedAgent("p4", "Four", {
        "nomination_intent": [
            {"action": "none"},
            {"action": "none"},
        ],
        "vote": [
            {"action": "vote", "decision": False},
            {"action": "vote", "decision": True},
        ],
        "defense_speech": [{"action": "defense_speech", "content": "Please spare me."}],
    }))

    await orch._run_nomination_phase()

    nomination_events = [
        event for event in orch.event_log.events
        if event.event_type == "nomination_started"
    ]
    assert len(nomination_events) == 2
    assert nomination_events[0].actor == "p1"
    assert nomination_events[0].target == "p3"
    assert nomination_events[1].actor == "p2"
    assert nomination_events[1].target == "p4"

    execution_events = [
        event for event in orch.event_log.events
        if event.event_type == "execution_resolved"
    ]
    assert execution_events
    assert execution_events[-1].payload["executed"] == "p4"

    event_types = [event.event_type for event in orch.event_log.events]
    first_nomination_idx = event_types.index("nomination_started")
    first_defense_idx = event_types.index("defense_started")
    first_vote_idx = event_types.index("vote_cast")
    first_voting_resolved_idx = event_types.index("voting_resolved")
    first_execution_idx = event_types.index("execution_resolved")

    assert first_nomination_idx < first_defense_idx < first_vote_idx < first_voting_resolved_idx < first_execution_idx
    assert orch.state.current_nominator is None
    assert orch.state.current_nominee is None
    assert orch.state.payload["nomination_state"]["current_nominator"] is None
    assert orch.state.payload["nomination_state"]["current_nominee"] is None
    assert orch.state.payload["nomination_state"]["votes"] == {}
    assert len(orch.state.payload["nomination_history"]) >= 4


@pytest.mark.asyncio
async def test_nomination_phase_records_no_nomination_and_clears_current_state():
    initial_state = GameState(
        phase=GamePhase.NOMINATION,
        round_number=1,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="One", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Two", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="p3", name="Three", role_id="imp", team=Team.EVIL),
        ),
        seat_order=("p1", "p2", "p3"),
        config=GameConfig(
            player_count=3,
            human_mode="none",
            human_player_ids=[],
            is_human_participant=False,
            discussion_rounds=1,
            max_nomination_rounds=1,
        ),
    )
    orch = GameOrchestrator(initial_state)
    orch.storyteller_agent = DummyStoryteller()
    orch.register_agent(TrackingAgent("p1", "One", {"nomination_intent": [{"action": "none"}]}))
    orch.register_agent(TrackingAgent("p2", "Two", {"nomination_intent": [{"action": "none"}]}))
    orch.register_agent(TrackingAgent("p3", "Three", {"nomination_intent": [{"action": "none"}]}))

    await orch._run_nomination_phase()

    history = orch.state.payload["nomination_history"]
    assert any(entry["kind"] == "no_nomination" for entry in history)
    assert orch.state.current_nominator is None
    assert orch.state.current_nominee is None
    assert orch.state.payload["nomination_state"]["current_nominator"] is None
    assert orch.state.payload["nomination_state"]["current_nominee"] is None
    assert orch.state.payload["nomination_state"]["last_result"]["reason"] == "no_nomination"


@pytest.mark.asyncio
async def test_nomination_phase_records_no_execution_when_votes_do_not_pass():
    initial_state = GameState(
        phase=GamePhase.NOMINATION,
        round_number=1,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="One", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Two", role_id="empath", team=Team.GOOD),
            PlayerState(player_id="p3", name="Three", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p4", name="Four", role_id="chef", team=Team.GOOD),
        ),
        seat_order=("p1", "p2", "p3", "p4"),
        config=GameConfig(
            player_count=4,
            human_mode="none",
            human_player_ids=[],
            is_human_participant=False,
            discussion_rounds=1,
            max_nomination_rounds=1,
        ),
    )
    orch = GameOrchestrator(initial_state)
    orch.storyteller_agent = DummyStoryteller()
    orch.register_agent(TrackingAgent("p1", "One", {
        "nomination_intent": [{"action": "nominate", "target": "p3"}],
        "vote": [{"action": "vote", "decision": True}],
        "defense_speech": [{"action": "defense_speech", "content": "No comment."}],
    }))
    orch.register_agent(TrackingAgent("p2", "Two", {
        "nomination_intent": [{"action": "none"}],
        "vote": [{"action": "vote", "decision": True}],
        "defense_speech": [{"action": "defense_speech", "content": "I disagree."}],
    }))
    orch.register_agent(TrackingAgent("p3", "Three", {
        "nomination_intent": [{"action": "none"}],
        "vote": [{"action": "vote", "decision": False}],
        "defense_speech": [{"action": "defense_speech", "content": "I am innocent."}],
    }))
    orch.register_agent(TrackingAgent("p4", "Four", {
        "nomination_intent": [{"action": "none"}],
        "vote": [{"action": "vote", "decision": False}],
        "defense_speech": [{"action": "defense_speech", "content": "Please spare me."}],
    }))

    await orch._run_nomination_phase()

    history = orch.state.payload["nomination_history"]
    assert any(entry["kind"] == "voting_resolved" for entry in history)
    assert orch.state.payload["nomination_state"]["current_nominator"] is None
    assert orch.state.payload["nomination_state"]["current_nominee"] is None
    assert orch.state.payload["nomination_state"]["last_result"]["executed"] is None
    assert orch.state.payload["nomination_state"]["last_result"]["reason"] == "no_execution"


@pytest.mark.asyncio
async def test_collect_nomination_intents_uses_human_and_ai_windows_consistently():
    initial_state = GameState(
        phase=GamePhase.NOMINATION,
        players=(
            PlayerState(player_id="p1", name="Human", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="AI", role_id="imp", team=Team.EVIL),
        ),
        seat_order=("p1", "p2"),
        config=GameConfig(
            player_count=2,
            human_mode="player",
            human_player_ids=("p1",),
            is_human_participant=True,
            discussion_rounds=1,
            max_nomination_rounds=1,
        ),
    )
    orch = GameOrchestrator(initial_state)
    orch.storyteller_agent = DummyStoryteller()
    human_agent = TrackingAgent("p1", "Human", {"nominate": [{"action": "none"}]})
    ai_agent = TrackingAgent("p2", "AI", {"nomination_intent": [{"action": "none"}]})
    orch.register_agent(human_agent)
    orch.register_agent(ai_agent)

    intents = await orch._collect_nomination_intents(1)

    assert human_agent.calls == ["nominate"]
    assert ai_agent.calls == ["nomination_intent"]
    assert "p1" in intents and "p2" in intents
