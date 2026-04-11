"""
游戏状态数据模型

定义游戏的全局状态、玩家状态等核心数据结构。
采用 Pydantic 不可变模型，支持序列化和快照。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# 枚举类型定义
# ============================================================

class Team(str, Enum):
    """阵营"""
    GOOD = "good"
    EVIL = "evil"


class RoleType(str, Enum):
    """角色类型"""
    TOWNSFOLK = "townsfolk"    # 村民
    OUTSIDER = "outsider"     # 外来者
    MINION = "minion"         # 爪牙
    DEMON = "demon"           # 恶魔


class GamePhase(str, Enum):
    """游戏阶段"""
    SETUP = "setup"                     # 游戏准备
    FIRST_NIGHT = "first_night"         # 第一夜
    DAY_DISCUSSION = "day_discussion"   # 白天讨论
    NOMINATION = "nomination"           # 提名阶段
    VOTING = "voting"                   # 投票阶段
    EXECUTION = "execution"             # 处决结算
    NIGHT = "night"                     # 夜晚阶段
    GAME_OVER = "game_over"             # 游戏结束


class Visibility(str, Enum):
    """信息可见性级别"""
    PUBLIC = "public"                   # 所有人可见
    TEAM_EVIL = "team_evil"             # 邪恶阵营可见
    TEAM_GOOD = "team_good"             # 正义阵营可见
    PRIVATE = "private"                 # 仅个人可见
    STORYTELLER_ONLY = "storyteller_only"  # 仅说书人可见


class PlayerStatus(str, Enum):
    """玩家特殊状态标记"""
    ALIVE = "alive"
    DEAD = "dead"
    POISONED = "poisoned"       # 中毒
    DRUNK = "drunk"             # 醉酒
    PROTECTED = "protected"     # 被保护
    NO_ABILITY = "no_ability"   # 能力失效


# ============================================================
# 角色定义
# ============================================================

class AbilityTrigger(str, Enum):
    """技能触发时机"""
    FIRST_NIGHT = "first_night"
    EACH_NIGHT = "each_night"
    EACH_NIGHT_EXCEPT_FIRST = "each_night_except_first"
    DAY = "day"
    PASSIVE = "passive"
    ON_DEATH = "on_death"
    ONCE_PER_GAME = "once_per_game"


class AbilityType(str, Enum):
    """技能类型"""
    INFO_GATHER = "info_gather"       # 信息收集
    PROTECTION = "protection"         # 保护
    KILL = "kill"                     # 击杀
    MANIPULATION = "manipulation"     # 操控
    DETECTION = "detection"           # 侦测
    PASSIVE_EFFECT = "passive_effect" # 被动效果


class Ability(BaseModel):
    """角色技能定义"""
    trigger: AbilityTrigger
    action_type: AbilityType
    description: str
    description_en: str = ""
    night_order: int = 50   # 夜晚行动优先级（越小越先执行）


class RoleDefinition(BaseModel):
    """角色定义"""
    role_id: str
    name: str
    name_en: str
    team: Team
    role_type: RoleType
    ability: Ability
    drunk_behavior: str = "no_effect"  # 中毒/醉酒时的行为
    setup_influence: str = ""          # 对游戏设置的影响


# ============================================================
# 玩家状态
# ============================================================

class PlayerState(BaseModel):
    """玩家状态"""
    model_config = {"frozen": True}

    player_id: str
    name: str
    role_id: str                                # 角色ID
    team: Team                                  # 阵营
    true_role_id: Optional[str] = None          # 真实身份
    perceived_role_id: Optional[str] = None     # 玩家自认身份
    public_claim_role_id: Optional[str] = None  # 公开宣称身份
    current_team: Optional[Team] = None         # 当前阵营（可被转化）
    is_alive: bool = True
    fake_role: Optional[str] = None             # 虚假身份（用于酒鬼等显示给玩家的假身份）
    statuses: tuple[PlayerStatus, ...] = (PlayerStatus.ALIVE,)
    has_used_dead_vote: bool = False             # 死后是否已使用最后一票
    ghost_votes_remaining: int = 1              # 剩余亡魂投票数
    storyteller_notes: tuple[str, ...] = ()
    ongoing_effects: tuple[str, ...] = ()

    def with_update(self, **kwargs) -> PlayerState:
        """创建一个更新了指定字段的新状态（不可变更新模式）"""
        data = self.model_dump()
        data.update(kwargs)
        if data.get("true_role_id") is None:
            data["true_role_id"] = data["role_id"]
        if data.get("perceived_role_id") is None:
            data["perceived_role_id"] = data.get("fake_role") or data["role_id"]
        if data.get("current_team") is None:
            data["current_team"] = data["team"]
        return PlayerState(**data)

    def model_post_init(self, __context) -> None:
        if self.true_role_id is None:
            object.__setattr__(self, "true_role_id", self.role_id)
        if self.perceived_role_id is None:
            object.__setattr__(self, "perceived_role_id", self.fake_role or self.role_id)
        if self.current_team is None:
            object.__setattr__(self, "current_team", self.team)

    @property
    def is_poisoned(self) -> bool:
        """是否处于中毒状态 (不含醉酒，用于说书人界面区分)"""
        return PlayerStatus.POISONED in self.statuses

    @property
    def is_drunk(self) -> bool:
        """是否处于醉酒状态"""
        return PlayerStatus.DRUNK in self.statuses
    
    @property
    def ability_suppressed(self) -> bool:
        """能力是否被抑制 (中毒或醉酒均导致抑制)"""
        return self.is_poisoned or self.is_drunk

    @property
    def can_vote(self) -> bool:
        """是否能投票"""
        if self.is_alive:
            return True
        return not self.has_used_dead_vote and self.ghost_votes_remaining > 0


# ============================================================
# 游戏事件
# ============================================================

class GameEvent(BaseModel):
    """游戏事件"""
    model_config = {"frozen": True}

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.now)
    phase: GamePhase
    round_number: int
    trace_id: str = ""
    actor: Optional[str] = None       # 事件发起者的 player_id
    target: Optional[str] = None      # 事件目标的 player_id
    payload: dict = Field(default_factory=dict)
    visibility: Visibility = Visibility.PUBLIC


# ============================================================
# 聊天消息
# ============================================================

class ChatMessage(BaseModel):
    """对话消息"""
    model_config = {"frozen": True}

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    speaker: str               # player_id 或 "system" / "storyteller"
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    phase: GamePhase
    round_number: int
    tone: str = "neutral"      # calm / passionate / accusatory / defensive
    target_player: Optional[str] = None  # 主要针对的玩家
    recipient_ids: Optional[tuple[str, ...]] = None # 私聊对象 (空则全公开)


class PrivatePlayerView(BaseModel):
    """同步给 Agent 的私有视角快照（已剥离所有上帝视角）"""

    player_id: str
    name: str
    perceived_role_id: str
    public_claim_role_id: Optional[str] = None
    current_team: Team
    is_alive: bool = True


class ExecutionCandidate(BaseModel):
    """当日可被处决候选记录"""

    nominee_id: str
    votes: int
    nominator_id: str
    passed: bool
    trace_id: str = ""


# ============================================================
# 游戏全局状态
# ============================================================

class GameState(BaseModel):
    """
    游戏全局状态 — 不可变快照

    每次状态变更都生成新的 GameState 实例，
    旧实例保留在历史记录中，支持回放和调试。
    """
    model_config = {"frozen": True}

    # 基础信息
    game_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    phase: GamePhase = GamePhase.SETUP
    round_number: int = 0
    day_number: int = 0

    # 玩家信息
    players: tuple[PlayerState, ...] = ()
    seat_order: tuple[str, ...] = ()            # 座位顺序 player_ids

    # 事件历史
    event_log: tuple[GameEvent, ...] = ()
    chat_history: tuple[ChatMessage, ...] = ()

    # 提名相关
    current_nominee: Optional[str] = None       # 当前被提名者
    current_nominator: Optional[str] = None     # 当前提名者
    votes_today: dict = Field(default_factory=dict)   # 今天的投票记录
    nominations_today: tuple[str, ...] = ()     # 今天已提名过的玩家
    nominees_today: tuple[str, ...] = ()        # 今天已被提名过的玩家
    execution_candidates: tuple[ExecutionCandidate, ...] = ()

    # 游戏结果
    winning_team: Optional[Team] = None

    # 配置与魔典 (Phase 8/9 扩展)
    config: Optional[GameConfig] = None
    grimoire: Optional[GrimoireInfo] = None
    bluffs: tuple[str, ...] = ()             # 给恶魔的伪装角色 (3个)
    payload: dict = Field(default_factory=dict)  # 存储特定角色的中间数据 (如预言家的红鲱鱼)

    def get_player(self, player_id: str) -> Optional[PlayerState]:
        """根据 player_id 获取玩家状态"""
        for player in self.players:
            if player.player_id == player_id:
                return player
        return None

    def get_player_by_name(self, name: str) -> Optional[PlayerState]:
        """根据名称获取玩家状态"""
        for player in self.players:
            if player.name == name:
                return player
        return None

    def get_alive_players(self) -> list[PlayerState]:
        """获取所有存活玩家"""
        return [p for p in self.players if p.is_alive]

    def get_dead_players(self) -> list[PlayerState]:
        """获取所有死亡玩家"""
        return [p for p in self.players if not p.is_alive]

    @property
    def alive_count(self) -> int:
        return len(self.get_alive_players())

    @property
    def player_count(self) -> int:
        return len(self.players)

    def with_update(self, **kwargs) -> GameState:
        """创建一个更新了指定字段的新状态"""
        data = self.model_dump()
        data.update(kwargs)
        return GameState(**data)

    def with_player_update(self, player_id: str, **kwargs) -> GameState:
        """更新指定玩家的状态，返回新的 GameState"""
        new_players = []
        for p in self.players:
            if p.player_id == player_id:
                new_players.append(p.with_update(**kwargs))
            else:
                new_players.append(p)
        return self.with_update(players=tuple(new_players))

    def with_event(self, event: GameEvent) -> GameState:
        """追加一个事件，返回新的 GameState"""
        return self.with_update(event_log=self.event_log + (event,))

    def with_message(self, message: ChatMessage) -> GameState:
        """追加一条聊天消息"""
        return self.with_update(chat_history=self.chat_history + (message,))


# ============================================================
# 游戏配置
# ============================================================

class ScriptConfig(BaseModel):
    """剧本配置"""
    script_id: str
    name: str
    name_en: str = ""
    roles: list[str]           # 剧本包含的角色ID列表


class GameConfig(BaseModel):
    """游戏配置"""
    player_count: int
    script: Optional[ScriptConfig] = None
    script_id: str = "trouble_brewing"
    human_client_id: Optional[str] = None
    human_mode: str = "none"  # player | storyteller | none
    storyteller_client_id: Optional[str] = None
    human_player_ids: list[str] = Field(default_factory=list)  # 人类玩家ID
    is_human_participant: bool = True     # 人类是否参与游戏 (True: 玩家, False: 旁观)
    storyteller_mode: str = "auto"   # "auto" 自动说书人 / "human" 人类说书人
    llm_model: str = "gpt-4o-mini"
    backend_mode: str = "auto"
    audit_mode: bool = False
    discussion_rounds: int = 3       # 每天讨论轮数
    max_nomination_rounds: Optional[int] = None
    turn_timeout: int = 300          # 人类玩家行动超时（秒）


# ============================================================
# 魔典信息 (说书人视角)
# ============================================================

class PlayerGrimoireInfo(BaseModel):
    """魔典中的玩家明细"""
    player_id: str
    name: str
    role_id: str
    true_role_id: Optional[str] = None
    perceived_role_id: Optional[str] = None
    public_claim_role_id: Optional[str] = None
    fake_role: Optional[str] = None
    team: Team
    current_team: Optional[Team] = None
    is_alive: bool
    is_poisoned: bool
    is_drunk: bool
    storyteller_notes: tuple[str, ...] = ()
    ongoing_effects: tuple[str, ...] = ()


class GrimoireInfo(BaseModel):
    """魔典：全局真实状态汇总"""
    players: tuple[PlayerGrimoireInfo, ...] = ()
    night_actions: tuple[dict, ...] = ()  # 昨晚行动记录 (扩展预留)
    reminders: tuple[str, ...] = ()
