# Alpha 0.3 重制开发总计划

## 1. 版本定位

`alpha 0.3` 的目标不是继续扩大技术宣传口径，而是基于当前仓库的真实完成度，把以下三条主线做成可验证、可复盘、可迭代的工程闭环：

- `A3-MEM`：AI 记忆优化
- `A3-DATA`：历史数据保存与训练资产
- `A3-ST`：AI 说书人优化
- `A3-ACC`：验收、评估与发布门禁

本版本遵循的第一性原理是：

1. 先保证信息**不被错记**
2. 再保证高可信信息**不被噪声冲掉**
3. 再保证重要信息**可持久化、可检索、可复盘**
4. 最后让 AI 说书人基于可靠状态**做出更好裁定**

---

## 2. A3-MEM：AI 记忆优化

### 目标

先解决：

- 记错
- 串错
- 高可信信息被公开噪声冲掉
- 跨天后忘记角色信息、跳身份与关键私密结果

再继续增强：

- 推理稳定性
- 发言一致性
- 提名与投票判断质量

### A3-MEM-1：记忆语义正确性

统一把身份相关发言解析成结构化 statement 事件，至少包含：

- `speaker_id`
- `subject_player_ids`
- `claim_type`
- `role_id`
- `day_number`
- `round_number`
- `source_text`
- `confidence`

必须做到：

- 否认不会被记成自报身份
- 质问不会被记成自报身份
- 转述不会被记成自报身份
- “我跳调查员并点名别人”不会把被点名玩家记成调查员

`social_graph` 统一升级为：

- `claim_history`
- `current_self_claim`
- `claims_about_others`
- `claim_conflicts`

### A3-MEM-2：三层记忆制度化

正式将记忆分为三层：

#### OBJECTIVE

绝对客观事实，默认百分百可信：

- 邪恶队友
- bluffs
- spy book
- 提名事件
- 投票结果
- 死亡事件
- 处决结果

#### HIGH_CONFIDENCE

高可信但可能受规则扰动影响的信息：

- 角色私密信息
- 夜晚结果
- 守鸦人 / 送葬者 / 占卜师 / 调查员 / 图书馆员 / 洗衣妇 / 共情者 / 厨师等结果

#### PUBLIC

公开发言与讨论信息：

- 跳身份
- 指认
- 质疑
- 转述
- 公开讨论

所有记忆写入都必须带：

- `tier`
- `category`
- `day_number`
- `round_number`
- `source`
- 能绑定到玩家时带 `target_player_ids`

### A3-MEM-3：记忆进入推理与发言

必须把分层记忆真正接进：

- `_target_signal_score()`
- 发言上下文
- 提名理由
- 投票理由

规则：

- `OBJECTIVE` 与 `HIGH_CONFIDENCE` 优先于 `PUBLIC`
- 当公开信息与高可信信息冲突时，默认高可信优先
- 一致的公开声明可以降低疑点
- 冲突的公开声明可以提高疑点

需要补齐“可绑定到具体玩家”的高可信线索角色：

- 占卜师
- 送葬者
- 守鸦人
- 洗衣妇
- 图书馆员
- 调查员

数值型信息单独处理：

- 厨师
- 共情者

它们进入高可信数值线索，不强行绑定具体玩家，但必须进入推理摘要和发言上下文。

---

## 3. A3-DATA：历史数据保存与训练资产

### 目标

把当前零散的：

- JSONL
- game records
- storyteller samples

收成可复盘、可训练、可评估的数据资产。

### A3-DATA-1：数据模型统一

统一两类数据：

#### 对局历史资产

由 `GameRecordStore` 负责，至少包含：

- 结算
- 时间线
- 玩家身份
- 事件流
- 提名 / 投票 / 死亡原因

#### AI 行为资产

由 `GameDataCollector` 负责，至少包含：

- thought trace
- memory snapshots
- social graph snapshots
- retrieval hits

同时明确区分：

- 发布面向的对局历史
- 训练面向的 AI 行为日志

### A3-DATA-2：Collector 闭环补全

补齐 `GameDataCollector.record_snapshot(...)` 的主线调用点。

固定快照时机：

- 首夜后
- 每个白天讨论后
- 提名前
- 投票后
- 结算后

每个快照最少包含：

- `phase`
- `day_number`
- `round_number`
- `visible_state_summary`
- `working_memory_summary`
- `social_graph_summary`
- `claim_history_summary`
- `retrieval_summary`

### A3-DATA-3：向量记忆闭环改正

目标不是宣传 RAG，而是先让 `VectorMemory` 真正可信。

必须完成：

- 修复 `add_message()` 与 `ChatMessage` 字段不一致问题
- 明确摄入来源：
  - 公开聊天进 `add_message`
  - 游戏事件进 `add_event`
  - 阶段总结进 `add_text`
- 在 `AIAgent.observe_event()` 和聊天处理链中补齐摄入
- 若 backend 不支持 embeddings，显式降级并记录 `vector_memory_disabled`
- 不允许把空索引 search 宣称为“RAG 已可用”

### A3-DATA-4：历史与训练数据出口

补齐最小统一导出链：

- `export_game_history`
- `export_ai_traces`
- `export_storyteller_judgements`

要求：

- 训练日志目录结构规范化
- 对局历史与训练日志通过 `game_id` 关联
- 说书人 judgement 与对局复盘共享同一标识

---

## 4. A3-ST：AI 说书人智能增强 (Intelligence Upgrade)

### 目标

让 AI 说书人从单纯的“规则执行者”进化为具备“导演思维”的游戏管理者，能够基于全局真相（Truth View）做出最有利于博弈精彩度与平衡性的决策。

### 核心任务清单

#### ST-1：上下文感知与 ST-Brain 架构
- **真实现状感知**：构建 `_build_st_brain_context()`，集成全局身份、投毒状态、玩家怀疑度及平衡性评分。
- **LLM 异步决策链**：在 `StorytellerAgent` 中引入 `act_as_director()` 异步方法，支持复杂逻辑裁量。

#### ST-2：智能信息伪造与平衡干预
- **智能扭曲 (Strategic Distortion)**：中毒/醉酒玩家的信息不再随机，而是由 AI 根据场上伪装情况，构造最具误导性且逻辑自洽的假信息。
- **平衡性介入**：在间谍/隐士误报、市长裁定等弹性规则上，AI 倾向于向弱势方倾斜，延长博弈寿命。

#### ST-3：叙事感与氛围引导
- **动态报幕 (AI Narration)**：基于昨晚战况、存活人数及场上气氛，生成血染风格的阶段报幕。
- **裁量过程可审计**：将 AI 的思考过程（Thought）与逻辑（Reasoning）全量计入 Judgement Ledger。

#### ST-4：说书人历史与复盘联动
- **对局轨迹导出**：将说书人的所有“幕后操作”与对局历史（game_id）绑定，支持在复盘页面查看“说书人为什么要这么做”。

---

## 5. A3-ACC：验收、评估与发布门禁

`alpha 0.3` 不允许只靠“代码看起来像做了”，必须同步建立门禁。

### Memory

- 身份否认不会被误记成自报
- “我跳调查员并点名别人”不会把别人记成调查员
- 高可信私密信息跨阶段归档后仍存在
- 高可信与公开声明冲突时，怀疑分变化符合预期
- 邪恶队友信息会稳定降低对己方的怀疑

### Data

- `GameDataCollector` 在一局内生成可读 JSONL
- 至少一个阶段快照被稳定写入
- `VectorMemory` 实际能摄入事件 / 聊天，并返回非空检索结果
- `add_message()` 与当前 `ChatMessage` 模型字段一致
- `GameRecordStore` 与训练日志能通过 `game_id` 对齐

### Storyteller

- 关键 judgement 分类稳定写入 ledger
- curated / full-game sample export 通过
- acceptance 不再只检查“导出成功”，还要检查样本覆盖率与 fallback 率
- 说书人历史详情能读取结算摘要与关键裁量摘要

---

## 6. 默认假设

- `alpha 0.3` 继续沿用当前 `docs/alpha-0.3-plan` 目录，不另起新版本目录结构。
- 当前阶段不引入 PostgreSQL，继续使用 SQLite + JSONL + sample exports，避免新基础设施分散重点。
- RAG 只作为辅助检索能力推进，不作为发布卖点，直到摄入闭环和降级逻辑都完成。
- 说书人优化优先做“可解释、可复盘、可验收”，不先追求更强自由裁量。
- 所有发布口径默认使用保守状态：
  - `Implemented`
  - `Partial`
  - `Planned`

不再使用：

- `零遗忘`
- `无限天数`
- `完全闭环`

这类绝对表述。

---

## 7. A3-GAME：游戏逻辑与交互体验 (补完)

### A3-GAME-1：规则确定性保证
- **夜晚行动顺序**：严格遵循“死亡即停止”原则，但 `ON_DEATH` 触发器（如守鸦人）除外。
- **存活状态实时性**：所有动作执行前必须进行二次存活检查，防止当晚先行死亡的玩家产生非法动作。

### A3-GAME-2：特殊技能全链路
- **猎手（Slayer）**：支持白天（讨论/提名）阶段的主动触发，具备前端专用 UI 唤起、二次确认及后端原子化执行。

### A3-GAME-3：邪恶阵营战术智能
- **防御感应**：恶魔 AI 应能通过社交图谱感知僧侣/士兵的潜在威胁。
- **反馈闭环**：通过夜晚行动结果（哑刀）反向修正刀人策略。
- **高级战术**：支持自刀传位（Imp Star-pass）等高阶博弈。

---

## 8. 下一阶段开发计划（2026-04-22 基线）

基于当前仓库完成度，下一阶段不再平均推进全部分支，而是按“先收数据闭环，再收记忆利用，再收说书人复盘”的顺序推进。

### Stage 1：A3-DATA 收口

目标：

- 让 `alpha 0.3` 的数据资产真正可导出、可对齐、可复盘

优先事项：

- 为 `GameDataCollector` 增加统一导出接口：
  - `export_game_history`
  - `export_ai_traces`
  - `export_storyteller_judgements`
- 用统一的 `game_id` 关联：
  - 对局历史
  - AI thought traces
  - data snapshots
  - storyteller judgements
- 为向量记忆增加最小统计：
  - 摄入条数
  - 检索命中数
  - embedding 禁用状态

阶段完成标准：

- 至少能导出一局完整对局的：
  - 历史摘要
  - AI trace
  - storyteller judgement 摘要
- 数据之间能通过 `game_id` 串起来

### Stage 2：A3-MEM 收口

目标：

- 让高可信 / 绝对可信信息不只是“被记住”，而是更稳定地进入发言、提名和投票理由

优先事项：

- 高可信线索进入发言上下文
- 高可信 vs 公开声明冲突时的理由模板
- 增加多轮、跨天一致性回归：
  - 昨天跳身份
  - 今天否认
  - 夜里拿到私密结果
  - 第二天仍能稳定引用

阶段完成标准：

- AI 发言能更明确地引用高可信私密信息
- 至少有一组跨天回归验证：
  - 公开噪声不会覆盖高可信信息

### Stage 3：A3-ST 收口

目标：

- 让说书人优化建立在稳定的输入、规范化 ledger 和历史联动上

优先事项：

- 统一 `StorytellerDecisionContext`
- judgement ledger 字段规范化
- 历史详情中可查看关键裁量摘要

阶段完成标准：

- 说书人历史详情能读取关键裁量摘要
- judgement ledger 字段稳定、可用于后续导出和分析

### Stage 4：A3-ACC 聚合验收

目标：

- 形成 `alpha 0.3` 的最小统一门禁，而不是只靠零散专项测试

优先事项：

- 增加统一 acceptance 脚本
- 汇总：
  - 记忆正确性
  - 数据快照与导出
  - 说书人 ledger / sample / history 联动

阶段完成标准：

- `alpha 0.3` 至少具备一条最小聚合验收入口

当前进展（2026-04-23）：

- 已落地：
  - `scripts/a3_data_acceptance.py`
  - `scripts/a3_memory_acceptance.py`
  - `scripts/storyteller_acceptance.py`
  - `scripts/alpha3_acceptance.py`
- 已继续增强：
  - `a3_memory_acceptance.py` 已串联 `long_loop_memory_acceptance.py` 与 `long_game_ai_acceptance.py`
- 下一步应继续增强：
  - 更完整的 storyteller sample coverage 门槛
  - 前端 / 真人验收联动

---

## 9. 当前文档改进说明

当前 `alpha 0.3` 文档体系已经比 Gemini 原版更真实，但仍需保持这几点：

1. `execution_summary.md` 必须继续只写“当前真实状态”
2. `gemini_audit.md` 保持“审计时结论”，不把后续实现混进去
3. `task_st_ai.md` 不再把“更强 LLM 导演能力”放在第一优先级
4. 所有新增子任务文档都要明确：
   - 当前阶段
   - 下一阶段
   - 完成标准
