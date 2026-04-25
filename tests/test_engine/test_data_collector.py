from pathlib import Path
from uuid import uuid4

from src.engine.data_collector import GameDataCollector


def _collector_dir(name: str) -> Path:
    root = Path("data") / "_pytest_data_collector" / f"{name}_{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_export_ai_traces_returns_stable_empty_structure() -> None:
    base_dir = _collector_dir("empty")
    exported = GameDataCollector.export_ai_traces("game-empty", base_dir=str(base_dir))

    assert exported["version"] == "a3-data-export-v1"
    assert exported["game_id"] == "game-empty"
    assert exported["entries"] == []
    assert exported["files"] == []
    assert exported["stats"] == {
        "file_count": 0,
        "entry_count": 0,
        "thought_trace_count": 0,
        "snapshot_count": 0,
        "parse_error_count": 0,
        "snapshot_stage_counts": {},
        "retrieval_snapshot_count": 0,
        "degraded_retrieval_snapshot_count": 0,
        "embeddings_disabled_snapshot_count": 0,
    }


def test_export_ai_traces_normalizes_records_and_counts_parse_errors() -> None:
    base_dir = _collector_dir("normalized")
    collector = GameDataCollector(base_dir=str(base_dir))
    collector.start_game("game-123")
    collector.record_thought_trace(
        player_id="p1",
        role_id="fortune_teller",
        phase="night",
        round_number=1,
        thought="先验一下 p2 和 p3。",
        action={"action": "night_action", "targets": ["p2", "p3"]},
        context={"visible_state_summary": "首夜"},
    )
    collector.record_snapshot(
        {
            "phase": "day_discussion",
            "day_number": 1,
            "round_number": 2,
            "stage": "day_discussion_complete",
            "summary": {
                "alive_players": 7,
                "retrieval_summary": {
                    "p1": {
                        "status": "degraded",
                        "embeddings_enabled": False,
                        "disable_reason": "404 embeddings unavailable",
                        "last_query": "vote p2",
                        "hit_count": 0,
                    }
                },
            },
        }
    )
    assert collector._log_file is not None
    collector._log_file.write_text(
        collector._log_file.read_text(encoding="utf-8") + "{broken json}\n",
        encoding="utf-8",
    )

    exported = GameDataCollector.export_ai_traces("game-123", base_dir=str(base_dir))

    assert exported["version"] == "a3-data-export-v1"
    assert exported["game_id"] == "game-123"
    assert exported["stats"]["file_count"] == 1
    assert exported["stats"]["entry_count"] == 2
    assert exported["stats"]["thought_trace_count"] == 1
    assert exported["stats"]["snapshot_count"] == 1
    assert exported["stats"]["parse_error_count"] == 1
    assert exported["stats"]["snapshot_stage_counts"] == {"day_discussion_complete": 1}
    assert exported["stats"]["retrieval_snapshot_count"] == 1
    assert exported["stats"]["degraded_retrieval_snapshot_count"] == 1
    assert exported["stats"]["embeddings_disabled_snapshot_count"] == 1
    assert len(exported["files"]) == 1

    thought_entry = exported["entries"][0]
    snapshot_entry = exported["entries"][1]

    assert thought_entry["record_type"] == "thought_trace"
    assert thought_entry["game_id"] == "game-123"
    assert thought_entry["player_id"] == "p1"
    assert thought_entry["role_id"] == "fortune_teller"
    assert thought_entry["round_number"] == 1
    assert thought_entry["action"]["targets"] == ["p2", "p3"]
    assert thought_entry["context_summary"]["visible_state_summary"] == "首夜"
    assert thought_entry["raw"]["type"] == "thought_trace"

    assert snapshot_entry["record_type"] == "snapshot"
    assert snapshot_entry["phase"] == "day_discussion"
    assert snapshot_entry["day_number"] == 1
    assert snapshot_entry["round_number"] == 2
    assert snapshot_entry["stage"] == "day_discussion_complete"
    assert snapshot_entry["summary"]["alive_players"] == 7
    assert snapshot_entry["raw"]["summary"]["alive_players"] == 7
    assert snapshot_entry["retrieval_summary"]["p1"]["status"] == "degraded"
    assert snapshot_entry["retrieval_summary"]["p1"]["embeddings_enabled"] is False
    assert snapshot_entry["retrieval_summary"]["p1"]["disable_reason"] == "404 embeddings unavailable"
    assert snapshot_entry["retrieval_summary"]["p1"]["last_query"] == "vote p2"
