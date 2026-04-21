"""
村民角色 (Townsfolk)

实现惹事生非(Trouble Brewing)剧本中的核心村民角色。
"""

from __future__ import annotations

import logging
import random
from typing import Any, Optional

from src.engine.roles.base_role import BaseRole, register_role


logger = logging.getLogger(__name__)
from src.state.game_state import (
    Ability,
    AbilityTrigger,
    AbilityType,
    GameEvent,
    GamePhase,
    GameState,
    PlayerState,
    RoleDefinition,
    RoleType,
    Team,
    Visibility,
)


def _is_first_night(game_state: GameState) -> bool:
    return game_state.phase in (GamePhase.SETUP, GamePhase.FIRST_NIGHT)


def _pick_decoy_pair(game_state: GameState, actor_id: str, target_player_id: str) -> list[str]:
    others = [p for p in game_state.players if p.player_id not in (actor_id, target_player_id)]
    decoy = random.choice(others) if others else game_state.get_player(target_player_id)
    pair = [target_player_id]
    if decoy:
        if decoy.player_id != target_player_id:
            pair.append(decoy.player_id)
    random.shuffle(pair)
    return pair


@register_role("washerwoman")
class WasherwomanRole(BaseRole):
    """洗衣妇: 你会得知两位玩家中有一位是某个特定的村民角色"""

    fixed_info_role = True
    storyteller_info_role = True

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
                night_order=34,
            ),
        )

    def build_storyteller_info(
        self,
        game_state: GameState,
        actor: PlayerState,
    ) -> Optional[dict]:
        """为洗衣妇生成供说书人裁定的原始夜晚信息。"""
        if not _is_first_night(game_state):
            return None

        # 优先从持久化记录中读取
        key = f"initial_info:washerwoman:{actor.player_id}"
        memo = game_state.payload.get(key)
        if memo:
            return memo

        # 如果中毒，可能会获得假信息
        # 1. 找到在场的所有其他村民
        townsfolks = [
            p for p in game_state.players 
            if p.player_id != actor.player_id 
            and (p.true_role_id or p.role_id) != "washerwoman"
            and self._is_townsfolk_role(game_state, p)
        ]
        
        if not townsfolks:
            return None
            
        # 2. 随机选一个真实的
        target_player = random.choice(townsfolks)
        target_role_id = target_player.true_role_id or target_player.role_id
        pair = _pick_decoy_pair(game_state, actor.player_id, target_player.player_id)
        
        info = {
            "type": "washerwoman_info",
            "players": pair,
            "role_seen": target_role_id
        }
        # 注意：在这里无法直接修改 game_state (只读视图)，持久化逻辑通常应在 Orchestrator 产生的 execute_ability 中
        return info

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        # 如果是首夜，生成信息并持久化
        if _is_first_night(game_state):
            info = self.build_storyteller_info(game_state, actor)
            if info:
                key = f"initial_info:washerwoman:{actor.player_id}"
                new_payload = dict(game_state.payload)
                new_payload[key] = info
                return game_state.with_update(payload=new_payload), []
        return game_state, []

    def _is_townsfolk_role(self, game_state: GameState, player: PlayerState) -> bool:
        from src.engine.roles.base_role import get_role_class
        role_id = player.true_role_id or player.role_id
        cls = get_role_class(role_id)
        if not cls: return False
        role_instance = cls()
        return role_instance.registers_as_role_type(game_state, player) == RoleType.TOWNSFOLK

    def get_night_info(
        self,
        game_state: GameState,
        actor: PlayerState,
    ) -> Optional[dict]:
        return self.build_storyteller_info(game_state, actor)



@register_role("empath")
class EmpathRole(BaseRole):
    """共情者: 每晚你会得知你的两个活着的邻居中有几个是邪恶的"""

    fixed_info_role = True
    storyteller_info_role = True

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

    def build_storyteller_info(
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

        def _is_evil(player_state: Any) -> bool:
            if not player_state: return False
            from src.engine.roles.base_role import get_role_class
            role_cls = get_role_class(player_state.true_role_id or player_state.role_id)
            if role_cls:
                role_instance = role_cls()
                return role_instance.registers_as_team(game_state, player_state) == Team.EVIL
            return (player_state.current_team or player_state.team) == Team.EVIL

        evil_count = 0
        left_player = game_state.get_player(seat_order[left_idx])
        if left_player and _is_evil(left_player):
            evil_count += 1
            
        right_player = game_state.get_player(seat_order[right_idx])
        # 如果只剩两个人（自己和另一个活人），不重复计算
        if left_idx != right_idx and right_player and _is_evil(right_player):
            evil_count += 1

        return {
            "type": "empath_info",
            "evil_count": evil_count
        }

    def get_night_info(
        self,
        game_state: GameState,
        actor: PlayerState,
    ) -> Optional[dict]:
        return self.build_storyteller_info(game_state, actor)


@register_role("undertaker")
class UndertakerRole(BaseRole):
    """送葬者: 每个夜晚*，得知今天白天被处决的玩家角色"""

    fixed_info_role = True
    storyteller_info_role = True

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

    def build_storyteller_info(self, game_state: GameState, actor: PlayerState) -> Optional[dict]:
        if actor.ability_suppressed:
            # 中毒/醉酒时给一个随机身份
            from src.engine.roles.base_role import get_all_role_ids
            fake = random.choice(get_all_role_ids())
            return {"type": "undertaker_info", "role_seen": fake}
            
        # 只查找“今天白天”被处决的人，不能错误读取更早轮次的旧处决结果。
        target_role = None
        target_player_id = None
        for event in reversed(game_state.event_log):
            if (
                event.event_type == "execution_resolved"
                and event.round_number == game_state.round_number
                and event.payload.get("executed")
            ):
                victim = game_state.get_player(event.payload["executed"])
                if victim:
                    target_role = victim.true_role_id or victim.role_id
                    target_player_id = victim.player_id
                    break
        
        if not target_role:
            return None
            
        # 允许说书人通过 payload 覆盖 (处理中毒/醉酒的假信息)
        key = f"undertaker_override:{game_state.round_number}"
        if key in game_state.payload:
            return {"type": "undertaker_info", "role_seen": game_state.payload[key], "player_id": target_player_id}

        return {"type": "undertaker_info", "role_seen": target_role, "player_id": target_player_id}

    def get_night_info(self, game_state: GameState, actor: PlayerState) -> Optional[dict]:
        return self.build_storyteller_info(game_state, actor)


@register_role("chef")
class ChefRole(BaseRole):
    """厨师: 你得知有多少对邪恶玩家邻座"""

    fixed_info_role = True
    storyteller_info_role = True

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
                night_order=37,
            ),
        )


    def build_storyteller_info(self, game_state: GameState, actor: PlayerState) -> Optional[dict]:
        if not _is_first_night(game_state):
            return None

        # 优先从持久化记录中读取
        key = f"initial_info:chef:{actor.player_id}"
        memo = game_state.payload.get(key)
        if memo:
            return memo

        def _is_evil(player_state: Any) -> bool:
            if not player_state: return False
            from src.engine.roles.base_role import get_role_class
            role_cls = get_role_class(player_state.true_role_id or player_state.role_id)
            if role_cls:
                role_instance = role_cls()
                return role_instance.registers_as_team(game_state, player_state) == Team.EVIL
            return (player_state.current_team or player_state.team) == Team.EVIL

        seat_order = game_state.seat_order
        n = len(seat_order)
        pairs = 0
        for i in range(n):
            p1 = game_state.get_player(seat_order[i])
            p2 = game_state.get_player(seat_order[(i+1)%n])
            if p1 and p2 and _is_evil(p1) and _is_evil(p2):
                pairs += 1
        
        # 如果中毒/醉酒或手动操作，计算出的 truth 仅作为参考，实际应由说书人决定
        # 在我们的架构中，StorytellerAgent 会在 SETUP 阶段调用此函数生成初始建议，并将其存入 payload
        info = {"type": "chef_info", "pairs": pairs}
        
        if actor.ability_suppressed:
            # 中毒/醉酒：说书人可以给任何数字。
            # 这里我们返回一个标记，或者如果 payload 中已经有 ST 的决定，则使用它
            logger.info(f"[ChefRole] actor {actor.player_id} is suppressed. Info may be false.")
        
        logger.info(f"[ChefRole] build_info: actor={actor.player_id} pairs={pairs}")
        return info

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        if _is_first_night(game_state):
            info = self.build_storyteller_info(game_state, actor)
            if info:
                key = f"initial_info:chef:{actor.player_id}"
                new_payload = dict(game_state.payload)
                new_payload[key] = info
                return game_state.with_update(payload=new_payload), []
        return game_state, []

    def get_night_info(self, game_state, actor):
        return self.build_storyteller_info(game_state, actor)


@register_role("librarian")
class LibrarianRole(BaseRole):
    """图书馆员: 你得知两位玩家中有一位是某个特定的外来者角色，或者没有外来者"""

    fixed_info_role = True
    storyteller_info_role = True

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
                night_order=35,
            ),
        )


    def build_storyteller_info(self, game_state, actor):
        if not _is_first_night(game_state):
            return None

        key = f"initial_info:librarian:{actor.player_id}"
        memo = game_state.payload.get(key)
        if memo:
            return memo

        outsiders = [p for p in game_state.players if p.player_id != actor.player_id and self._is_outsider_role(game_state, p)]
        if not outsiders:
            info = {"type": "librarian_info", "has_outsider": False}
        else:
            target_p = random.choice(outsiders)
            pair = _pick_decoy_pair(game_state, actor.player_id, target_p.player_id)
            info = {"type": "librarian_info", "has_outsider": True, "players": pair, "role_seen": target_p.true_role_id or target_p.role_id}
        
        return info

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        if _is_first_night(game_state):
            info = self.build_storyteller_info(game_state, actor)
            if info:
                key = f"initial_info:librarian:{actor.player_id}"
                new_payload = dict(game_state.payload)
                new_payload[key] = info
                return game_state.with_update(payload=new_payload), []
        return game_state, []

    def _is_outsider_role(self, game_state: GameState, player: PlayerState):
        from src.engine.roles.base_role import get_role_class
        role_id = player.true_role_id or player.role_id
        cls = get_role_class(role_id)
        if not cls: return False
        role_instance = cls()
        return role_instance.registers_as_role_type(game_state, player) == RoleType.OUTSIDER

    def get_night_info(self, game_state, actor):
        return self.build_storyteller_info(game_state, actor)


@register_role("investigator")
class InvestigatorRole(BaseRole):
    """调查员: 你得知两位玩家中有一位是某个特定的爪牙角色"""

    fixed_info_role = True
    storyteller_info_role = True

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
                night_order=36,
            ),
        )


    def build_storyteller_info(self, game_state, actor):
        if not _is_first_night(game_state):
            return None

        key = f"initial_info:investigator:{actor.player_id}"
        memo = game_state.payload.get(key)
        if memo:
            return memo

        minions = [p for p in game_state.players if p.player_id != actor.player_id and self._is_minion_role(game_state, p)]
        if not minions:
            return None
        
        target_p = random.choice(minions)
        pair = _pick_decoy_pair(game_state, actor.player_id, target_p.player_id)
        info = {"type": "investigator_info", "players": pair, "role_seen": target_p.true_role_id or target_p.role_id}
        return info

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        if _is_first_night(game_state):
            info = self.build_storyteller_info(game_state, actor)
            if info:
                key = f"initial_info:investigator:{actor.player_id}"
                new_payload = dict(game_state.payload)
                new_payload[key] = info
                return game_state.with_update(payload=new_payload), []
        return game_state, []

    def _is_minion_role(self, game_state: GameState, player: PlayerState):
        from src.engine.roles.base_role import get_role_class
        role_id = player.true_role_id or player.role_id
        cls = get_role_class(role_id)
        if not cls: return False
        role_instance = cls()
        return role_instance.registers_as_role_type(game_state, player) == RoleType.MINION

    def get_night_info(self, game_state, actor):
        return self.build_storyteller_info(game_state, actor)



@register_role("fortune_teller")
class FortuneTellerRole(BaseRole):
    """预言家: 每晚选择两位玩家，得知其中是否有恶魔。此外还会有一位好人玩家被当作恶魔对待"""

    storyteller_info_role = True
    requires_night_target = True

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

    def get_required_targets(self, game_state: GameState, phase: GamePhase) -> int:
        return 2

    def can_target_self(self) -> bool:
        return True

    def execute_ability(self, game_state: GameState, actor: PlayerState, target: Optional[str | list[str]] = None, **kwargs: Any) -> tuple[GameState, list[GameEvent]]:
        # 预言家由于选两个，这里处理嵌套列表、列表或逗号分隔字符串
        def flatten_targets(value: Any) -> list[str]:
            flattened: list[str] = []

            def visit(item: Any) -> None:
                if item is None:
                    return
                if isinstance(item, str):
                    for piece in item.split(","):
                        piece = piece.strip()
                        if piece:
                            flattened.append(piece)
                    return
                if isinstance(item, (list, tuple, set)):
                    for nested in item:
                        visit(nested)
                    return
                text = str(item).strip()
                if text:
                    flattened.append(text)

            visit(value)
            return flattened

        targets = flatten_targets(kwargs.get("targets")) or flatten_targets(target)

        if len(targets) < 2:
            raise ValueError("预言家必须选择两名玩家")
            
        # 记录行动事件，供 build_storyteller_info 使用
        event = GameEvent(
            event_type="night_action_resolved",
            phase=game_state.phase,
            round_number=game_state.round_number,
            actor=actor.player_id,
            target=targets[0] if targets else None,
            payload={"targets": targets, "role_id": self.role_id()},
            visibility=Visibility.STORYTELLER_ONLY
        )
        return game_state.with_event(event), [event]

    def build_storyteller_info(self, game_state: GameState, actor: PlayerState) -> Optional[dict]:
        # 注意：预言家通常需要主动选择两个目标。在 Orchestrator 中应先请求 act
        # 这里为了模拟/AI决策，如果 action 中没有提供 target，我们需要通过某种方式获取
        # 实际全自动化运行时，这部分由 AIAgent.act 返回，Orchestrator 传入 execute_ability
        # get_night_info 仅用于向玩家展示其获得的结果。
        
        # 预言家特定的“宿敌/红鲱鱼”逻辑：在 SETUP 时应已确定一个好人被视为恶魔
        # 这里动态寻找或从状态中获取。为简单起见，我们假设在 GameState.payload 中存有 fortune_teller_red_herring
        red_herring_id = game_state.payload.get("fortune_teller_red_herring")
        
        # 寻找最近的一次预言家行动事件
        last_action = None
        for event in reversed(game_state.event_log):
            if event.event_type == "night_action_resolved" and event.actor == actor.player_id:
                last_action = event
                break
        
        if not last_action:
            return None
            
        targets = last_action.payload.get("targets", [])
        if not targets and last_action.target:
            targets = [last_action.target]
        if not targets:
            return None
            
        has_demon = False
        for t_id in targets:
            target_p = game_state.get_player(t_id)
            if not target_p: continue
            
            # 检查是否表现为恶魔 (含红鲱鱼逻辑)
            from src.engine.roles.base_role import get_role_class
            cls = get_role_class(target_p.true_role_id or target_p.role_id)
            if cls:
                role_instance = cls()
                if role_instance.registers_as_role_type(game_state, target_p) == RoleType.DEMON:
                    has_demon = True
                    break
            
            # 兼容旧有的 red_herring_id 逻辑 (如果角色钩子未覆盖)
            if t_id == red_herring_id:
                has_demon = True
                break
        
        return {
            "type": "fortune_teller_info",
            "players": targets,
            "has_demon": has_demon
        }

    def get_night_info(self, game_state: GameState, actor: PlayerState) -> Optional[dict]:
        return self.build_storyteller_info(game_state, actor)


@register_role("monk")
class MonkRole(BaseRole):
    """僧侣: 每晚（除了第一夜）选择一名玩家（不能选自己），该玩家今晚免受恶魔侵害"""

    requires_night_target = True

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
        if not target:
            raise ValueError("僧侣必须选择一名玩家")
        if target == actor.player_id:
            raise ValueError("僧侣不能选择自己")
        
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
            payload={"role_seen": target_p.true_role_id or target_p.role_id, "player_id": target_p.player_id},
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

    @classmethod
    def has_used_shot(cls, actor: PlayerState) -> bool:
        return "slayer_used" in actor.storyteller_notes

    @classmethod
    def mark_shot_used(cls, game_state: GameState, actor_id: str) -> GameState:
        actor = game_state.get_player(actor_id)
        if not actor:
            return game_state
        return game_state.with_player_update(
            actor_id,
            storyteller_notes=actor.storyteller_notes + ("slayer_used",),
        )

    def can_act_at_phase(self, game_state: GameState, phase: GamePhase) -> bool:
        return phase in (GamePhase.DAY_DISCUSSION, GamePhase.NOMINATION, GamePhase.VOTING)

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
        if not target:
            return game_state, []
        if self.has_used_shot(actor):
            raise ValueError("杀手本局已经使用过能力")
        target_p = game_state.get_player(target)
        if not target_p:
            return game_state, []
        
        from src.engine.roles.base_role import get_role_class
        cls = get_role_class(target_p.true_role_id or target_p.role_id)
        is_demon = cls and cls.get_definition().role_type == RoleType.DEMON
        
        events = []
        new_state = self.mark_shot_used(game_state, actor.player_id)
        shot_event = GameEvent(
            event_type="slayer_shot",
            phase=game_state.phase,
            round_number=game_state.round_number,
            actor=actor.player_id,
            target=target,
            visibility=Visibility.PUBLIC,
            payload={"success": is_demon, "used": True}
        )
        events.append(shot_event)
        new_state = new_state.with_event(shot_event)
        if is_demon:
            pre_death_state = new_state
            new_state = new_state.with_player_update(target, is_alive=False)
            death_event = GameEvent(
                event_type="player_death",
                phase=game_state.phase,
                round_number=game_state.round_number,
                actor=actor.player_id,
                target=target,
                visibility=Visibility.PUBLIC,
                payload={"reason": "slayer_shot"}
            )
            events.append(death_event)
            new_state = new_state.with_event(death_event)
            
            from src.engine.roles.minions import ScarletWomanRole
            new_state, sw_events = ScarletWomanRole.check_and_transfer(
                pre_death_state, new_state, target, ""
            )
            events.extend(sw_events)
            
        return new_state, events


@register_role("soldier")
class SoldierRole(BaseRole):
    """士兵: 你不会死于恶魔之手"""

    @classmethod
    def is_immune_to_demon(cls, actor: PlayerState | None = None) -> bool:
        return bool(actor and (actor.true_role_id or actor.role_id) == "soldier")

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

    @classmethod
    def should_redirect_night_death(cls, game_state: GameState, actor: PlayerState) -> bool:
        return actor.is_alive and (actor.true_role_id or actor.role_id) == "mayor"

    @classmethod
    def choose_redirection_target(
        cls,
        game_state: GameState,
        mayor_player_id: str,
        killer_id: Optional[str] = None,
    ) -> Optional[str]:
        for player in game_state.get_alive_players():
            if player.player_id in {mayor_player_id, killer_id}:
                continue
            return player.player_id
        return None

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
                description="如果你在夜晚被恶魔杀死，可能会有另一名存活玩家替你而死。",
                night_order=0,
            ),
        )

    def execute_ability(self, game_state, actor, target=None, **kwargs):
        return game_state, []
