---
doc_id: "REV-014"
title: "文档治理审计报告：docs 语料诊断 + PLN-044/045 合规审查"
category: "review"
role: "[Delta]"
status: "published"
date: "2026-09-08"
author: "Ravenswood Bluff"
tags: ["doc-governance", "audit", "frontmatter", "index", "agent-friendly"]
related:
  - "../plans/pln044-long-term-roadmap.md"
  - "../plans/pln045-execution-handbook.md"
  - "../README.md"
---

# 文档治理审计报告：docs 语料诊断 + PLN-044/045 合规审查

> **审计日期**：2026-09-08
> **审计范围**：`docs/` 全量 138 篇 md；重点审查本次新增 `PLN-044`/`PLN-045`；索引 `docs/README.md`
> **审计方法**：混合——① 项目既有 `scripts/check_doc_health.py`（frontmatter + 链接）；② 一次性扫描脚本（巨型单文件 / 幽灵文档 / role 一致性，已用后删除）；③ 人工审查（代码一致性抽查、反模式清单 §6）
> **规范依据**：`doc-governance` Skill（`references/documentation-governance.md`）+ 项目既有约定 DECISIONS D011

---

## 一、审计结论

### 1.1 本次新增文档（PLN-044 / PLN-045，修复后）

| 维度 | 评分 | 说明 |
|------|:--:|------|
| 元数据完整性 | 25/25 | 必填 7 字段齐全，另补 `tags` + `related` |
| 角色标注 | 15/15 | `role: [Delta]` 与 `plans/` 目录一致 |
| 链接健康度 | 20/20 | 内部链接全为相对路径且目标存在；`check_doc_health.py` PASSED |
| 代码一致性 | 20/20 | 抽查 `ToolCallNode.timeout_seconds=10.0`（`workflow.py:50`）与文档描述一致；基线数字（676/710/1660.9/2.5%/53.83%）与 PROGRESS/RPT-020 一致 |
| 可检索性 | 10/10 | `doc_id` + `tags` + 已注册 `docs/README.md` |
| 时效性 | 10/10 | 当日创建 |
| **Agent 友好度** | **100/100** | 优秀 |

| 维度 | 评分 | 说明 |
|------|:--:|------|
| 排版规范 | 25/25 | 表格对齐、代码块标注语言（`text`/`markdown`/`powershell`）、章节分隔线 |
| TOC 目录 | 15/15 | 已补章节速览目录（12 / 11 章节） |
| 示例丰富 | 20/20 | 任务板、命令速查、PLN 模板骨架、架构图 |
| 图表辅助 | 12/20 | 仅 ASCII 图（架构/生命周期），无 Mermaid/图片 |
| 语言清晰 | 20/20 | 无占位符、无歧义缩写 |
| **人类可读性** | **92/100** | 优秀（图表维度可后续用 Mermaid 补齐） |

### 1.2 文档体系整体（修复后）

| 维度 | 评分 | 说明 |
|------|:--:|------|
| 完整性（元数据/索引） | 92/100 | 138 篇全部有 frontmatter；4 篇幽灵文档已注册 |
| 一致性（角色/链接/代码） | 90/100 | 4 处 role 偏差（2 修 2 豁免）；链接 0 死链（1 个历史非致命 warning） |
| 时效性 | 85/100 | 历史计划（2026-04~06）超 30 天，按 §3.2 `[Delta]` 原则豁免 |
| **综合** | **89/100** | 优秀（治理就绪） |

---

## 二、问题清单

| # | 严重度 | 位置 | 问题描述 | 处置 |
|---|:--:|------|----------|------|
| 1 | 🟡 P1 | `reviews/cr-review-pln041-042-2026-08-13.md` | 幽灵文档：存在但未注册索引；`doc_id` 为 `CR-PLN041-042-2026-08-13`（不合受控前缀） | ✅ 已改 `REV-012` + 注册索引 |
| 2 | 🟡 P1 | `reviews/cr-review-pln043-2026-08-14.md` | 幽灵文档；`doc_id: CR-043` 不合受控前缀 | ✅ 已改 `REV-013` + 注册索引 |
| 3 | 🟡 P1 | `plans/token-budget-optimization-plan.md` | 幽灵文档 + **doc_id 冲突**：`PLN-037` 同时被 `agent-native-redesign-plan.md` 占用 | ✅ 改 `PLN-046` + 注册索引（draft，待确认与 PLN-039 关系） |
| 4 | 🟡 P1 | `releases/v0.8/AGENTS_refactor.md` | 幽灵文档，且 REL 编号序列缺 `REL-008` | ✅ 注册为 `REL-008`，补全序列 |
| 5 | 🟡 P1 | `reviews/cr-review-pln041-042-2026-08-13.md` | 僵尸/角色错误：`role: [State]` 与 review 类（做过什么）不符 | ✅ 已改 `[Delta]` |
| 6 | 🔵 P2 | `docs/reference/harness-engineering-analysis.md`(979 行)、`docs/plans/alpha-1.1-plan.md`(622 行)、`docs/plans/alpha-1.1-plan/task_m5_ai_speed_flow.md`(524 行) | 巨型单文件（>500 行，反模式） | ⏳ 登记豁免：均为历史/调研 `[Delta]`/`[Cold]` 文档，拆分收益 < churn 风险；下次重大修改时再拆 |
| 7 | 🔵 P2 | `guides/alpha-1.0-data-operations.md`、`guides/alpha-1.0-feedback-template.md` | `role: [Delta]` 与 `guides/` 期望 `[Cold]` 不符 | ⏳ 已知豁免：索引中归为 RPT-003/RPT-004（报告类），身份以索引为准 |
| 8 | 🔵 P2 | `releases/v0.8/AGENTS_refactor.md` | `role: [State]` 与 `releases/` 期望 `[Delta]` 不符 | ⏳ 已知豁免：内容属设计说明 |
| 9 | 🔵 P2 | PLN-044 / PLN-045（初版） | 超 3 章节无 TOC；3 处代码块无语言标注；正文交叉引用用根相对路径而非同目录相对路径 | ✅ 已全部修复 |
| 10 | 🔵 P2 | 全库 | 图表仅 ASCII，无 Mermaid | ⏳ 后续文档逐步采用 Mermaid |
| 11 | 🔵 P2 | 全库（138 篇） | 大量历史文档超 30 天未更新 | ⏳ 按 §3.2 `[Delta]` 原则豁免（完成后不改动）；仅对确被替代者标 `superseded` |

---

## 三、逐项分析

### 3.1 幽灵文档（4 篇）与 doc_id 冲突

扫描 `docs/**/*.md`（排除 `alpha-1.1-evidence/` 脚本产物豁免目录）比对 `docs/README.md` 索引，命中 4 篇未注册文档。其中 `plans/token-budget-optimization-plan.md` 原 `doc_id: PLN-037` 与 `agent-native-redesign-plan.md`（README 中 PLN-037/038 均指向该文件）**编号冲突**——同一 doc_id 对应两个文件，会破坏 Agent 按 doc_id 检索的唯一性（skill §4.2「编号递增 / 全局唯一标识」）。已分配新号 `PLN-046`（status 保持 `draft`，其与 PLN-039 的取代关系待用户确认后再标 `superseded_by`）。

### 3.2 角色标注偏差（4 处）

按 skill §3.2：`[Delta]` 描述"做过什么"。两份 CR 报告属审查记录，`cr-review-pln041-042` 误标 `[State]`（描述"当前是什么"）已修正。其余 3 处（2 份 guides 下的 RPT 文档 + AGENTS_refactor）为"内容性质与目录默认角色不一致"，但内容本身准确、且索引已按真实身份归类 → 登记为**已知豁免**，避免为对齐目录而 churn。

### 3.3 巨型单文件（3 篇）

979/622/524 行，均超 skill §6 的 500 行红线。核查内容性质：`harness-engineering-analysis.md` 为外部调研报告（`[Cold]`，只读性质）；另两篇为 Alpha 1.1 历史计划与任务板（`[Delta]`，已完成）。按 §3.2「Delta 完成后不再修改，只新增」原则，拆分会制造大量 churn 且无实际收益 → 登记豁免，仅在下次因实质原因修改该文件时顺带拆分。

### 3.4 代码一致性

抽查路线图中引用的关键代码事实：`ToolCallNode.timeout_seconds = 10.0`（`src/agents/workflow/workflow.py:50`），且 `action_workflows.py` 未覆盖该值 → 与 PLN-044 §5.1 T2「decide 超时对齐」的前提完全吻合，任务设计基于真实代码而非推测。

### 3.5 反模式清单对照

| 反模式 | 命中 |
|--------|:--:|
| 无 frontmatter | 0 |
| 幽灵文档 | 4（已修） |
| 僵尸规则 | 1（role 错标，已修） |
| 巨型单文件 >500 行 | 3（已登记豁免） |
| 死链接 | 0（1 个历史非致命绝对路径 warning） |
| 岛文档 | 0（新增文档互相引用 + 索引 + AGENTS.md 三处入口） |
| 裸代码块 | 3（已修，补 `text`/`markdown`/`powershell`） |
| 空格/特殊字符文件名 | 1 历史（`血染钟楼_工作流与RAG融入计划_2026-08-12.md`，中文命名符合项目惯例，豁免） |
| 硬编码绝对路径 | 0 |

---

## 四、修复优先级

| 优先级 | 问题数 | 状态 | 预估工时 |
|:--:|:--:|:--:|:--:|
| P0 | 0 | — | 0h |
| P1 | 5（#1-5） | ✅ 全部已修 | 0.5h |
| P2 | 6（#6-11） | ✅ 2 项已修（#9 拆为 3 子项）；⏳ 5 项登记豁免/后续 | 2h（若全部执行） |
| **合计** | **11** | 已修 7 / 豁免 4 | — |

---

## 五、后续行动

- [x] P1 全部修复（幽灵文档注册、doc_id 冲突消解、role 修正）
- [x] 新增文档合规修复（TOC / 代码块语言 / 相对链接 / tags+related）
- [x] 复跑 `scripts/check_doc_health.py` 确认 PASSED
- [x] 清理一次性扫描脚本（临时产物纪律，skill §8.9）
- [x] **常态化门禁**（2026-09-08 落地）：`scripts/check_doc_health.py` 新增两项检查——① **幽灵文档**（未被 `docs/README.md` 引用）判为 HARD failure，RC=1 阻断 CI；② **巨型单文件**（>500 行）判为 warning，`--strict` 下升级为 failure。验证记录：默认模式 PASSED / RC=0（4 条 warning = 3 oversized + 1 历史绝对链接）；植入幽灵探针文件 → FAILED / RC=1；`--strict` → RC=1；探针删除后恢复 RC=0；`ruff check scripts` 0 告警。
- [ ] 3 个巨型单文件在下次实质修改时拆分（或标记 `archived`）
- [ ] 新建文档统一套用 `PLN-045 §11-A` 模板 + 本文档 §二必检项清单
- [ ] 下个里程碑收尾时执行第二轮审计验证

---

## 六、规范适配说明

本项目 `docs/` 语料根与 `doc_id` 前缀制（`PLN-0XX`/`RPT-0XX`/`REV-0XX`/`REL-0XX`/`REF-0XX`）为 DECISIONS D011 既定约定，与 skill 默认的 `documents/` 根目录 + `{category}-{NNN}` 编号为同一治理模型的两种实例化。本次审计**以项目既有约定为准**（避免为对齐默认而大规模重命名），仅要求：编号全局唯一、前缀与 category 对应、索引必注册——三者与 skill §4.2 目标一致。
