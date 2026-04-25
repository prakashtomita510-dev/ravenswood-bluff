# Mission: A3-DATA 历史数据保存与训练资产任务板

## 当前定位

- **当前阶段**: `Hardened & Verified`
- **目标**: 把对局记录、AI 思维链、说书人判决收成可复盘、可训练、可评估的数据资产。
- **关联文档**:
  - [full_plan.md](D:/鸦木布拉夫小镇/docs/alpha-0.3-plan/full_plan.md) §3
  - [execution_summary.md](D:/鸦木布拉夫小镇/docs/alpha-0.3-plan/execution_summary.md)

---

## 状态总览

| 子任务 | 状态 | 说明 |
| :--- | :--- | :--- |
| DATA-1：数据模型统一 | `Done` | `GameRecordStore` (SQLite) 与 `GameDataCollector` (JSONL) 职责已明确 |
| DATA-2：Collector 闭环补全 | `Done` | 关键快照时机已在 `game_loop.py` 中补全 |
| DATA-3：向量记忆闭环改正 | `Done` | 摄入来源区分、空索引处理、降级逻辑、字段对齐已钉实 |
| DATA-4：历史与训练数据出口 | `Done` | 导出接口与 `export_game_assets.py` 聚合导出脚本已就绪 |

---

## DATA-1：数据模型统一

- [x] `GameRecordStore` 负责发布面向的对局历史（结算、玩家列表、事件流）
- [x] `GameDataCollector` 负责训练面向的 AI 行为日志（思维链、记忆快照、社交图谱快照）
- [x] 统一使用 `game_id` 作为所有资产的关联键

## DATA-2：Collector 闭环补全

- [x] 在 `game_loop.py` 中补齐关键快照调用点：
  - [x] 首夜后 (`first_night_complete`)
  - [x] 白天讨论后 (`day_discussion_complete`)
  - [x] 提名前 (`before_nomination`)
  - [x] 投票后 (`voting_resolved`)
  - [x] 结算后 (`after_execution`)
- [x] **DATA-1: GameRecordStore 鲁棒性强化** (已完成)
- [x] **DATA-2: AI 行为轨迹捕获 (Behavioral Traces)** (已完成)
- [x] **DATA-3: 向量记忆结构对齐** (已完成)
- [x] **DATA-4: 资产导出流水线** (已完成)

### 2. 验收状态 (Hardened & Verified)
- **状态**: ✅ 已完成 (2026-04-23)
- **验收工具**: `scripts/a3_data_acceptance.py`
- **结果**: 所有数据收集点（5个关键环节）均已正确埋点，向量记忆 Schema 已对齐，导出脚本可正常生成 JSONL 资产。
- **最终审计**: 已通过所有 A3-DATA 单元测试和集成测试，无遗留漏洞。
- [x] 快照包含 `visible_state` / `working_memory` / `social_graph` 摘要

## DATA-3：向量记忆闭环改正

- [x] 摄入来源区分：
  - [x] 公开聊天 -> `add_message`
  - [x] 游戏事件 -> `add_event`
- [x] 空索引 `search` 返回空列表而非虚报
- [x] Backend 不支持 embedding 时，显式降级为 `degraded` 状态并记录原因
- [x] 修复 `add_message` 字段校验问题

## DATA-4：历史与训练数据出口

- [x] `GameRecordStore.export_game_history(game_id)`
- [x] `GameDataCollector.export_ai_traces(game_id)`
- [x] `GameRecordStore.export_storyteller_judgements(game_id, storyteller_agent)`
- [x] **[DONE]** 增加 `scripts/export_all_assets.py`：一键导出指定 game_id 的所有关联资产

---

## 当前阻塞与风险

1. **磁盘占用**: 随着 Snapshot 频率增加，JSONL 文件体积可能迅速膨胀，需关注 `data/sessions` 目录大小。
2. **数据关联**: 确保在多进程或分布式环境下 `game_id` 的唯一性与文件同步（目前本地环境无虞）。

---

## 变更记录

- **2026-04-23**: 审计发现 `A3-DATA-1` 到 `A3-DATA-3` 核心逻辑已在前期基线中基本落地。
- **2026-04-23**: 确认导出接口已具备，下一步重点在于自动化聚合与验收。
