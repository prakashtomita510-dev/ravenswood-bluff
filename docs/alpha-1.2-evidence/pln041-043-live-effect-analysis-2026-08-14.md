---
doc_id: "RPT-020"
title: "PLN-041/042/043 live 效果分析报告"
category: "report"
role: "[Delta]"
status: "published"
date: "2026-08-14"
author: "Ravenswood Bluff"
---

# PLN-041/042/043 live 效果分析报告

> 覆盖：2026-08-14，两局真实 LLM（DeepSeek deepseek-v4-flash）5 人完整对局（game_over）统计口径对照：
> 基线局（全部开关 off）vs 改进局（`BOTC_WORKFLOW_ACTIONS=1`）。
> 关联：PLN-041（D016/RPT-017）、PLN-042（D018/RPT-018）、PLN-043（D019/RPT-019）。

---

## 1. 摘要

| 结论 | 判定 |
|------|------|
| PLN-043 观点演化闭环真实生效 | ✅ 26 条观点（6 创建 / 20 更新快照），置信度单调递增 0.41→0.77，跨 3 天演化（时间戳验证）；基线局零观点零 trace（开关 off 零污染） |
| PLN-043 全动作工作流覆盖 | ✅ 80/80 动作有 workflow trace，覆盖 5 类工作流；76/80 四节点完整；validate 零非法决策 |
| PLN-043 稳定性 | ⚠️ 4/80（5%）工作流 decide 节点 TimeoutError——**根因：`ToolCallNode` 默认 10s 超时 < live LLM 实际延迟**；回退原路径后 2 个动作挽回、2 个最终 fallback |
| PLN-041 规则静态注入 | ✅ 两局 LLM 请求 messages 均含规则书（基线 22/119、改进 31/119 命中"能力边界/阵营红线/角色能力"）；动态检索因 DeepSeek embeddings 端点 404 自动降级未启用 |
| PLN-042 认知工作流 | ➖ 本次两局 `BOTC_COGNITIVE_SPEAK` 均 off（未直接验证）；但观点-证据模型在动作工作流路径下运行正常（76 条 soft evidence、置信度封顶未超 0.95） |
| 发言质量对照 | 两局均呈现论证式发言（当前 prompt 已含 PLN-041 规则注入等多重防线）；改进局发言略结构化（recall 观点摘要进 strategic_thought），未见显著鸿沟；基线局出现 2 条"机械复述"发言 |
| token/fallback 对照 | 改进局 per-action token 1660.9 < 基线 1849.8；fallback 2.5% < 9.3%（两局 fallback 根因均为 deepseek 推理模式下 `finish_reason=length` 空响应，非开关差异） |

---

## 2. 对局基本信息

| 项 | 基线局（off） | 改进局（on） |
|----|--------------|--------------|
| game_id | `673cd086-4ece-4d69-8d19-2ecac14af0a3` | `7341fec5-7602-4bfe-8b65-3c41e137d506` |
| 时间 | 17:27:15–17:31:05 | 17:31:27–17:36:10 |
| 玩家数 / 天数 | 5 / 2 | 5 / 3 |
| 角色 | p1 送葬者 / p2 恶魔 / p3 投毒者 / p4 占卜师 / p5 洗衣妇 | p1 猎手 / p2 僧侣 / p3 荡妇 / p4 恶魔 / p5 共情者 |
| 胜负 | good（恶魔 p2 于 day1 被处决） | good（恶魔 p4 于 day2 被处决） |
| 动作数 | 54 | 80 |
| AI token（动作层） | 99,887 | 132,874 |
| AI token（llm.jsonl 全量） | 215,088 | 305,063 |
| per-action token | 1849.8 | 1660.9 |
| fallback | 5（9.3%） | 2（2.5%） |
| 前缀缓存命中率 | 54.78% | 53.83% |
| 产物 | action_trace + thoughts（**零 viewpoints / 零 trace** ✓） | action_trace + thoughts + **viewpoints（26 条）+ workflow_trace（80 个）** |

> 两局无 `--seed`（`simulate_game.py` 不支持），角色/座位随机，属**统计口径对照**；局长不同（2 天 vs 3 天）使 token 总量不可直接比，采用 per-action 口径。
> 干扰项：live 模式自动启用 `AI_FAST_LOW_VALUE_ACTIONS=1`（vote/nomination_intent 零 LLM 为既有启发式，**非 PLN-043 功劳**）与 `AI_FORCE_PROGRESS_ACTIONS=1`（投票优先赞成以推进处决链，压缩讨论轮次、影响观点演化节奏）。

---

## 3. PLN-043 全动作声明式工作流效果（本次对照核心）

### 3.1 观点演化闭环：真实发生 ✅

| 指标 | 数值 |
|------|------|
| 观点总数（5 玩家） | 26（p1:2 / p2:7 / p3:4 / p4:5 / p5:8） |
| 创建 / 更新快照 / superseded | 6 / 20 / 0 |
| evidence 总量 | 76，全部 `soft` + `decision_feedback` |
| 同 subject 演化组数 | 6 组 |

- **置信度递增轨迹**（p2→P1，7 条快照）：`0.41 → 0.47 → 0.53 → 0.59 → 0.65 → 0.71 → 0.77`，单调递增，符合"决策反复提名同一人→怀疑度上升"的演化语义。
- **跨天演化**：观点 `created_at` 集中于 day1（17:31–17:32），`updated_at` 延伸至 17:33–17:34+（day2–day3），证明演化发生在整局进程中，而非单轮一次性。
- **来源唯一性符合设计**：改进局未开 `BOTC_COGNITIVE_SPEAK`，观点全部由 `record` 节点决策回写创建（`decision_feedback`）——与 RPT-019 修复后的"决策创建软印象观点作演化起点"设计一致。
- **基线局对照**：零 viewpoints.jsonl、零 workflow_trace（开关 off 零污染），确认产物完全由开关驱动。
- ⚠️ **已知缺陷**：`ViewpointStore.update_confidence` 追加快照时**不更新 `day_number` 字段**（保留创建日 1），导致 viewpoints.jsonl 中所有更新快照 `day_number=1`；演化真实性需用时间戳佐证（本报告已用 `updated_at` 验证）。

### 3.2 工作流覆盖：80/80 全覆盖 ✅

| workflow_id | trace 数 | decide 输出 action |
|-------------|---------|-------------------|
| action_vote | 30 | vote 30 |
| action_nomination_intent | 25 | nomination_intent 25 |
| action_speak | 15 | speak 12（3 个 decide 超时未产出） |
| action_defense | 6 | defense_speech 5（1 个 decide 超时未产出） |
| action_night | 4 | night_action 4 |
| **合计** | **80** | |

- **节点完整性**：76/80 四节点（recall/decide/validate/record）齐全；4 个 incomplete 均为 decide 节点超时中断（见 §3.3）。
- **合法性**：`validate` 零 `workflow_invalid_decision`（无非法决策进入游戏）。
- **record 回写**：24 次创建/更新观点、52 次跳过（本地启发式决策无 reasoning 或 reasoning 无可提取玩家，符合设计）。
- **trace 可观测性**：每动作独立 `workflow_trace_{ts}.json`，含四节点 inputs/outputs/duration/error 与 finish status，可完整回放。

### 3.3 稳定性：decide 节点 10s 超时是主要痛点 ⚠️

**现象**：4/80（5%）工作流 `status=failed`，全部为 `decide` 节点 `TimeoutError`（p1 day3 speak、p4 day2 speak、p5 day3 speak、p5 day3 defense）。

**根因**（代码核查）：`ToolCallNode.timeout_seconds` 默认 **10.0s**（`src/agents/workflow/workflow.py:50`），而 `action_workflows.py` 构造节点时未覆盖该值。live 模式下 DeepSeek speak/defense 实测延迟 4–19.8s（成功动作平均 5–8s，最长 19.8s），10s 预算对复杂发言明显过紧。

**回退链路验证**（失败回退原路径设计生效）：
- 4 个超时动作在 act() 层 `wf_decision.get("action")` 为空 → 回退原路径重新决策；
- p1 day3 speak（trace 失败）→ 原路径重试成功（tool_calling，16.4s，6,804 tokens，fallback=False）；
- p4 day2 speak（trace 失败）→ 原路径重试成功（tool_calling，6.2s）；
- p5 day3 speak + defense → 原路径重试仍 `finish_reason=length` 空响应 → 最终 fallback（2 次）。
- **代价**：超时动作的 LLM 请求被取消后重发，token 双倍消耗。

### 3.4 token 与 fallback 对照

| 指标 | 基线 | 改进 | 解读 |
|------|------|------|------|
| per-action token | 1849.8 | 1660.9 | 改进局略低（vote/nomination_intent 占比更高：55/80 vs 36/54） |
| llm 层总 token | 215,088 | 305,063 | 差异主要来自局长（3 天 vs 2 天）+ 4 次超时重试 |
| 缓存命中率 | 54.78% | 53.83% | 基本持平（观点摘要仅进 user 段，system 前缀稳定） |
| fallback_rate | 9.3%（5/54） | 2.5%（2/80） | 两局 fallback 根因相同（见下），样本小不可归因开关 |
| `finish_reason=length` 次数 | 17 | 14 | deepseek-v4-flash 推理模式下 completion_tokens 打满 2000、content 为空——**两局共有的既存问题** |

---

## 4. PLN-041 规则注入与检索效果（两局同代码，非对照变量）

- **规则静态注入生效**：两局 LLM 请求 messages 中均检出规则书关键字（基线 22/119、改进 31/119 命中"能力边界 / 阵营红线 / 角色能力 / 规则书"），注入位置在 user 首段 stable_context（非 system 层，符合 D016 同局稳定设计）。
- **发言合规**：两局抽样发言未见角色能力边界违反（无"洗衣妇每晚验人""士兵开刀"类幻觉），阵营红线（邪恶不公开自曝）在抽样的 evil 私聊/公开发言中均守住。
- **动态检索未启用**：DeepSeek `POST /embeddings` 返回 404，后端自动禁用向量检索（"disabling embeddings and continuing without vector retrieval"）——live 动态 RAG 实际降级为不启用，规则静态注入是实际生效的防幻觉防线。
- **残余问题**：基线局出现 2 条"机械复述"发言（直接抛出记忆摘要："D2讨论：p4死亡引发复盘，p3质疑p1攻击性…"），违反 system prompt 第 5 条（拒绝机械复述），speech sanitizer 未拦截——提示词约束层面的既存缺口。

---

## 5. PLN-042 认知工作流相关观察（间接验证）

本次两局 `BOTC_COGNITIVE_SPEAK` 均 off，未直接验证认知工作流，但观察到：

- **观点-证据模型在动作工作流路径下运行正常**：26 条观点全部经 `ViewpointEngine` 确定性置信度计算（soft 单证据 0.41 起步，逐次 +0.06 递增），封顶未超 0.95，符合 D018 红线（LLM 不参与论证数值）。
- **互补路径有效**：D019"无认知工作流时由决策回写创建软印象观点"的设计在 live 中真实产生演化起点（6 个创建），解决了 RPT-019 踩坑 1 记录的观点库恒空问题。
- **演化维度单一**：superseded=0——所有回写证据均为"提名即怀疑"的单向 soft 证据，无"信任/洗白"反向证据，观点只会同向增强不会冲突推翻。这与 PLN-042 的 hard/soft 分级互补（hard 证据来自认知工作流，本次未启用）。

---

## 6. 发言质量对照（采样证据）

> 改进局样本取自 workflow trace 的 `decide.outputs.decision.content`；基线局无 trace，取自 llm.jsonl 自然语言 content（已过滤说书人报幕与 JSON 工具参数）。

**基线局（off）典型发言**：
- ✅ 论证式（占多数）："p2 在被提名后反手提名 p1，而且自己给自己投了赞成票，这个行为很反常，像是在搅浑水…"（引用具体行为+推理）
- ⚠️ 机械复述 ×2："D2讨论：p4死亡引发复盘，p3质疑p1攻击性，p4对p5态度转变，p5怀疑p3。"（直接抛记忆摘要）

**改进局（on）典型发言**：
- ✅ 论证式且更结构化："场上最可疑的是 Player 5。他一边说自己有信息但藏着不亮，一边又急着指责我不亮信息——这种双标太明显了…目前我比较愿意暂时信任 Player 3，他的发言比较理性，强调容错率低、不轻易推人…"（引用具体人+具体话+对比论证）
- ✅ 观点演化体现："p2被5票送上去之后反手提名p3，这个反打有点意思…我这边坐拥共情信息，邻座有1个邪恶，p2和p3里应该至少有一个是坏的。"（观点与推理融合）

**结论**：两局发言均为论证式为主（当前 prompt 体系已含 PLN-041 规则注入与多轮优化，非 PLN-043 独有贡献）；改进局发言呈现更强的"引证+对比+分层结论"结构，与 recall 节点观点摘要（strategic_thought）注入 LLM 一致。因样本小、局长不同，此差异为趋势性观察而非严格归因。

---

## 7. 结论

1. **PLN-043 核心目标达成**：全动作工作流在 live 中全覆盖（80/80），观点演化闭环真实运行——创建→跨天更新→置信度递增轨迹全部落盘，开关 off 零污染零回归。
2. **行为兼容设计经受住 live 考验**：4 次 decide 超时触发"回退原路径"，2 个动作被挽回，未造成对局中断或非法决策。
3. **主要短板在工程参数而非架构**：decide 节点 10s 默认超时是 5% 工作流失败 + token 双倍消耗的直接原因，需对齐动作级预算。
4. **PLN-041 静态防线在 live 中实际生效**（规则注入两局均命中），动态检索因 embeddings 端点 404 未启用——live 环境的防幻觉收益主要来自静态注入。
5. **PLN-042 认知工作流本次未直接验证**（开关 off），但其观点-证据模型在动作工作流路径下运行正常，为后续"speak 认知与动作工作流统一"（RPT-019 建议 1）提供了兼容性证据。

---

## 8. 遗留问题清单

| # | 级别 | 问题 | 建议 |
|---|------|------|------|
| 1 | **P1** | `ToolCallNode.timeout_seconds` 默认 10s 对 live LLM 过紧 → 4/80 工作流 decide 超时失败、回退重试烧双倍 token | `action_workflows.py` 构造节点时按动作类型覆盖 timeout（如对齐 `timeout_budget_ms`/difficulty_preset，speak 类 ≥60s） |
| 2 | P2 | `ViewpointStore.update_confidence` 追加快照不更新 `day_number`（全为创建日）→ viewpoints.jsonl 时间维度失真 | update 时同步 day/round（或改字段为 `last_updated_day`） |
| 3 | P2 | deepseek-v4-flash 推理模式下 `finish_reason=length` 频发（两局 14–17 次），content 空→fallback（两局 fallback 主因） | 评估 max_tokens/reasoning 预算配置或对 length+空 content 增加"丢弃 reasoning 重试"策略 |
| 4 | P2 | 基线局 2 条"机械复述"发言（直接抛记忆摘要）违反发言多样性约束 | speech_sanitizer 增加摘要式发言拦截规则；观察 PLN-042/043 开启后是否缓解 |
| 5 | P2 | p5 day3 defense fallback 的 `speech_source=tool_calling` 而 `fallback_used=True`（指标口径不一致） | 统一 fallback 路径的 speech_source 标记 |
| 6 | P3 | superseded=0：观点演化只有单向增强无冲突推翻（decision_feedback 证据单向） | record 节点增加"信任/洗白"类反向证据回写；或依赖 PLN-042 认知路径补充 hard 证据 |
| 7 | P3 | workflow_trace 体积大（每 trace 内嵌完整 visible_state，单文件 30KB+，80/局） | trace 精简（ctx 摘要化）或滚动清理策略 |
| 8 | — | 干扰项确认：`AI_FAST_LOW_VALUE_ACTIONS`/`AI_FORCE_PROGRESS_ACTIONS` 使 vote/nomination_intent 零 LLM（既有启发式）且处决链快推压缩讨论轮次 | 后续"观点演化质量"专项评估建议在关审计推进的配置下复测 |

---

## 9. 数据归档

- 对局产物：`data/agents/{p1..p5}/games/{game_id}/`（两局 game_id 见 §2，改进局含 viewpoints/workflow_trace）
- runtime 日志留档：`tmp_work/runtime_baseline_673cd086/`、`tmp_work/runtime_workflow_on_7341fec5/`（`runtime_game_logs/` 仅保留最近 3 局，已轮换）
- 分析脚本与中间结果：`tmp_work/analyze_live*.py`、`tmp_work/analysis_result.json` 等
- 对局控制台输出：`tmp_work/live_analysis_baseline.txt`、`tmp_work/live_analysis_workflow_on.txt`
