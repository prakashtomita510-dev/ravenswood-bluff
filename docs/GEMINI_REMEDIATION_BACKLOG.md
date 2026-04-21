# Gemini 遗留问题收口清单

**更新时间**: 2026-04-13  
**适用范围**: Alpha 0.2 / Wave 3 相关 AI 智能、视角隔离、记忆与评估体系  
**目的**: 记录 Gemini 交接工作中已补齐、部分补齐、仍待处理的问题，方便后续按优先级持续收口。

---

## 一、结论摘要

当前状态不是“Gemini 留下的所有漏洞都已完全补完”，而是：

- 一批高风险漏洞已经补掉
- 一批“文档写满但实现未满”的问题已经被纠偏
- 剩余问题主要集中在“进一步收紧架构边界”和“把轻量门禁提升为长局/趋势级门禁”

换句话说，项目已经从“需要救火”进入“需要继续打磨和收口”的阶段。

---

## 二、已补齐或已显著收口

### 1. 顺序投票链的真实功能漏洞

**状态**: 已补齐  
**问题描述**:
- `_run_defense_and_voting` 中 `votes_cast / yes_votes` 存在未初始化即使用的风险
- 会导致顺序投票链不可信

**当前结果**:
- 已在 `src/orchestrator/game_loop.py` 中修复初始化与累加逻辑
- 已补专项回归

**相关文件**:
- [game_loop.py](d:/鸦木布拉夫小镇/src/orchestrator/game_loop.py)
- [test_game_loop.py](d:/鸦木布拉夫小镇/tests/test_orchestrator/test_game_loop.py)

---

### 2. 情节记忆只有结构没有写入

**状态**: 已补齐主链  
**问题描述**:
- `episodic_memory` 之前只有 `get_summary()` 接入 prompt
- 但主流程没有稳定把阶段记忆写入 `Episode`

**当前结果**:
- 已增加 `archive_phase_memory()` 钩子
- 阶段切换前会把当前阶段观察与思考提炼为 `Episode`
- `WorkingMemory` 也增加了 `clear_transient()`，避免跨阶段印象被一并清空

**相关文件**:
- [base_agent.py](d:/鸦木布拉夫小镇/src/agents/base_agent.py)
- [ai_agent.py](d:/鸦木布拉夫小镇/src/agents/ai_agent.py)
- [working_memory.py](d:/鸦木布拉夫小镇/src/agents/memory/working_memory.py)
- [game_loop.py](d:/鸦木布拉夫小镇/src/orchestrator/game_loop.py)
- [test_agent_reasoning.py](d:/鸦木布拉夫小镇/tests/test_agents/test_agent_reasoning.py)
- [test_memory.py](d:/鸦木布拉夫小镇/tests/test_agents/test_memory.py)

---

### 3. Wave 3 文档与任务板虚高完成度

**状态**: 已纠偏  
**问题描述**:
- 交接文档和任务板把部分完成写成了完全完成
- 尤其是“绝对信息隔离”“三层记忆架构”“Wave 3 DONE”等表述过满

**当前结果**:
- 已将完成状态调整为更诚实的 `PARTIAL`
- 已把未落地门禁从“已通过”改成“待补/待验证”

**相关文件**:
- [HANDOVER_ALPHA_0.2.md](d:/鸦木布拉夫小镇/docs/HANDOVER_ALPHA_0.2.md)
- [wave-3-task-board.md](d:/鸦木布拉夫小镇/docs/alpha-0.2-plan/wave-3-task-board.md)

---

### 4. Wave 3 验收脚本缺失

**状态**: 已补齐第一版  
**问题描述**:
- 任务板里提到的 `wave3_acceptance.py / ai_eval_acceptance.py` 原先并不存在

**当前结果**:
- 已新增 Wave 3 聚合门禁和 AI 评估门禁
- 已补测试验证脚本可运行

**相关文件**:
- [wave3_acceptance.py](d:/鸦木布拉夫小镇/scripts/wave3_acceptance.py)
- [ai_eval_acceptance.py](d:/鸦木布拉夫小镇/scripts/ai_eval_acceptance.py)
- [test_wave3_acceptance.py](d:/鸦木布拉夫小镇/tests/test_orchestrator/test_wave3_acceptance.py)

---

### 5. 指标级 AI 门禁完全缺失

**状态**: 已补齐轻量版  
**问题描述**:
- 原先只有“脚本能跑”的门禁，没有真正的 AI 指标门槛

**当前结果**:
- 已新增轻量指标评估脚本
- 当前覆盖：
  - `ai_none_nomination_rate`
  - `ai_strong_nomination_rate`
  - `persona_diversity_score`

**相关文件**:
- [ai_evaluation.py](d:/鸦木布拉夫小镇/scripts/ai_evaluation.py)
- [test_ai_evaluation.py](d:/鸦木布拉夫小镇/tests/test_orchestrator/test_ai_evaluation.py)

---

## 三、必修项

这些属于“虽然不一定会立刻炸，但必须继续推进，否则 Wave 3 不能算真正站稳”。

### P0-1. 将 AI 视角隔离从软隔离推进到硬隔离

**状态**: 已补齐主链  
**当前结果**:
- `BaseAgent.act()` / `observe_event()` / `think()` / `archive_phase_memory()` 已统一切到：
  - `AgentVisibleState`
  - `AgentActionLegalContext`
- `GameOrchestrator` 和 `InformationBroker` 已负责构造玩家可见状态与合法动作快照
- `AIAgent` 的 prompt、动作上下文、目标打分、提名/投票选择、兜底决策、事件文本格式化都已改成基于：
  - `AgentVisibleState`
  - `AgentActionLegalContext`
- Wave 3 相关 acceptance 脚本已能直接从 `scripts/` 入口运行，不再依赖完整 `GameState` 输入链

**剩余增强项**:
- 继续补更强的 prompt/上下文断言，防止后续开发者把隐藏字段重新接回 AI
- 把更多脚本化场景扩展为更长局的玩家视角回归

**相关文件**:
- [base_agent.py](d:/鸦木布拉夫小镇/src/agents/base_agent.py)
- [ai_agent.py](d:/鸦木布拉夫小镇/src/agents/ai_agent.py)
- [game_state.py](d:/鸦木布拉夫小镇/src/state/game_state.py)
- [information_broker.py](d:/鸦木布拉夫小镇/src/orchestrator/information_broker.py)
- [game_loop.py](d:/鸦木布拉夫小镇/src/orchestrator/game_loop.py)

---

### P0-2. 把轻量指标门禁升级成趋势化门禁

**状态**: 已补齐  
**现状**:
- `ai_evaluation.py` 现在已扩成多局、多轮、分压力档位评估
- 当前覆盖：
  - `ai_none_nomination_rate`
  - `ai_strong_nomination_rate`
  - `nomination_trend_monotonicity_rate`
  - `vote_trend_monotonicity_rate`
  - `persona_diversity_score`
  - `multi_game_stability_score`
  - `front_position_nomination_bias_rate`
  - `ambiguous_nomination_diversity_score`
  - `aggressive_vote_push_rate`
  - `silent_vote_restraint_rate`
  - `cooperative_follow_rate`

**当前结果补充**:
- 已新增 `scripts/long_game_ai_acceptance.py`
- 已补跨日长局行为门禁，覆盖：
  - `long_game_persona_diversity_score`
  - `long_game_stability_score`
  - `aggressive_nomination_rate`
  - `silent_nomination_rate`
  - `aggressive_vote_push_rate`
  - `silent_vote_restraint_rate`

**建议动作**:
1. 继续扩展到更长对局和更多局数
2. 补 `ai_vote_alignment_rate`、顺位偏置、跟票率等行为级指标
3. 增加“连续多局不出现机械前置位提名”的正式门槛

---

### P0-3. 社交图谱与长期记忆的长局级验证仍不足

**状态**: 已补齐  
**现状**:
- 有 `social_graph`
- 有 `episodic_memory`
- 有阶段归档

**当前结果补充**:
- 已通过 `scripts/long_loop_memory_acceptance.py`
- 已通过 `scripts/long_game_ai_acceptance.py`
- 当前已覆盖：
  - 跨阶段 `Episode` 递增
  - 跨日摘要保留
  - trust 分值跨日积累
  - 长局社交轨迹一致性

**建议动作**:
1. 增加长局模拟下的 Episode 数量与摘要质量断言
2. 记录并检查 trust score 的轨迹变化
3. 给“因多次矛盾而降低信任”的行为补专项回归

---

## 四、应修项

这些不是当前最危险的洞，但继续放着会拖慢 Wave 3 收尾。

### P1-1. 提名/投票的真人感仍需更强门禁

**状态**: 已显著收口  

**当前结果**:
- 已有 `none` 提名能力
- 已有短局行为画像门禁
- 已有长局行为门禁：
  - 激进人格在模糊与强信号场景下更愿意推进提名
  - 沉默人格更保守，且早期投票更克制

**后续方向**:
1. 继续引入更复杂的群体压力与残局场景
2. 扩展真人前端整局 playtest 验证

---

### P1-2. Persona 多样性仍是“能看出差异”，还不是“长期稳定人格”

**现状**:
- archetype 已有
- persona prompt block 已接入

**问题**:
- 当前更多是门槛和语气差异
- 长局人格稳定性与角色叠加层仍比较轻

**建议动作**:
1. 扩展 persona 原型矩阵
2. 给角色叠加层更多显式偏置
3. 增加长局 persona 漂移检测

---

### P1-3. 日志里的 “Could not find platform independent libraries <prefix>”

**状态**: 已知环境噪声  
**问题**:
- 当前不影响返回码与主要功能
- 但会污染 acceptance 输出

**建议动作**:
1. 后续单独检查 `.venv` / Python 包装器环境
2. 如可行，清掉该噪声，避免掩盖真实错误

---

## 五、增强项

这些不是 Gemini 遗留漏洞本身，但已经很适合放进后续 Wave。

### P2-1. 将 `AgentVisibleState` 推成真正的唯一玩家推理上下文

目标是最终做到：
- AI 只吃 `AgentVisibleState`
- 合法性判断通过显式 helper 注入
- 不再把完整 `GameState` 传进主推理链

---

### P2-2. 给 Wave 3 增加更强的多局评估资产

例如：
- 多局 mock simulation
- 多人格对照局
- 典型失真场景集合

---

### P2-3. 人格、记忆、社交图谱的前端可观测性

例如：
- impression 面板
- suspicion / trust 轨迹
- 回合摘要展示

---

## 六、建议执行顺序

建议接下来按这个顺序继续推进：

1. **P1-2**：继续增强 persona 长局稳定性与角色叠加层
2. **P1-3**：清理环境噪声，减轻 acceptance 输出污染
3. **P2**：补更强可观测性与前端呈现

---

## 七、当前判断

如果按“Gemini 的工作是否已经被彻底补洞”来判断：

- **P0 级问题已经补完**
- **最关键的功能漏洞和最容易误导人的完成度问题，已经补掉了**
- **剩下的是继续增强和打磨，不再是大面积返工**

这意味着当前代码基线已经更可信，可以继续推进 Alpha 0.2，而不是被 Gemini 的遗留问题卡住。
