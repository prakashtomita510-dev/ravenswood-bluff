"""Trouble Brewing role names and rules text used for UI-facing surfaces."""

from __future__ import annotations

from typing import TypedDict


class RoleTerm(TypedDict):
    role_id: str
    zh_name: str
    en_name: str
    description: str


TROUBLE_BREWING_ROLE_TERMS: dict[str, RoleTerm] = {
    "washerwoman": {"role_id": "washerwoman", "zh_name": "洗衣妇", "en_name": "Washerwoman", "description": "首夜，你得知两名玩家中有一人是某个村民角色。"},
    "librarian": {"role_id": "librarian", "zh_name": "图书管理员", "en_name": "Librarian", "description": "首夜，你得知两名玩家中有一人是某个外来者，或得知场上没有外来者。"},
    "investigator": {"role_id": "investigator", "zh_name": "调查员", "en_name": "Investigator", "description": "首夜，你得知两名玩家中有一人是某个爪牙角色。"},
    "chef": {"role_id": "chef", "zh_name": "厨师", "en_name": "Chef", "description": "首夜，你得知有多少对相邻的邪恶玩家。"},
    "empath": {"role_id": "empath", "zh_name": "共情者", "en_name": "Empath", "description": "每晚，你得知你两个活着的邻座中有多少人是邪恶阵营。"},
    "fortune_teller": {"role_id": "fortune_teller", "zh_name": "占卜师", "en_name": "Fortune Teller", "description": "每晚，你选择两名玩家，得知其中是否至少有一名是恶魔。"},
    "undertaker": {"role_id": "undertaker", "zh_name": "送葬者", "en_name": "Undertaker", "description": "每晚，你得知当天被处决玩家的真实身份。"},
    "monk": {"role_id": "monk", "zh_name": "僧侣", "en_name": "Monk", "description": "除首夜外，每晚选择一名其他玩家；该玩家今晚免受恶魔伤害。"},
    "ravenkeeper": {"role_id": "ravenkeeper", "zh_name": "守鸦人", "en_name": "Ravenkeeper", "description": "如果你在夜晚死亡，当晚你会得知一名玩家的身份。"},
    "virgin": {"role_id": "virgin", "zh_name": "贞洁者", "en_name": "Virgin", "description": "如果你首次被一名村民提名，该提名者会立刻被处决。"},
    "slayer": {"role_id": "slayer", "zh_name": "猎手", "en_name": "Slayer", "description": "每局一次，白天公开选择一名玩家；如果他是恶魔，他立刻死亡。"},
    "soldier": {"role_id": "soldier", "zh_name": "士兵", "en_name": "Soldier", "description": "你不会被恶魔杀死。"},
    "mayor": {"role_id": "mayor", "zh_name": "镇长", "en_name": "Mayor", "description": "如果你夜里本会死亡，死亡可能转移给别人；若白天无人被处决，善良阵营可能因此获胜。"},
    "butler": {"role_id": "butler", "zh_name": "管家", "en_name": "Butler", "description": "每晚选择一名玩家；明天除非该玩家投票，否则你不能投票。"},
    "drunken": {"role_id": "drunken", "zh_name": "酒鬼", "en_name": "Drunk", "description": "你以为自己是某个村民角色，但其实你是外来者，且你的能力会失效或得到错误信息。"},
    "recluse": {"role_id": "recluse", "zh_name": "陌客", "en_name": "Recluse", "description": "即使你是好人外来者，你也可能被当作邪恶角色、爪牙或恶魔。"},
    "saint": {"role_id": "saint", "zh_name": "圣徒", "en_name": "Saint", "description": "如果你被处决，善良阵营立刻失败。"},
    "poisoner": {"role_id": "poisoner", "zh_name": "投毒者", "en_name": "Poisoner", "description": "每晚选择一名玩家；他今晚与次日白天中毒。"},
    "spy": {"role_id": "spy", "zh_name": "间谍", "en_name": "Spy", "description": "每晚查看魔典；你可能被判定为好人、村民或外来者。"},
    "scarlet_woman": {"role_id": "scarlet_woman", "zh_name": "红唇女郎", "en_name": "Scarlet Woman", "description": "若恶魔死亡且场上有 5 名或更多存活玩家，你立刻成为新的恶魔。"},
    "baron": {"role_id": "baron", "zh_name": "男爵", "en_name": "Baron", "description": "由于你的加入，剧本中额外加入 2 名外来者并相应减少 2 名村民。"},
    "imp": {"role_id": "imp", "zh_name": "小恶魔", "en_name": "Imp", "description": "除首夜外，每晚选择一名玩家使其死亡；若你自杀，一名爪牙会成为新的小恶魔。"},
}

TROUBLE_BREWING_ROLE_PERSONA_HINTS: dict[str, str] = {
    "washerwoman": "谨慎确认信息，喜欢先观察别人的反应再下结论。",
    "librarian": "习惯先做排除法，说话温和但会暗自记住边界条件。",
    "investigator": "发言简洁直接，喜欢盯住嫌疑链条中的具体人。",
    "chef": "偏好把信息转成结构化判断，说话时会带着一点整理感。",
    "empath": "语气克制，容易从邻座关系里寻找情绪和阵营线索。",
    "fortune_teller": "会先给出判断倾向，再补上为什么这两个目标值得关注。",
    "undertaker": "关注结果而不是过程，常把注意力放在已发生的处决上。",
    "monk": "防守型，优先考虑保护和减伤，表达会比较稳。",
    "ravenkeeper": "沉静、敏感，遇到死亡和身份信息时会更认真。",
    "virgin": "警惕提名和规则触发，发言里会强调边界。",
    "slayer": "行动果断，愿意承担风险，措辞往往直接。",
    "soldier": "稳重、克制，常把重点放在自己如何活下来。",
    "mayor": "温和但重视局势稳定，喜欢从整体节奏看问题。",
    "butler": "说话会尽量委婉，容易绕着核心结论先铺垫。",
    "drunken": "表达容易含糊，自我怀疑感更强，也更容易改口。",
    "recluse": "习惯用模糊措辞保护自己，容易反向解释局势。",
    "saint": "语气认真，常提醒大家注意误处决的代价。",
    "poisoner": "喜欢试探和误导，发言不太直接，会保留后手。",
    "spy": "冷静而观察欲强，喜欢盯住所有人的细节和破绽。",
    "scarlet_woman": "会刻意压低存在感，必要时才突然站出来。",
    "baron": "说话像在推局势但不想暴露自己，重视资源压力。",
    "imp": "压迫感强，偏主动推进节奏，发言更像掌控局面的人。",
}


def get_role_term(role_id: str) -> RoleTerm | None:
    return TROUBLE_BREWING_ROLE_TERMS.get(role_id)


def get_role_name(role_id: str) -> str:
    term = get_role_term(role_id)
    return term["zh_name"] if term else role_id


def get_role_description(role_id: str, fallback: str = "") -> str:
    term = get_role_term(role_id)
    return term["description"] if term else fallback


def get_role_persona_hint(role_id: str, fallback: str = "") -> str:
    return TROUBLE_BREWING_ROLE_PERSONA_HINTS.get(role_id, fallback)
