"""
胜负判定器 (Victory Checker)

检查游戏是否达到结束条件。
"""

from __future__ import annotations

from typing import Optional

from src.state.game_state import GameState, RoleType, Team


class VictoryChecker:
    """胜负判定器"""

    @staticmethod
    def check_victory(game_state: GameState) -> Optional[Team]:
        """
        检查游戏是否结束。
        
        Args:
            game_state: 当前游戏状态
            
        Returns:
            获胜阵营 (Team)，如果未结束则返回 None
        """
        alive_players = game_state.get_alive_players()
        alive_count = len(alive_players)
        
        # 1. 如果恶魔死亡，善良阵营获胜
        # （假设这里没有"镇长"等特殊角色导致恶魔死后游戏继续的规则，先以核心规则为主）
        demons = [p for p in game_state.players if p.role_id in _get_demon_role_ids()]
        alive_demons = [d for d in demons if d.is_alive]
        
        if not alive_demons and demons:
            # 恶魔已死
            return Team.GOOD

        # 2. 如果只剩 2 个存活玩家 (其中一个是恶魔)，邪恶阵营获胜
        if alive_count <= 2 and alive_demons:
            return Team.EVIL
            
        return None


def _get_demon_role_ids() -> list[str]:
    """获取所有恶魔相关的 role_id，便于判断"""
    from src.engine.roles.base_role import get_all_role_ids, get_role_class
    demon_ids = []
    for role_id in get_all_role_ids():
        cls = get_role_class(role_id)
        if cls:
            role_def = cls.get_definition()
            if role_def.role_type == RoleType.DEMON:
                demon_ids.append(role_id)
    # 如果还没有注册真实角色，这里给一个默认值方便测试
    if not demon_ids:
        return ["imp"]
    return demon_ids
