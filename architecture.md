# 🏰 鸦木布拉夫小镇 — 多Agent桌游系统 顶层架构设计

> **Ravenswood Bluff — Multi-Agent Board Game System**
>
> 一个基于LLM多智能体的社交推理桌游平台，以「血染钟楼」(Blood on the Clocktower) 为核心玩法，用户可作为玩家或主持人（说书人），与AI Agent们展开一场智慧与谎言的较量。

---

## 1. 项目愿景与目标

### 1.1 核心愿景

在鸦木布拉夫小镇中，每个AI Agent都是一位"有血有肉"的小镇居民：它有自己的性格、记忆、推理能力和社交策略。用户可以作为**玩家**融入其中与AI斗智斗勇，也可以作为**说书人（管理员）**主持一场AI之间的精彩对决。

### 1.2 具体目标

| 目标 | 描述 |
|------|------|
| 🎮 **可玩性** | 完整实现血染钟楼的游戏流程（夜晚→白天→提名→处决） |
| 🤖 **智能性** | AI Agent具备推理、欺骗、说服、结盟等社交推理能力 |
| 🧩 **可扩展性** | 模块化设计，方便日后扩展其他桌游（狼人杀、阿瓦隆等） |
| 👥 **人机混合** | 支持纯AI对局、人机混合对局、纯人类对局（AI辅助说书人） |
| 📊 **可观测性** | 完善的日志与事件回放，可追溯每个Agent的决策链路 |

---

## 2. 系统全局架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        🌐 前端展示层 (Frontend)                      │
│   Web UI / Terminal UI — 对话面板、游戏面板、说书人控制台、回放面板      │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ WebSocket / REST API
┌──────────────────────────▼──────────────────────────────────────────┐
│                     🎯 游戏编排层 (Orchestrator)                      │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │ 游戏循环管理  │  │  回合调度器   │  │   事件总线 (Event Bus)    │   │
│  │ (Game Loop) │  │ (Turn Sched) │  │  发布/订阅 异步消息机制    │   │
│  └─────────────┘  └──────────────┘  └──────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌────────────────┐
│ 🎲 游戏引擎  │  │ 🤖 Agent层   │  │ 📋 状态管理层   │
│ (Game Engine)│  │ (Agent Layer)│  │ (State Store)  │
│              │  │              │  │                │
│ • 规则引擎   │  │ • Agent工厂  │  │ • 游戏状态     │
│ • 阶段状态机 │  │ • 记忆系统   │  │ • 玩家状态     │
│ • 行动校验器 │  │ • 推理引擎   │  │ • 事件日志     │
│ • 胜负判定器 │  │ • 对话生成器 │  │ • 快照/回放    │
└──────────────┘  └──────┬───────┘  └────────────────┘
                         │
                ┌────────▼────────┐
                │ 🧠 LLM适配层    │
                │ (LLM Backend)   │
                │                 │
                │ • OpenAI / GPT  │
                │ • Anthropic     │
                │ • Google Gemini │
                │ • 本地模型       │
                └─────────────────┘
```

---

## 3. 核心模块详细设计

### 3.1 游戏引擎 (Game Engine)

游戏引擎是系统的「真理之源」(Ground Truth)，负责维护游戏规则的绝对权威。

#### 3.1.1 阶段状态机

血染钟楼的游戏流程本质上是一个有限状态机 (FSM)：

```
          ┌──────────────────────────────────────┐
          │                                      │
          ▼                                      │
    ┌──────────┐     ┌──────────┐     ┌─────────┴──┐
    │ 游戏准备  │────▶│  第一夜   │────▶│   白天讨论   │
    │  SETUP   │     │ 1st NIGHT│     │  DAY_DISC  │
    └──────────┘     └──────────┘     └─────┬──────┘
                                            │
                                  ┌─────────▼──────────┐
                                  │    提名与投票       │
                                  │  NOMINATION_VOTE   │
                                  └─────────┬──────────┘
                                            │
                              ┌─────────────▼───────────────┐
                              │         处决结算             │
                              │       EXECUTION             │
                              └─────────────┬───────────────┘
                                            │
                               ┌────────────▼────────────┐
                               │     胜负判定             │
                               │   WIN_CHECK             │
                               └─────┬──────────┬────────┘
                                     │          │
                              善恶一方获胜   游戏继续
                                     │          │
                              ┌──────▼──┐  ┌───▼──────┐
                              │ 游戏结束 │  │ 夜晚阶段  │──▶ 回到白天讨论
                              │ GAME_END│  │  NIGHT   │
                              └─────────┘  └──────────┘
```

#### 3.1.2 核心类设计

```
GameEngine
├── RuleEngine          # 规则引擎：校验行动合法性
│   ├── validate_action(action, game_state) -> bool
│   ├── get_legal_actions(player, phase) -> List[Action]
│   └── apply_action(action, game_state) -> GameState
│
├── PhaseManager        # 阶段管理器：管理状态机转移
│   ├── current_phase: GamePhase
│   ├── transition_to(next_phase)
│   └── get_night_order() -> List[Role]  # 夜晚行动顺序
│
├── VictoryChecker      # 胜负判定器
│   ├── check_victory(game_state) -> Optional[Team]
│   └── is_game_over() -> bool
│
└── NominationManager   # 提名投票管理器
    ├── nominate(nominator, nominee)
    ├── cast_vote(voter, vote: bool)
    └── resolve_nomination() -> Optional[Player]
```

#### 3.1.3 角色与技能系统

采用**数据驱动**的方式定义角色，便于扩展：

```python
# 角色定义示例（以JSON/YAML配置文件驱动）
{
    "role_id": "washerwoman",
    "name": "洗衣妇",
    "name_en": "Washerwoman",
    "team": "good",
    "type": "townsfolk",
    "ability": {
        "trigger": "first_night",       # 触发时机
        "action_type": "info_gather",   # 行动类型
        "description": "你会得知两位玩家中有一位是某个特定的村民角色",
        "parameters": {
            "shown_players": 2,
            "shown_role_type": "townsfolk",
            "one_is_correct": true
        }
    },
    "drunk_behavior": "receive_false_info",  # 中毒/醉酒时行为
    "night_order": 32   # 夜晚行动优先级
}
```

---

### 3.2 Agent层 (Agent Layer)

这是系统的「大脑」，每个Agent都是一个具备完整认知能力的智能体。

#### 3.2.1 Agent架构

```
┌─────────────────────────────────────────────┐
│               Agent (单个智能体)              │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │         🧠 认知核心 (Cognitive Core) │    │
│  │                                     │    │
│  │  ┌───────────┐  ┌───────────────┐  │    │
│  │  │  感知模块  │  │  推理模块      │  │    │
│  │  │ Perceiver │  │  Reasoner     │  │    │
│  │  │           │  │               │  │    │
│  │  │ •观察解析  │  │ •阵营推理     │  │    │
│  │  │ •信息过滤  │  │ •可信度分析   │  │    │
│  │  │ •上下文构建│  │ •策略规划     │  │    │
│  │  └───────────┘  └───────────────┘  │    │
│  │                                     │    │
│  │  ┌───────────┐  ┌───────────────┐  │    │
│  │  │  记忆模块  │  │  行动模块      │  │    │
│  │  │  Memory   │  │  Actor        │  │    │
│  │  │           │  │               │  │    │
│  │  │ •短期记忆  │  │ •夜晚选择     │  │    │
│  │  │ •长期记忆  │  │ •发言生成     │  │    │
│  │  │ •社交图谱  │  │ •投票决策     │  │    │
│  │  └───────────┘  └───────────────┘  │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  ┌──────────────┐  ┌────────────────────┐   │
│  │ 🎭 人格模块   │  │ 🗣️ 对话管理器      │   │
│  │  Persona     │  │  DialogManager    │   │
│  │              │  │                   │   │
│  │ •性格特征    │  │ •发言风格控制      │   │
│  │ •说话风格    │  │ •论点构建          │   │
│  │ •情绪状态    │  │ •质疑/反驳         │   │
│  └──────────────┘  └────────────────────┘   │
└─────────────────────────────────────────────┘
```

#### 3.2.2 记忆系统 (Memory System)

Agent的记忆是分层的，模拟人类的记忆机制：

| 记忆类型 | 内容 | 生命周期 | 存储方式 |
|---------|------|---------|---------|
| **工作记忆** | 当前阶段的即时信息（正在讨论什么、谁在说话） | 当前阶段 | 上下文窗口 |
| **短期记忆** | 今天发生的事件、对话摘要 | 当前轮次 | 结构化摘要 |
| **长期记忆** | 角色行为模式、信任/怀疑关系 | 整局游戏 | 向量存储/图谱 |
| **私密记忆** | 自己的角色、夜晚获得的信息 | 整局游戏 | 专属存储 |

#### 3.2.3 社交推理引擎

Agent需要维护一张动态的**社交信任图谱**：

```python
class SocialGraph:
    """每个Agent维护的社交关系图"""

    def __init__(self, players: List[str]):
        # 信任度矩阵: -1.0 (完全不信) ~ 1.0 (完全信任)
        self.trust_scores: Dict[str, float] = {}
        # 角色推测: 对每个玩家可能角色的概率分布
        self.role_beliefs: Dict[str, Dict[str, float]] = {}
        # 阵营推测: good/evil 概率
        self.alignment_beliefs: Dict[str, Dict[str, float]] = {}
        # 发言一致性记录
        self.consistency_log: Dict[str, List[Statement]] = {}

    def update_trust(self, player: str, event: GameEvent):
        """基于游戏事件更新信任度"""
        ...

    def predict_alignment(self, player: str) -> Dict[str, float]:
        """预测某玩家的阵营概率"""
        ...
```

#### 3.2.4 Agent工厂与角色绑定

```python
class AgentFactory:
    """根据角色配置创建Agent实例"""

    def create_agent(
        self,
        player_name: str,
        role: Role,
        persona: Persona,
        llm_backend: LLMBackend,
    ) -> Agent:
        """
        创建一个绑定了角色、人格和LLM后端的Agent。
        善良阵营的Agent会收到"找出恶魔"的战略目标，
        邪恶阵营的Agent会收到"隐藏身份、误导村民"的战略目标。
        """
        ...
```

---

### 3.3 编排层 (Orchestrator)

编排层是整个系统的**指挥中枢**，协调游戏引擎和Agent之间的交互。

#### 3.3.1 游戏循环 (Game Loop)

```python
class GameOrchestrator:
    """游戏编排器 — 驱动整个游戏生命周期"""

    async def run_game(self, config: GameConfig):
        # 1. 初始化
        game_state = self.engine.setup(config)
        agents = self.agent_factory.create_all(config)

        # 2. 第一夜
        await self._run_night(game_state, agents, is_first_night=True)

        # 3. 主循环
        while not self.engine.is_game_over(game_state):
            # 白天讨论
            await self._run_day_discussion(game_state, agents)
            # 提名投票
            await self._run_nomination(game_state, agents)
            # 处决结算
            self.engine.resolve_execution(game_state)
            # 胜负判定
            if self.engine.check_victory(game_state):
                break
            # 夜晚阶段
            await self._run_night(game_state, agents)

        # 4. 游戏结束
        return self._generate_game_summary(game_state)
```

#### 3.3.2 事件总线 (Event Bus)

所有游戏中发生的事情都通过事件总线进行传播，实现**松耦合**：

```python
# 事件类型示例
class GameEvent:
    event_type: str          # "player_speaks", "nomination", "vote", "death", "night_action"
    timestamp: datetime
    phase: GamePhase
    round_number: int
    actor: Optional[str]     # 事件发起者（None表示系统事件）
    target: Optional[str]    # 事件目标
    payload: Dict            # 事件详细数据
    visibility: Visibility   # PUBLIC / TEAM_EVIL / PRIVATE / STORYTELLER_ONLY
```

**可见性控制**是社交推理游戏的关键——不同角色能看到不同的信息：

| 可见性级别 | 谁能看到 | 示例 |
|-----------|---------|------|
| `PUBLIC` | 所有人 | 白天发言、投票结果、死亡公告 |
| `TEAM_EVIL` | 邪恶阵营 | 恶魔和爪牙互相知道身份 |
| `PRIVATE` | 仅个人 | 夜晚获得的角色信息 |
| `STORYTELLER_ONLY` | 仅说书人 | 魔典（Grimoire）全局真实信息 |

---

### 3.4 状态管理层 (State Store)

#### 3.4.1 游戏状态结构

```python
@dataclass
class GameState:
    """游戏全局状态 — 不可变快照"""

    # 基础信息
    game_id: str
    script: Script              # 使用的剧本（角色集合）
    phase: GamePhase
    round_number: int

    # 玩家信息
    players: Dict[str, PlayerState]   # {player_name: state}
    seat_order: List[str]             # 座位顺序（环形）

    # 夜晚信息 (仅说书人可见)
    grimoire: Grimoire                # 魔典：所有角色的真实信息

    # 事件历史
    event_log: List[GameEvent]        # 完整事件日志
    chat_history: List[ChatMessage]   # 对话记录

@dataclass
class PlayerState:
    name: str
    role: Role
    alignment: Alignment        # GOOD / EVIL
    is_alive: bool
    is_poisoned: bool           # 是否中毒（影响能力）
    has_used_dead_vote: bool    # 死亡后是否已使用最后一票
    statuses: List[Status]      # 特殊状态标记
```

#### 3.4.2 状态快照与回放

游戏状态采用**不可变快照 (Immutable Snapshot)** 模式：

- 每次状态变更都生成新的快照并存入历史
- 支持游戏回放和"时间旅行调试"
- 前端可以逐步回放整局游戏进程

---

### 3.5 LLM适配层 (LLM Backend)

#### 3.5.1 统一接口

```python
class LLMBackend(ABC):
    """LLM后端统一抽象接口"""

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        messages: List[Message],
        tools: Optional[List[ToolDef]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        ...

class OpenAIBackend(LLMBackend): ...
class AnthropicBackend(LLMBackend): ...
class GeminiBackend(LLMBackend): ...
class LocalModelBackend(LLMBackend): ...
```

#### 3.5.2 模型路由策略

不同任务使用不同级别的模型，优化成本与效果：

| 任务类型 | 推荐模型级别 | 原因 |
|---------|------------|------|
| 夜晚行动选择 | 轻量模型 | 决策空间小，格式化输出 |
| 白天公开发言 | 高级模型 | 需要自然语言生成、说服力 |
| 推理分析（内心独白） | 高级模型 | 逻辑推理、信息整合 |
| 投票决策 | 中等模型 | 需要基于推理结果做选择 |

#### 3.5.3 结构化输出 (Tool Calling)

Agent的行动通过**工具调用 (Tool Calling)** 而非自由文本解析，确保可靠性：

```python
# Agent可调用的工具定义示例
tools = [
    {
        "name": "speak",
        "description": "在白天讨论中发言",
        "parameters": {
            "content": "发言内容",
            "tone": "calm | passionate | accusatory | defensive",
            "target_player": "（可选）主要针对的玩家"
        }
    },
    {
        "name": "nominate",
        "description": "提名一位玩家进行处决投票",
        "parameters": {
            "nominee": "被提名的玩家名",
            "reason": "提名理由"
        }
    },
    {
        "name": "vote",
        "description": "对当前提名进行投票",
        "parameters": {
            "decision": "yes | no",
            "reasoning": "投票理由（内部）"
        }
    },
    {
        "name": "night_action",
        "description": "执行夜晚能力",
        "parameters": {
            "target": "能力目标玩家",
            "ability_id": "使用的能力ID"
        }
    }
]
```

---

### 3.6 前端展示层 (Frontend)

#### 3.6.1 界面组成

```
┌──────────────────────────────────────────────────────────┐
│                       鸦木布拉夫小镇                       │
├────────────────────────┬─────────────────────────────────┤
│                        │                                 │
│       🪑 座位圈        │        💬 对话面板               │
│                        │                                 │
│    [玩家1] [玩家2]     │    玩家A: "我是洗衣妇..."       │
│  [玩家8]      [玩家3]  │    玩家B: "你在说谎！"           │
│  [玩家7]      [玩家4]  │    玩家C: "等等，让我想想..."    │
│    [玩家6] [玩家5]     │    ...                          │
│                        │                                 │
│  存活状态 / 角色标记    │    [📝 输入框 - 人类玩家发言]    │
│                        │                                 │
├────────────────────────┼─────────────────────────────────┤
│   📊 游戏状态面板       │    🎭 个人面板（人类玩家视角）    │
│                        │                                 │
│  当前阶段: 白天讨论     │    你的角色: 共情者              │
│  存活人数: 8/12        │    夜晚信息: 你的两位邻居中...    │
│  当前轮次: 第2天       │    笔记本: [自由记录]            │
│  最近事件: ...         │                                 │
└────────────────────────┴─────────────────────────────────┘
```

#### 3.6.2 说书人控制台（管理员视角）

说书人拥有**上帝视角**，可以看到魔典 (Grimoire)：

- 查看所有角色的真实身份
- 手动触发特定游戏事件（如中毒、醉酒）
- 控制游戏节奏（暂停/继续/跳过）
- 监控所有Agent的内部推理过程
- 干预Agent行为（当AI做出不合理行为时）

---

## 4. 关键设计决策

### 4.1 Agent间的信息隔离

> [!CAUTION]
> 这是系统设计中最关键的一点。在社交推理游戏中，信息不对称是游戏性的本质。

**原则**：每个Agent只能通过编排层获取其**应当知道**的信息。

```python
class InformationBroker:
    """信息代理 — 控制每个Agent能看到什么"""

    def get_observation(
        self,
        agent_id: str,
        game_state: GameState,
    ) -> Observation:
        """
        根据Agent的角色和阵营，过滤并构造
        该Agent视角下的观察信息。

        善良村民只能看到公开信息 + 自己的私密信息；
        恶魔则额外知道谁是爪牙。
        """
        ...
```

### 4.2 人类玩家集成

人类玩家通过一个**特殊的HumanAgent适配器**接入系统：

```python
class HumanAgent(BaseAgent):
    """人类玩家的Agent适配器"""

    async def decide_action(self, observation: Observation) -> Action:
        # 不调用LLM，而是：
        # 1. 将observation序列化后推送到前端WebSocket
        # 2. 等待人类玩家通过UI输入操作
        # 3. 将输入反序列化为Action返回
        action = await self.websocket.wait_for_human_input(timeout=300)
        return action
```

从编排层的角度看，HumanAgent和AI Agent的接口**完全一致**，实现了人机无缝混合。

### 4.3 说书人模式

系统支持两种说书人模式：

| 模式 | 说书人 | 适用场景 |
|------|-------|---------|
| **AI说书人** | 由系统自动执行（规则确定性引擎） | 快速自动对局、AI评测 |
| **人类说书人** | 由管理员通过控制台操作 | 沉浸式体验、特殊情境处理 |

> [!IMPORTANT]
> 在血染钟楼中，说书人并非纯粹的规则执行者——很多能力的效果有说书人自由裁量的空间（如给醉酒玩家假信息的选择），因此人类说书人模式下需要提供足够的控制接口。

### 4.4 Prompt工程策略

每个Agent的System Prompt由以下模板层层组合：

```
1. 基础层：你是鸦木布拉夫小镇的一位居民…（世界观设定）
2. 人格层：你的名字是{name}，你{persona_description}…
3. 角色层：你的角色是{role}，你的能力是{ability}…
4. 阵营层：你属于{team}阵营，你的目标是{objective}…
5. 策略层：在当前局势下，你应注意{strategic_guidance}…
6. 输出层：请以JSON格式通过工具调用来执行行动…
```

---

## 5. 技术栈选型

| 层次 | 技术选型 | 理由 |
|------|---------|------|
| **语言** | Python 3.11+ | AI/LLM生态最成熟 |
| **Agent框架** | 自研 + LangChain(可选) | 自研核心逻辑，LangChain用于LLM调用 |
| **异步运行时** | asyncio | 多Agent并发交互 |
| **状态管理** | Pydantic + 不可变数据模型 | 类型安全、便于序列化和快照 |
| **事件系统** | 自研发布/订阅 | 轻量级，贴合游戏场景 |
| **前端** | Web (HTML/CSS/JS) + WebSocket | 实时交互、跨平台 |
| **数据持久化** | SQLite / JSON文件 | 游戏记录和Agent记忆存储 |
| **配置管理** | YAML + Pydantic Settings | 角色数据和系统配置 |
| **测试** | pytest + 模拟LLM调用 | 自动化测试流程 |
| **日志** | structlog | 结构化日志便于调试Agent行为 |

---

## 6. 目录结构

```
鸦木布拉夫小镇/
│
├── README.md                    # 项目说明
├── architecture.md              # 本文档 — 架构设计
├── pyproject.toml               # 项目配置与依赖
│
├── config/                      # 配置文件
│   ├── game_config.yaml         # 游戏默认配置
│   ├── scripts/                 # 血染钟楼剧本定义
│   │   ├── trouble_brewing.yaml #   惹事生非（入门剧本）
│   │   ├── bad_moon_rising.yaml #   黯月升起
│   │   └── sects_and_violets.yaml # 教派与紫罗兰
│   └── personas/                # Agent人格配置
│       ├── default_personas.yaml
│       └── custom_personas.yaml
│
├── src/                         # 源代码
│   ├── __init__.py
│   │
│   ├── engine/                  # 🎲 游戏引擎
│   │   ├── __init__.py
│   │   ├── game_engine.py       # 游戏引擎主入口
│   │   ├── phase_manager.py     # 阶段状态机
│   │   ├── rule_engine.py       # 规则校验
│   │   ├── victory_checker.py   # 胜负判定
│   │   ├── nomination.py        # 提名投票
│   │   └── roles/               # 角色技能实现
│   │       ├── __init__.py
│   │       ├── base_role.py     # 角色基类
│   │       ├── townsfolk.py     # 村民角色
│   │       ├── outsiders.py     # 外来者角色
│   │       ├── minions.py       # 爪牙角色
│   │       └── demons.py        # 恶魔角色
│   │
│   ├── agents/                  # 🤖 Agent层
│   │   ├── __init__.py
│   │   ├── base_agent.py        # Agent基类/接口
│   │   ├── ai_agent.py          # AI Agent实现
│   │   ├── human_agent.py       # 人类玩家适配器
│   │   ├── agent_factory.py     # Agent工厂
│   │   ├── memory/              # 记忆系统
│   │   │   ├── __init__.py
│   │   │   ├── working_memory.py
│   │   │   ├── episodic_memory.py
│   │   │   └── social_graph.py  # 社交信任图谱
│   │   ├── reasoning/           # 推理模块
│   │   │   ├── __init__.py
│   │   │   ├── deduction.py     # 推理引擎
│   │   │   └── strategy.py      # 策略规划
│   │   └── dialogue/            # 对话模块
│   │       ├── __init__.py
│   │       ├── dialogue_manager.py
│   │       └── persuasion.py    # 说服/欺骗策略
│   │
│   ├── orchestrator/            # 🎯 编排层
│   │   ├── __init__.py
│   │   ├── game_orchestrator.py # 游戏编排器（主循环）
│   │   ├── turn_scheduler.py    # 回合/发言调度
│   │   ├── event_bus.py         # 事件总线
│   │   └── info_broker.py       # 信息代理（可见性控制）
│   │
│   ├── state/                   # 📋 状态管理
│   │   ├── __init__.py
│   │   ├── game_state.py        # 游戏状态数据模型
│   │   ├── player_state.py      # 玩家状态
│   │   ├── event_log.py         # 事件日志
│   │   └── snapshot.py          # 快照与回放
│   │
│   ├── llm/                     # 🧠 LLM适配层
│   │   ├── __init__.py
│   │   ├── base_backend.py      # LLM后端接口
│   │   ├── openai_backend.py
│   │   ├── anthropic_backend.py
│   │   ├── gemini_backend.py
│   │   ├── local_backend.py
│   │   └── model_router.py      # 模型路由策略
│   │
│   └── api/                     # 🌐 前端API
│       ├── __init__.py
│       ├── server.py            # Web服务器
│       ├── websocket_handler.py # WebSocket处理
│       └── routes.py            # REST API路由
│
├── frontend/                    # 🎨 前端
│   ├── index.html
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── app.js               # 主应用逻辑
│       ├── game_board.js        # 游戏面板
│       ├── chat_panel.js        # 对话面板
│       └── storyteller.js       # 说书人控制台
│
├── tests/                       # 测试
│   ├── test_engine/
│   ├── test_agents/
│   ├── test_orchestrator/
│   └── test_integration/
│
└── scripts/                     # 工具脚本
    ├── run_game.py              # 启动一局游戏
    ├── replay_game.py           # 回放游戏记录
    └── benchmark.py             # Agent能力评测
```

---

## 7. 开发路线图

### Phase 0: 基础框架搭建 🏗️
- [ ] 项目初始化（pyproject.toml、基本目录结构）
- [ ] 核心数据模型定义（GameState、PlayerState、GameEvent）
- [ ] 事件总线实现
- [ ] LLM后端抽象接口 + 至少一个实现

### Phase 1: 游戏引擎 MVP 🎲
- [ ] 阶段状态机
- [ ] 基本规则引擎（行动验证、合法行动查询）
- [ ] 提名投票系统
- [ ] 胜负判定
- [ ] 实现 3-5 个基础角色（惹事生非剧本核心角色）

### Phase 2: Agent智能体 🤖
- [ ] Agent基类与AI Agent框架
- [ ] 记忆系统（工作记忆 + 短期记忆）
- [ ] 基础推理能力（阵营推理、信任度更新）
- [ ] 对话生成（发言、论证、质疑）
- [ ] 工具调用集成

### Phase 3: 编排层与完整游戏循环 🎯
- [ ] 游戏编排器主循环
- [ ] 信息代理（可见性控制）
- [ ] 回合/发言调度
- [ ] 完整的"第一夜→白天→夜晚"循环
- [ ] 纯AI对局测试

### Phase 4: 人机交互 👥
- [ ] HumanAgent适配器
- [ ] Web前端 + WebSocket通信
- [ ] 人类玩家视角渲染
- [ ] 说书人控制台

### Phase 5: 优化与扩展 ✨
- [ ] 社交信任图谱
- [ ] 高级推理（信息交叉验证、长期策略规划）
- [ ] Agent人格多样化
- [ ] 游戏回放系统
- [ ] 性能优化（模型路由、缓存）
- [ ] 更多角色和剧本支持

---

## 8. 设计原则总结

| 原则 | 说明 |
|------|------|
| **信息隔离第一** | Agent绝不能获取超出其角色权限的信息 |
| **数据驱动** | 角色、剧本、人格全部通过配置文件定义 |
| **接口统一** | 人类玩家和AI Agent对编排层而言无差别 |
| **状态不可变** | 每次状态变更生成新快照，便于调试和回放 |
| **异步优先** | 多Agent的感知-推理-行动本质上是并发的 |
| **可观测性** | 结构化日志 + 事件总线，可追溯每个决策 |
| **渐进式复杂度** | 从最小可玩版本出发，逐步增加Agent智能 |

---

## 9. 参考资料

- [ChatArena](https://github.com/chatarena/chatarena) — 多Agent LLM对话框架
- [Werewolf Arena (Google)](https://github.com/google/werewolf_arena) — LLM社交推理评测框架
- [Avalon-LLM](https://github.com/jonathanmli/Avalon-LLM) — 阿瓦隆LLM Agent基准测试
- [Blood on the Clocktower 官方规则](https://bloodontheclocktower.com)
- [OpenSpiel (DeepMind)](https://github.com/google-deepmind/open_spiel) — 博弈论游戏框架
- [LangGraph](https://github.com/langchain-ai/langgraph) — 状态化多Agent编排
