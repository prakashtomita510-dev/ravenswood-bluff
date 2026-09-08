---
doc_id: "PLN-046"
title: "Token 预算优化计划：缓存命中率提升 + 输出削减"
category: "planning"
role: "[Delta]"
status: "draft"
date: "2026-08-03"
author: "Ravenswood Bluff"
---

# Token 预算优化计划：缓存命中率提升 + 输出削减

> 目标：在 2 局 5 人真人验收对局（约 49.5 万 tokens）的基础上，将 AI 输入缓存命中率从 ~17% 提升到 60%+，并将输出 token 削减 40%~60%，同时保持对局质量与延迟预算。

---

## 1. 现状与数据诊断

### 1.1 实测消耗（2 局 5 人真人验收）

| 项目 | Tokens | 占总输入/总 token |
|---|---|---|
| Total | 494,542 | 100% |
| Input (Cache hit) | 38,784 | 输入中 16.9% |
| Input (Cache miss) | 190,514 | 输入中 83.1% |
| Output | 265,244 | 总计 53.6% |

### 1.2 成本拆解（deepseek-v4-flash，官方价）

| 计费项 | 单价（¥/M tokens） | 用量 | 成本（¥） | 成本占比 |
|---|---|---|---|---|
| Input 缓存命中 | 0.02 | 38,784 | ~0.0008 | ~0.1% |
| Input 缓存未命中 | 1.0 | 190,514 | ~0.19 | ~26.4% |
| Output | 2.0 | 265,244 | ~0.53 | ~73.5% |
| **合计** | — | 494,542 | **~0.72** | 100% |

**结论**：
1. **成本大头是 Output（73.5%）**：输出 token 占比 53.6%，且单价是输入未命中的 2 倍、命中价格的 100 倍。**削减输出是性价比最高的一步**。
2. **输入未命中是第二大项（26.4%）**：缓存命中率仅 16.9%，提升命中率可同时降成本与延迟。

---

## 2. 机制调查结论（官方口径）

### 2.1 DeepSeek 上下文硬盘缓存

- 默认开启，无需改代码；按 **messages 完整前缀**匹配。
- **每条缓存前缀是独立完整单元，必须整体匹配**（Sliding Window Attention 影响），不能部分匹配。
- 落盘时机：① 请求结束位置 ② 公共前缀检测 ③ 固定 token 间隔。
- 缓存不活跃后**数小时~数天自动清空**；构建耗时秒级，尽力而为不保证 100% 命中。
- 命中率由 `usage.prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` 返回。
- **最大化命中关键**：不变内容放 messages 最前且逐 token 稳定；多轮对话复用完整历史前缀。

### 2.2 DeepSeek V4 思考模式（Thinking）

- **V4 系列默认开启思考，默认 effort=high**；`reasoning_content`（思维链）token **计入输出 token 计费**。
- OpenAI 兼容参数：
  - `thinking: {"type": "enabled" | "disabled"}`（通过 `extra_body` 传递）
  - `reasoning_effort: "low" | "high" | "max"`（flash 映射 low→low、high→high、xhigh→high、max→max）
- **思考模式下 `temperature` / `top_p` / presence_penalty / frequency_penalty 不生效**（传入不报错）。
- 有 `completion_tokens_details.reasoning_tokens` 字段可单独统计思维链 token。

### 2.3 价格

| 模型 | 命中输入 | 未命中输入 | 输出 |
|---|---|---|---|
| deepseek-v4-flash | ¥0.02/M | ¥1/M | ¥2/M |
| deepseek-v4-pro | ¥0.025/M | ¥3/M | ¥6/M |

---

## 3. 根因分析

### 3.1 为什么缓存命中率只有 16.9%

本项目 LLM 调用模式（`ai_agent.act()` / `generate_draft_speech()`）：
- 每次调用 = **一个大 system_prompt + 1 条 user 消息**，无历史轮次。
- system_prompt 内嵌大量**每轮变化的内容**（见 `ai_agent.py` act() 构建顺序）：
  1. persona_block（角色、人格，**稳定**）
  2. deception_budget（日变化）
  3. episodic_text / social_text（记忆，**每轮变**）
  4. visible_state_text（局势摘要，**每轮变**）
  5. action_type / action_context（行动上下文，**每次变**）
  6. tiered_memory_text（分层记忆，**每轮变**）
- DeepSeek 缓存按前缀匹配：**只要记忆/局势/行动部分变化，前缀就在变化点断裂**，只有靠前的稳定段（角色+人格+规则，约 16.9%）能命中。
- 5 个 agent 各自 build system prompt，**跨 agent 也没有共享稳定前缀**，无法互相复用缓存。

### 3.2 为什么输出 token 高达 26.5 万（53.6%）

1. **V4 思考模式默认开启且 effort=high**：项目从未传 `thinking`/`reasoning_effort`，每次调用都触发完整思维链，reasoning token 计入输出。这是最大单一来源。
2. **speak 双重调用**：`speech_cache.pregenerate_batch()` 先调 `generate_draft_speech()`，随后 `act("speak")` 又带草稿调一次 LLM 修正。
3. **辅助 LLM 调用频繁**：
   - `memory_controller.reflect()`（反思，>阈值即调）
   - `archive_phase_memory()`（阶段归档提炼）
   - `claims/_extract_claims_via_llm()`（**每条发言后异步提取身份声明**）
   - evil 频道协调、storyteller 内心独白
4. **无 max_tokens 上限**：`act()` 未传 max_tokens，模型可自由产出长 JSON + 长 reasoning。

---

## 4. 改进方案

### P0 — 削减输出 token（成本占比 73.5%，改动小、见效最快）

#### 4.1 按 action_type 分级控制思考模式与输出上限

在 `LLMBackend.generate()` 增加透传参数 `thinking`（str|None）与 `reasoning_effort`（str|None），`OpenAIBackend` 映射到 `extra_body={"thinking": {...}}` 与 `reasoning_effort`，`MockBackend` 忽略。

策略表（新增常量，如 `AIAgent.LLM_STRATEGY_BY_ACTION`）：

| action_type | thinking | reasoning_effort | max_tokens |
|---|---|---|---|
| vote | disabled | — | 200 |
| night_action | disabled | — | 200 |
| nomination_intent / nominate | disabled | — | 200 |
| speak | enabled | low | 400 |
| defense_speech | enabled | low | 400 |
| reflect / archive / claim | disabled | — | 150 |

- 简单决策（vote/night/nominate）**关闭思考**：这些是低复杂度决策，关闭思考可省大量 reasoning token。
- 发言类**保留思考但降到 low**：维持表达质量同时压缩思维链。
- 兜底：`max_tokens` 一律设上限，防失控。

#### 4.2 精简 JSON 输出

- `_json_schema_for_action()` 中所有 `reasoning` 字段描述追加「≤30 字，只写关键结论」。
- 删除 `speak` schema 中不必要的字段（如保留 `tone` 枚举）。

#### 4.3 削减 speak 双重调用

- 评估 `speech_cache` 草稿质量门槛：草稿校验通过（有 content、非 fallback）时，`act("speak")` 直接使用草稿（仅做 `_sanitize_public_speech_content`），**跳过第二次 LLM 调用**。
- 仅当草稿缺失/失败时才走在线生成。预计 speak 类输出减半。

#### 4.4 降低辅助调用开销

- `claims/_extract_claims_via_llm`：由「每条发言一次 LLM」改为**批量**（每个发言轮次结束时合并提取）或**规则优先**（关键词命中再调 LLM）。`system_prompt=""` 空串调用也可消除。
- `reflect` 的 `_reflection_threshold` 已存在，可结合局数上调；`archive_phase_memory` 的 LLM 提炼仅在观察数 > 3 时触发，可提升到 > 5。

### P1 — 提升输入缓存命中率（成本占比 26.4%，同时降延迟）

#### 4.5 system prompt 前缀稳定化（核心）

将 messages 重组为「三层前缀」结构：

```
messages = [
  {role: "system",  content: <稳定规则层>},      # 不变：角色/人格/规则/JSON schema
  {role: "user",    content: <稳定长上下文>},    # 记忆/社交图谱（同一天内尽量复用）
  {role: "user",    content: <逐次变化短内容>},  # 局势增量 + action_type + action_context
]
```

- **稳定规则层**：把 persona_block、角色能力说明、游戏规则、`_json_schema_for_action` 全部前置，且**同一 agent 内逐 token 不变**（现 persona_block 已接近稳定，但 `strategy_block` 依赖 visible_state 会变，需移出）。
- **变化内容后置**：`visible_state_text`、`tiered_memory_text`、`action_context` 移到最末 user 消息。
- 目标：稳定前缀占比 >70%，命中率从 16.9% → 60%+。

#### 4.6 跨 agent 共享游戏规则前缀

- 抽取「公共游戏规则块」（Trouble Brewing 规则、阶段说明、通用约束）到**所有 agent 完全一致**的字符串，置于 system prompt 最前。
- DeepSeek 缓存全局共享，5 个 agent 可复用同一段规则前缀，进一步放大命中。

#### 4.7 避免变量污染前缀

- 检查 `persona_block` 中 `strategy_block`（night_action 等会带 `_get_evil_strategic_summary`，随 visible_state 变）——**移出稳定段**。
- `_deception_budget_prompt` 内容按日变化，若在稳定段后部，可保留（其后还有动态段，不影响稳定段命中），但若其前存在变化点则需重排。

### P2 — 度量与回归（保障可持续优化）

#### 4.8 usage 解析扩展

- `LLMResponse.usage` 解析补充：`prompt_cache_hit_tokens`、`prompt_cache_miss_tokens`、`completion_tokens_details.reasoning_tokens`。
- `_record_action_metric()` 追加上述字段，`action_metrics` / `game_debug_logger` 完整记录。
- 新增基准脚本 `scripts/benchmark/token_cost_metrics.py`：按对局汇总 total / hit / miss / output / reasoning，输出命中率与成本估算。

#### 4.9 回归保障

- `MockBackend` 签名保持兼容（thinking/effort 透传参数可忽略）。
- 新增单测：各 action 传入的 thinking/effort/max_tokens 符合策略表；system prompt 稳定段在相同 agent 不同 action 间前缀一致（快照断言）。
- live 验收：跑 1 局 5 人 mock 对局对比改造前后 usage 快照。

---

## 5. 预期收益估算（乐观/保守）

| 指标 | 现状 | 保守 | 乐观 |
|---|---|---|---|
| 缓存命中率 | 16.9% | 40% | 65% |
| 输入未命中 tokens | 190,514 | ~114K | ~80K |
| 输出 tokens | 265,244 | ~160K | ~106K |
| 每局总成本 | ~¥0.72/2局 | ~¥0.40/2局 | ~¥0.26/2局 |

---

## 6. 落地步骤

1. **P0-4.1**：`base_backend.py` / `openai_backend.py` / `mock_backend.py` 增加 thinking/reasoning_effort 透传；`ai_agent.py` 增加策略表并按 action 传参；`memory_controller.py` / `claims` 传 max_tokens 与关闭思考。
2. **P0-4.2**：精简 `_json_schema_for_action` 的 reasoning 描述与多余字段。
3. **P0-4.3**：`speech_cache.py` 草稿复用逻辑（跳过二次 LLM）。
4. **P0-4.4**：claim 提取批量/规则优先改造。
5. **P1-4.5~4.7**：重构 `prompt_factory.py` 与 `ai_agent.act()` 的 prompt 组装为三层结构；抽取公共规则前缀常量。
6. **P2-4.8~4.9**：usage 解析扩展 + 基准脚本 + 单测。
7. 全量回归：`pytest tests -q` + `ruff check src tests` + mock 对局对比。

## 7. 风险与权衡

| 风险 | 缓解 |
|---|---|
| 关闭思考后简单决策质量下降 | 仅对 vote/night/nominate 关闭；保留 A/B 开关 `BOTC_THINKING_MODE=auto|disabled|low` |
| 发言保留思考但 effort=low 可能让表达变平淡 | 先在 defense_speech/speak 用 low，live 对比再决定是否回 high |
| system prompt 重构影响现有测试 | 现有测试断言的是行为/JSON 结构，非 prompt 文本；仅 `test_deduction_engine` 断言「day_discussion in messages[0]」等少数用例需同步（DeductionEngine 单独维护，不受 act 重构影响） |
| DeepSeek 缓存不保证 100% 命中 / 数小时过期 | 命中率目标 60% 为尽力而为；主要收益来自输出削减，不依赖缓存 |
| 跨 agent 公共前缀若与现有 prompt 融合不当影响角色一致性 | 公共块只放中性规则文本，不放任何 agent/阵营相关内容 |

## 8. 验收标准

- [ ] 两局 5 人 live 对局 total tokens ≤ 30 万（现状 49.5 万）。
- [ ] 缓存命中率 ≥ 50%（现状 16.9%）。
- [ ] 输出 token 占总比 ≤ 40%（现状 53.6%）。
- [ ] `pytest tests -q` 全绿；`ruff check src tests` 零告警。
- [ ] 发言自然度 / 决策质量经 1 次真人局验收不低于现状（对比 transcript）。
