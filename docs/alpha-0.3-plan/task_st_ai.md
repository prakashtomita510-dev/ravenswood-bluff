# Mission: A3-ST 说书人优化任务板

## 当前定位

- **当前阶段**: `Active Balancing & Acceptance`
- **目标**: 已完成输入收窄与 Ledger 规范化，当前正基于稳定 Context 增强主动平衡与氛围引导
- **关联文档**:
  - [full_plan.md](D:/鸦木布拉夫小镇/docs/alpha-0.3-plan/full_plan.md)
  - [execution_summary.md](D:/鸦木布拉夫小镇/docs/alpha-0.3-plan/execution_summary.md)

---

## 第一性原理

说书人优化不先追求“更会演”，而是按以下顺序推进：

1. **输入可靠** (Done)
2. **裁量可解释** (Done)
3. **结果可复盘** (Done)
4. **增强主动平衡与叙事** (In Progress)

---

## 状态看板

### ST-1：输入边界收紧

- [x] 定义 `StorytellerDecisionContext` 第一版
- [x] 统一最小输入字段
- [x] 迁移裁量逻辑到统一 context，引入 helper methods (get_player, is_evil 等)

### ST-2：Judgement Ledger 规范化

- [x] 为 judgement ledger 增加稳定字段 (category, bucket, decision, temporal fields)
- [x] 固定分类进入主线 bucket
- [x] 补齐所有 call sites 的 metadata (day_number, round_number, phase)

### ST-3：样本与复盘资产收口

- [x] `mock_full_game` 要求真实 `night_info judgement`
- [x] 收口 `curated samples` 与 `full-game node samples`
- [x] 为样本增加最低门槛统计 (coverage, fallback_rate, distortion_rate)

### ST-4：历史详情联动

- [x] 结算时保存 `judgement_summary`
- [x] 历史详情后端支持返回关键裁量摘要
- [x] 对局历史与 judgement 联动
- [x] 前端历史详情接入 `storyteller_judgements` 展示

### ST-5：更强主动裁量

- [x] 基于稳定上下文做更智能的扰动与平衡干预 (Empath/Chef/Washerwoman 等)
- [x] 增强阶段报幕与氛围引导 (动态 Flavor Text)

---

## 当前阻塞与风险

- **无明显阻塞**: ST-1 到 ST-5 的核心架构已打通。
- **后续优化方向**:
  - [x] 针对更多角色实现 Smart Balancing (已实现 fortune_teller, ravenkeeper, empath, chef, investigator, washerwoman, librarian)
  - [x] 优化 AI Storyteller 模式下的 LLM Prompt 质量 (提升了 analyze_game_situation 的上帝视角与隐秘计划引导)

---

## 下一阶段建议顺序

1. **A3-DATA**: 强化数据工厂，支持更大规模的样本生成。
2. **A3-EVAL**: 建立自动化的 Storyteller 裁量质量评估流水线。

---

## 变更记录

- **2026-04-22**: 重写任务板，改为先收口输入、分类、复盘，再增强智能裁量。
- **2026-04-23**: ST-1/ST-2/ST-4 核心功能落地。
- **2026-04-23**: 完成 ST-3 统计增强与 ST-5 智能平衡逻辑初步实现。
