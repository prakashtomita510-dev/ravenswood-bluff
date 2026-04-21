"""生成说书人平衡裁量样本。"""

from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.agents.storyteller_agent import StorytellerAgent
from src.llm.mock_backend import MockBackend
from src.orchestrator.storyteller_balance import (
    build_storyteller_adjudication_sample,
    export_storyteller_adjudication_sample,
)
from src.state.game_state import GameConfig, GameEvent, GamePhase, GameState, PlayerState, PlayerStatus, Team, Visibility


def _base_config() -> GameConfig:
    return GameConfig(
        player_count=4,
        script_id="trouble_brewing",
        human_mode="none",
        storyteller_mode="auto",
        backend_mode="mock",
        audit_mode=True,
        discussion_rounds=1,
    )


def _fortune_teller_state() -> GameState:
    return GameState(
        phase=GamePhase.NIGHT,
        round_number=2,
        day_number=1,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            PlayerState(player_id="p1", name="FT", role_id="fortune_teller", team=Team.GOOD),
            PlayerState(player_id="p2", name="Imp", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p3", name="Town", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p4", name="Chef", role_id="chef", team=Team.GOOD),
        ),
        event_log=(
            GameEvent(
                event_type="night_action_resolved",
                phase=GamePhase.NIGHT,
                round_number=2,
                actor="p1",
                payload={"targets": ["p2", "p3"]},
                visibility=Visibility.STORYTELLER_ONLY,
            ),
        ),
        payload={"fortune_teller_red_herring": "p4"},
        config=_base_config(),
    )


def _suppressed_empath_state() -> GameState:
    return GameState(
        phase=GamePhase.NIGHT,
        round_number=3,
        day_number=2,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            PlayerState(
                player_id="p1",
                name="Empath",
                role_id="empath",
                team=Team.GOOD,
                statuses=(PlayerStatus.ALIVE, PlayerStatus.POISONED),
            ),
            PlayerState(player_id="p2", name="Imp", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p3", name="Town", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p4", name="Spy", role_id="spy", team=Team.EVIL),
        ),
        config=_base_config(),
    )


def _spy_book_state() -> GameState:
    return GameState(
        phase=GamePhase.NIGHT,
        round_number=2,
        day_number=1,
        seat_order=("p1", "p2", "p3", "p4"),
        players=(
            PlayerState(player_id="p1", name="Town", role_id="washerwoman", team=Team.GOOD),
            PlayerState(player_id="p2", name="Spy", role_id="spy", team=Team.EVIL, statuses=(PlayerStatus.ALIVE, PlayerStatus.DRUNK)),
            PlayerState(player_id="p3", name="Imp", role_id="imp", team=Team.EVIL),
            PlayerState(player_id="p4", name="Lib", role_id="librarian", team=Team.GOOD),
        ),
        config=_base_config(),
    )


def _sample_specs() -> list[tuple[str, str, GameState]]:
    return [
        ("fortune_teller_red_herring", "p1", _fortune_teller_state()),
        ("suppressed_empath", "p1", _suppressed_empath_state()),
        ("suppressed_spy_book", "p2", _spy_book_state()),
    ]


async def _build_samples(output_dir: Path) -> list[Path]:
    agent = StorytellerAgent(MockBackend())
    exported: list[Path] = []
    manifest: list[dict[str, str]] = []
    for sample_name, actor_id, state in _sample_specs():
        actor = state.get_player(actor_id)
        role_id = actor.true_role_id or actor.role_id
        info = await agent.decide_night_info(state, actor_id, role_id)
        enriched_state = state.with_event(
            GameEvent(
                event_type="private_info_delivered",
                phase=state.phase,
                round_number=state.round_number,
                actor="storyteller",
                target=actor_id,
                payload=info,
                visibility=Visibility.PRIVATE,
            )
        )
        sample = build_storyteller_adjudication_sample(
            enriched_state,
            storyteller_agent=agent,
            seed=sample_name,
        )
        sample_path = export_storyteller_adjudication_sample(sample, output_dir / f"{sample_name}.json")
        exported.append(sample_path)
        manifest.append({"name": sample_name, "path": str(sample_path)})
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return exported


def main() -> int:
    import asyncio
    import sys

    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("artifacts") / "storyteller_eval_samples"
    output_dir.mkdir(parents=True, exist_ok=True)
    exported = asyncio.run(_build_samples(output_dir))
    print(f"storyteller balance samples: {len(exported)} exported to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
