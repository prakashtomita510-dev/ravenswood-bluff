"""
剧本配置 (Scripts Configuration)
"""

from src.state.game_state import ScriptConfig

# 暗流涌动 (Trouble Brewing)
TROUBLE_BREWING = ScriptConfig(
    script_id="trouble_brewing",
    name="暗流涌动",
    name_en="Trouble Brewing",
    roles=[
        # Townsfolk
        "washerwoman", "librarian", "investigator", "chef", "empath", 
        "fortune_teller", "undertaker", "monk", "ravenkeeper", 
        "virgin", "slayer", "soldier", "mayor",
        # Outsiders
        "butler", "drunken", "recluse", "saint",
        # Minions
        "poisoner", "spy", "scarlet_woman", "baron",
        # Demon
        "imp"
    ]
)

SCRIPTS = {
    "trouble_brewing": TROUBLE_BREWING
}

def get_role_counts(player_count: int) -> dict:
    """根据人数获取官方角色分配(暗流涌动)"""
    # [Townsfolk, Outsider, Minion, Demon]
    table = {
        5:  [3, 0, 1, 1],
        6:  [3, 1, 1, 1],
        7:  [5, 0, 1, 1],
        8:  [5, 1, 1, 1],
        9:  [5, 2, 1, 1],
        10: [7, 0, 2, 1],
        11: [7, 1, 2, 1],
        12: [7, 2, 2, 1],
        13: [9, 0, 3, 1],
        14: [9, 1, 3, 1],
        15: [9, 2, 3, 1],
    }
    counts = table.get(player_count, [3, 0, 1, 1])
    return {
        "townsfolk": counts[0],
        "outsider": counts[1],
        "minion": counts[2],
        "demon": counts[3]
    }

def distribute_roles(script: ScriptConfig, player_count: int) -> tuple[list[str], list[str]]:
    """随机分配角色 ID，返回 (已选角色, 邪恶方伪装角色)"""
    import random
    counts = get_role_counts(player_count)
    
    # 分类备选角色
    import src.engine.roles
    from src.engine.roles.base_role import get_role_class
    from src.state.game_state import RoleType
    
    pools = {
        RoleType.TOWNSFOLK: [],
        RoleType.OUTSIDER: [],
        RoleType.MINION: [],
        RoleType.DEMON: []
    }
    
    for rid in script.roles:
        cls = get_role_class(rid)
        if cls:
            rtype = cls.get_definition().role_type
            if rtype in pools:
                pools[rtype].append(rid)
                
    # 抽签
    selected = []
    selected.extend(random.sample(pools[RoleType.DEMON], counts["demon"]))
    selected.extend(random.sample(pools[RoleType.MINION], counts["minion"]))
    
    # 特殊逻辑：男爵 (Baron)
    if "baron" in selected:
        baron_cls = get_role_class("baron")
        outsider_bonus = baron_cls.outsider_bonus() if baron_cls else 2
        counts["townsfolk"] -= outsider_bonus
        counts["outsider"] += outsider_bonus
        
    selected.extend(random.sample(pools[RoleType.OUTSIDER], min(counts["outsider"], len(pools[RoleType.OUTSIDER]))))
    selected.extend(random.sample(pools[RoleType.TOWNSFOLK], min(counts["townsfolk"], len(pools[RoleType.TOWNSFOLK]))))
    
    random.shuffle(selected)
    
    # 抽取 3 个不在场上的村民/外来者角色作为恶魔的伪装 (Bluffs)
    in_play = set(selected)
    bluff_candidates = [r for r in script.roles if get_role_class(r).get_definition().role_type in (RoleType.TOWNSFOLK, RoleType.OUTSIDER) and r not in in_play]
    bluffs = random.sample(bluff_candidates, min(3, len(bluff_candidates)))
    
    return selected, bluffs
