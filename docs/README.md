---
doc_id: "REF-INDEX"
title: "鸦木布拉夫小镇 — 文档索引"
category: "reference"
role: "[State]"
status: "published"
date: "2026-07-31"
author: "Ravenswood Bluff"
---

# 鸦木布拉夫小镇 — 文档索引

> 单一语料根：`docs/`（共 66 篇人工文档，均带 frontmatter）。治理规范见 `.codebuddy/skills/doc-governance`。
> `alpha-1.1-evidence/` 为脚本自动生成的验收证据，豁免 frontmatter，文件名索引见本文件 §7。

## 1. 场景查找表

| 我想… | 先看 | 再看 |
|------|------|------|
| 了解项目、如何运行与验证 | `README.md`(根) · `AGENTS.md`(根) | `architecture.md`(根) · `CLAUDE.md`(根) |
| 看当前进度与待办 | `PROGRESS.md`(根) | `DECISIONS.md`(根) · `docs/plans/alpha-1.1-plan.md` |
| 看长期规划 / 如何执行迭代 | `docs/plans/pln044-long-term-roadmap.md`(PLN-044) | `docs/plans/pln045-execution-handbook.md`(PLN-045) |
| 查某角色能力 / 避坑 | `docs/reference/rule_matrix.md`(ARC-002) · `docs/reference/tech-traps.md`(REF-004) | — |
| 跟进某版本计划 / 任务 | `docs/plans/alpha-1.1-plan.md`(PLN-003) 及其子目录 | `docs/alpha-1.1-evidence/`（验收证据） |
| 部署 / 本地联机 | `docs/guides/cloud_deployment_guide.md`(REF-001) · `docs/guides/lan_play_guide.md`(REF-003) | — |
| 看验收 / 测试报告 | `docs/reviews/validation_report.md`(RPT-007) · `docs/frontend_acceptance.md`(RPT-006) | `docs/alpha-1.0-benchmark-results.md`(RPT-002) |
| 复盘某局对战 | `docs/reviews/game-analysis/`(RPT-011/012) | — |
| 查历史移交 / 审查 | review 类文档（`REV-*`） | — |

## 2. 目录结构（带角色标签）

```
docs/
|- README.md               本索引（State）
|- frontend_acceptance.md          脚本生成，路径固定（scripts/acceptance/frontend_acceptance.py 写入）
|- alpha-1.0-benchmark-results.md  脚本生成，路径固定（scripts/benchmark/batch_benchmark.py 写入）
|- alpha-1.1-evidence/     验收证据（脚本写入，免 frontmatter，原地保留）
|- alpha-1.2-evidence/     Alpha 1.2 人工验收证据（带 frontmatter，如 live-agent-native-verification）
|- plans/                  计划与任务板（Delta）
|   |- alpha-0.2-plan/  alpha-0.3-plan/  alpha-1.0-plan/  alpha-1.1-plan/  alpha-1.2-plan/
|- releases/               发布说明 / 清单 / 已知问题（Delta）
|- reviews/                审查、移交、验证报告、对局分析（Delta）
|   |- game-analysis/
|- guides/                 部署 / 联机 / 数据运维 / 反馈模板（Cold）
|- reference/              架构与规范速查：rule_matrix / tech-traps / test-system / harness 分析（State·Cold）
```

> **归位规则**：脚本会写入的文档（`frontend_acceptance.md`、`alpha-1.0-benchmark-results.md`、
> `alpha-1.1-evidence/`）路径已被代码硬编码，**保留在 `docs/` 根**，移动会改变运行时行为。
> 其余人工文档一律按上表五类归位。

## 3. 分类索引

### 架构 / 规范（State）

| doc_id | 标题 | 角色 | 日期 | 路径 |
|--------|------|:----:|:----:|------|
| ARC-001 | [LLM Harness 工程解析报告：鸦木布拉夫小镇](reference/harness-engineering-analysis.md) | [State] | 2026-06-01 | `docs/reference/harness-engineering-analysis.md` |
| ARC-002 | [BOTC 规则-实现矩阵](reference/rule_matrix.md) | [State] | 2026-04-29 | `docs/reference/rule_matrix.md` |

### 计划 / 任务（Delta）

| doc_id | 标题 | 角色 | 日期 | 路径 |
|--------|------|:----:|:----:|------|
| PLN-001 | [Alpha 0.3 开发计划：AI 记忆进化与对局数据工程 (已封板 - 2026-04-24)](plans/alpha-0.3-plan.md) | [Delta] | 2026-04-25 | `docs/plans/alpha-0.3-plan.md` |
| PLN-002 | [Alpha 1.0 正式内测发布开发计划](plans/alpha-1.0-plan.md) | [Delta] | 2026-04-29 | `docs/plans/alpha-1.0-plan.md` |
| PLN-003 | [Alpha 1.1 开发计划：Gameplay & AI Difficulty](plans/alpha-1.1-plan.md) | [Delta] | 2026-06-01 | `docs/plans/alpha-1.1-plan.md` |
| PLN-004 | [Alpha 1.2 开发计划：Network Hosting & Multiplayer Readiness](plans/alpha-1.2-plan.md) | [Delta] | 2026-06-09 | `docs/plans/alpha-1.2-plan.md` |
| PLN-005 | [Ravenswood Bluff 项目瘦身与审计计划](plans/project-slimming-plan.md) | [Delta] | 2026-06-01 | `docs/plans/project-slimming-plan.md` |
| PLN-006 | [Alpha 0.2 专项计划：AI 玩家智能增强](plans/alpha-0.2-plan/ai-player-intelligence-plan.md) | [Delta] | 2026-04-11 | `docs/plans/alpha-0.2-plan/ai-player-intelligence-plan.md` |
| PLN-007 | [Alpha 0.2 当前开发进度](plans/alpha-0.2-plan/current-status.md) | [Delta] | 2026-04-21 | `docs/plans/alpha-0.2-plan/current-status.md` |
| PLN-008 | [Alpha 0.2 专项计划：前端界面优化](plans/alpha-0.2-plan/frontend-ui-optimization-plan.md) | [Delta] | 2026-04-11 | `docs/plans/alpha-0.2-plan/frontend-ui-optimization-plan.md` |
| PLN-009 | [游戏结算与复盘系统开发计划](plans/alpha-0.2-plan/gameover_implementation_plan.md) | [Delta] | 2026-04-21 | `docs/plans/alpha-0.2-plan/gameover_implementation_plan.md` |
| PLN-010 | [Alpha 0.2 规划总览](plans/alpha-0.2-plan/README.md) | [Delta] | 2026-04-21 | `docs/plans/alpha-0.2-plan/README.md` |
| PLN-011 | [Alpha 0.2 路线图](plans/alpha-0.2-plan/roadmap.md) | [Delta] | 2026-04-21 | `docs/plans/alpha-0.2-plan/roadmap.md` |
| PLN-012 | [Alpha 0.2 专项计划：说书人平衡裁量模拟数据与评估](plans/alpha-0.2-plan/storyteller-balance-simulation-plan.md) | [Delta] | 2026-04-11 | `docs/plans/alpha-0.2-plan/storyteller-balance-simulation-plan.md` |
| PLN-013 | [Alpha 0.2 专项计划：说书人智能优化](plans/alpha-0.2-plan/storyteller-intelligence-plan.md) | [Delta] | 2026-04-11 | `docs/plans/alpha-0.2-plan/storyteller-intelligence-plan.md` |
| PLN-014 | [Alpha 0.2 Wave 1 任务板](plans/alpha-0.2-plan/wave-1-task-board.md) | [Delta] | 2026-04-11 | `docs/plans/alpha-0.2-plan/wave-1-task-board.md` |
| PLN-015 | [Alpha 0.2 Wave 2 任务板](plans/alpha-0.2-plan/wave-2-task-board.md) | [Delta] | 2026-04-11 | `docs/plans/alpha-0.2-plan/wave-2-task-board.md` |
| PLN-016 | [Alpha 0.2 Wave 3 任务板](plans/alpha-0.2-plan/wave-3-task-board.md) | [Delta] | 2026-04-21 | `docs/plans/alpha-0.2-plan/wave-3-task-board.md` |
| PLN-017 | [Alpha 0.2 Wave 4 任务板](plans/alpha-0.2-plan/wave-4-task-board.md) | [Delta] | 2026-04-21 | `docs/plans/alpha-0.2-plan/wave-4-task-board.md` |
| PLN-018 | [Alpha 0.3 当前执行摘要（2026-04-22 校正版）](plans/alpha-0.3-plan/execution_summary.md) | [Delta] | 2026-04-25 | `docs/plans/alpha-0.3-plan/execution_summary.md` |
| PLN-019 | [Alpha 0.3 重制开发总计划](plans/alpha-0.3-plan/full_plan.md) | [Delta] | 2026-04-25 | `docs/plans/alpha-0.3-plan/full_plan.md` |
| PLN-020 | [Mission: A3-DATA 历史数据保存与训练资产任务板](plans/alpha-0.3-plan/task_data.md) | [Delta] | 2026-04-25 | `docs/plans/alpha-0.3-plan/task_data.md` |
| PLN-021 | [Mission: A3-GAME 游戏逻辑与交互体验任务板](plans/alpha-0.3-plan/task_game.md) | [Delta] | 2026-04-25 | `docs/plans/alpha-0.3-plan/task_game.md` |
| PLN-022 | [Mission: A3-ST 说书人优化任务板](plans/alpha-0.3-plan/task_st_ai.md) | [Delta] | 2026-04-25 | `docs/plans/alpha-0.3-plan/task_st_ai.md` |
| PLN-023 | [Alpha 1.0 任务板目录](plans/alpha-1.0-plan/README.md) | [Delta] | 2026-04-29 | `docs/plans/alpha-1.0-plan/README.md` |
| PLN-024 | [当前 AI 动作决策 Prompt 结构样例](plans/alpha-1.0-plan/sample_prompt.md) | [Delta] | 2026-04-29 | `docs/plans/alpha-1.0-plan/sample_prompt.md` |
| PLN-025 | [M1 任务板：规则与流程封板](plans/alpha-1.0-plan/task_m1_rules_flow.md) | [Delta] | 2026-04-29 | `docs/plans/alpha-1.0-plan/task_m1_rules_flow.md` |
| PLN-026 | [M2 任务板：真人前端内测流](plans/alpha-1.0-plan/task_m2_frontend_human_flow.md) | [Delta] | 2026-04-29 | `docs/plans/alpha-1.0-plan/task_m2_frontend_human_flow.md` |
| PLN-027 | [M3 任务板：Live Backend 性能与可靠性](plans/alpha-1.0-plan/task_m3_live_backend.md) | [Delta] | 2026-04-29 | `docs/plans/alpha-1.0-plan/task_m3_live_backend.md` |
| PLN-028 | [M4 任务板：说书人真相源与复盘封板](plans/alpha-1.0-plan/task_m4_storyteller_replay.md) | [Delta] | 2026-04-29 | `docs/plans/alpha-1.0-plan/task_m4_storyteller_replay.md` |
| PLN-029 | [M5 任务板：AI 玩家内测体验](plans/alpha-1.0-plan/task_m5_ai_player_experience.md) | [Delta] | 2026-04-29 | `docs/plans/alpha-1.0-plan/task_m5_ai_player_experience.md` |
| PLN-030 | [Alpha 1.1 开发入口](plans/alpha-1.1-plan/README.md) | [Delta] | 2026-06-01 | `docs/plans/alpha-1.1-plan/README.md` |
| PLN-031 | [M5-R 修复计划：AI 发言质量回归与并行机制纠偏](plans/alpha-1.1-plan/task_m5r_ai_speech_quality_repair.md) | [Delta] | 2026-06-01 | `docs/plans/alpha-1.1-plan/task_m5r_ai_speech_quality_repair.md` |
| PLN-032 | [M5 任务板：AI 响应速度与流畅体验](plans/alpha-1.1-plan/task_m5_ai_speed_flow.md) | [Delta] | 2026-06-01 | `docs/plans/alpha-1.1-plan/task_m5_ai_speed_flow.md` |
| PLN-033 | [M6 任务板：难度系统校准与架构补丁](plans/alpha-1.1-plan/task_m6_difficulty_system_refactor.md) | [Delta] | 2026-06-01 | `docs/plans/alpha-1.1-plan/task_m6_difficulty_system_refactor.md` |
| PLN-034 | [Alpha 1.1 验证规范：证明改进真实存在](plans/alpha-1.1-plan/verification_policy.md) | [Delta] | 2026-06-01 | `docs/plans/alpha-1.1-plan/verification_policy.md` |
| PLN-035 | [Alpha 1.2 开发入口](plans/alpha-1.2-plan/README.md) | [Delta] | 2026-06-09 | `docs/plans/alpha-1.2-plan/README.md` |
| PLN-036 | [M8 任务板：多人联机与局域网部署服务](plans/alpha-1.2-plan/task_m8_network_hosting.md) | [Delta] | 2026-06-09 | `docs/plans/alpha-1.2-plan/task_m8_network_hosting.md` |
| PLN-037 | [Agent 原生重构设计](plans/agent-native-redesign-plan.md) | [Delta] | 2026-08-04 | `docs/plans/agent-native-redesign-plan.md` |
| PLN-038 | [Agent 原生重构方案](plans/agent-native-redesign-plan.md) | [Delta] | 2026-08-04 | `docs/plans/agent-native-redesign-plan.md` |
| PLN-039 | [Prompt 前缀缓存命中率优化方案与任务板](plans/prompt-cache-optimization-plan.md) | [Delta] | 2026-08-04 | `docs/plans/prompt-cache-optimization-plan.md` |
| PLN-040 | [差异化玩家进化 + 量化基准方案与任务板](plans/pln040-player-distinctness-plan.md) | [Delta] | 2026-08-07 | `docs/plans/pln040-player-distinctness-plan.md` |
| PLN-041 | [工作流与 RAG 融入计划（含可行性核查）](plans/血染钟楼_工作流与RAG融入计划_2026-08-12.md) | [Delta] | 2026-08-12 | `docs/plans/血染钟楼_工作流与RAG融入计划_2026-08-12.md` |
| PLN-043 | [全动作声明式工作流：agent 决策统一工作流化](plans/pln043-all-action-workflow-plan.md) | [Delta] | 2026-08-14 | `docs/plans/pln043-all-action-workflow-plan.md` |
| PLN-042 | [认知工作流：观点-证据层 + 人类式决策/发言工作流](plans/pln042-cognitive-workflow-plan.md) | [Delta] | 2026-08-13 | `docs/plans/pln042-cognitive-workflow-plan.md` |
| PLN-044 | [项目长期路线图：从 Alpha 1.2 到 Beta 2.0（分阶段实现）](plans/pln044-long-term-roadmap.md) | [Delta] | 2026-09-08 | `docs/plans/pln044-long-term-roadmap.md` |
| PLN-045 | [Agent 迭代执行手册：里程碑与任务的标准执行流程](plans/pln045-execution-handbook.md) | [Delta] | 2026-09-08 | `docs/plans/pln045-execution-handbook.md` |
| PLN-046 | [Token 预算优化计划：缓存命中率提升 + 输出削减](plans/token-budget-optimization-plan.md) | [Delta] | 2026-08-03 | `docs/plans/token-budget-optimization-plan.md`（draft，与 PLN-039 主题相邻） |

### 审查 / 移交（Delta）

| doc_id | 标题 | 角色 | 日期 | 路径 |
|--------|------|:----:|:----:|------|
| REV-001 | [Project Handoff: Slimming & Modular Refactor (May 2026)](reviews/CLAUDE_HANDOFF.md) | [Delta] | 2026-06-01 | `docs/reviews/CLAUDE_HANDOFF.md` |
| REV-002 | [Gemini 移交文档复核记录（2026-04-18）](reviews/GEMINI_HANDOFF_REVIEW_2026-04-18.md) | [Delta] | 2026-04-21 | `docs/reviews/GEMINI_HANDOFF_REVIEW_2026-04-18.md` |
| REV-003 | [Gemini 遗留问题收口清单](reviews/GEMINI_REMEDIATION_BACKLOG.md) | [Delta] | 2026-04-21 | `docs/reviews/GEMINI_REMEDIATION_BACKLOG.md` |
| REV-004 | [当前遗留问题与并行修复计划](reviews/remediation_backlog.md) | [Delta] | 2026-04-08 | `docs/reviews/remediation_backlog.md` |
| REV-005 | [Gemini Alpha 0.3 审计记录](plans/alpha-0.3-plan/gemini_audit.md) | [Delta] | 2026-04-25 | `docs/plans/alpha-0.3-plan/gemini_audit.md` |
| REV-006 | [Alpha 0.2 AI 智能重构移交文档 (Handover Document)](reviews/HANDOVER_ALPHA_0.2.md) | [Delta] | 2026-04-21 | `docs/reviews/HANDOVER_ALPHA_0.2.md` |
| REV-007 | [Agent 原生重构 CR 审查报告](reviews/agent-native-redesign-cr-review-2026-08-03.md) | [Delta] | 2026-08-03 | `docs/reviews/agent-native-redesign-cr-review-2026-08-03.md` |
| REV-008 | [PLN-039 缓存命中率优化 CR 审查报告（修复指引版）](reviews/pln039-cache-opt-cr-review-2026-08-04.md) | [Delta] | 2026-08-04 | `docs/reviews/pln039-cache-opt-cr-review-2026-08-04.md` |
| REV-009 | [CR 与测试验收提示词：PLN-041/042 未提交改动](reviews/cr-prompt-pln041-042-2026-08-13.md) | [Delta] | 2026-08-13 | `docs/reviews/cr-prompt-pln041-042-2026-08-13.md` |
| REV-010 | [CR 审查提示词：PLN-043 全动作声明式工作流](reviews/cr-prompt-pln043-2026-08-14.md) | [Delta] | 2026-08-14 | `docs/reviews/cr-prompt-pln043-2026-08-14.md` |
| REV-011 | [live 验收与效果分析提示词：PLN-041/042/043 改进效果](reviews/live-analysis-prompt-pln041-043-2026-08-14.md) | [Delta] | 2026-08-14 | `docs/reviews/live-analysis-prompt-pln041-043-2026-08-14.md` |
| REV-012 | [PLN-041/042 代码审查与测试验收报告（工作流 + RAG + 认知工作流）](reviews/cr-review-pln041-042-2026-08-13.md) | [Delta] | 2026-08-13 | `docs/reviews/cr-review-pln041-042-2026-08-13.md` |
| REV-013 | [PLN-043 全动作声明式工作流 CR 审查 + 验收报告](reviews/cr-review-pln043-2026-08-14.md) | [Delta] | 2026-08-14 | `docs/reviews/cr-review-pln043-2026-08-14.md` |
| REV-014 | [文档治理审计报告：docs 语料诊断 + PLN-044/045 合规审查](reviews/doc-governance-audit-2026-09-08.md) | [Delta] | 2026-09-08 | `docs/reviews/doc-governance-audit-2026-09-08.md` |

### 发布（Delta）

| doc_id | 标题 | 角色 | 日期 | 路径 |
|--------|------|:----:|:----:|------|
| REL-001 | [Alpha 0.1 发布说明](releases/alpha-0.1-release-notes.md) | [Delta] | 2026-04-09 | `docs/releases/alpha-0.1-release-notes.md` |
| REL-002 | [Alpha 0.2 开发总结与发布梳理](releases/alpha-0.2-release-summary.md) | [Delta] | 2026-04-21 | `docs/releases/alpha-0.2-release-summary.md` |
| REL-003 | [Alpha 0.3 开发总结与发布说明](releases/alpha-0.3-release-summary.md) | [Delta] | 2026-04-25 | `docs/releases/alpha-0.3-release-summary.md` |
| REL-004 | [Alpha 1.0 Release Checklist](releases/alpha-1.0-release-checklist.md) | [Delta] | 2026-04-29 | `docs/releases/alpha-1.0-release-checklist.md` |
| REL-005 | [Wave 4 Release Checklist](plans/alpha-0.2-plan/wave-4-release-checklist.md) | [Delta] | 2026-04-21 | `docs/plans/alpha-0.2-plan/wave-4-release-checklist.md` |
| REL-006 | [M6 任务板：发布工程与内测包](plans/alpha-1.0-plan/task_m6_release_package.md) | [Delta] | 2026-04-29 | `docs/plans/alpha-1.0-plan/task_m6_release_package.md` |
| REL-007 | [Alpha 1.2「觉醒之鸦」Agent 原生重构版发布记录](releases/alpha-1.2-agent-native-release.md) | [Delta] | 2026-08-04 | `docs/releases/alpha-1.2-agent-native-release.md` |
| REL-008 | [AIAgent / StorytellerAgent / GameOrchestrator 上帝对象拆分计划](releases/v0.8/AGENTS_refactor.md) | [State] | 2026-07-31 | `docs/releases/v0.8/AGENTS_refactor.md`（内容属设计说明，role 保留 `[State]`） |
| REL-009 | [Alpha 1.2「觉醒之鸦」Release Checklist](releases/alpha-1.2-release-checklist.md) | [Delta] | 2026-08-07 | `docs/releases/alpha-1.2-release-checklist.md` |

### 报告 / 分析（Delta）

| doc_id | 标题 | 角色 | 日期 | 路径 |
|--------|------|:----:|:----:|------|
| RPT-001 | [Alpha 1.0 M5 AI 行为样本](reviews/alpha-1.0-ai-behavior-sample.md) | [Delta] | 2026-04-29 | `docs/reviews/alpha-1.0-ai-behavior-sample.md` |
| RPT-002 | [Alpha 1.0 多人数配置基准测试报告](alpha-1.0-benchmark-results.md) | [Delta] | 2026-05-03 | `docs/alpha-1.0-benchmark-results.md` |
| RPT-003 | [Alpha 1.0 数据与日志目录说明](guides/alpha-1.0-data-operations.md) | [Delta] | 2026-04-29 | `docs/guides/alpha-1.0-data-operations.md` |
| RPT-004 | [Alpha 1.0 内测反馈模板](guides/alpha-1.0-feedback-template.md) | [Delta] | 2026-04-29 | `docs/guides/alpha-1.0-feedback-template.md` |
| RPT-005 | [Alpha 1.0 Known Issues](releases/alpha-1.0-known-issues.md) | [Delta] | 2026-04-29 | `docs/releases/alpha-1.0-known-issues.md` |
| RPT-006 | [Frontend Acceptance Flow](frontend_acceptance.md) | [Delta] | 2026-04-29 | `docs/frontend_acceptance.md` |
| RPT-007 | [验证与修复记录](reviews/validation_report.md) | [Delta] | 2026-04-08 | `docs/reviews/validation_report.md` |
| RPT-008 | [Alpha 0.2 专项计划：自动化验收与测试](plans/alpha-0.2-plan/acceptance-and-testing-plan.md) | [Delta] | 2026-04-11 | `docs/plans/alpha-0.2-plan/acceptance-and-testing-plan.md` |
| RPT-009 | [Alpha 0.2 专项计划：全部角色业务实现与验证](plans/alpha-0.2-plan/role-implementation-and-validation-plan.md) | [Delta] | 2026-04-11 | `docs/plans/alpha-0.2-plan/role-implementation-and-validation-plan.md` |
| RPT-010 | [M7 任务板：验证规范与增量证据](plans/alpha-1.1-plan/task_m7_validation_evidence.md) | [Delta] | 2026-06-01 | `docs/plans/alpha-1.1-plan/task_m7_validation_evidence.md` |
| RPT-011 | [对局分析报告: efa662a3 (8人Live局)](reviews/game-analysis/2026-05-07_efa662a3_8player_live.md) | [Delta] | 2026-06-01 | `docs/reviews/game-analysis/2026-05-07_efa662a3_8player_live.md` |
| RPT-012 | [对局分析目录](reviews/game-analysis/README.md) | [Delta] | 2026-06-01 | `docs/reviews/game-analysis/README.md` |
| RPT-013 | [Alpha 1.2 Agent 原生重构 live 对局验收证据（真实 LLM）](alpha-1.2-evidence/live-agent-native-verification-2026-08-04.md) | [Delta] | 2026-08-04 | `docs/alpha-1.2-evidence/live-agent-native-verification-2026-08-04.md` |
| RPT-014 | [PLN-039 第二轮缓存优化 live 8 人局实测报告](alpha-1.2-evidence/pln039-live-8p-cache-verification-2026-08-04.md) | [Delta] | 2026-08-04 | `docs/alpha-1.2-evidence/pln039-live-8p-cache-verification-2026-08-04.md` |
| RPT-015 | [PLN-040 T3 tendency 标定实验结果](alpha-1.2-evidence/pln040-t3-tendency-calibration-2026-08-07.md) | [Delta] | 2026-08-07 | `docs/alpha-1.2-evidence/pln040-t3-tendency-calibration-2026-08-07.md` |
| RPT-016 | [PLN-040 T4 进化有效性 A/B 基准结果](alpha-1.2-evidence/pln040-t4-evolution-ab-2026-08-07.md) | [Delta] | 2026-08-07 | `docs/alpha-1.2-evidence/pln040-t4-evolution-ab-2026-08-07.md` |
| RPT-017 | [PLN-041 工作流 + RAG 融入实施与验证报告](alpha-1.2-evidence/pln041-workflow-rag-report-2026-08-13.md) | [Delta] | 2026-08-13 | `docs/alpha-1.2-evidence/pln041-workflow-rag-report-2026-08-13.md` |
| RPT-018 | [PLN-042 认知工作流实施与 live 实测报告](alpha-1.2-evidence/pln042-cognitive-workflow-report-2026-08-13.md) | [Delta] | 2026-08-13 | `docs/alpha-1.2-evidence/pln042-cognitive-workflow-report-2026-08-13.md` |
| RPT-019 | [PLN-043 全动作声明式工作流实施与 live 实测报告](alpha-1.2-evidence/pln043-all-action-workflow-report-2026-08-14.md) | [Delta] | 2026-08-14 | `docs/alpha-1.2-evidence/pln043-all-action-workflow-report-2026-08-14.md` |
| RPT-020 | [PLN-041/042/043 live 效果分析报告](alpha-1.2-evidence/pln041-043-live-effect-analysis-2026-08-14.md) | [Delta] | 2026-08-14 | `docs/alpha-1.2-evidence/pln041-043-live-effect-analysis-2026-08-14.md` |

### 参考 / 指南（Cold）

| doc_id | 标题 | 角色 | 日期 | 路径 |
|--------|------|:----:|:----:|------|
| REF-001 | [《鸦木布拉夫小镇》云端服务器部署指南](guides/cloud_deployment_guide.md) | [Cold] | 2026-06-09 | `docs/guides/cloud_deployment_guide.md` |
| REF-003 | [《鸦木布拉夫小镇》多人/局域网联机配置指南](guides/lan_play_guide.md) | [Cold] | 2026-06-09 | `docs/guides/lan_play_guide.md` |
| REF-004 | [技术陷阱速查 (tech-traps)](reference/tech-traps.md) | [Cold] | 2026-07-30 | `docs/reference/tech-traps.md` |
| REF-005 | [测试系统参考 (test-system)](reference/test-system.md) | [Cold] | 2026-07-31 | `docs/reference/test-system.md` |
| REF-006 | [AI 玩家输入提示词（Prompt）设计总览](guides/prompt-design.md) | [Cold] | 2026-08-04 | `docs/guides/prompt-design.md` |

## 4. ADR 索引

本项目决策集中在根目录 `DECISIONS.md`（轻量决策日志），尚未单列 ADR 目录。涉及架构/约定的重大变更请同步更新 `DECISIONS.md` 与 `.codebuddy/memory/MEMORY.md`。

## 5. 模板索引

本仓库暂未内置本地 `templates/` 目录。通用文档模板（六类：决策 / 规范 / 计划 / 报告 / 参考 / 移交）见技能：

`.codebuddy/skills/doc-governance/references/templates/`

新增文档建议直接套用对应模板的 frontmatter 字段（`doc_id / title / category / role / status / date / author`）。

## 6. 主题归口（原 8 类速览）

| 主题 | 对应分类 / 文档 |
|------|----------------|
| 设计与架构 | architecture 类（`ARC-*`）、根 `architecture.md` |
| 版本计划 | planning 类（`PLN-*`），按 `alpha-*` 子目录组织 |
| 发布说明 | release 类（`REL-*`） |
| 验收 / 报告 / 分析 | report 类（`RPT-*`）、`game-analysis/` |
| 审查 / 移交 | review 类（`REV-*`） |
| 部署 / 指南 / 陷阱 | reference 类（`REF-*`） |
| 自动生成证据 | `alpha-1.1-evidence/`（27 个验收证据 + README/template 目录脚手架，均豁免 frontmatter；详见本文件 §7） |
| 本索引 | `docs/README.md` |

## 7. 自动生成验收证据（alpha-1.1-evidence/）

> 该目录由 `scripts/alpha1.1_acceptance.py` 在每次验收门禁运行时**自动生成**，属脚本产物，**豁免 frontmatter**（不纳入人工文档治理）。下表为文件名索引，便于检索；文件内容以脚本产出为准。

| 类别 | 文件（相对路径链接） |
|------|----------------------|
| 难度修复 (DIFF-FIX) | [20260503_A11-DIFF-FIX-022_strategy_prompt_team_boundary.md](alpha-1.1-evidence/20260503_A11-DIFF-FIX-022_strategy_prompt_team_boundary.md) · [20260503_A11-DIFF-FIX-022_team_boundary.md](alpha-1.1-evidence/20260503_A11-DIFF-FIX-022_team_boundary.md) · [20260503_A11-DIFF-FIX-023_multi_axis_difficulty_preset.md](alpha-1.1-evidence/20260503_A11-DIFF-FIX-023_multi_axis_difficulty_preset.md) · [20260503_A11-DIFF-FIX-023_multi_axis.md](alpha-1.1-evidence/20260503_A11-DIFF-FIX-023_multi_axis.md) · [20260503_A11-DIFF-FIX-024_standard_baseline.md](alpha-1.1-evidence/20260503_A11-DIFF-FIX-024_standard_baseline.md) · [20260503_A11-DIFF-FIX-025_deception_budget.md](alpha-1.1-evidence/20260503_A11-DIFF-FIX-025_deception_budget.md) · [20260503_A11-DIFF-FIX-026_chaos_guardrails.md](alpha-1.1-evidence/20260503_A11-DIFF-FIX-026_chaos_guardrails.md) |
| 速度 (SPEED) | [20260503_A11-SPEED-015-016_latency_metrics_and_budget.md](alpha-1.1-evidence/20260503_A11-SPEED-015-016_latency_metrics_and_budget.md) · [20260503_A11-SPEED-019_prompt_compression.md](alpha-1.1-evidence/20260503_A11-SPEED-019_prompt_compression.md) · [20260503_A11-SPEED-020_adaptive_speed.md](alpha-1.1-evidence/20260503_A11-SPEED-020_adaptive_speed.md) · [20260504_A11-SPEED-022_speed_acceptance.md](alpha-1.1-evidence/20260504_A11-SPEED-022_speed_acceptance.md) · [20260505_A11-SPEED-FIX_m5r_regression.md](alpha-1.1-evidence/20260505_A11-SPEED-FIX_m5r_regression.md) |
| 验证 (VERIFY) | [20260503_A11-VERIFY-029_verification_policy.md](alpha-1.1-evidence/20260503_A11-VERIFY-029_verification_policy.md) · [20260503_A11-VERIFY-030_aggregate_acceptance.md](alpha-1.1-evidence/20260503_A11-VERIFY-030_aggregate_acceptance.md) · [20260503_A11-VERIFY-031_difficulty_behavior.md](alpha-1.1-evidence/20260503_A11-VERIFY-031_difficulty_behavior.md) · [20260503_A11-VERIFY-032_ai_speed.md](alpha-1.1-evidence/20260503_A11-VERIFY-032_ai_speed.md) · [20260503_A11-VERIFY-033_evidence_template.md](alpha-1.1-evidence/20260503_A11-VERIFY-033_evidence_template.md) · [20260503_A11-VERIFY-034_faction_boundary.md](alpha-1.1-evidence/20260503_A11-VERIFY-034_faction_boundary.md) · [20260503_A11-VERIFY-035_release_index.md](alpha-1.1-evidence/20260503_A11-VERIFY-035_release_index.md) · [20260504_A11-VERIFY-035_final_fixes.md](alpha-1.1-evidence/20260504_A11-VERIFY-035_final_fixes.md) |
| Live 发言 (m5l_live_speech) | [m5l_live_speech_20260506-125852.md](alpha-1.1-evidence/m5l_live_speech_20260506-125852.md) · [m5l_live_speech_20260506-131029.md](alpha-1.1-evidence/m5l_live_speech_20260506-131029.md) · [m5l_live_speech_20260506-131937.md](alpha-1.1-evidence/m5l_live_speech_20260506-131937.md) · [m5l_live_speech_20260507-071702.md](alpha-1.1-evidence/m5l_live_speech_20260507-071702.md) · [m5l_live_speech_20260507-081313.md](alpha-1.1-evidence/m5l_live_speech_20260507-081313.md) · [m5l_live_speech_20260601-115555.md](alpha-1.1-evidence/m5l_live_speech_20260601-115555.md) · [m5l_live_speech_20260609-085322.md](alpha-1.1-evidence/m5l_live_speech_20260609-085322.md) |
| 目录脚手架 | `README.md`（本目录说明）· `template.md`（证据模板）—— 非验收证据 |

共 27 个验收证据文件（脚本产物，豁免 frontmatter），另含 `README.md` / `template.md` 两项目录脚手架。
