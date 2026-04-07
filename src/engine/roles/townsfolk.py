"""
村民角色 (Townsfolk)

实现惹事生非(Trouble Brewing)剧本中的核心村民角色。
"""

from __future__ import annotations

import random
from typing import Any, Optional

from src.engine.roles.base_role import BaseRole, register_role
from src.state.game_state import (
    Ability,
    AbilityTrigger,
    AbilityType,
    GameEvent,
    GameState,
    PlayerState,
    RoleDefinition,
    RoleType,
    Team,
)


@register_role("washerwoman")
class WasherwomanRole(BaseRole):
    """洗衣妇: 你会得知两位玩家中有一位是某个特定的村民角色"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="washerwoman",
            name="洗衣妇",
            name_en="Washerwoman",
            team=Team.GOOD,
            role_type=RoleType.TOWNSFOLK,
            ability=Ability(
                trigger=AbilityTrigger.FIRST_NIGHT,
                action_type=AbilityType.INFO_GATHER,
                description="你会得知两位玩家中有一位是某个特定的村民角色",
                night_order=32,
            ),
        )

    def execute_ability(
        self,
        game_state: GameState,
        actor: PlayerState,
        target: Optional[str] = None,
        **kwargs: Any,
    ) -> tuple[GameState, list[GameEvent]]:
        # 在AI系统中，信息获取能力通常表现为其 get_night_info 被说书人/引擎调用。
        # 实际修改游戏状态的"主动技能"才需要在此处实现复杂逻辑。
        # 记录使用了技能。
        return game_state, []

    def get_night_info(
        self,
        game_state: GameState,
        actor: PlayerState,
    ) -> Optional[dict]:
        """为洗衣妇生成夜晚信息（由编排器或自动说书人调用）"""
        # 如果中毒，可能会获得假信息（这通常由编排器决定，这里只提供基础真实逻辑）
        # 1. 找到在场的所有其他村民
        townsfolks = [
            p for p in game_state.players 
            if p.player_id != actor.player_id 
            and p.role_id != "washerwoman"
            and self._is_townsfolk_role(p.role_id)
        ]
        
        if not townsfolks:
            return None
            
        # 2. 随机选一个真实的
        target_player = random.choice(townsfolks)
        target_role_id = target_player.role_id
        
        # 3. 随机选一个其他人干扰
        others = [p for p in game_state.players 
                  if p.player_id not in (actor.player_id, target_player.player_id)]
        decoy = random.choice(others) if others else target_player
        
        # 打乱顺序
        pair = [target_player.player_id, decoy.player_id]
        random.shuffle(pair)
        
        return {
            "type": "washerwoman_info",
            "players": pair,
            "role_seen": target_role_id
        }

    def _is_townsfolk_role(self, role_id: str) -> bool:
        from src.engine.roles.base_role import get_role_class
        cls = get_role_class(role_id)
        if cls:
            return cls.get_definition().role_type == RoleType.TOWNSFOLK
        return False


@register_role("empath")
class EmpathRole(BaseRole):
    """共情者: 每晚你会得知你的两个活着的邻居中有几个是邪恶的"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="empath",
            name="共情者",
            name_en="Empath",
            team=Team.GOOD,
            role_type=RoleType.TOWNSFOLK,
            ability=Ability(
                trigger=AbilityTrigger.EACH_NIGHT,
                action_type=AbilityType.INFO_GATHER,
                description="每晚你会得知你的两个活着的邻居中有几个是邪恶的",
                night_order=50,
            ),
        )

    def execute_ability(
        self,
        game_state: GameState,
        actor: PlayerState,
        target: Optional[str] = None,
        **kwargs: Any,
    ) -> tuple[GameState, list[GameEvent]]:
        return game_state, []

    def get_night_info(
        self,
        game_state: GameState,
        actor: PlayerState,
    ) -> Optional[dict]:
        seat_order = game_state.seat_order
        if not seat_order or actor.player_id not in seat_order:
            return None

        my_idx = seat_order.index(actor.player_id)
        n = len(seat_order)
        
        # 找左边最近的活人
        left_idx = (my_idx - 1) % n
        while not game_state.get_player(seat_order[left_idx]).is_alive:
            left_idx = (left_idx - 1) % n
            if left_idx == my_idx: break # 大家都死了
            
        # 找右边最近的活人
        right_idx = (my_idx + 1) % n
        while not game_state.get_player(seat_order[right_idx]).is_alive:
            right_idx = (right_idx + 1) % n
            if right_idx == my_idx: break

        evil_count = 0
        left_player = game_state.get_player(seat_order[left_idx])
        if left_player and left_player.team == Team.EVIL:
            evil_count += 1
            
        right_player = game_state.get_player(seat_order[right_idx])
        # 如果只剩两个人（自己和另一个活人），不重复计算
        if left_idx != right_idx and right_player and right_player.team == Team.EVIL:
            evil_count += 1

        return {
            "type": "empath_info",
            "evil_count": evil_count
        }


@register_role("undertaker")
class UndertakerRole(BaseRole):
    """送葬者: 每个夜晚*，得知今天白天被处决的玩家角色"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="undertaker",
            name="送葬者",
            name_en="Undertaker",
            team=Team.GOOD,
            role_type=RoleType.TOWNSFOLK,
            ability=Ability(
                trigger=AbilityTrigger.EACH_NIGHT,
                action_type=AbilityType.INFO_GATHER,
                description="得知今天白天被处决的玩家角色",
                night_order=52,
            ),
        )

    def execute_ability(
        self, game_state: GameState, actor: PlayerState, target: Optional[str] = None, **kwargs: Any
    ) -> tuple[GameState, list[GameEvent]]:
        return game_state, []

    def get_night_info(self, game_state: GameState, actor: PlayerState) -> Optional[dict]:
        if actor.is_drunk() or actor.is_poisoned():
            return {"type": "undertaker_info", "role_seen": "drunk_fake_role"}
            
        # Simplified: Check if anyone died by execution today.
        return {"type": "undertaker_info", "role_seen": "unknown_due_to_simple_impl"}


@register_role("chef")
class ChefRole(BaseRole):
    """厨师: 你得知有多少对邪恶玩家邻座"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="chef",
            name="厨师",
            name_en="Chef",
            team=Team.GOOD,
            role_type=RoleType.TOWNSFOLK,
            ability=Ability(
                trigger=AbilityTrigger.FIRST_NIGHT,
                action_type=AbilityType.INFO_GATHER,
                description="你会得知有多少对邪恶阵营玩家是邻座的",
                night_order=35,
            ),
        )

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        return game_state, []

    def get_night_info(self, game_state, actor):
        seat_order = game_state.seat_order
        n = len(seat_order)
        pairs = 0
        for i in range(n):
            p1 = game_state.get_player(seat_order[i])
            p2 = game_state.get_player(seat_order[(i+1)%n])
            if p1 and p2 and p1.team == Team.EVIL and p2.team == Team.EVIL:
                pairs += 1
        return {"type": "chef_info", "pairs": pairs}


@register_role("librarian")
class LibrarianRole(BaseRole):
    """图书馆员: 你得知两位玩家中有一位是某个特定的外来者角色，或者没有外来者"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="librarian",
            name="图书馆员",
            name_en="Librarian",
            team=Team.GOOD,
            role_type=RoleType.TOWNSFOLK,
            ability=Ability(
                trigger=AbilityTrigger.FIRST_NIGHT,
                action_type=AbilityType.INFO_GATHER,
                description="你会得知两位玩家中有一位是某个特定的外来者角色，或者没有外来者",
                night_order=33,
            ),
        )

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        return game_state, []

    def get_night_info(self, game_state, actor):
        outsiders = [p for p in game_state.players if p.player_id != actor.player_id and self._is_outsider_role(p.role_id)]
        if not outsiders:
            return {"type": "librarian_info", "has_outsider": False}
        
        target_p = random.choice(outsiders)
        others = [p for p in game_state.players if p.player_id not in (actor.player_id, target_p.player_id)]
        decoy = random.choice(others) if others else target_p
        pair = [target_p.player_id, decoy.player_id]
        random.shuffle(pair)
        return {"type": "librarian_info", "has_outsider": True, "players": pair, "role_seen": target_p.role_id}

    def _is_outsider_role(self, role_id):
        from src.engine.roles.base_role import get_role_class
        cls = get_role_class(role_id)
        return cls and cls.get_definition().role_type == RoleType.OUTSIDER


@register_role("investigator")
class InvestigatorRole(BaseRole):
    """调查员: 你得知两位玩家中有一位是某个特定的爪牙角色"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="investigator",
            name="调查员",
            name_en="Investigator",
            team=Team.GOOD,
            role_type=RoleType.TOWNSFOLK,
            ability=Ability(
                trigger=AbilityTrigger.FIRST_NIGHT,
                action_type=AbilityType.INFO_GATHER,
                description="你会得知两位玩家中有一位是某个特定的爪牙角色",
                night_order=34,
            ),
        )

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        return game_state, []

    def get_night_info(self, game_state, actor):
        minions = [p for p in game_state.players if p.player_id != actor.player_id and self._is_minion_role(p.role_id)]
        if not minions:
            return None
        
        target_p = random.choice(minions)
        others = [p for p in game_state.players if p.player_id not in (actor.player_id, target_p.player_id)]
        decoy = random.choice(others) if others else target_p
        pair = [target_p.player_id, decoy.player_id]
        random.shuffle(pair)
        return {"type": "investigator_info", "players": pair, "role_seen": target_p.role_id}

    def _is_minion_role(self, role_id):
        from src.engine.roles.base_role import get_role_class
        cls = get_role_class(role_id)
        return cls and cls.get_definition().role_type == RoleType.MINION


@register_role("fortune_teller")
class FortuneTellerRole(BaseRole):
    """预言家: 每晚选择两位玩家，得知其中是否有恶魔。此外还会有一位好人玩家被当作恶魔对待"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="fortune_teller",
            name="预言家",
            name_en="Fortune Teller",
            team=Team.GOOD,
            role_type=RoleType.TOWNSFOLK,
            ability=Ability(
                trigger=AbilityTrigger.EACH_NIGHT,
                action_type=AbilityType.INFO_GATHER,
                description="每晚你会选择两名玩家。你会得知其中是否有一名是恶魔（即便他已死亡）",
                night_order=55,
            ),
        )

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        # 预言家由于选两个，这里 target 可能是逗号分隔或 list
        return game_state, []

    def get_night_info(self, game_state, actor):
        # 注意：预言家通常需要主动选择两个目标。在 Orchestrator 中应先请求 act
        # 这里为了演示暂用随机或模拟。
        pass


@register_role("monk")
class MonkRole(BaseRole):
    """僧侣: 每晚（除了第一夜）选择一名玩家（不能选自己），该玩家今晚免受恶魔侵害"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="monk",
            name="僧侣",
            name_en="Monk",
            team=Team.GOOD,
            role_type=RoleType.TOWNSFOLK,
            ability=Ability(
                trigger=AbilityTrigger.EACH_NIGHT_EXCEPT_FIRST,
                action_type=AbilityType.PROTECTION,
                description="除第一夜外，每晚选择一名玩家（不能选你自己），该玩家今晚免受恶魔攻击",
                night_order=21,
            ),
        )

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        if not target: return game_state, []
        # 添加保护状态
        from src.state.game_state import PlayerStatus
        new_state = game_state
        target_p = game_state.get_player(target)
        if target_p:
            new_statuses = tuple(list(target_p.statuses) + [PlayerStatus.PROTECTED])
            new_state = game_state.with_player_update(target, statuses=new_statuses)
        
        event = GameEvent(
            event_type="protection",
            phase=GamePhase.NIGHT,
            round_number=game_state.round_number,
            actor=actor.player_id,
            target=target,
            visibility=Visibility.STORYTELLER_ONLY
        )
        return new_state.with_event(event), [event]


@register_role("ravenkeeper")
class RavenkeeperRole(BaseRole):
    """守鸦人: 如果你在夜晚死亡，你可以选择一名玩家并得知其角色"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="ravenkeeper",
            name="守鸦人",
            name_en="Ravenkeeper",
            team=Team.GOOD,
            role_type=RoleType.TOWNSFOLK,
            ability=Ability(
                trigger=AbilityTrigger.ON_DEATH,
                action_type=AbilityType.INFO_GATHER,
                description="如果你在夜晚死去，你会得知一名玩家的角色",
                night_order=58,
            ),
        )

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        if not target: return game_state, []
        target_p = game_state.get_player(target)
        if not target_p: return game_state, []
        
        event = GameEvent(
            event_type="night_info",
            phase=GamePhase.NIGHT,
            round_number=game_state.round_number,
            target=actor.player_id,
            payload={"role_seen": target_p.role_id},
            visibility=Visibility.PRIVATE
        )
        return game_state.with_event(event), [event]


@register_role("virgin")
class VirginRole(BaseRole):
    """圣女: 如果你是第一个提名你的人，且你是正义阵营，该提名者将被处决"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="virgin",
            name="圣女",
            name_en="Virgin",
            team=Team.GOOD,
            role_type=RoleType.TOWNSFOLK,
            ability=Ability(
                trigger=AbilityTrigger.DAY,
                action_type=AbilityType.PASSIVE_EFFECT,
                description="如果你被第一名提名你的玩家（且他是村民角色）提名，该玩家立即被处决",
                night_order=0,
            ),
        )

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        # 圣女的逻辑通常在 NominationManager 中被动触发
        return game_state, []


@register_role("slayer")
class SlayerRole(BaseRole):
    """杀手: 每局游戏一次，在白天你可以公开选择一名玩家，如果是恶魔，该玩家死亡"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="slayer",
            name="杀手",
            name_en="Slayer",
            team=Team.GOOD,
            role_type=RoleType.TOWNSFOLK,
            ability=Ability(
                trigger=AbilityTrigger.ONCE_PER_GAME,
                action_type=AbilityType.KILL,
                description="每局游戏一次，在白天，你可以公开选择一名玩家：如果他是恶魔，他将死亡",
                night_order=0,
            ),
        )

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        if not target: return game_state, []
        target_p = game_state.get_player(target)
        if not target_p: return game_state, []
        
        from src.engine.roles.base_role import get_role_class
        cls = get_role_class(target_p.role_id)
        is_demon = cls and cls.get_definition().role_type == RoleType.DEMON
        
        events = []
        new_state = game_state
        if is_demon:
            new_state = game_state.with_player_update(target, is_alive=False)
            death_event = GameEvent(
                event_type="player_death",
                phase=game_state.phase,
                round_number=game_state.round_number,
                target=target,
                payload={"reason": "slayer_shot"}
            )
            events.append(death_event)
            new_state = new_state.with_event(death_event)
            
        return new_state, events


@register_role("soldier")
class SoldierRole(BaseRole):
    """士兵: 你不会死于恶魔之手"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="soldier",
            name="士兵",
            name_en="Soldier",
            team=Team.GOOD,
            role_type=RoleType.TOWNSFOLK,
            ability=Ability(
                trigger=AbilityTrigger.PASSIVE,
                action_type=AbilityType.PROTECTION,
                description="你不会被恶魔杀死",
                night_order=0,
            ),
        )

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        return game_state, []


@register_role("mayor")
class MayorRole(BaseRole):
    """市长: 如果白天没有人被处决，你可能被宣布获胜。如果你在晚上被杀，另一名玩家可能替你而死"""

    @staticmethod
    def get_definition() -> RoleDefinition:
        return RoleDefinition(
            role_id="mayor",
            name="市长",
            name_en="Mayor",
            team=Team.GOOD,
            role_type=RoleType.TOWNSFOLK,
            ability=Ability(
                trigger=AbilityTrigger.PASSIVE,
                action_type=AbilityType.PASSIVE_EFFECT,
                description="如果你在夜晚被杀，可能会有另一名玩家替你而死。如果白天没人被处决，游戏可能以此结束",
                night_order=0,
            ),
        )

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        return game_state, []
