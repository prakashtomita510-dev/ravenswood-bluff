"""说书人平衡裁量样本与评估工具。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.state.game_state import GameEvent, GamePhase, GameState, PlayerState, Team


class StorytellerBalanceSignal(BaseModel):
    good_alive: int
    evil_alive: int
    alive_total: int
    alive_margin: int
    reached_final_4: bool
    reached_final_3: bool
    ended_before_day_3: bool
    single_side_runaway_risk: bool
    hard_lock_risk: bool
    execution_count: int
    no_nomination_count: int
    private_info_delivery_count: int
    night_action_resolution_count: int
    early_end_pressure: bool
    storyteller_judgement_count: int
    suppressed_info_count: int
    distorted_info_count: int
    legacy_fallback_count: int
    human_storyteller_step_count: int


class StorytellerAdjudicationSample(BaseModel):
    game_id: str
    script_id: str
    seed: str | None = None
    round_number: int
    day_number: int
    phase: str
    seat_order: list[str]
    players_truth: list[dict[str, Any]]
    players_public_state: list[dict[str, Any]]
    players_private_delivery_history: dict[str, list[dict[str, Any]]]
    event_log_so_far: list[dict[str, Any]]
    current_effects: dict[str, dict[str, Any]]
    storyteller_context: dict[str, Any]
    candidate_adjudications: list[dict[str, Any]] = Field(default_factory=list)
    chosen_adjudication: dict[str, Any] | None = None
    balance_signals: StorytellerBalanceSignal


_PHASE_ORDER = {
    GamePhase.SETUP: 0,
    GamePhase.FIRST_NIGHT: 1,
    GamePhase.DAY_DISCUSSION: 2,
    GamePhase.NOMINATION: 3,
    GamePhase.VOTING: 4,
    GamePhase.EXECUTION: 5,
    GamePhase.NIGHT: 6,
    GamePhase.GAME_OVER: 7,
}

_DEFAULT_NODE_EVENT_TYPES = {
    "private_info_delivered",
    "night_action_resolved",
    "nomination_started",
    "voting_resolved",
    "execution_resolved",
}

_DAY_EVENT_CATEGORY_MAP = {
    "nomination_started": {"nomination_started", "nomination_choice", "nomination_window"},
    "voting_resolved": {"voting", "voting_resolution"},
    "execution_resolved": {"execution"},
}

_FIXED_INFO_TYPES = {
    "washerwoman_info",
    "librarian_info",
    "investigator_info",
    "chef_info",
    "empath_info",
    "undertaker_info",
}

_STORYTELLER_INFO_TYPES = {
    "fortune_teller_info",
    "ravenkeeper_info",
}


def _phase_to_value(phase: GamePhase | str | None) -> str | None:
    if phase is None:
        return None
    if hasattr(phase, "value"):
        return getattr(phase, "value")
    return str(phase)


def _serialize_player_truth(player: PlayerState) -> dict[str, Any]:
    return {
        "player_id": player.player_id,
        "name": player.name,
        "true_role_id": player.true_role_id or player.role_id,
        "perceived_role_id": player.perceived_role_id,
        "public_claim_role_id": player.public_claim_role_id,
        "team": player.team.value,
        "current_team": (player.current_team or player.team).value,
        "is_alive": player.is_alive,
        "statuses": [status.value for status in player.statuses],
        "storyteller_notes": list(player.storyteller_notes),
        "ongoing_effects": list(player.ongoing_effects),
    }


def _serialize_player_public_state(player: PlayerState) -> dict[str, Any]:
    return {
        "player_id": player.player_id,
        "name": player.name,
        "public_claim_role_id": player.public_claim_role_id,
        "current_team": (player.current_team or player.team).value,
        "is_alive": player.is_alive,
        "ghost_votes_remaining": player.ghost_votes_remaining,
        "has_used_dead_vote": player.has_used_dead_vote,
    }


def _serialize_event(event: GameEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "phase": event.phase.value,
        "round_number": event.round_number,
        "trace_id": event.trace_id,
        "actor": event.actor,
        "target": event.target,
        "visibility": event.visibility.value,
        "payload": event.payload,
        "timestamp": event.timestamp.isoformat(),
    }


def _collect_private_delivery_history(state: GameState) -> dict[str, list[dict[str, Any]]]:
    history: dict[str, list[dict[str, Any]]] = {}
    for event in state.event_log:
        if event.event_type != "private_info_delivered" or not event.target:
            continue
        history.setdefault(event.target, []).append(
            {
                "trace_id": event.trace_id,
                "phase": event.phase.value,
                "round_number": event.round_number,
                "payload": event.payload,
            }
        )
    return history


def _collect_current_effects(state: GameState) -> dict[str, dict[str, Any]]:
    effects: dict[str, dict[str, Any]] = {}
    for player in state.players:
        effects[player.player_id] = {
            "is_poisoned": player.is_poisoned,
            "is_drunk": player.is_drunk,
            "statuses": [status.value for status in player.statuses],
            "ongoing_effects": list(player.ongoing_effects),
            "storyteller_notes": list(player.storyteller_notes),
        }
    return effects


def _collect_storyteller_context(state: GameState) -> dict[str, Any]:
    config = state.config
    nomination_history = state.payload.get("nomination_history", [])
    last_private_delivery = next(
        (
            {
                "target": event.target,
                "info_type": event.payload.get("type"),
                "phase": event.phase.value,
            }
            for event in reversed(state.event_log)
            if event.event_type == "private_info_delivered"
        ),
        None,
    )
    return {
        "viewer_mode": config.storyteller_mode if config else "unknown",
        "backend_mode": config.backend_mode if config else "unknown",
        "human_mode": config.human_mode if config else "unknown",
        "audit_mode": bool(config.audit_mode) if config else False,
        "fortune_teller_red_herring": state.payload.get("fortune_teller_red_herring"),
        "nomination_history_count": len(nomination_history),
        "current_nomination_stage": state.payload.get("nomination_state", {}).get("stage"),
        "last_private_delivery": last_private_delivery,
        "winning_team": state.winning_team.value if state.winning_team else None,
    }


def derive_balance_signals(
    state: GameState,
    recent_judgements: list[dict[str, Any]] | None = None,
) -> StorytellerBalanceSignal:
    recent_judgements = list(recent_judgements or [])
    good_alive = sum(1 for player in state.get_alive_players() if (player.current_team or player.team) == Team.GOOD)
    evil_alive = sum(1 for player in state.get_alive_players() if (player.current_team or player.team) == Team.EVIL)
    alive_total = good_alive + evil_alive
    nomination_history = state.payload.get("nomination_history", [])
    recent_no_nomination = [
        item for item in nomination_history[-2:]
        if item.get("kind") == "no_nomination"
    ]
    execution_count = sum(1 for event in state.event_log if event.event_type == "execution_resolved" and (event.payload.get("executed") or event.target))
    private_info_delivery_count = sum(1 for event in state.event_log if event.event_type == "private_info_delivered")
    night_action_resolution_count = sum(1 for event in state.event_log if event.event_type == "night_action_resolved")
    no_nomination_count = sum(1 for item in nomination_history if item.get("kind") == "no_nomination")
    early_end_pressure = (state.day_number <= 2 and (alive_total <= 4 or abs(good_alive - evil_alive) >= 2)) or (
        len(recent_no_nomination) >= 2 and alive_total <= 4
    )
    suppressed_info_count = sum(
        1
        for entry in recent_judgements
        if entry.get("category") == "night_info" and entry.get("decision") == "suppressed"
    )
    distorted_info_count = sum(
        1
        for entry in recent_judgements
        if entry.get("category") == "night_info" and entry.get("distortion_strategy") not in {None, "", "none"}
    )
    legacy_fallback_count = sum(
        1
        for entry in recent_judgements
        if "legacy_fallback" in str(entry.get("adjudication_path") or entry.get("contract_mode") or "")
    )
    human_storyteller_step_count = sum(
        1 for entry in recent_judgements if entry.get("category") == "human_step"
    )
    return StorytellerBalanceSignal(
        good_alive=good_alive,
        evil_alive=evil_alive,
        alive_total=alive_total,
        alive_margin=abs(good_alive - evil_alive),
        reached_final_4=alive_total <= 4,
        reached_final_3=alive_total <= 3,
        ended_before_day_3=bool(state.winning_team) and state.day_number < 3,
        single_side_runaway_risk=abs(good_alive - evil_alive) >= 3,
        hard_lock_risk=len(recent_no_nomination) >= 2 and alive_total <= 5,
        execution_count=execution_count,
        no_nomination_count=no_nomination_count,
        private_info_delivery_count=private_info_delivery_count,
        night_action_resolution_count=night_action_resolution_count,
        early_end_pressure=early_end_pressure,
        storyteller_judgement_count=len(recent_judgements),
        suppressed_info_count=suppressed_info_count,
        distorted_info_count=distorted_info_count,
        legacy_fallback_count=legacy_fallback_count,
        human_storyteller_step_count=human_storyteller_step_count,
    )


def build_storyteller_adjudication_sample(
    state: GameState,
    *,
    storyteller_agent: Any | None = None,
    chosen_adjudication: dict[str, Any] | None = None,
    candidate_adjudications: list[dict[str, Any]] | None = None,
    seed: str | None = None,
) -> StorytellerAdjudicationSample:
    recent_judgements = []
    if storyteller_agent and hasattr(storyteller_agent, "get_recent_judgements"):
        recent_judgements = list(storyteller_agent.get_recent_judgements(50))
    chosen = chosen_adjudication or (recent_judgements[-1] if recent_judgements else None)
    candidates = list(candidate_adjudications or [])
    return StorytellerAdjudicationSample(
        game_id=state.game_id,
        script_id=state.config.script_id if state.config else "trouble_brewing",
        seed=seed,
        round_number=state.round_number,
        day_number=state.day_number,
        phase=state.phase.value,
        seat_order=list(state.seat_order),
        players_truth=[_serialize_player_truth(player) for player in state.players],
        players_public_state=[_serialize_player_public_state(player) for player in state.players],
        players_private_delivery_history=_collect_private_delivery_history(state),
        event_log_so_far=[_serialize_event(event) for event in state.event_log],
        current_effects=_collect_current_effects(state),
        storyteller_context=_collect_storyteller_context(state),
        candidate_adjudications=candidates,
        chosen_adjudication=chosen,
        balance_signals=derive_balance_signals(state, recent_judgements),
    )


def _phase_rank(phase: GamePhase) -> int:
    return _PHASE_ORDER.get(phase, 999)


def _select_base_state_for_event(
    final_state: GameState,
    event: GameEvent,
    snapshots: list[GameState] | None,
) -> GameState:
    if not snapshots:
        return final_state
    eligible = [
        snapshot
        for snapshot in snapshots
        if (
            snapshot.round_number < event.round_number
            or (
                snapshot.round_number == event.round_number
                and _phase_rank(snapshot.phase) <= _phase_rank(event.phase)
            )
        )
    ]
    return eligible[-1] if eligible else snapshots[0]


def _build_event_node_adjudication(event: GameEvent) -> dict[str, Any]:
    return {
        "category": "event_node",
        "decision": event.event_type,
        "trace_id": event.trace_id,
        "phase": event.phase.value,
        "round_number": event.round_number,
        "actor": event.actor,
        "target": event.target,
        "visibility": event.visibility.value,
        "payload": event.payload,
    }


def _normalize_private_info_judgement_for_event(
    entry: dict[str, Any],
    event: GameEvent,
) -> dict[str, Any]:
    if event.event_type != "private_info_delivered":
        return entry
    if entry.get("category") != "private_info":
        return entry

    info_type = str(entry.get("info_type") or (event.payload or {}).get("type") or "")
    if not info_type.endswith("_info"):
        return entry

    normalized = dict(entry)
    if info_type in _FIXED_INFO_TYPES:
        scope = "fixed_info"
        adjudication_path = "fixed_info.adjudicated"
    elif info_type in _STORYTELLER_INFO_TYPES:
        scope = "storyteller_info"
        adjudication_path = "storyteller_info.adjudicated"
    else:
        scope = "storyteller_info"
        adjudication_path = "adjudicated"

    normalized["category"] = "night_info"
    normalized.setdefault("decision", "deliver")
    normalized.setdefault("player_id", event.target)
    normalized.setdefault("target", event.target)
    normalized.setdefault("source", "private_info_delivered")
    normalized["scope"] = scope
    normalized["bucket"] = f"night_info.{scope}"
    normalized["adjudication_path"] = normalized.get("adjudication_path") or adjudication_path
    return normalized


def _match_recent_judgements_for_event(
    recent_judgements: list[dict[str, Any]],
    event: GameEvent,
) -> list[dict[str, Any]]:
    def _filter_for_event(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if event.event_type == "private_info_delivered":
            payload = event.payload or {}
            target = event.target
            info_type = payload.get("type")
            filtered = [
                entry
                for entry in entries
                if entry.get("category") in {"night_info", "private_info"}
                and (
                    entry.get("player_id") == target
                    or entry.get("actor") == target
                    or entry.get("target") == target
                )
                and (info_type is None or entry.get("info_type") == info_type)
            ]
            return [_normalize_private_info_judgement_for_event(entry, event) for entry in filtered]
        mapped = _DAY_EVENT_CATEGORY_MAP.get(event.event_type)
        if mapped:
            return [entry for entry in entries if entry.get("category") in mapped]
        return entries

    exact = [
        entry
        for entry in recent_judgements
        if entry.get("trace_id") and entry.get("trace_id") == event.trace_id
    ]
    exact = _filter_for_event(exact)
    if exact:
        return exact

    phase_value = event.phase.value
    same_round_same_phase = [
        entry
        for entry in recent_judgements
            if entry.get("round_number") == event.round_number
            and _phase_to_value(entry.get("phase")) == phase_value
    ]
    if event.event_type == "private_info_delivered":
        scoped_exact = _filter_for_event(same_round_same_phase)
        if scoped_exact:
            return scoped_exact[-4:]
        scoped = [
            entry
            for entry in same_round_same_phase
            if entry.get("category") == "night_info"
        ]
        if scoped:
            return scoped[-4:]
    if event.event_type in _DAY_EVENT_CATEGORY_MAP:
        scoped = _filter_for_event(same_round_same_phase)
        if scoped:
            return scoped[-4:]
    return same_round_same_phase[-4:]


def _iter_sample_judgements(sample: StorytellerAdjudicationSample) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if sample.chosen_adjudication:
        entries.append(sample.chosen_adjudication)
    entries.extend(sample.candidate_adjudications)
    return entries


def aggregate_storyteller_node_samples(
    samples: list[StorytellerAdjudicationSample],
) -> dict[str, Any]:
    summary = {
        "node_count": len(samples),
        "judgement_entry_count": 0,
        "night_info_judgement_count": 0,
        "suppressed_info_count": 0,
        "distorted_info_count": 0,
        "legacy_fallback_count": 0,
        "human_storyteller_step_count": 0,
        "event_node_fallback_count": 0,
        "private_info_delivery_node_count": 0,
        "night_action_resolution_node_count": 0,
        "nomination_started_node_count": 0,
        "voting_resolved_node_count": 0,
        "execution_resolved_node_count": 0,
        "ended_before_day_3_count": 0,
        "reached_final_4_count": 0,
        "reached_final_3_count": 0,
        "single_side_runaway_risk_count": 0,
        "hard_lock_risk_count": 0,
        "judgement_category_counts": {},
        "judgement_bucket_counts": {},
        "distortion_strategy_counts": {},
        "adjudication_path_counts": {},
        "phase_counts": {},
        "event_type_counts": {},
        "night_info_delivers": 0,
    }
    for sample in samples:
        if sample.balance_signals.ended_before_day_3:
            summary["ended_before_day_3_count"] += 1
        if sample.balance_signals.reached_final_4:
            summary["reached_final_4_count"] += 1
        if sample.balance_signals.reached_final_3:
            summary["reached_final_3_count"] += 1
        if sample.balance_signals.single_side_runaway_risk:
            summary["single_side_runaway_risk_count"] += 1
        if sample.balance_signals.hard_lock_risk:
            summary["hard_lock_risk_count"] += 1

        event_type = sample.event_log_so_far[-1]["event_type"] if sample.event_log_so_far else None
        if event_type:
            summary["event_type_counts"][event_type] = summary["event_type_counts"].get(event_type, 0) + 1
        if event_type == "private_info_delivered":
            summary["private_info_delivery_node_count"] += 1
        elif event_type == "night_action_resolved":
            summary["night_action_resolution_node_count"] += 1
        elif event_type == "nomination_started":
            summary["nomination_started_node_count"] += 1
        elif event_type == "voting_resolved":
            summary["voting_resolved_node_count"] += 1
        elif event_type == "execution_resolved":
            summary["execution_resolved_node_count"] += 1

        for entry in _iter_sample_judgements(sample):
            summary["judgement_entry_count"] += 1
            category = entry.get("category")
            if category:
                summary["judgement_category_counts"][category] = summary["judgement_category_counts"].get(category, 0) + 1
            bucket = entry.get("bucket")
            if bucket:
                summary["judgement_bucket_counts"][bucket] = summary["judgement_bucket_counts"].get(bucket, 0) + 1
            phase = _phase_to_value(entry.get("phase"))
            if phase:
                summary["phase_counts"][phase] = summary["phase_counts"].get(phase, 0) + 1
            if category == "night_info":
                summary["night_info_judgement_count"] += 1
                if entry.get("decision") == "suppressed":
                    summary["suppressed_info_count"] += 1
                if entry.get("decision") == "deliver":
                    summary["night_info_delivers"] += 1
                distortion_strategy = entry.get("distortion_strategy")
                if distortion_strategy not in {None, "", "none"}:
                    summary["distorted_info_count"] += 1
                    summary["distortion_strategy_counts"][str(distortion_strategy)] = (
                        summary["distortion_strategy_counts"].get(str(distortion_strategy), 0) + 1
                    )
            adjudication_path = str(entry.get("adjudication_path") or entry.get("contract_mode") or "")
            if adjudication_path:
                summary["adjudication_path_counts"][adjudication_path] = (
                    summary["adjudication_path_counts"].get(adjudication_path, 0) + 1
                )
            if "legacy_fallback" in adjudication_path:
                summary["legacy_fallback_count"] += 1
            if category == "human_step":
                summary["human_storyteller_step_count"] += 1
            if category == "event_node":
                summary["event_node_fallback_count"] += 1
    
    # [A3-ST-3] 增加最低门槛统计计算
    summary["fallback_rate"] = round(summary["legacy_fallback_count"] / (summary["judgement_entry_count"] or 1), 3)
    summary["distortion_rate"] = round(summary["distorted_info_count"] / (summary["night_info_judgement_count"] or 1), 3)
    # 覆盖率：产出的 night_info judgement 数量 / 实际交付私密信息的节点数量
    summary["night_info_coverage"] = round(summary["night_info_judgement_count"] / (summary["private_info_delivery_node_count"] or 1), 3)
    
    return summary


def build_storyteller_node_samples(
    final_state: GameState,
    *,
    snapshots: list[GameState] | None = None,
    storyteller_agent: Any | None = None,
    seed: str | None = None,
    interesting_event_types: set[str] | None = None,
) -> list[StorytellerAdjudicationSample]:
    node_event_types = interesting_event_types or _DEFAULT_NODE_EVENT_TYPES
    all_events = list(final_state.event_log)
    recent_judgements = []
    if storyteller_agent and hasattr(storyteller_agent, "get_recent_judgements"):
        if hasattr(storyteller_agent, "decision_ledger"):
            recent_judgements = list(getattr(storyteller_agent, "decision_ledger"))
        else:
            recent_judgements = list(storyteller_agent.get_recent_judgements(200))

    samples: list[StorytellerAdjudicationSample] = []
    for index, event in enumerate(all_events):
        if event.event_type not in node_event_types:
            continue
        base_state = _select_base_state_for_event(final_state, event, snapshots)
        prefix_state = base_state.with_update(
            phase=event.phase,
            round_number=event.round_number,
            event_log=tuple(all_events[: index + 1]),
        )
        matched = _match_recent_judgements_for_event(recent_judgements, event)
        chosen = matched[-1] if matched else _build_event_node_adjudication(event)
        candidates = matched[:-1] if len(matched) > 1 else []
        sample = build_storyteller_adjudication_sample(
            prefix_state,
            storyteller_agent=None,
            chosen_adjudication=chosen,
            candidate_adjudications=candidates,
            seed=seed,
        )
        samples.append(sample)
    return samples


def export_storyteller_adjudication_sample(sample: StorytellerAdjudicationSample, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sample.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path
