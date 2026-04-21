"""Multi-game / multi-round AI evaluation metrics for Wave 3."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.agents.ai_agent import AIAgent, Persona
from src.llm.base_backend import LLMBackend, LLMResponse, Message
from src.state.game_state import ChatMessage, GameEvent, GamePhase, GameState, PlayerState, Team

ARCHETYPES = ("logic", "aggressive", "cooperative", "chaos", "silent")
PRESSURE_LEVELS = ("weak", "medium", "strong")
GAME_COUNT = 10
ROUNDS_PER_GAME = len(PRESSURE_LEVELS)

logging.getLogger("src.agents.ai_agent").setLevel(logging.CRITICAL)


class InvalidJSONBackend(LLMBackend):
    async def generate(self, system_prompt: str, messages: list[Message], **kwargs) -> LLMResponse:
        return LLMResponse(content="not-json", tool_calls=[])

    def get_model_name(self) -> str:
        return "invalid-json"


def _game_players(game_index: int) -> tuple[PlayerState, PlayerState, PlayerState]:
    return (
        PlayerState(player_id="p1", name=f"Alice-{game_index}", role_id="washerwoman", team=Team.GOOD),
        PlayerState(player_id="p2", name=f"Bob-{game_index}", role_id="chef", team=Team.GOOD),
        PlayerState(player_id="p3", name=f"Cathy-{game_index}", role_id="imp", team=Team.EVIL),
    )


def _nomination_state(game_index: int, pressure: str) -> GameState:
    players = _game_players(game_index)
    bob_name = players[1].name
    chat_history = ()
    event_log = ()
    nominations_today = ()
    nominees_today = ()

    if pressure == "medium":
        chat_history = (
            ChatMessage(
                speaker="p3",
                content=f"{bob_name} 的说法有点怪。",
                phase=GamePhase.DAY_DISCUSSION,
                round_number=game_index,
            ),
            ChatMessage(
                speaker="p1",
                content=f"{bob_name} 这边我还要再看一眼。",
                phase=GamePhase.DAY_DISCUSSION,
                round_number=game_index,
            ),
        )
        event_log = (
            GameEvent(
                event_type="player_speaks",
                phase=GamePhase.DAY_DISCUSSION,
                round_number=game_index,
                actor="p3",
                payload={"content": f"{bob_name} 的说法有点怪。"},
            ),
        )
    elif pressure == "strong":
        chat_history = (
            ChatMessage(
                speaker="p3",
                content=f"{bob_name} 需要今天被提名。",
                phase=GamePhase.DAY_DISCUSSION,
                round_number=game_index,
            ),
            ChatMessage(
                speaker="p1",
                content=f"{bob_name} 前后不一致，而且很危险。",
                phase=GamePhase.DAY_DISCUSSION,
                round_number=game_index,
            ),
            ChatMessage(
                speaker="p3",
                content=f"我觉得 {bob_name} 很可疑，应该直接提。",
                phase=GamePhase.DAY_DISCUSSION,
                round_number=game_index,
            ),
        )
        event_log = (
            GameEvent(
                event_type="nomination_started",
                phase=GamePhase.NOMINATION,
                round_number=game_index,
                actor="p3",
                target="p2",
            ),
            GameEvent(
                event_type="player_speaks",
                phase=GamePhase.DAY_DISCUSSION,
                round_number=game_index,
                actor="p1",
                payload={"content": f"{bob_name} 前后不一致，而且很危险。"},
            ),
        )
        nominations_today = ("p3",)
        nominees_today = ("p2",)

    return GameState(
        game_id=f"trend-nom-{game_index}-{pressure}",
        players=players,
        phase=GamePhase.NOMINATION,
        round_number=game_index,
        day_number=game_index,
        seat_order=("p1", "p2", "p3"),
        nominations_today=nominations_today,
        nominees_today=nominees_today,
        chat_history=chat_history,
        event_log=event_log,
    )


def _vote_state(game_index: int, pressure: str) -> GameState:
    players = _game_players(game_index)
    bob_name = players[1].name
    votes_today: dict[str, bool] = {}
    chat_history = ()
    event_log = ()

    if pressure == "weak":
        votes_today = {"p3": False}
        chat_history = (
            ChatMessage(
                speaker="p3",
                content=f"{bob_name} 还没到必须处决的程度。",
                phase=GamePhase.VOTING,
                round_number=game_index,
            ),
        )
    elif pressure == "medium":
        votes_today = {"p1": True}
        chat_history = (
            ChatMessage(
                speaker="p3",
                content=f"{bob_name} 现在看着很危险。",
                phase=GamePhase.VOTING,
                round_number=game_index,
            ),
            ChatMessage(
                speaker="p1",
                content=f"我觉得可以先跟一票。",
                phase=GamePhase.VOTING,
                round_number=game_index,
            ),
        )
        event_log = (
            GameEvent(
                event_type="vote_cast",
                phase=GamePhase.VOTING,
                round_number=game_index,
                actor="p1",
                target="p2",
                payload={"vote": True},
            ),
        )
    else:
        votes_today = {"p1": True, "p3": True}
        chat_history = (
            ChatMessage(
                speaker="p3",
                content=f"{bob_name} 真的很像恶魔。",
                phase=GamePhase.VOTING,
                round_number=game_index,
            ),
            ChatMessage(
                speaker="p1",
                content="这一票已经接近处决线了。",
                phase=GamePhase.VOTING,
                round_number=game_index,
            ),
        )
        event_log = (
            GameEvent(
                event_type="vote_cast",
                phase=GamePhase.VOTING,
                round_number=game_index,
                actor="p1",
                target="p2",
                payload={"vote": True},
            ),
            GameEvent(
                event_type="vote_cast",
                phase=GamePhase.VOTING,
                round_number=game_index,
                actor="p3",
                target="p2",
                payload={"vote": True},
            ),
            GameEvent(
                event_type="voting_resolved",
                phase=GamePhase.VOTING,
                round_number=game_index,
                target="p2",
                payload={"passed": True},
            ),
        )

    return GameState(
        game_id=f"trend-vote-{game_index}-{pressure}",
        players=players,
        phase=GamePhase.VOTING,
        round_number=game_index,
        day_number=game_index,
        current_nominee="p2",
        current_nominator="p3",
        votes_today=votes_today,
        seat_order=("p1", "p2", "p3"),
        chat_history=chat_history,
        event_log=event_log,
    )


def _ambiguous_nomination_state(game_index: int) -> GameState:
    players = (
        PlayerState(player_id="p1", name=f"Alice-{game_index}", role_id="washerwoman", team=Team.GOOD),
        PlayerState(player_id="p2", name=f"Bob-{game_index}", role_id="chef", team=Team.GOOD),
        PlayerState(player_id="p3", name=f"Cathy-{game_index}", role_id="imp", team=Team.EVIL),
        PlayerState(player_id="p4", name=f"David-{game_index}", role_id="monk", team=Team.GOOD),
        PlayerState(player_id="p5", name=f"Eve-{game_index}", role_id="poisoner", team=Team.EVIL),
    )
    return GameState(
        game_id=f"trend-ambiguous-{game_index}",
        players=players,
        phase=GamePhase.NOMINATION,
        round_number=game_index,
        day_number=game_index,
        seat_order=("p1", "p2", "p3", "p4", "p5"),
        chat_history=(
            ChatMessage(
                speaker="p4",
                content=f"{players[1].name} 和 {players[2].name} 今天都很可疑。",
                phase=GamePhase.DAY_DISCUSSION,
                round_number=game_index,
            ),
            ChatMessage(
                speaker="p5",
                content=f"我怀疑 {players[1].name}，也怀疑 {players[2].name}。",
                phase=GamePhase.DAY_DISCUSSION,
                round_number=game_index,
            ),
        ),
        event_log=(
            GameEvent(
                event_type="player_speaks",
                phase=GamePhase.DAY_DISCUSSION,
                round_number=game_index,
                actor="p4",
                payload={"content": f"{players[1].name} 和 {players[2].name} 今天都很可疑。"},
            ),
            GameEvent(
                event_type="player_speaks",
                phase=GamePhase.DAY_DISCUSSION,
                round_number=game_index,
                actor="p5",
                payload={"content": f"我怀疑 {players[1].name}，也怀疑 {players[2].name}。"},
            ),
        ),
    )


async def _evaluate_single_game(game_index: int, archetype: str, backend: LLMBackend) -> dict[str, Any]:
    agent = AIAgent(
        player_id="p1",
        name=f"Tester-{archetype}-{game_index}",
        backend=backend,
        persona=Persona(
            description=f"{archetype} persona",
            speaking_style="自然表达",
            archetype=archetype,
        ),
    )
    agent.synchronize_role(_nomination_state(game_index, "weak").get_player("p1"))
    agent.social_graph.init_player("p2", f"Bob-{game_index}")
    agent.social_graph.init_player("p3", f"Cathy-{game_index}")

    nomination_actions: list[str] = []
    vote_actions: list[bool] = []
    round_records: list[dict[str, Any]] = []

    for pressure in PRESSURE_LEVELS:
        nomination_state = _nomination_state(game_index, pressure)
        vote_state = _vote_state(game_index, pressure)
        
        # W3-D: 让 Agent 平等观察场上事件，触发自主社交图谱更新
        for event in nomination_state.event_log:
            await agent.observe_event(event, agent._build_visible_state(nomination_state))
        for event in vote_state.event_log:
            await agent.observe_event(event, agent._build_visible_state(vote_state))
        nomination_visible = agent._build_visible_state(nomination_state)
        nomination_legal = agent._build_legal_action_context(nomination_state, nomination_visible)
        vote_visible = agent._build_visible_state(vote_state)
        vote_legal = agent._build_legal_action_context(vote_state, vote_visible)

        nomination = await agent.act(nomination_visible, "nomination_intent", legal_context=nomination_legal)
        vote = await agent.act(vote_visible, "vote", legal_context=vote_legal)

        nomination_actions.append(str(nomination.get("action", "none")))
        vote_actions.append(bool(vote.get("decision", False)))
        round_records.append(
            {
                "game_index": game_index,
                "archetype": archetype,
                "pressure": pressure,
                "nomination_action": nomination.get("action", "none"),
                "nomination_target": nomination.get("target"),
                "vote_decision": bool(vote.get("decision", False)),
                "vote_reasoning": vote.get("reasoning", ""),
            }
        )

    return {
        "game_index": game_index,
        "archetype": archetype,
        "nomination_actions": tuple(nomination_actions),
        "vote_actions": tuple(vote_actions),
        "round_records": round_records,
        "final_trust_p2": agent.social_graph.get_profile("p2").trust_score if agent.social_graph.get_profile("p2") else 0.5,
    }


async def _evaluate_ambiguous_nomination(game_index: int, archetype: str, backend: LLMBackend) -> dict[str, Any]:
    state = _ambiguous_nomination_state(game_index)
    agent = AIAgent(
        player_id="p1",
        name=f"Ambiguous-{archetype}-{game_index}",
        backend=backend,
        persona=Persona(
            description=f"{archetype} persona",
            speaking_style="自然表达",
            archetype=archetype,
        ),
    )
    agent.synchronize_role(state.get_player("p1"))
    for target_id, target_name in (("p2", f"Bob-{game_index}"), ("p3", f"Cathy-{game_index}"), ("p4", f"David-{game_index}"), ("p5", f"Eve-{game_index}")):
        agent.social_graph.init_player(target_id, target_name)
    agent.social_graph.update_trust("p2", -0.7)
    agent.social_graph.update_trust("p3", -0.7)
    agent.social_graph.add_note("p2", "今天发言比较飘")
    agent.social_graph.add_note("p3", "今天发言比较飘")
    agent.social_graph.add_note("p2", "需要继续追踪")
    agent.social_graph.add_note("p3", "需要继续追踪")

    visible_state = agent._build_visible_state(state)
    legal_context = agent._build_legal_action_context(state, visible_state)
    for event in state.event_log:
        await agent.observe_event(event, visible_state)

    candidate_band, best_score = agent._nomination_candidate_band(
        list(legal_context.legal_nomination_targets),
        visible_state,
        tolerance=0.05,
    )
    decision = await agent.act(visible_state, "nomination_intent", legal_context=legal_context)
    front_target = candidate_band[0] if candidate_band else None
    return {
        "game_index": game_index,
        "archetype": archetype,
        "candidate_band": candidate_band,
        "front_target": front_target,
        "best_score": round(best_score, 3),
        "decision_action": decision.get("action", "none"),
        "decision_target": decision.get("target"),
    }


def _sequence_strength(actions: tuple[Any, ...]) -> tuple[int, ...]:
    return tuple(1 if action in {True, "nominate"} else 0 for action in actions)


def _sequence_is_monotonic(sequence: tuple[int, ...]) -> bool:
    return all(left <= right for left, right in zip(sequence, sequence[1:]))


async def evaluate_agents() -> dict[str, Any]:
    backend = InvalidJSONBackend()
    game_reports: list[dict[str, Any]] = []
    all_round_records: list[dict[str, Any]] = []
    ambiguous_reports: list[dict[str, Any]] = []

    for game_index in range(1, GAME_COUNT + 1):
        for archetype in ARCHETYPES:
            report = await _evaluate_single_game(game_index, archetype, backend)
            game_reports.append(report)
            all_round_records.extend(report["round_records"])
            ambiguous_reports.append(await _evaluate_ambiguous_nomination(game_index, archetype, backend))

    level_nomination_counts: dict[str, Counter[str]] = {
        level: Counter() for level in PRESSURE_LEVELS
    }
    level_vote_counts: dict[str, Counter[str]] = {
        level: Counter() for level in PRESSURE_LEVELS
    }

    for record in all_round_records:
        level = str(record["pressure"])
        level_nomination_counts[level][str(record["nomination_action"])] += 1
        level_vote_counts[level]["yes" if record["vote_decision"] else "no"] += 1

    total_nomination_rounds = len(all_round_records)
    total_vote_rounds = len(all_round_records)
    weak_nomination_total = sum(level_nomination_counts["weak"].values()) or 1
    medium_nomination_total = sum(level_nomination_counts["medium"].values()) or 1
    strong_nomination_total = sum(level_nomination_counts["strong"].values()) or 1
    weak_vote_total = sum(level_vote_counts["weak"].values()) or 1
    medium_vote_total = sum(level_vote_counts["medium"].values()) or 1
    strong_vote_total = sum(level_vote_counts["strong"].values()) or 1

    weak_none_rate = level_nomination_counts["weak"]["none"] / weak_nomination_total
    medium_none_rate = level_nomination_counts["medium"]["none"] / medium_nomination_total
    strong_nomination_rate = level_nomination_counts["strong"]["nominate"] / strong_nomination_total

    weak_vote_false_rate = level_vote_counts["weak"]["no"] / weak_vote_total
    medium_vote_yes_rate = level_vote_counts["medium"]["yes"] / medium_vote_total
    strong_vote_yes_rate = level_vote_counts["strong"]["yes"] / strong_vote_total

    nomination_trend_hits = 0
    vote_trend_hits = 0
    for report in game_reports:
        nomination_strength = _sequence_strength(report["nomination_actions"])
        vote_strength = _sequence_strength(report["vote_actions"])
        if _sequence_is_monotonic(nomination_strength) and nomination_strength[-1] == 1:
            nomination_trend_hits += 1
        if _sequence_is_monotonic(vote_strength) and vote_strength[-1] == 1:
            vote_trend_hits += 1

    game_trend_total = len(game_reports) or 1
    nomination_trend_monotonicity_rate = nomination_trend_hits / game_trend_total
    vote_trend_monotonicity_rate = vote_trend_hits / game_trend_total

    archetype_signatures: dict[str, list[tuple[tuple[int, ...], tuple[int, ...]]]] = defaultdict(list)
    for report in game_reports:
        archetype_signatures[str(report["archetype"])].append(
            (_sequence_strength(report["nomination_actions"]), _sequence_strength(report["vote_actions"]))
        )

    archetype_representatives: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
    stability_ratios: list[float] = []
    for archetype in ARCHETYPES:
        signatures = archetype_signatures[archetype]
        if not signatures:
            continue
        most_common_signature, most_common_count = Counter(signatures).most_common(1)[0]
        archetype_representatives.append(most_common_signature)
        stability_ratios.append(most_common_count / len(signatures))

    social_trust_changes = [report["final_trust_p2"] for report in game_reports if report["final_trust_p2"] != 0.5]
    social_trust_responsiveness_score = len(social_trust_changes) / (len(game_reports) or 1)
    
    persona_diversity_score = len(set(archetype_representatives)) / len(ARCHETYPES)
    multi_game_stability_score = sum(stability_ratios) / len(stability_ratios) if stability_ratios else 0.0

    ambiguous_target_counts: Counter[str] = Counter(
        str(report["decision_target"])
        for report in ambiguous_reports
        if report["decision_action"] == "nominate" and report["decision_target"]
    )
    ambiguous_nomination_total = sum(ambiguous_target_counts.values()) or 1
    front_position_hits = sum(
        1
        for report in ambiguous_reports
        if report["decision_action"] == "nominate"
        and report["decision_target"]
        and report["decision_target"] == report["front_target"]
    )
    front_position_nomination_bias_rate = front_position_hits / ambiguous_nomination_total
    ambiguous_nomination_diversity_score = len(ambiguous_target_counts) / 2 if ambiguous_target_counts else 0.0

    archetype_vote_profiles: dict[str, dict[str, float]] = {}
    for archetype in ARCHETYPES:
        archetype_records = [record for record in all_round_records if record["archetype"] == archetype]
        total = len(archetype_records) or 1
        weak_records = [record for record in archetype_records if record["pressure"] == "weak"]
        medium_strong_records = [
            record for record in archetype_records if record["pressure"] in {"medium", "strong"}
        ]
        archetype_vote_profiles[archetype] = {
            "yes_rate": round(
                sum(1 for record in archetype_records if record["vote_decision"]) / total,
                3,
            ),
            "weak_no_rate": round(
                sum(1 for record in weak_records if not record["vote_decision"]) / (len(weak_records) or 1),
                3,
            ),
            "medium_strong_yes_rate": round(
                sum(1 for record in medium_strong_records if record["vote_decision"]) / (len(medium_strong_records) or 1),
                3,
            ),
        }

    aggressive_vote_push_rate = archetype_vote_profiles["aggressive"]["yes_rate"]
    silent_vote_restraint_rate = archetype_vote_profiles["silent"]["weak_no_rate"]
    cooperative_follow_rate = archetype_vote_profiles["cooperative"]["medium_strong_yes_rate"]

    return {
        "game_count": GAME_COUNT,
        "rounds_per_game": ROUNDS_PER_GAME,
        "archetype_count": len(ARCHETYPES),
        "records_total": total_nomination_rounds,
        "games": game_reports,
        "ai_none_nomination_rate": round(
            sum(1 for item in all_round_records if item["nomination_action"] == "none") / total_nomination_rounds,
            3,
        ),
        "ai_strong_nomination_rate": round(strong_nomination_rate, 3),
        "weak_nomination_none_rate": round(weak_none_rate, 3),
        "medium_nomination_none_rate": round(medium_none_rate, 3),
        "strong_vote_yes_rate": round(strong_vote_yes_rate, 3),
        "weak_vote_false_rate": round(weak_vote_false_rate, 3),
        "medium_vote_yes_rate": round(medium_vote_yes_rate, 3),
        "nomination_trend_monotonicity_rate": round(nomination_trend_monotonicity_rate, 3),
        "vote_trend_monotonicity_rate": round(vote_trend_monotonicity_rate, 3),
        "persona_diversity_score": round(persona_diversity_score, 3),
        "multi_game_stability_score": round(multi_game_stability_score, 3),
        "social_trust_responsiveness_score": round(social_trust_responsiveness_score, 3),
        "front_position_nomination_bias_rate": round(front_position_nomination_bias_rate, 3),
        "ambiguous_nomination_diversity_score": round(ambiguous_nomination_diversity_score, 3),
        "aggressive_vote_push_rate": round(aggressive_vote_push_rate, 3),
        "silent_vote_restraint_rate": round(silent_vote_restraint_rate, 3),
        "cooperative_follow_rate": round(cooperative_follow_rate, 3),
        "level_breakdown": {
            "nomination": {
                level: dict(counter) for level, counter in level_nomination_counts.items()
            },
            "vote": {
                level: dict(counter) for level, counter in level_vote_counts.items()
            },
        },
        "ambiguous_nomination": {
            "target_counts": dict(ambiguous_target_counts),
            "samples": ambiguous_reports,
        },
        "archetype_vote_profiles": archetype_vote_profiles,
    }


def _validate(metrics: dict[str, Any]) -> None:
    if metrics["game_count"] < 3:
        raise SystemExit(f"game_count too low: {metrics['game_count']}")
    if metrics["rounds_per_game"] < 3:
        raise SystemExit(f"rounds_per_game too low: {metrics['rounds_per_game']}")
    if metrics["ai_none_nomination_rate"] < 0.30:
        raise SystemExit(f"ai_none_nomination_rate too low: {metrics['ai_none_nomination_rate']}")
    if metrics["ai_strong_nomination_rate"] < 0.45:
        raise SystemExit(f"ai_strong_nomination_rate too low: {metrics['ai_strong_nomination_rate']}")
    if metrics["nomination_trend_monotonicity_rate"] < 0.6:
        raise SystemExit(
            f"nomination_trend_monotonicity_rate too low: {metrics['nomination_trend_monotonicity_rate']}"
        )
    if metrics["vote_trend_monotonicity_rate"] < 0.6:
        raise SystemExit(f"vote_trend_monotonicity_rate too low: {metrics['vote_trend_monotonicity_rate']}")
    if metrics["persona_diversity_score"] < 0.4:
        raise SystemExit(f"persona_diversity_score too low: {metrics['persona_diversity_score']}")
    if metrics["multi_game_stability_score"] < 0.4:
        raise SystemExit(f"multi_game_stability_score too low: {metrics['multi_game_stability_score']}")
    if metrics["social_trust_responsiveness_score"] < 0.5:
        raise SystemExit(f"social_trust_responsiveness_score too low: {metrics['social_trust_responsiveness_score']}")
    if metrics["front_position_nomination_bias_rate"] > 0.8:
        raise SystemExit(
            f"front_position_nomination_bias_rate too high: {metrics['front_position_nomination_bias_rate']}"
        )
    if metrics["ambiguous_nomination_diversity_score"] < 0.5:
        raise SystemExit(
            f"ambiguous_nomination_diversity_score too low: {metrics['ambiguous_nomination_diversity_score']}"
        )
    if metrics["aggressive_vote_push_rate"] < 0.65:
        raise SystemExit(f"aggressive_vote_push_rate too low: {metrics['aggressive_vote_push_rate']}")
    if metrics["silent_vote_restraint_rate"] < 0.8:
        raise SystemExit(f"silent_vote_restraint_rate too low: {metrics['silent_vote_restraint_rate']}")
    if metrics["cooperative_follow_rate"] < 0.75:
        raise SystemExit(f"cooperative_follow_rate too low: {metrics['cooperative_follow_rate']}")


def main() -> int:
    metrics = asyncio.run(evaluate_agents())
    _validate(metrics)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print("ai evaluation: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
