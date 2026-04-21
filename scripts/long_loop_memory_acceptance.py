"""Wave 3 P0-3: long-loop episodic memory and social graph acceptance runner."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.agents.ai_agent import AIAgent, Persona
from src.llm.mock_backend import MockBackend
from src.state.game_state import ChatMessage, GameEvent, GamePhase, GameState, PlayerState, Team, Visibility


def _backend() -> MockBackend:
    backend = MockBackend()
    backend.set_response(
        '{"action":"speak","content":"我先听听大家对 Bob 的看法。","tone":"calm","reasoning":"phase1"}'
    )
    backend.set_response(
        '{"action":"none","reasoning":"phase2"}'
    )
    backend.set_response(
        '{"action":"vote","decision":true,"reasoning":"phase3"}'
    )
    backend.set_response(
        '{"action":"speak","content":"Bob 这轮的说法还是很怪。","tone":"accusatory","reasoning":"phase4"}'
    )
    backend.set_response(
        '{"action":"speak","content":"我对 Cathy 的判断更有信心。","tone":"calm","reasoning":"phase5"}'
    )
    return backend


def _players() -> tuple[PlayerState, PlayerState, PlayerState]:
    return (
        PlayerState(player_id="p1", name="Alice", role_id="washerwoman", team=Team.GOOD),
        PlayerState(player_id="p2", name="Bob", role_id="imp", team=Team.EVIL),
        PlayerState(player_id="p3", name="Cathy", role_id="chef", team=Team.GOOD),
    )


def _state(
    *,
    game_id: str,
    phase: GamePhase,
    round_number: int,
    day_number: int,
    chat_messages: list[tuple[str, str, str | None]],
    event_entries: list[tuple[str, str | None, str | None, dict[str, Any]]],
) -> GameState:
    players = _players()
    chat_history = tuple(
        ChatMessage(
            speaker=speaker,
            content=content,
            phase=phase,
            round_number=round_number,
            recipient_ids=(recipient,) if recipient else None,
        )
        for speaker, content, recipient in chat_messages
    )
    event_log = tuple(
        GameEvent(
            event_type=event_type,
            phase=phase,
            round_number=round_number,
            actor=actor,
            target=target,
            payload=payload,
            visibility=Visibility.PUBLIC,
        )
        for event_type, actor, target, payload in event_entries
    )
    return GameState(
        game_id=game_id,
        phase=phase,
        round_number=round_number,
        day_number=day_number,
        players=players,
        seat_order=("p1", "p2", "p3"),
        chat_history=chat_history,
        event_log=event_log,
    )


async def run_acceptance() -> dict[str, Any]:
    backend = _backend()
    agent = AIAgent(
        player_id="p1",
        name="Alice",
        backend=backend,
        persona=Persona(
            description="谨慎观察者",
            speaking_style="先观察再表态",
            archetype="logic",
        ),
    )

    phase_specs = [
        (
            _state(
                game_id="p0-long-memory",
                phase=GamePhase.DAY_DISCUSSION,
                round_number=1,
                day_number=1,
                chat_messages=[
                    ("p2", "Bob 的说法有点怪。", None),
                    ("p3", "Cathy 的判断很靠谱。", None),
                ],
                event_entries=[
                    ("player_speaks", "p2", None, {"content": "Bob 的说法有点怪。"}),
                    ("player_speaks", "p3", None, {"content": "Cathy 的判断很靠谱。"}),
                ],
            ),
            "speak",
            "第一天白天：讨论与初始侧写",
        ),
        (
            _state(
                game_id="p0-long-memory",
                phase=GamePhase.NOMINATION,
                round_number=1,
                day_number=1,
                chat_messages=[
                    ("p2", "Bob 很可疑，需要被提名。", None),
                    ("p1", "我还想再听听 Bob 的解释。", None),
                    ("p3", "Cathy 这票我同意。", None),
                ],
                event_entries=[
                    ("nomination_started", "p3", "p2", {"threshold": 2}),
                    ("player_speaks", "p1", None, {"content": "我还想再听听 Bob 的解释。"}),
                ],
            ),
            "nomination_intent",
            "第一天提名：局势开始形成",
        ),
        (
            _state(
                game_id="p0-long-memory",
                phase=GamePhase.VOTING,
                round_number=1,
                day_number=1,
                chat_messages=[
                    ("p2", "Bob 现在看起来很危险。", None),
                    ("p3", "Cathy 的分析还是合理。", None),
                    ("p1", "这一票已经接近处决线了。", None),
                ],
                event_entries=[
                    ("vote_cast", "p1", "p2", {"vote": True}),
                    ("vote_cast", "p3", "p2", {"vote": True}),
                    ("voting_resolved", "storyteller", "p2", {"passed": True, "votes": 2, "needed": 2}),
                ],
            ),
            "vote",
            "第一天投票：票型开始收束",
        ),
        (
            _state(
                game_id="p0-long-memory",
                phase=GamePhase.NIGHT,
                round_number=2,
                day_number=1,
                chat_messages=[
                    ("p2", "Bob 这轮的说法还是很怪。", None),
                    ("p3", "Cathy 的判断依旧靠谱。", None),
                ],
                event_entries=[
                    ("player_death", "storyteller", "p2", {"reason": "execution"}),
                    ("execution_resolved", "storyteller", "p2", {"executed": "p2", "votes": 2}),
                ],
            ),
            "speak",
            "第一天夜晚：处决结果沉淀为新记忆",
        ),
        (
            _state(
                game_id="p0-long-memory",
                phase=GamePhase.DAY_DISCUSSION,
                round_number=2,
                day_number=2,
                chat_messages=[
                    ("p2", "Bob 的前后发言依然矛盾。", None),
                    ("p3", "Cathy 的解释让我更愿意暂时信任。", None),
                    ("p1", "Bob 的问题不能只看一轮。", None),
                ],
                event_entries=[
                    ("player_speaks", "p2", None, {"content": "Bob 的前后发言依然矛盾。"}),
                    ("player_speaks", "p3", None, {"content": "Cathy 的解释让我更愿意暂时信任。"}),
                ],
            ),
            "speak",
            "第二天白天：跨日记忆继续累积",
        ),
    ]

    agent.synchronize_role(phase_specs[0][0].get_player("p1"))
    agent.social_graph.init_player("p2", "Bob")
    agent.social_graph.init_player("p3", "Cathy")

    episode_counts: list[int] = []
    bob_trust_scores: list[float] = []
    cathy_trust_scores: list[float] = []
    bob_notes_counts: list[int] = []
    cathy_notes_counts: list[int] = []
    decisions: list[dict[str, Any]] = []

    for state, action_type, reflection_note in phase_specs:
        visible_state = agent._build_visible_state(state)
        legal_context = agent._build_legal_action_context(state, visible_state)
        for event in state.event_log:
            await agent.observe_event(event, visible_state)
        agent.working_memory.add_thought(f"{reflection_note}；我在持续跟踪 Bob 和 Cathy 的变化。")
        decision = await agent.act(visible_state, action_type, legal_context=legal_context)
        await agent.archive_phase_memory(visible_state)
        decisions.append(decision)

        bob_profile = agent.social_graph.get_profile("p2")
        cathy_profile = agent.social_graph.get_profile("p3")
        bob_trust_scores.append(round(bob_profile.trust_score if bob_profile else 0.0, 3))
        cathy_trust_scores.append(round(cathy_profile.trust_score if cathy_profile else 0.0, 3))
        bob_notes_counts.append(len(bob_profile.notes) if bob_profile else 0)
        cathy_notes_counts.append(len(cathy_profile.notes) if cathy_profile else 0)
        episode_counts.append(len(agent.episodic_memory.episodes))

    episode_summaries = [
        {
            "phase": episode.phase.value,
            "day_number": episode.day_number,
            "round_number": episode.round_number,
            "summary": episode.summary,
            "key_events": list(episode.key_events),
        }
        for episode in agent.episodic_memory.episodes
    ]
    episodic_summary = agent.episodic_memory.get_summary(max_episodes=5)

    metrics = {
        "episode_count": len(agent.episodic_memory.episodes),
        "episode_counts_progression": episode_counts,
        "episode_summaries": episode_summaries,
        "episodic_summary": episodic_summary,
        "bob_trust_scores": bob_trust_scores,
        "cathy_trust_scores": cathy_trust_scores,
        "bob_notes_count": bob_notes_counts[-1] if bob_notes_counts else 0,
        "cathy_notes_count": cathy_notes_counts[-1] if cathy_notes_counts else 0,
        "working_memory_empty": agent.working_memory.is_empty,
        "decision_actions": [decision.get("action") for decision in decisions],
    }
    return metrics


def _validate(metrics: dict[str, Any]) -> None:
    if metrics["episode_count"] < 5:
        raise SystemExit(f"episode_count too low: {metrics['episode_count']}")
    if metrics["episode_counts_progression"] != [1, 2, 3, 4, 5]:
        raise SystemExit(f"episode progression broken: {metrics['episode_counts_progression']}")
    if metrics["bob_trust_scores"][0] <= metrics["bob_trust_scores"][-1]:
        raise SystemExit(f"bob trust did not accumulate downward: {metrics['bob_trust_scores']}")
    if metrics["bob_trust_scores"][-1] > -0.2:
        raise SystemExit(f"bob trust too weakly accumulated: {metrics['bob_trust_scores']}")
    if metrics["cathy_trust_scores"][-1] <= metrics["cathy_trust_scores"][0]:
        raise SystemExit(f"cathy trust did not accumulate upward: {metrics['cathy_trust_scores']}")
    if metrics["bob_notes_count"] < 4:
        raise SystemExit(f"bob_notes_count too low: {metrics['bob_notes_count']}")
    if metrics["cathy_notes_count"] < 4:
        raise SystemExit(f"cathy_notes_count too low: {metrics['cathy_notes_count']}")
    if not metrics["working_memory_empty"]:
        raise SystemExit("working memory should be empty after repeated archives")
    summary = metrics["episodic_summary"]
    if ">> 第1天 白天" not in summary or ">> 第2天 白天" not in summary:
        raise SystemExit("episodic summary does not retain cross-day history")


def main() -> int:
    metrics = asyncio.run(run_acceptance())
    _validate(metrics)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print("long loop memory acceptance: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
