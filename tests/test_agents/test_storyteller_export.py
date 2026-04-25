from src.agents.storyteller_agent import StorytellerAgent
from src.state.game_state import GamePhase, GameState, PlayerState, Team


def test_storyteller_export_judgement_history_aligns_entries_with_game_id():
    agent = StorytellerAgent()
    agent.record_judgement(
        "night_info",
        decision="deliver",
        reason="fortune_teller_result",
        phase="night",
        round_number=2,
        bucket="night_info.storyteller_info",
        player_id="p1",
    )
    agent.record_judgement(
        "execution",
        decision="executed",
        phase="execution",
        round_number=2,
        bucket="day_judgement",
        target="p3",
    )

    exported = agent.export_judgement_history("game-export-2")

    assert exported["game_id"] == "game-export-2"
    assert exported["judgement_count"] == 2
    assert exported["categories"] == ["execution", "night_info"]
    assert all(item["game_id"] == "game-export-2" for item in exported["judgements"])
    assert exported["recent_summary"]
    assert exported["recent_summary"][0]["bucket"] == "night_info.storyteller_info"


def test_storyteller_build_decision_context_uses_bounded_inputs():
    agent = StorytellerAgent()
    agent.record_judgement(
        "night_info",
        decision="deliver",
        reason="chef_info",
        phase="first_night",
        day_number=1,
        round_number=1,
        player_id="p1",
        bucket="night_info.fixed_info",
    )
    state = GameState(
        phase=GamePhase.DAY_DISCUSSION,
        round_number=2,
        day_number=2,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="imp", team=Team.EVIL),
        ),
    )

    context = agent.build_decision_context(state, recent_limit=4)

    assert context.truth_view["players"][0]["true_role_id"] == "chef"
    assert context.public_state["phase"] == "day_discussion"
    assert isinstance(context.private_delivery_history, list)
    assert context.recent_judgements
    assert context.balance_context["round_number"] == 2


def test_storyteller_balance_sample_embeds_decision_context():
    agent = StorytellerAgent()
    state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="imp", team=Team.EVIL),
        ),
    )

    sample = agent.build_balance_sample(state, "p1", "chef")

    assert "decision_context" in sample
    assert sample["decision_context"]["public_state"]["phase"] == "first_night"
    assert "balance_context" in sample["decision_context"]


def test_storyteller_record_judgement_normalizes_standard_fields():
    agent = StorytellerAgent()

    entry = agent.record_judgement(
        "narration",
        decision="announce",
        reason="phase_open",
        phase="day_discussion",
    )

    assert entry["bucket"] == "phase_narration"
    assert "day_number" in entry
    assert "round_number" in entry
    assert "trace_id" in entry
    assert "adjudication_path" in entry
    assert "distortion_strategy" in entry


def test_storyteller_decide_night_info_keeps_fixed_info_scope_after_normalization():
    agent = StorytellerAgent()
    state = GameState(
        phase=GamePhase.FIRST_NIGHT,
        round_number=1,
        day_number=1,
        players=(
            PlayerState(player_id="p1", name="Alice", role_id="chef", team=Team.GOOD),
            PlayerState(player_id="p2", name="Bob", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p3", name="Charlie", role_id="washerwoman", team=Team.GOOD),
        ),
    )

    info = __import__("asyncio").run(agent.decide_night_info(state, "p1", "chef"))

    assert info
    recent = agent.get_recent_judgements(1)[0]
    assert recent["category"] == "night_info"
    assert recent["scope"] == "fixed_info"
    assert recent["bucket"] == "night_info.fixed_info"
