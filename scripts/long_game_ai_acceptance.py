"""Wave 3 long-game behavior acceptance runner.

Focuses on the remaining W3-B / W3-C / W3-D gaps:
- longer-loop nomination / voting behavior
- persona divergence that remains stable across repeated games
- cross-day episodic retention and social graph trajectories
"""

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
GAME_COUNT = 4

logging.getLogger("src.agents.ai_agent").setLevel(logging.CRITICAL)


class InvalidJSONBackend(LLMBackend):
    async def generate(self, system_prompt: str, messages: list[Message], **kwargs) -> LLMResponse:
        return LLMResponse(content="not-json", tool_calls=[])

    def get_model_name(self) -> str:
        return "invalid-json"


def _players(game_index: int) -> tuple[PlayerState, ...]:
    return (
        PlayerState(player_id="p1", name=f"Alice-{game_index}", role_id="washerwoman", team=Team.GOOD),
        PlayerState(player_id="p2", name=f"Bob-{game_index}", role_id="chef", team=Team.GOOD),
        PlayerState(player_id="p3", name=f"Cathy-{game_index}", role_id="empath", team=Team.GOOD),
        PlayerState(player_id="p4", name=f"David-{game_index}", role_id="monk", team=Team.GOOD),
        PlayerState(player_id="p5", name=f"Eve-{game_index}", role_id="imp", team=Team.EVIL),
    )


def _state(
    *,
    player_seed: int,
    game_id: str,
    phase: GamePhase,
    round_number: int,
    day_number: int,
    current_nominee: str | None = None,
    current_nominator: str | None = None,
    votes_today: dict[str, bool] | None = None,
    nominations_today: tuple[str, ...] = (),
    nominees_today: tuple[str, ...] = (),
    chat_messages: list[tuple[str, str]] | None = None,
    event_entries: list[tuple[str, str | None, str | None, dict[str, Any]]] | None = None,
) -> GameState:
    players = _players(player_seed)
    chat_history = tuple(
        ChatMessage(
            speaker=speaker,
            content=content,
            phase=phase,
            round_number=round_number,
        )
        for speaker, content in (chat_messages or [])
    )
    event_log = tuple(
        GameEvent(
            event_type=event_type,
            phase=phase,
            round_number=round_number,
            actor=actor,
            target=target,
            payload=payload,
        )
        for event_type, actor, target, payload in (event_entries or [])
    )
    return GameState(
        game_id=game_id,
        phase=phase,
        round_number=round_number,
        day_number=day_number,
        players=players,
        seat_order=("p1", "p2", "p3", "p4", "p5"),
        current_nominee=current_nominee,
        current_nominator=current_nominator,
        votes_today=votes_today or {},
        nominations_today=nominations_today,
        nominees_today=nominees_today,
        chat_history=chat_history,
        event_log=event_log,
    )


def _phase_specs(game_index: int) -> list[tuple[GameState, str, str]]:
    return [
        (
            _state(
                player_seed=game_index,
                game_id=f"long-game-{game_index}",
                phase=GamePhase.DAY_DISCUSSION,
                round_number=game_index,
                day_number=1,
                chat_messages=[
                    ("p4", f"Bob-{game_index} 今天前后说法有点怪。"),
                    ("p3", f"Cathy-{game_index} 的信息我暂时愿意信。"),
                    ("p5", f"我也觉得 Bob-{game_index} 看着不太对。"),
                ],
                event_entries=[
                    ("player_speaks", "p4", None, {"content": f"Bob-{game_index} 今天前后说法有点怪。"}),
                    ("player_speaks", "p3", None, {"content": f"Cathy-{game_index} 的信息我暂时愿意信。"}),
                ],
            ),
            "speak",
            "第一天白天：Bob 可疑，Cathy 暂时可信。",
        ),
        (
            _state(
                player_seed=game_index,
                game_id=f"long-game-{game_index}",
                phase=GamePhase.NOMINATION,
                round_number=game_index,
                day_number=1,
                chat_messages=[
                    ("p4", f"Bob-{game_index} 和 Eve-{game_index} 都有点怪，但证据还不算硬。"),
                    ("p3", f"如果非要提，我会先看 Bob-{game_index}。"),
                ],
                event_entries=[
                    ("player_speaks", "p4", None, {"content": f"Bob-{game_index} 和 Eve-{game_index} 都有点怪，但证据还不算硬。"}),
                    ("player_speaks", "p3", None, {"content": f"如果非要提，我会先看 Bob-{game_index}。"}),
                ],
            ),
            "nominate",
            "第一天提名：模糊可疑带，观察不同人格是否分流或保留。",
        ),
        (
            _state(
                player_seed=game_index,
                game_id=f"long-game-{game_index}",
                phase=GamePhase.VOTING,
                round_number=game_index,
                day_number=1,
                current_nominee="p2",
                current_nominator="p4",
                votes_today={"p4": True},
                chat_messages=[
                    ("p4", f"Bob-{game_index} 已经快到处决线了。"),
                    ("p3", f"如果票数够，我愿意跟票处决 Bob-{game_index}。"),
                ],
                event_entries=[
                    ("vote_cast", "p4", "p2", {"vote": True}),
                    ("player_speaks", "p3", None, {"content": f"如果票数够，我愿意跟票处决 Bob-{game_index}。"}),
                ],
            ),
            "vote",
            "第一天投票：测试跟票与保守人格差异。",
        ),
        (
            _state(
                player_seed=game_index,
                game_id=f"long-game-{game_index}",
                phase=GamePhase.NIGHT,
                round_number=game_index,
                day_number=1,
                current_nominee="p2",
                current_nominator="p4",
                votes_today={"p4": True, "p1": True},
                chat_messages=[
                    ("p3", f"白天的焦点还在 Bob-{game_index} 身上。"),
                ],
                event_entries=[
                    ("voting_resolved", "storyteller", "p2", {"passed": True, "votes": 2, "needed": 2}),
                    ("execution_resolved", "storyteller", "p2", {"executed": "p2", "votes": 2}),
                    ("player_death", "storyteller", "p2", {"reason": "execution"}),
                ],
            ),
            "speak",
            "第一天夜晚：处决 Bob，沉淀第一天记忆。",
        ),
        (
            _state(
                player_seed=game_index,
                game_id=f"long-game-{game_index}",
                phase=GamePhase.DAY_DISCUSSION,
                round_number=game_index + 10,
                day_number=2,
                chat_messages=[
                    ("p4", f"Eve-{game_index} 现在越来越像恶魔了。"),
                    ("p3", f"Cathy-{game_index} 昨天的信息依旧站得住。"),
                    ("p5", f"我还是觉得 Eve-{game_index} 很危险。"),
                ],
                event_entries=[
                    ("player_speaks", "p4", None, {"content": f"Eve-{game_index} 现在越来越像恶魔了。"}),
                    ("player_speaks", "p3", None, {"content": f"Cathy-{game_index} 昨天的信息依旧站得住。"}),
                ],
            ),
            "speak",
            "第二天白天：跨日把怀疑转向 Eve，并继续信任 Cathy。",
        ),
        (
            _state(
                player_seed=game_index,
                game_id=f"long-game-{game_index}",
                phase=GamePhase.NOMINATION,
                round_number=game_index + 10,
                day_number=2,
                nominations_today=("p4",),
                nominees_today=("p2",),
                chat_messages=[
                    ("p4", f"如果今天继续提名，我首选 Eve-{game_index}。"),
                    ("p3", f"Eve-{game_index} 的问题比昨天更大。"),
                ],
                event_entries=[
                    ("nomination_started", "p4", "p5", {"threshold": 2}),
                    ("player_speaks", "p3", None, {"content": f"Eve-{game_index} 的问题比昨天更大。"}),
                ],
            ),
            "nominate",
            "第二天提名：强信号场景，观察是否稳定推进。",
        ),
        (
            _state(
                player_seed=game_index,
                game_id=f"long-game-{game_index}",
                phase=GamePhase.VOTING,
                round_number=game_index + 10,
                day_number=2,
                current_nominee="p5",
                current_nominator="p4",
                votes_today={"p4": True},
                nominations_today=("p4",),
                nominees_today=("p2", "p5"),
                chat_messages=[
                    ("p4", f"Eve-{game_index} 这票已经接近终结。"),
                    ("p3", f"如果现在不投 Eve-{game_index}，后面会更难。"),
                ],
                event_entries=[
                    ("vote_cast", "p4", "p5", {"vote": True}),
                    ("player_speaks", "p3", None, {"content": f"如果现在不投 Eve-{game_index}，后面会更难。"}),
                ],
            ),
            "vote",
            "第二天投票：长局里继续检验人格化投票。",
        ),
    ]


async def _run_archetype_game(game_index: int, archetype: str) -> dict[str, Any]:
    backend = InvalidJSONBackend()
    agent = AIAgent(
        player_id="p1",
        name=f"Alice-{archetype}-{game_index}",
        backend=backend,
        persona=Persona(
            description=f"{archetype} persona",
            speaking_style="自然表达",
            archetype=archetype,
        ),
    )

    specs = _phase_specs(game_index)
    agent.synchronize_role(specs[0][0].get_player("p1"))
    for player in specs[0][0].players:
        if player.player_id != "p1":
            agent.social_graph.init_player(player.player_id, player.name)

    decisions: list[dict[str, Any]] = []
    episode_counts: list[int] = []

    for state, action_type, reflection_note in specs:
        visible_state = agent._build_visible_state(state)
        legal_context = agent._build_legal_action_context(state, visible_state)
        for event in state.event_log:
            await agent.observe_event(event, visible_state)
        agent.working_memory.add_thought(reflection_note)
        decision = await agent.act(visible_state, action_type, legal_context=legal_context)
        await agent.archive_phase_memory(visible_state)
        decisions.append(
            {
                "phase": state.phase.value,
                "day_number": state.day_number,
                "round_number": state.round_number,
                "action_type": action_type,
                "action": decision.get("action"),
                "target": decision.get("target"),
                "decision": decision.get("decision"),
            }
        )
        episode_counts.append(len(agent.episodic_memory.episodes))

    nomination_signature = tuple(
        f"{item['action']}:{item['target'] or '-'}"
        for item in decisions
        if item["action_type"] in {"nomination_intent", "nominate"}
    )
    vote_signature = tuple(
        bool(item["decision"])
        for item in decisions
        if item["action_type"] == "vote"
    )
    signature = nomination_signature + tuple("Y" if value else "N" for value in vote_signature)

    bob_profile = agent.social_graph.get_profile("p2")
    cathy_profile = agent.social_graph.get_profile("p3")
    eve_profile = agent.social_graph.get_profile("p5")
    episodic_summary = agent.episodic_memory.get_summary(max_episodes=8)
    return {
        "game_index": game_index,
        "archetype": archetype,
        "signature": signature,
        "nomination_signature": nomination_signature,
        "vote_signature": vote_signature,
        "decisions": decisions,
        "episode_count": len(agent.episodic_memory.episodes),
        "episode_counts_progression": episode_counts,
        "episodic_summary": episodic_summary,
        "bob_trust": round(bob_profile.trust_score if bob_profile else 0.0, 3),
        "cathy_trust": round(cathy_profile.trust_score if cathy_profile else 0.0, 3),
        "eve_trust": round(eve_profile.trust_score if eve_profile else 0.0, 3),
        "bob_notes_count": len(bob_profile.notes) if bob_profile else 0,
        "cathy_notes_count": len(cathy_profile.notes) if cathy_profile else 0,
        "eve_notes_count": len(eve_profile.notes) if eve_profile else 0,
    }


async def run_acceptance() -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    for game_index in range(1, GAME_COUNT + 1):
        for archetype in ARCHETYPES:
            reports.append(await _run_archetype_game(game_index, archetype))

    signatures_by_archetype: dict[str, list[tuple[str, ...]]] = defaultdict(list)
    nomination_counts: dict[str, list[int]] = defaultdict(list)
    vote_yes_counts: dict[str, list[int]] = defaultdict(list)
    retention_hits = 0
    social_hits = 0

    for report in reports:
        archetype = str(report["archetype"])
        signature = tuple(report["signature"])
        signatures_by_archetype[archetype].append(signature)
        nomination_counts[archetype].append(
            sum(1 for entry in report["nomination_signature"] if not entry.startswith("none"))
        )
        vote_yes_counts[archetype].append(sum(1 for value in report["vote_signature"] if value))

        if (
            report["episode_count"] == len(_phase_specs(report["game_index"]))
            and report["episode_counts_progression"] == list(range(1, len(_phase_specs(report["game_index"])) + 1))
            and ">> 第1天 白天" in report["episodic_summary"]
            and ">> 第2天 白天" in report["episodic_summary"]
        ):
            retention_hits += 1
        if (
            report["bob_trust"] < report["cathy_trust"]
            and report["eve_trust"] < report["cathy_trust"]
            and report["bob_notes_count"] >= 2
            and report["eve_notes_count"] >= 2
        ):
            social_hits += 1

    representative_signatures: list[tuple[str, ...]] = []
    archetype_stability: dict[str, float] = {}
    for archetype in ARCHETYPES:
        signature_counter = Counter(signatures_by_archetype[archetype])
        representative, count = signature_counter.most_common(1)[0]
        representative_signatures.append(representative)
        archetype_stability[archetype] = round(count / len(signatures_by_archetype[archetype]), 3)

    long_game_persona_diversity_score = round(
        len(set(representative_signatures)) / len(ARCHETYPES),
        3,
    )
    long_game_stability_score = round(
        sum(archetype_stability.values()) / len(archetype_stability),
        3,
    )
    long_game_retention_rate = round(retention_hits / len(reports), 3)
    long_game_social_consistency_rate = round(social_hits / len(reports), 3)

    aggressive_nomination_rate = round(
        sum(nomination_counts["aggressive"]) / (len(nomination_counts["aggressive"]) * 2 or 1),
        3,
    )
    silent_nomination_rate = round(
        sum(nomination_counts["silent"]) / (len(nomination_counts["silent"]) * 2 or 1),
        3,
    )
    aggressive_vote_push_rate = round(
        sum(vote_yes_counts["aggressive"]) / (len(vote_yes_counts["aggressive"]) * 2 or 1),
        3,
    )
    silent_vote_restraint_rate = round(
        1.0 - (sum(vote_yes_counts["silent"]) / (len(vote_yes_counts["silent"]) * 2 or 1)),
        3,
    )

    return {
        "game_count": GAME_COUNT,
        "archetype_count": len(ARCHETYPES),
        "report_count": len(reports),
        "long_game_persona_diversity_score": long_game_persona_diversity_score,
        "long_game_stability_score": long_game_stability_score,
        "long_game_retention_rate": long_game_retention_rate,
        "long_game_social_consistency_rate": long_game_social_consistency_rate,
        "aggressive_nomination_rate": aggressive_nomination_rate,
        "silent_nomination_rate": silent_nomination_rate,
        "aggressive_vote_push_rate": aggressive_vote_push_rate,
        "silent_vote_restraint_rate": silent_vote_restraint_rate,
        "archetype_stability": archetype_stability,
        "reports": reports,
    }


def _validate(metrics: dict[str, Any]) -> None:
    if metrics["long_game_persona_diversity_score"] < 0.6:
        raise SystemExit(
            f"long_game_persona_diversity_score too low: {metrics['long_game_persona_diversity_score']}"
        )
    if metrics["long_game_stability_score"] < 0.75:
        raise SystemExit(f"long_game_stability_score too low: {metrics['long_game_stability_score']}")
    if metrics["long_game_retention_rate"] < 1.0:
        raise SystemExit(f"long_game_retention_rate too low: {metrics['long_game_retention_rate']}")
    if metrics["long_game_social_consistency_rate"] < 0.8:
        raise SystemExit(
            f"long_game_social_consistency_rate too low: {metrics['long_game_social_consistency_rate']}"
        )
    if metrics["aggressive_nomination_rate"] <= metrics["silent_nomination_rate"]:
        raise SystemExit(
            "aggressive_nomination_rate should exceed silent_nomination_rate: "
            f"{metrics['aggressive_nomination_rate']} <= {metrics['silent_nomination_rate']}"
        )
    if metrics["aggressive_vote_push_rate"] <= (1.0 - metrics["silent_vote_restraint_rate"]):
        raise SystemExit(
            "aggressive_vote_push_rate should exceed silent_yes_rate: "
            f"{metrics['aggressive_vote_push_rate']} <= {1.0 - metrics['silent_vote_restraint_rate']}"
        )


def main() -> int:
    metrics = asyncio.run(run_acceptance())
    _validate(metrics)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print("long game ai acceptance: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
