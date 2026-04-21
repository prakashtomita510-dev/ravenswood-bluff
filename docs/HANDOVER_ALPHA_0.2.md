# Alpha 0.2 AI 智能重构移交文档 (Handover Document)

**版本日期**：2026-04-13
**涵盖范围**：Wave 2-B 至 Wave 3-D
**核心目标**：实现 AI 玩家从机械规则执行者到“拟人化社交推理体”的进化。

---

## 1. 核心架构升级 (Core Architecture)

### 1.1 玩家视角硬隔离 (Information Privacy)
- **机制**：当前通过 `BaseAgent.synchronize_role` 仅下发可见字段，并且 `BaseAgent.act / observe_event / think / archive_phase_memory` 都已经改为接收：
  - `AgentVisibleState`
  - `AgentActionLegalContext`
- **自认身份**：Agent 主要基于 `perceived_role_id` 进行推理。即使是酒鬼，在被告知真相前也会倾向于把自己当作认知身份来看待。
- **关键逻辑**：`GameOrchestrator` 与 `InformationBroker` 负责构造玩家视角对象，AI 主决策链不再直接以完整 `GameState` 作为接口输入。

### 1.2 顺序投票流程 (Sequential Voting)
- **机制**：投票逻辑已经接入顺序处理（按座位号），但仍需继续核对状态初始化与边界条件。
- **社交压力**：后序玩家可以感知当前的累计票数，从而触发“临门一脚”或“保下这一票（亡魂保护）”的逻辑。
- **文件参考**：`src/orchestrator/game_loop.py` 中的 `_run_defense_and_voting`。

---

## 2. AI 内存与认知系统 (Memory & Cognition)

### 2.1 三层记忆架构 (Hierarchical Memory)
AI 不再只是简单的 Token 堆栈，而是已经具备观察层、印象层和情节层的结构雏形：
1.  **观察层 (Raw Observations)**：存储最近的 12-15 条原始日志/对话。
2.  **印象层 (Impressions)**：通过 `_reflect()` 提炼的局势定性认知（由 LLM 总结，存放在 `WorkingMemory.impressions`）。
3.  **情节层 (Episodic Memory)**：跨越天数的核心情节摘要，但目前仍需继续补齐主流程写入。

### 2.2 自动反思与蒸馏 (`_reflect`)
- **逻辑**：当 `WorkingMemory` 的观察记录超过阈值（30条）时，会触发轻量反思与压缩，生成“印象总结”并清空部分原始记录，降低 Token 损耗。

---

## 3. 人格与偏置系统 (Persona & Biases)

### 3.1 原型注册表 (Archetype Registry)
引入了 `Archetype` (类定义在 `src/agents/persona_registry.py`)。
- **Logic (逻辑型)**：依赖 `thinking_template`，高门槛提名。
- **Aggressive (强势型)**：低门槛提名，倾向于压迫式发言。
- **Cooperative (随大流型)**：受群体压力（momentum）影响极大。
- **Chaos (搅局者)**：决策随机性高。

### 3.2 动态门槛偏置
- **提名与投票**：`_nomination_threshold` 和 `_vote_threshold` 会根据人格原型进行正负加减。
- **亡魂保护**：死亡玩家在仅剩一票时，其投票门槛会自动提升（+0.15），优先保留至 Deciding Vote。

---

## 4. 关键模块图谱 (Module Index)

- `src/agents/ai_agent.py`: 核心推理大脑。
- `src/agents/persona_registry.py`: 人格偏置数据源。
- `src/agents/memory/working_memory.py`: 分层记忆管理器（Raw vs Impression）。
- `src/orchestrator/game_loop.py`: 驱动顺序投票的总控逻辑。
- `src/engine/nomination.py`: 处理票数决算与 `ghost_votes` 扣除。

---

## 5. 现状与建议 (Next Steps)

### 当前已解决 (Resolved)
- ✅ 已把 AI 视角隔离从 prompt 侧过滤推进到接口级玩家视角对象。
- ✅ 实现了初步的、具备人格差异的提名与投票。
- ✅ 建立了印象层与压缩机制，情节层仍需继续打通主流程写入。

### 待后续处理 (Pending)
1. **Wave 4: 社交发言增强**：目前的发言仍偏向描述事实，需要增加针对他人矛盾点的“攻击性/逻辑质询”模板。
2. **进阶欺骗策略**：邪恶阵营需要具备“跨回合身份铺垫”的能力（例如：第一天预埋我是占卜师，第二天根据局势反跳）。
3. **前端思考展示**：将 `WorkingMemory` 中的 `impressions` 展示在 UI 上，增强可观赏性。

---

*致接手的 AI 同志：请务必阅读 `scripts/persona_divergence_test.py` 以理解不同人格下 AI 的逻辑分歧点。*
