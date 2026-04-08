import argparse
import asyncio
import json
import logging
import os
import sys
from contextlib import suppress
from dataclasses import dataclass

from src.llm.mock_backend import MockBackend
from src.llm.openai_backend import OpenAIBackend
from src.orchestrator.game_loop import GameOrchestrator
from src.state.game_state import GamePhase, GameState, Team


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("simulation")


@dataclass
class SimulationOptions:
    backend: str
    player_count: int
    discussion_rounds: int
    timeout_seconds: int
    stop_after: str
    audit_mode: bool
    max_nomination_rounds: int | None


def parse_args() -> SimulationOptions:
    parser = argparse.ArgumentParser(description="快速审计或真实 LLM 短局验证。")
    parser.add_argument("--backend", choices=("mock", "live"), default="mock")
    parser.add_argument("--player-count", type=int, default=5)
    parser.add_argument("--discussion-rounds", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--stop-after", choices=("first_execution", "day_1", "night_2", "game_over"), default="first_execution")
    parser.add_argument("--audit-mode", action="store_true")
    parser.add_argument("--max-nomination-rounds", type=int, default=2)
    args = parser.parse_args()
    return SimulationOptions(
        backend=args.backend,
        player_count=args.player_count,
        discussion_rounds=args.discussion_rounds,
        timeout_seconds=args.timeout_seconds,
        stop_after=args.stop_after,
        audit_mode=bool(args.audit_mode),
        max_nomination_rounds=args.max_nomination_rounds,
    )


def build_backend(mode: str):
    from dotenv import load_dotenv

    load_dotenv()
    if mode == "mock":
        print(">>> [信息] 使用 MockBackend 进行快速规则审计。")
        return MockBackend()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("已请求 live backend，但当前环境没有 OPENAI_API_KEY")
    print(">>> [信息] 使用 OpenAIBackend 进行真实模型短局验证。")
    return OpenAIBackend()


def merged_events(orchestrator: GameOrchestrator):
    seen = set()
    merged = []
    for source_events in (getattr(orchestrator.state, "event_log", ()), getattr(orchestrator.event_log, "events", ())):
        for event in source_events:
            key = json.dumps(
                {
                    "event_type": event.event_type,
                    "trace_id": event.trace_id,
                    "actor": event.actor,
                    "target": event.target,
                    "round_number": event.round_number,
                    "payload": event.payload or {},
                },
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(event)
    return merged


def collect_summary(orchestrator: GameOrchestrator) -> dict:
    events = merged_events(orchestrator)
    phases = [e for e in events if e.event_type == "phase_changed"]
    nominations = [e for e in events if e.event_type == "nomination_started"]
    nomination_prompts = [
        e for e in events
        if e.event_type in {"nomination_prompted", "nomination_window_opened"}
    ]
    nomination_attempts = [e for e in events if e.event_type == "nomination_attempted"]
    votes = [e for e in events if e.event_type == "vote_cast"]
    execution_resolutions = [e for e in events if e.event_type == "execution_resolved"]
    actual_executions = [
        e for e in execution_resolutions
        if e.payload.get("executed") or e.target
    ]
    night_actions = [e for e in events if e.event_type == "night_action_resolved"]
    return {
        "phase_count": len(phases),
        "nomination_prompt_count": len(nomination_prompts),
        "nomination_attempt_count": len(nomination_attempts),
        "legal_nomination_count": len(nominations),
        "vote_count": len(votes),
        "execution_count": len(actual_executions),
        "execution_resolution_count": len(execution_resolutions),
        "night_action_count": len(night_actions),
        "last_execution": actual_executions[-1].payload if actual_executions else None,
        "current_phase": orchestrator.state.phase.value,
        "day_number": orchestrator.state.day_number,
        "round_number": orchestrator.state.round_number,
        "alive_count": orchestrator.state.alive_count,
    }


def should_stop(orchestrator: GameOrchestrator, stop_after: str) -> bool:
    events = merged_events(orchestrator)
    if stop_after == "game_over":
        return orchestrator.state.phase == GamePhase.GAME_OVER
    if stop_after == "first_execution":
        return any(
            e.event_type == "execution_resolved"
            and (e.payload.get("executed") or e.target)
            for e in events
        )
    if stop_after == "day_1":
        return any(
            e.event_type == "phase_changed" and e.phase == GamePhase.NIGHT and e.payload.get("day_number", 0) >= 1
            for e in events
        ) or orchestrator.state.phase == GamePhase.GAME_OVER
    if stop_after == "night_2":
        night_count = sum(
            1 for e in events
            if e.event_type == "phase_changed" and e.phase in {GamePhase.FIRST_NIGHT, GamePhase.NIGHT}
        )
        return night_count >= 2 or orchestrator.state.phase == GamePhase.GAME_OVER
    return False


def event_triggers_stop(event, stop_after: str) -> bool:
    if stop_after == "first_execution":
        return event.event_type == "execution_resolved" and bool(event.payload.get("executed") or event.target)
    return False


async def wait_for_stop_condition(orchestrator: GameOrchestrator, stop_after: str, timeout_seconds: int):
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        if should_stop(orchestrator, stop_after):
            return stop_after
        await asyncio.sleep(0.2)
    return "timeout"


async def run_simulation(options: SimulationOptions):
    print("\n" + "=" * 60)
    print("=== [开始全自动对局测试 & 规则审计] ===")
    print("=" * 60 + "\n")
    print(
        f">>> 配置: backend={options.backend}, players={options.player_count}, "
        f"discussion_rounds={options.discussion_rounds}, stop_after={options.stop_after}, "
        f"timeout={options.timeout_seconds}s"
    )

    backend = build_backend(options.backend)
    state = GameState(phase=GamePhase.SETUP)
    orchestrator = GameOrchestrator(state)

    from src.agents.storyteller_agent import StorytellerAgent

    storyteller = StorytellerAgent(backend)
    orchestrator.storyteller_agent = storyteller
    orchestrator.default_agent_backend = backend

    stop_reason = {"value": "timeout"}
    original_publish = orchestrator.event_bus.publish

    async def publish_with_stop(event):
        await original_publish(event)
        if event_triggers_stop(event, options.stop_after) or should_stop(orchestrator, options.stop_after):
            stop_reason["value"] = options.stop_after
            logger.info(">>> [STOP] 命中停止条件: stop_after=%s, event=%s, phase=%s, round=%s", options.stop_after, event.event_type, event.phase, event.round_number)
            raise asyncio.CancelledError

    orchestrator.event_bus.publish = publish_with_stop  # type: ignore[assignment]

    loop_task = asyncio.create_task(orchestrator.run_game_loop())
    try:
        await asyncio.sleep(0.2)
        await orchestrator.run_setup_with_options(
            player_count=options.player_count,
            host_id="host",
            is_human=False,
            discussion_rounds=options.discussion_rounds,
            storyteller_mode="auto",
            audit_mode=options.audit_mode,
            max_nomination_rounds=options.max_nomination_rounds,
            backend_mode=options.backend,
        )

        print(">>> [OK] setup 完成。")
        print(f">>> 当前座位顺序: {list(orchestrator.state.seat_order)}")
        try:
            await asyncio.wait_for(loop_task, timeout=options.timeout_seconds)
        except asyncio.TimeoutError:
            stop_reason["value"] = "timeout"
            if not loop_task.done():
                loop_task.cancel()
            with suppress(asyncio.CancelledError):
                await loop_task
        except asyncio.CancelledError:
            with suppress(asyncio.CancelledError):
                await loop_task
        else:
            stop_reason["value"] = "game_over" if orchestrator.state.phase == GamePhase.GAME_OVER else "completed"
    finally:
        orchestrator.event_bus.publish = original_publish  # type: ignore[assignment]

    summary = collect_summary(orchestrator)
    print("\n" + "-" * 60)
    print("审计摘要")
    for key, value in summary.items():
        print(f"- {key}: {value}")
    print(f"- stop_after_requested: {options.stop_after}")
    print(f"- stop_status: {stop_reason['value']}")
    if orchestrator.winner:
        print(f"- winner: {orchestrator.winner.value}")
    print("-" * 60 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(run_simulation(parse_args()))
    except Exception as exc:
        logger.exception("模拟局运行失败: %s", exc)
        raise
