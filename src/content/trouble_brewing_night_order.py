"""Trouble Brewing night order reference used by backend validation and player-facing rulebook."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class NightOrderSpec:
    role_id: str
    sort_order: int
    zh_name: str
    en_name: str
    timing: str
    queued: bool
    note_zh: str
    note_en: str


_TROUBLE_BREWING_NIGHT_ORDER: tuple[NightOrderSpec, ...] = (
    NightOrderSpec("poisoner", 15, "投毒者", "Poisoner", "each_night", True, "每晚先决定一名中毒目标。", "Acts each night to poison one player."),
    NightOrderSpec("monk", 21, "僧侣", "Monk", "each_night_except_first", True, "除首夜外，每晚保护一名其他玩家。", "Acts each night except the first to protect another player."),
    NightOrderSpec("scarlet_woman", 23, "红唇女郎", "Scarlet Woman", "special_reaction", False, "恶魔死亡且仍有 5 名或更多存活玩家时立即接管。", "Triggers immediately on demon death while 5+ players live."),
    NightOrderSpec("imp", 24, "小恶魔", "Imp", "each_night_except_first", True, "除首夜外，每晚选择一名玩家击杀。", "Acts each night except the first to kill a player."),
    NightOrderSpec("washerwoman", 34, "洗衣妇", "Washerwoman", "first_night", False, "首夜获得两名玩家中一名是真村民的信息。", "Receives first-night information about a townsfolk."),
    NightOrderSpec("librarian", 35, "图书管理员", "Librarian", "first_night", False, "首夜获得外来者信息。", "Receives first-night outsider information."),
    NightOrderSpec("investigator", 36, "调查员", "Investigator", "first_night", False, "首夜获得爪牙信息。", "Receives first-night minion information."),
    NightOrderSpec("chef", 37, "厨师", "Chef", "first_night", False, "首夜得知相邻邪恶玩家对数。", "Receives first-night adjacent evil pair count."),
    NightOrderSpec("empath", 50, "共情者", "Empath", "each_night", False, "每晚得知相邻活人中的邪恶人数。", "Receives adjacent evil count each night."),
    NightOrderSpec("undertaker", 52, "送葬者", "Undertaker", "each_night", False, "每晚得知当天被处决者的身份。", "Receives the executed player's role each night."),
    NightOrderSpec("fortune_teller", 55, "占卜师", "Fortune Teller", "each_night", True, "每晚选择两名玩家，判断其中是否有恶魔。", "Chooses two players each night to detect a demon."),
    NightOrderSpec("ravenkeeper", 58, "守鸦人", "Ravenkeeper", "on_death", True, "若在夜晚死亡，当晚得知一名玩家身份。", "If killed at night, learns one player's role that night."),
    NightOrderSpec("butler", 70, "管家", "Butler", "each_night", True, "每晚绑定一名玩家，次日投票受限。", "Chooses a player each night, constraining next day's vote."),
    NightOrderSpec("spy", 70, "间谍", "Spy", "each_night", False, "每晚查看魔典。与管家同一顺位时，按规则书顺序先管家后间谍。", "Views the grimoire each night. If tied with Butler, Butler is processed first."),
)

_BY_ROLE_ID = {item.role_id: item for item in _TROUBLE_BREWING_NIGHT_ORDER}
_ROLE_INDEX = {item.role_id: index for index, item in enumerate(_TROUBLE_BREWING_NIGHT_ORDER)}


def get_night_order_spec(role_id: str) -> NightOrderSpec | None:
    return _BY_ROLE_ID.get(role_id)


def get_night_order_sort_key(role_id: str, fallback_order: int, seat_index: int = 0) -> tuple[int, int, int]:
    spec = get_night_order_spec(role_id)
    if spec is None:
        return (10_000 + fallback_order, 10_000 + seat_index, seat_index)
    return (spec.sort_order, _ROLE_INDEX[role_id], seat_index)


def validate_night_order_value(role_id: str, actual_order: int) -> dict[str, Any] | None:
    spec = get_night_order_spec(role_id)
    if spec is None:
        return {
            "role_id": role_id,
            "actual_order": actual_order,
            "expected_order": None,
            "reason": "missing_reference",
        }
    if spec.sort_order == actual_order:
        return None
    return {
        "role_id": role_id,
        "actual_order": actual_order,
        "expected_order": spec.sort_order,
        "reason": "canonical_mismatch",
    }


def build_night_order_tie_groups(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[str]] = {}
    for step in steps:
        grouped.setdefault(int(step["night_order"]), []).append(str(step["role_id"]))

    ties: list[dict[str, Any]] = []
    for order, role_ids in grouped.items():
        if len(role_ids) < 2:
            continue
        canonical = sorted(role_ids, key=lambda role_id: _ROLE_INDEX.get(role_id, 99_999))
        ties.append(
            {
                "night_order": order,
                "role_ids": role_ids,
                "resolution": "canonical_rolebook_then_seat_order",
                "resolved_order": canonical,
            }
        )
    return ties


def export_rulebook_night_order() -> list[dict[str, Any]]:
    return [asdict(item) for item in _TROUBLE_BREWING_NIGHT_ORDER]
