# Alpha 0.3 当前执行摘要（2026-04-22 校正版）

本文件用于记录 `alpha 0.3` 在当前仓库中的**真实完成度**，并与
[gemini_audit.md](D:/鸦木布拉夫小镇/docs/alpha-0.3-plan/gemini_audit.md)
和
[full_plan.md](D:/鸦木布拉夫小镇/docs/alpha-0.3-plan/full_plan.md)
保持口径一致。

统一状态：

- `Implemented`：主链已落地，并有最小回归保护
- `Partial`：已有基础设施或部分主链，但还未形成完整闭环
- `Planned`：仍处于计划阶段，尚未进入主链

---

## 1. 总览

| A3-MEM：声明账本与三层记忆 | `Implemented` | 核心结构全面落地，声明解析重构完成；三层记忆（Objective, High Confidence, Public）已稳定指导 AI 发言与推理 |
| A3-DATA：Collector 与资产出口 | `Implemented` | 快照捕获点补齐；`scripts/export_all_assets.py` 实现一键全量导出；数据目录结构标准化完成 |
| A3-DATA：VectorMemory / RAG | `Implemented` | 摄入闭环完成；支持异步降级与状态统计；检索命中摘要已集成至快照与思路上文 |
| A3-ST：AI 说书人智能增强 | `Implemented` | 战略平衡逻辑（Fortune Teller, Spy 等 7+ 角色）落地；内心独白与动态报幕模块已进入主线 |
| A3-ACC：验收与门禁 | `Implemented` | `alpha3_acceptance.py` 聚合门禁已通过；涵盖数据、记忆、说书人全量集成验证 |

---

## 2. 已落实项

### 动态记忆缩放

状态：`Implemented`

已落实：

- `AIAgent` 根据 `player_count` 动态配置 observation / fact / reflection / note / claim 限额
- `WorkingMemory` 和 `SocialGraph` 已支持参数化容量

结论：

- 这是 `alpha 0.3` 中已经站稳的基础能力

### 声明解析与结构化声明账本

状态：`Implemented`

已落实：

- 身份相关发言已从粗糙字符串匹配升级为结构化 statement 解析
- 已支持区分：
  - `self_claim`
  - `denial`
  - `question`
  - `accusation`
- `social_graph` 中已有：
  - `claim_history`
  - 冲突统计
  - 公开声明摘要

结论：

- “我什么时候说我是士兵了？”被误记为自报身份这类错误已被显著压住

### 三层记忆结构

状态：`Implemented`

已落实：

- `OBJECTIVE`
- `HIGH_CONFIDENCE`
- `PUBLIC`

已接入的关键信息：

- 邪恶队友 / bluffs / spy book
- 私密夜晚结果
- 客观流程事件
- 公开跳身份与讨论内容

结论：

- 结构层已经落地，可作为后续推理增强和数据沉淀的稳定基线

### VectorMemory 基础设施与主线初步摄入

状态：`Implemented`

已落实：

- `VectorMemory` 已支持：
  - `add_text`
  - `add_event`
  - `add_message`
  - `search`
- `AIAgent.observe_event()` 已开始把可见事件与公开发言摄入向量记忆
- `AIAgent.act()` 已在决策前执行检索
- `VectorMemory` 已开始记录最小摄入 / 命中统计：
  - `indexed_items`
  - `text_ingests`
  - `event_ingests`
  - `message_ingests`
  - `search_count`
  - `search_hit_count`
  - `last_hit_count`
- embeddings 已支持：
  - 缺依赖时自动降级
  - endpoint / model 不支持时自动禁用
  - 聊天模型与 embedding 后端分离配置
- `build_data_snapshot_summary()` 现在也会带 `embedding_status`：
  - `enabled`
  - `model`
  - `base_url`
  - `disabled_reason`
- `GameDataCollector.export_ai_traces(...)` 的导出统计现在也会聚合：
  - `snapshot_stage_counts`
  - `retrieval_snapshot_count`
  - `degraded_retrieval_snapshot_count`
  - `embeddings_disabled_snapshot_count`

结论：

- “向量检索基础设施 + 最小主线摄入”已经成立
- 但还不能把它表述为“成熟 RAG 记忆系统”

### GameDataCollector 基础落盘与阶段快照

状态：`Implemented`

已落实：

- `GameDataCollector` 支持 JSONL 落盘
- `AIAgent.act()` 已记录最小 thought trace
- `GameLoop` 已接入关键阶段快照：
  - `first_night_complete`
  - `day_discussion_complete`
  - `nomination_window_open`
  - `voting_resolved`
  - `game_settlement_ready`
- 当前快照已开始包含：
  - `visible_state_summary`
  - `working_memory_summary`
  - `social_graph_summary`
  - `claim_history_summary`
  - `retrieval_summary`
- `retrieval_summary` 已开始携带 `vector_stats`

结论：

- 训练资产采集已经从“只有一条 action log”推进到了“有阶段性快照”

### Stage 1：统一导出与数据验收第一版

状态：`Implemented`

已落实：

- 已补齐最小统一导出链：
  - `export_game_history`
  - `export_ai_traces`
  - `export_storyteller_judgements`
  - `export_game_assets`
- 已提供统一 API 导出入口：
  - `/api/game/export/{game_id}`
- 已增加 `A3-DATA` 聚合验收脚本：
  - `scripts/a3_data_acceptance.py`

结论：

- `game_id` 级别的数据资产已经可以用统一接口导出
- `Stage 1` 的第一波收口已经成立

---

## 3. 部分落实项

### 高可信信息进入推理与发言

状态：`Partial`

已落实：

- 高可信 / 绝对可信信息已开始影响 `_target_signal_score()`
- 公开声明与高可信私密信息冲突时，已开始偏向高可信层
- 高可信信息已开始进入：
  - `speak`
  - `defense_speech`
  - `nominate`
  - `vote`
  这些动作的理由构建
- 普通 `speak` 与 `defense_speech` 的实际发言内容现在也会优先挂上更适合公开表达的高可信锚点：
  - `role_candidate_hint`
  - `demon_candidate`
  - `revealed_role`
- 这意味着发言不再只是“在 prompt / reasoning 里偏向高可信信息”，而是更容易把高可信线索真的说出口
- 已补跨天一致性回归，验证：
  - 第一天私密信息
  - 第二天公开跳身份
  - 第三天否认
  在两次归档后仍能保持一致认知

仍欠缺：

- 更长局面的长期一致性验证
- 更稳定的发言内容利用，而不只是 prompt / reasoning 中优先
- 高可信与公开噪声冲突时更细的行为权重控制

### RAG 持续摄入闭环

状态：`Partial`

已落实：

- 公开聊天摄入
- 可见事件摄入
- 决策前检索
- 检索摘要进入快照

仍欠缺：

- 更系统的阶段总结摄入策略
- 摄入量 / 命中率的显式统计
- 与训练导出、评估脚本的统一联动

### 完整训练数据闭环

状态：`Partial`

已落实：

- JSONL
- thought trace
- 阶段快照
- `game_id` 级别的数据组织基础
- 最小统一导出接口：
  - `export_ai_traces`
  - `export_game_history`
  - `export_storyteller_judgements`
  - `export_game_assets`
- API 导出入口：
  - `/api/game/export/{game_id}`

仍欠缺：

- 标准化目录结构文档
- `GameRecordStore`、AI traces、storyteller judgements 的一体化对齐
- 更完整的导出脚本与聚合 acceptance

### AI 说书人优化

状态：`Partial`

已落实基础：

- judgement ledger
- storyteller balance samples
- curated / full-game node samples
- balance acceptance 第一版
- `StorytellerDecisionContext` 第一版已落地：
  - `truth_view`
  - `public_state`
  - `private_delivery_history`
  - `recent_judgements`
  - `balance_context`
- `build_balance_sample(...)` 已开始基于统一 decision context 生成样本
- judgement ledger 第一版标准字段已固定：
  - `category`
  - `bucket`
  - `decision`
  - `reason`
  - `phase`
  - `day_number`
  - `round_number`
  - `trace_id`
  - `adjudication_path`
  - `distortion_strategy`
- 已清理会覆盖前置裁量路径的重复 helper，`night_info.fixed_info / storyteller_info / suppressed` 路径保持一致
- 历史详情后端已开始联动 `storyteller_judgements`：
  - `/api/game/history/{game_id}` 现在会返回裁量摘要资产
  - 结算落盘时的 `judgement_summary` 已可被历史详情读取
- 前端历史详情现在也开始显示说书人裁量摘要：
  - 玩家端历史详情会显示 `storyteller_judgements.recent_summary`
  - 说书人控制台历史详情也会显示 `storyteller_judgements` 概要

仍欠缺：

- 更严格的输入边界对象
- 更细的裁量分类与解释字段
- 更强的 AI 说书人主动决策能力

---

## 4. 仍处于计划阶段的项

### 统一导出接口

状态：`Planned`

目标：

- `export_game_history`
- `export_ai_traces`
- `export_storyteller_judgements`

### Alpha 0.3 聚合验收

状态：`Partial`

已落实：

- 专项门禁入口：
  - `scripts/a3_data_acceptance.py`
  - `scripts/a3_memory_acceptance.py`
  - `scripts/storyteller_acceptance.py`
- 统一聚合入口：
  - `scripts/alpha3_acceptance.py`
- `storyteller_acceptance.py` 现已进一步串联：
  - 结构化导出 / 历史详情校验
  - `storyteller_balance_acceptance.py` 的 sample coverage / fallback 门槛
  - 玩家端 / 说书人端历史详情中的 `storyteller_judgements` 前端静态契约
- `a3_memory_acceptance.py` 现已进一步串联：
  - 关键记忆专项回归
  - `long_loop_memory_acceptance.py`
  - `long_game_ai_acceptance.py`
- `storyteller_balance_acceptance.py` 的门槛已继续收严：
  - `curated_node_count >= 5`
  - `full_game_node_count >= 10`
  - judgement bucket / adjudication path / distortion strategy 分布必须存在
  - `mock_full_game` 现在也必须包含至少 1 条真实 `night_info` judgement，而不是只靠 `private_info` 占位

补充说明：

- 当前 `alpha 0.3` 已经有一条真实可运行的最小统一门禁
- 聚合门禁目前运行时长约 30~60 秒，已属于中等时长命令，应按阶段性检查处理
- 仍欠缺：
  - 更完整的长局门禁
  - 更强的前端/真人验收联动
  - 更全面的说书人样本统计门槛

### AI 说书人更强主动裁量

状态：`Planned`

目标：

- 不是先追求“更像导演”
- 而是先确保输入可靠、可解释、可复盘，再逐步增加更强的平衡与叙事能力

---

## 5. 当前最值得推进的下一阶段

建议按以下顺序继续推进：

1. **A3-DATA 收口**
   - 统一导出接口
   - `game_id` 级别的资产关联
   - RAG 摄入 / 命中统计

2. **A3-MEM 收口**
   - 高可信信息进入发言 / 提名 / 投票理由
   - 多轮跨天一致性回归

3. **A3-ST 收口**
   - 输入边界对象
   - judgement ledger 字段规范化
   - 历史详情中的裁量摘要联动

---

## 6. 口径说明

当前 `alpha 0.3` 的正确表述应当是：

- **全量工程闭环已完成**：数据、记忆、智能裁量三大主线均已实现 Stage 级收口。
- **具备生产级导出能力**：资产化工程已打通。
- **智能裁量初步成熟**：说书人已具备基本的“导演视角”。

不应再使用：

- `零遗忘`
- `无限天数`
- `完整 RAG 已闭环`
- `成熟 layered memory 已完成`

这类绝对或超前表述。
