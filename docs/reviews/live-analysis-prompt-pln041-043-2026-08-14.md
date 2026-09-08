---
doc_id: "REV-011"
title: "live 验收与效果分析提示词：PLN-041/042/043 改进效果"
category: "review"
role: "[Delta]"
status: "published"
date: "2026-08-14"
author: "Ravenswood Bluff"
---

# live 验收与效果分析提示词：PLN-041/042/043 改进效果

> 用途：交给新窗口 agent 的首条消息（整段复制即可）。自包含：含启动命令、开关、落盘产物路径、对照方法与报告模板。
> 已修正：`--stop-after day_2` 非法值（→ `day_1`）、无 `--seed` 参数（→ 统计口径对照）、报告 frontmatter 补 `title`、证据 source 补 `public_claim`。

---

```text
你是《血染钟楼》(Ravenswood Bluff) 多 Agent 社交推演引擎的 live 验收与效果分析 agent。
任务：启动最新 live 对局（真实 LLM），分析最近三项改进（PLN-041 工作流+RAG、
PLN-042 认知工作流、PLN-043 全动作声明式工作流）的实际效果，产出量化分析报告。

## 上班必读（按顺序）
1. AGENTS.md（命令 + 硬约束 + 清洁状态定义）
2. 最近改进的计划与报告：
   - docs/plans/血染钟楼_工作流与RAG融入计划_2026-08-12.md（PLN-041）+ docs/alpha-1.2-evidence/pln041-workflow-rag-report-2026-08-13.md（RPT-017）
   - docs/plans/pln042-cognitive-workflow-plan.md（PLN-042）+ docs/alpha-1.2-evidence/pln042-cognitive-workflow-report-2026-08-13.md（RPT-018）
   - docs/plans/pln043-all-action-workflow-plan.md（PLN-043）+ docs/alpha-1.2-evidence/pln043-all-action-workflow-report-2026-08-14.md（RPT-019）
3. DECISIONS.md（D016 工作流+RAG / D018 认知工作流 / D019 全动作声明式工作流）

## 三项改进速览（本次要验证的效果）
- PLN-041：规则书静态注入（22 角色能力边界/阵营红线进 system stable 段，防"不按规则乱发言"）+ BM25/Faiss 混合检索 + Workflow 引擎 + ActionTrace 落盘
- PLN-042：speak 认知工作流（观点-证据模型 + 确定性置信度 + 门控 hard_count≥1，无硬证据强断言降级）
- PLN-043：全动作声明式工作流（8 动作 recall→decide→validate→record）+ 观点演化闭环（决策回写观点库：创建/更新/supersede）

## 关键开关
- `BOTC_WORKFLOW_ACTIONS=1`：全动作工作流（PLN-043，本次重点）
- `BOTC_COGNITIVE_SPEAK=1`：speak 认知工作流（PLN-042，可与上面叠加或单独测）
- `BOTC_VIEWPOINTS=1`：强制观点库落盘（BOTC_BACKEND=live 时默认已开）
- 以上开关默认 off，mock 下全零落盘

## 启动 live 对局（PowerShell，.env 需有 OPENAI_API_KEY）
```powershell
cd d:\ravenswood-bluff
.\.venv\Scripts\activate
New-Item -ItemType Directory -Force -Path tmp_work | Out-Null
$env:BOTC_BACKEND="live"
$env:BOTC_WORKFLOW_ACTIONS="1"   # 开启全动作工作流
# 完整局（5 人，跑到 game_over，才能观察跨轮次观点演化；timeout 给足）
.\.venv\Scripts\python.exe simulate_game.py --backend live --player-count 5 --stop-after game_over --timeout-seconds 900 2>&1 | Tee-Object -FilePath tmp_work\live_analysis.txt
```

## 对照局方法（重要）
- 跑两局：一局开关全 off（基线）、一局 `BOTC_WORKFLOW_ACTIONS=1`（改进），量化差异。
- **没有 `--seed` 参数**：`simulate_game.py` 的 `--stop-after` 只有 4 个合法值
  （`first_execution` / `day_1` / `night_2` / `game_over`），角色/座位每局随机，
  两局无法严格同局复现。对照采用**统计口径对比**（同玩家数 5、同配置，仅开关维度不同），
  结论聚焦趋势性差异，不逐事件比对。
- 每局 game_id 随机（uuid），产物按 game_id 目录天然隔离、不会互相覆盖；但跑完一局
  **立即记录该局 game_id**（审计摘要里会打印），归档分析时标注是 off 局还是 on 局。

## 分析对象（落盘产物路径）
- `data/agents/{player_id}/games/{game_id}/viewpoints.jsonl` —— **观点演化闭环**（PLN-043 核心）：统计观点创建数/更新数/superseded 数、置信度跨轮次变化轨迹、证据 source 分布（三类：`hard_memory`=硬证据 / `public_claim`=软公开声明，来自认知工作流；`decision_feedback`=软决策回写，来自动作工作流）
- `data/agents/{player_id}/games/{game_id}/workflow_trace_*.json` —— **工作流覆盖**：统计 workflow_id 分布（action_speak/action_vote/action_defense/action_nomination_intent/action_nominate/... 是否覆盖全部动作类型）、每个 trace 的节点完整性（recall/decide/validate/record 四节点齐全）
- `data/agents/{player_id}/games/{game_id}/action_trace.jsonl` —— 每步行动（action_type/model/fallback_used/speech_source/latency）
- `data/agents/{player_id}/games/{game_id}/thoughts.jsonl` —— 思考记录
- `runtime_game_logs/recent_1/llm.jsonl` —— LLM 调用明细（token/cache hit/fallback），注意每次 live 会轮换 recent_1/2/3（只保留最近 3 局），分析完立即拷贝留档

## 已知干扰项（分析时须排除/说明）
- live 模式下 `simulate_game.py` 自动启用 `AI_FAST_LOW_VALUE_ACTIONS=1`（nomination_intent/vote
  走本地启发式、零 LLM）与 `AI_FORCE_PROGRESS_ACTIONS=1`（投票优先赞成以触发处决链）。
  因此 vote/nomination_intent 的"零 LLM token"是既有低价值动作启发式，**不算 PLN-043 的功劳**；
  处决链快速推进也会压缩讨论轮次、影响观点演化节奏，报告须注明。

## 分析维度（产出量化结论）
1. **观点演化是否真实发生**：viewpoints 里是否存在"同一 subject 多条记录、置信度递增或 superseded"？还是每步独立观点无演化？（PLN-043 闭环是否生效）
2. **工作流是否全覆盖**：workflow_trace 的 workflow_id 是否覆盖 speak/vote/nomination/defense 等；每动作是否真走 4 节点
3. **发言质量**（PLN-042 认知 + PLN-041 规则注入）：抽取 speak 内容，判断是否"论证式"（有依据/引用前人发言）vs 早期"断言式/规则幻觉"；有无违反角色能力边界的发言（如洗衣妇称每晚验人）
4. **稳定性**：fallback_rate（目标 0 或极低）、token 消耗、动作合法性（无 workflow_invalid_decision）
5. **对照结论**：开关 on vs off 的差异（观点演化有无、trace 有无、发言论证度、token 增量）

## 输出
写分析报告到 `docs/alpha-1.2-evidence/pln041-043-live-effect-analysis-2026-08-14.md`
（frontmatter 必含：`doc_id: "RPT-020"` / `title: "PLN-041/042/043 live 效果分析报告"` /
`category: "report"` / `role: "[Delta]"` / `status: "published"` / `date: "2026-08-14"` /
`author: "Ravenswood Bluff"`），内容含：
- 对局基本信息（game_id/玩家数/开关/胜负/token/fallback）
- 三项改进逐项效果（对照上表维度，量化数字 + 采样证据）
- 结论：改进是否真实生效，哪些需继续调优
- 遗留问题清单

## 红线
- 只用真实 live 数据，禁止虚构/推测数字；不确定处明确标注
- 不修改任何生产代码（本会话只跑测试 + 分析）
- 不 commit / 不 push
- 分析完更新 docs/README.md 的 RPT 索引 + .codebuddy/memory/YYYY-MM-DD.md 工作日志
```

---

## 用法

1. 新开窗口，整段复制上面的代码块作为首条消息。
2. 快速验证：先跑 `--stop-after day_1` 短局（验证「观点演化 + 工作流覆盖」两个核心点，约几分钟）；完整验证「跨轮次观点 supersede/置信度递增」必须跑到 `game_over`（5 人局，timeout 900s）。
3. 若要单独验证 PLN-042 认知发言，把 `$env:BOTC_WORKFLOW_ACTIONS` 换成 `$env:BOTC_COGNITIVE_SPEAK="1"` 再跑一局。
