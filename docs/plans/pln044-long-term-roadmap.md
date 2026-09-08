---
doc_id: "PLN-044"
title: "项目长期路线图：从 Alpha 1.2 到 Beta 2.0（分阶段实现）"
category: "planning"
role: "[Delta]"
status: "published"
date: "2026-09-08"
updated: "2026-09-08"
author: "Ravenswood Bluff"
tags: ["roadmap", "milestone", "planning", "agent-native", "botc"]
related:
  - "pln045-execution-handbook.md"
  - "pln043-all-action-workflow-plan.md"
  - "../alpha-1.2-evidence/pln041-043-live-effect-analysis-2026-08-14.md"
  - "../releases/alpha-1.2-release-checklist.md"
---

# 项目长期路线图：从 Alpha 1.2 到 Beta 2.0（PLN-044）

> **定位**：本文件是项目跨版本的长期演进总纲——定义现状、愿景、方向决策与五个里程碑的分阶段计划。
> **配套**：迭代执行手册见 [pln045-execution-handbook.md](pln045-execution-handbook.md)（PLN-045）。后续 agent 按「PLN-044 定方向 → PLN-045 定流程」即可自主完成迭代升级。
> **滚动机制**：本路线图按里程碑滚动细化——每个里程碑启动时将其任务板细化为独立 PLN 文档（见 §11），远期阶段（1.4/1.5/2.0）当前为方向级规划。
>
> **目录**：§1 现状全景 · §2 愿景与成功标准 · §3 演进策略与方向决策 · §4 里程碑总览 · §5 Alpha 1.2.x 淬火 · §6 Alpha 1.3 深潜 · §7 Alpha 1.4 新月 · §8 Alpha 1.5 广场 · §9 Beta 2.0 开门 · §10 跨阶段红线 · §11 滚动规划机制 · §12 相关文档

---

## 1. 现状全景（2026-09 快照）

### 1.1 版本与质量基线

| 项 | 状态 |
|----|------|
| 当前版本 | Alpha 1.2「觉醒之鸦」(`alpha1.2-awakening`, pyproject 0.2.0)，tag 已打 |
| 测试基线 | 快速单测（`-m "not slow"`）710 passed / 0 failed；全量含 slow 676（2026-08-13 口径，以 PROGRESS 最新登记为准） |
| 静态质量 | `ruff check` 0 告警；`ruff format --check` 全绿；doc health RC=0 |
| 聚合门禁 | `alpha1.1_acceptance.py` 10/10 全绿（含 PLN-041 新增检索/工作流 gate） |
| CI | GitHub Actions：lint + 快速测试 + doc health（slow 排除，timeout 25min） |
| live 实测 | DeepSeek 5 人局完整 game_over：fallback 2.5%、per-action token 1660.9、前缀缓存命中 53.83%、观点演化闭环生效（26 观点、置信度 0.41→0.77 跨天递增，RPT-020） |

### 1.2 已建成能力资产

| 层 | 资产 | 关键证据 |
|----|------|---------|
| 游戏引擎 | TB 剧本全角色、完整阶段机、提名/投票/处决、胜利判定、快照回放、SQLite 持久化 | alpha1.0 起稳定 |
| Agent 原生化 | 8 行动工具 + 4 世界感知工具 + 记忆工具；三层前缀缓存；LLM 策略表（简单动作零 thinking、草稿复用 0 token） | D012-D015，token -62% |
| 工作流/认知 | Workflow DSL/引擎/trace；检索基础设施（BM25+Faiss 可选+RRF，Recall@5=1.0）；规则知识库静态注入；观点-证据模型（hard/soft+确定性置信度+门控）；全动作声明式工作流（8 动作 recall→decide→validate→record）；观点演化闭环 | D016-D019，RPT-017/018/019/020 |
| 进化体系 | 跨局档案（战绩/复盘/反思/学习/策略）+ tendency 四维画像 + 共享经验池 + 说书人档案 | D013/D014 |
| 差异化 | 12 维行为指纹基准 + tendency 标定（polarized Δ+0.03）+ 盲测样本导出/评分工具 | PLN-040 T1-T5 |
| 工程体系 | MockBackend-first 测试、10 gate 验收、CR/RPT/DECISIONS 文档闭环、harness 五子系统 | D001-D011 |
| 部署 | Docker / 云部署指南 / 局域网联机 / 玩家与说书人前端 | REF-001/003 |

### 1.3 遗留问题清单

来源：RPT-020 §8 + PROGRESS 任务板，按优先级：

| # | 级别 | 问题 |
|---|------|------|
| 1 | **P1** | `ToolCallNode` 默认 10s 超时 < live LLM 延迟 → 4/80 工作流 decide 超时失败 + token 双倍消耗 |
| 2 | P2 | 观点更新快照 `day_number` 不随演化更新（时间维度失真） |
| 3 | P2 | deepseek 推理模式 `finish_reason=length` 空响应频发（14-17 次/局，fallback 主因） |
| 4 | P2 | 基线局 2 条「机械复述」发言未拦截（speech_sanitizer 缺摘要式检测） |
| 5 | P2 | fallback 路径 `speech_source` 指标口径不一致 |
| 6 | P3 | 观点演化单向（superseded=0，无信任/洗白反向证据） |
| 7 | P3 | workflow_trace 体积大（单文件 30KB+，内嵌全量 visible_state） |
| 8 | — | 三开关并存（`BOTC_WORKFLOW_ACTIONS` / `BOTC_COGNITIVE_SPEAK` / `BOTC_VIEWPOINTS`）语义复杂 |
| 9 | — | 新能力（工作流/认知/观点）**默认 off**——已建成但未默认启用 |
| 10 | — | 进化有效性 A/B 未达 M4（Δ+2pp，RPT-016 诚实负结果）；盲测 M3 待真人标注 |
| 11 | — | 动态 RAG 未启用（DeepSeek embeddings 端点 404 自动降级） |
| 12 | — | RPT-020/REV-011/blind_ready3 等上次会话收尾文档未提交 |

### 1.4 短板与机会

**短板**：
- 单剧本（Trouble Brewing）——内容天花板，长期可玩性受限
- AI「像真人」尚未系统证实——盲测 M3 未收口，进化有效性 M4 未达
- 规模上限——8 人局验证过，12+ 人局未验证（MockBackend 选项池碰撞风险）；无并发多局能力
- 前端复盘与 AI 透明化薄弱——观点/思考已落盘但无可视化

**机会（差异化价值）**：
- agent-native 架构（行动工具化 + 世界感知查询化 + 认知工作流 + 观点演化）在开源 AI 社交推理领域稀缺
- 完整的可审计性（trace/viewpoints/thoughts 落盘）天然适合作为 multi-agent 社交推演的**研究/教学平台**
- 不可变状态 + 快照体系是时间旅行复盘的独特基础

---

## 2. 愿景与成功标准

**使命**：让 AI 玩家真正像人类一样思考、发言、成长——把《鸦木布拉夫小镇》做成 AI 社交推理游戏的标杆引擎与 multi-agent 研究平台。

**Beta 2.0 北极星指标**（全部达成才算愿景落地）：

| # | 维度 | 指标 | 当前值 |
|---|------|------|--------|
| 1 | 拟人度 | 盲测 M3：人类猜中 AI 身份率接近随机基线（PLN-040 口径） | 未收口（待标注） |
| 2 | 对局质量 | fallback <2%、工作流 decide 超时 <1%、论证式发言占比 >80% | fallback 2.5%、超时 5%、占比未量化 |
| 3 | 进化有效 | M4：跨局 A/B 胜率差异达 PLN-040 目标 | Δ+2pp（未达） |
| 4 | 内容 | ≥2 个官方剧本可玩 | 1 |
| 5 | 规模 | 12 人局稳定 + 并发多局 | 8 人局稳定 |
| 6 | 成本 | per-action token ≤1,700（能力扩展不推高单位成本） | 1,660.9 |

---

## 3. 演进策略与方向决策

**三主线**：

| 主线 | 内涵 | 对应里程碑 |
|------|------|-----------|
| A. 认知纵深 | 让 AI 更像人：认知统一、双向观点、动态 RAG、LLM 蒸馏、发言质量 | Alpha 1.3 |
| B. 内容广度 | 更多可玩性：剧本抽象层 + 第二剧本 | Alpha 1.4 |
| C. 体验规模 | 更多人玩得爽：复盘 UI、AI 透明化、12+ 人、并发局、部署 | Alpha 1.5 |
| D. 工程质量（横切） | 稳定化、开关默认化、监控、发布工程 | Alpha 1.2.x + 2.0 |

**顺序决策**：D → A → B → C。理由：
1. **先淬火**：RPT-020 的 P1（decide 超时）是 5% 工作流失败 + token 双耗的地基裂缝，认知深化不能建在其上；
2. **认知优先于内容**：agent-native 认知链（观点/工作流/检索）刚建成且是项目差异化核心，趁热闭环收益最大；新剧本内容（rule_knowledge/检索语料）依赖认知架构稳定；
3. **内容优先于规模**：复盘 UI 与并发局在内容单一时受众有限；剧本扩展后放大价值的杠杆更高；
4. **发布殿后**：公测前所有能力默认开启、质量指标收口。

**跨阶段取舍原则**（每个里程碑的任务设计须遵守）：
- 确定性红线不破：说书人真实信息计算、观点置信度/门控数值永远不经 LLM（D016/D018）；
- 交付「默认开启的能力」，不积累「开关遗产」——每阶段结束前必须完成开关默认化或显式废弃；
- token 预算护栏：新能力须评估 per-action token 影响，超基线 +10% 须在任务板标注权衡；
- 重构走「原语提取 + 包装非重写」模式（D019 验证有效），禁止大爆炸重写。

---

## 4. 里程碑总览

| 版本 | 代号（建议） | 主题 | 周期估算 | 核心交付 | 前置条件 |
|------|------------|------|:-------:|---------|---------|
| Alpha 1.2.x | —（补丁系列） | **淬火**：稳定化收尾 | 1-2 周 | RPT-020 P1/P2 修复、开关默认化、盲测收口、文档清账 | 无（当前即启动） |
| Alpha 1.3 | 深潜 | **认知深化** | 3-5 周 | 认知统一管线、双向观点、动态 RAG、LLM 蒸馏、进化有效性 | 1.2.x DoD |
| Alpha 1.4 | 新月 | **第二剧本**（Bad Moon Rising，可改 Sects & Violets） | 5-8 周 | 剧本抽象层 + BMR 全角色 + 多剧本知识库/难度/验收 | 1.3 DoD |
| Alpha 1.5 | 广场 | **体验与规模** | 4-6 周 | 复盘 UI、AI 透明化、12+ 人局、并发多局、部署运维 | 1.4 DoD（复盘 UI 可与 1.4 并行） |
| Beta 2.0 | 开门 | **公测发布** | 2-4 周 | 发布工程、安全加固、玩家手册、公测看护 | 1.5 DoD + 北极星指标 1-3 收口 |

> 周期按当前 agent 协作节奏（PLN-039~043 约每 2-4 天一个计划）与用户投入估算，实际以里程碑滚动细化为准。代号沿用「1.2 觉醒之鸦」命名传统，最终由用户定夺。

---

## 5. Alpha 1.2.x「淬火」—— 稳定化收尾（P0，当前阶段）

**目标**：修复 RPT-020 全部 P1/P2，完成工作流能力默认化，收口盲测与文档清账。**这是唯一不需要新建 PLN 的阶段**——任务板直接在本节执行（启动时核对现状后可复制为 PLN-046）。

### 5.1 任务板

| # | 任务 | 级别 | 验收标准 |
|:-:|------|:--:|---------|
| T1 | **文档清账**：提交 RPT-020 / REV-011 / `data/blind_ready3/` / PROGRESS / docs 索引等上次会话遗留 + 本路线图与手册 | P0 | git clean（commit 须用户确认） |
| T2 | **decide 超时对齐**：`action_workflows.py` 构造 `ToolCallNode` 时按动作类型覆盖 `timeout_seconds`——对齐该动作的 `_action_latency_budgets`/difficulty preset 预算，保证工作流预算 ≥ act() 原路径预算（speak/defense 类按 live P95 ≈20s 上浮） | P1 | 单测覆盖 8 动作超时映射；live 5 人局 decide 超时率 <1%、trace 四节点完整率 ≥99% |
| T3 | **观点时间维度修复**：`ViewpointStore.update_confidence` 追加快照时同步 `day_number`（或引入 `last_updated_day`，保持向后兼容） | P2 | 单测 + live viewpoints.jsonl 更新快照 day 与 `updated_at` 一致 |
| T4 | **length 空响应缓解**：`finish_reason=length` 且 content 为空时「丢弃 reasoning 重试一次」或提高该动作 max_tokens；统计命中率 | P2 | live 局因 length 空响应导致的 fallback 下降 ≥50% |
| T5 | **机械复述拦截**：`speech_sanitizer` 增加摘要式发言检测（特征：罗列记忆条目、无推理连接词、匹配「D\d讨论：」等模式），触发时走 fallback 改写而非放行 | P2 | 单测覆盖 ≥3 类复述样本；live 抽样复述率 0 |
| T6 | **fallback 口径统一**：`fallback_used=True` 时 `speech_source` 统一标记（如 `fallback`），修复 RPT-020 #5 | P2 | 指标一致性单测；live llm.jsonl/metrics 无矛盾记录 |
| T7 | **workflow_trace 瘦身**：ctx 摘要化（可见状态降为要点）+ 单局 trace 滚动清理策略 | P3 | 单 trace <10KB；磁盘占用可配额 |
| T8 | **开关默认化**：`BOTC_WORKFLOW_ACTIONS` 默认 on（前置 T2 完成）；`BOTC_COGNITIVE_SPEAK`/`BOTC_VIEWPOINTS` 语义收编说明；mock 全量零回归 + live 验证 | P1 | DECISIONS 登记（含回退方式：env 显式 off）；mock 676+ 全绿；live 对照局无退化 |
| T9 | **盲测 M3 收口**（人工环节）：协助用户完成 ≥3 人 × ≥30 次标注 → 跑 `score` 统计 → M3 判定报告 | P2 | M3 报告（无论达标与否，诚实记录） |

### 5.2 DoD

1. 全量门禁：`pytest tests -q`（含 slow）全绿 + `ruff check`/`format` 0 + 10/10 gate + doc health PASS；
2. live 5 人局 ×2：decide 超时 <1%、fallback <3%、观点演化/trace 产物正常；
3. T8 开关默认化经 DECISIONS 登记且 mock 零回归；
4. 修复验证报告（RPT-021）：逐项对照 RPT-020 §8 的修复前后数据；
5. PROGRESS / MEMORY / session-handoff 更新，git clean（经用户确认提交）。

### 5.3 风险与缓解

| 风险 | 缓解 |
|------|------|
| T2 超时放宽导致整体对局时长上升 | 超时仅放宽到动作预算上限（与 orchestrator 双超时体系一致），live 实测对局时长对照 |
| T8 默认 on 引爆存量测试对开关 off 的隐式依赖 | 先全量跑 on 状态 mock，逐个修复依赖（预期仅 trace 断言类）；保留 env 显式 off 逃生门 |
| T4 重试增加 token | 仅重试一次且只对空 content；统计写入 RPT 权衡 |

---

## 6. Alpha 1.3「深潜」—— 认知深化

**目标**：把「已建成但分散」的认知能力收敛为一条统一管线并默认启用，让 AI 的思考-发言-成长闭环在质量与可证实性上达到新台阶。

### 6.1 目标架构

```text
act()（唯一入口，默认走工作流）
  └─ run_action_workflow(action_type)
       ├─ recall   : 记忆快照 + 激活观点 + 检索注入（规则/跨局经验/共享池，token 护栏）
       ├─ reason   : 观点形成/更新（speak/defense/nominate/night 启用；hard+soft 双向证据）
       ├─ decide   : 决策原语（本地启发式 / LLM 工具调用，动作级超时）
       ├─ validate : normalize + 合法性校验 + fallback
       └─ record   : 双向观点回写（怀疑↑ / 信任↑，冲突 supersede）+ trace
局末：LLM 蒸馏复盘（fallback 规则模板）→ 跨局进化
```

### 6.2 任务板（启动时细化为独立 PLN）

| # | 任务 | 验收标准 |
|:-:|------|---------|
| T1 | **认知统一管线**：`cognitive_workflow`（speak 认知块）并入 `action_workflows`，统一 recall→reason→decide→validate→record；三开关收敛为 `BOTC_WORKFLOW_ACTIONS` 一个（旧开关保留一版兼容并标 deprecated） | speak/defense 走统一管线单测；开关矩阵回归；live A/B：认知 speak 开启后观点 hard 证据占比 >0（RPT-020 时为 0） |
| T2 | **观点双向演化**：record 节点识别「信任/辩护/合作」类决策 → 正向证据；与怀疑证据冲突时 supersede 激活 | 单测：正/反证据更新置信度方向正确、冲突触发 superseded；live：观点库 superseded >0、置信度有降有升 |
| T3 | **动态 RAG 启用**：修复 embeddings 端点（更换模型/供应商或在 .env 配置可用端点）；recall 节点注入检索结果（规则白名单 + 跨局经验 + 共享池）；token 护栏（检索注入 ≤N tokens 可配） | 检索注入进 user 段（前缀缓存不受破坏）；live A/B：幻觉类发言（能力边界违反）抽检为 0；per-action token 增幅 ≤10% |
| T4 | **LLM 蒸馏复盘**：局末 `finalize_game_review` 从规则模板升级为 LLM 蒸馏（超时/解析失败 fallback 模板，异步不阻塞局末） | live：复盘文本质量抽检优于模板；失败率 <5%；进化文件向后兼容 |
| T5 | **发言质量工程**：论证式结构 prompt 强化 + 指标化验收（引证率/复述率/低信息率入 live 验收脚本） | 新增发言质量 gate（或扩展现有 conversation quality gate）；live 抽样论证式占比 >80% |
| T6 | **进化有效性复测**：关闭 `AI_FORCE_PROGRESS_ACTIONS` 干扰，重跑 `evolution_ab_benchmark`，扩充局数提升置信度 | M4 判定报告（达标 → 北极星 3 收口；未达 → 诚实记录 + 根因分析进 1.4 前置） |
| T7 | **说书人 LLM 策略试点**：`BOTC_ST_LLM_STRATEGY=low` 多局评估扭曲质量与平衡性 | 评估报告：扭曲决策合理性抽检 + storyteller_balance gate 不退化 |
| T8 | （可选）**后端健壮性**：多供应商 failover / 本地模型适配层（基于 T4 经验） | 配置化 backend 切换单测 |

### 6.3 DoD

1. 全量门禁全绿（含新增 gate）；
2. live 多局 A/B 对照报告（RPT）：统一管线 vs 1.2.x 基线——观点 superseded>0、hard 证据占比>0、发言引证率提升、decide 超时 <1%；
3. T6 M4 判定报告（或未达标的根因与后续路径）；
4. `BOTC_COGNITIVE_SPEAK`/`BOTC_VIEWPOINTS` deprecated 说明 + 迁移指引；
5. DECISIONS（统一管线架构）+ PLN/RPT/PROGRESS 收尾 + git clean。

### 6.4 风险与缓解

| 风险 | 缓解 |
|------|------|
| 统一管线重构破坏 speak 热路径（草稿复用/缓存） | 沿用 D019「原语提取+包装非重写」模式；710 单测 + mock 8 人局为硬门禁 |
| 动态 RAG 破坏前缀缓存/信息隔离 | 检索结果只进 user 末段动态区；注入前过敏感过滤 + type=rule 白名单（D016 约束） |
| LLM 蒸馏失败拖垮局末 | 异步 + 超时 + 模板 fallback（三层防护） |
| M4 仍不达标 | 这是研究性风险——诚实记录，将「进化信号强度」分析纳入 1.4 前置评估，不硬凑指标 |

---

## 7. Alpha 1.4「新月」—— 第二剧本（内容扩展）

**目标**：建立多剧本架构并落地第二剧本，验证 agent 认知体系对新内容的泛化能力。

**剧本选择**：默认 **Bad Moon Rising**（死亡/循环机制与现有 executor/death 系统衔接自然）；启动时与用户确认是否改为 Sects & Violets。角色定义以 `ref_docs/` 官方规则书为准。

### 7.1 任务板（方向级，启动时细化）

| # | 任务 | 验收标准 |
|:-:|------|---------|
| T1 | **剧本抽象层**：`ScriptDefinition` 协议（角色注册/night order/分发规则/术语知识库）；Trouble Brewing 迁移为第一个实现，行为零变更 | TB 迁移后 676+ 全量零回归（抽象层的硬门禁） |
| T2 | **BMR 内容定义**：角色元数据 + night order + 术语 + rule_knowledge 语料 | 静态检查 + 检索 gate 在 BMR 语料上 Recall@5 ≥0.9 |
| T3 | **角色实现**（分批：townsfolk → outsider → minion → demon，每批独立 PR 粒度提交） | 每批角色能力单测 + rule_matrix 更新 |
| T4 | **说书人/引擎适配**：BMR 特有机制（如 demon 死亡判定差异、信息错乱）在 engine + storyteller 的适配 | BMR mock 局 game_over + storyteller_balance gate 多剧本化 |
| T5 | **难度预设适配**：四预设 × 新剧本行为差异验证 | difficulty gate 扩展双剧本 |
| T6 | **前端剧本选择** + 玩家/说书人 UI 适配 | 手动验收 + 截图证据 |
| T7 | **认知体系泛化验证**：观点/工作流/检索在 BMR 局的 live 表现 | live BMR 5 人局：产物齐全、无剧本专属幻觉 |

### 7.2 DoD（要点）

全量门禁全绿（双剧本）；BMR mock 8 人局 + live 5 人局 game_over；rule_matrix/知识库/难度/前端文档收尾；发布 Alpha 1.4（REL + checklist + tag，用户确认）。

---

## 8. Alpha 1.5「广场」—— 体验与规模

**目标**：把「引擎能力」转化为「玩家可感知的体验」，并支撑更大规模对局。

### 8.1 任务板（方向级）

| # | 任务 | 验收标准 |
|:-:|------|---------|
| T1 | **对局复盘 UI**：基于 SnapshotManager 时间轴回放（事件流 + 阶段跳转） | 真人验收：能用复盘 UI 讲清一局完整走向 |
| T2 | **AI 透明化**：观点演化/置信度曲线/工作流 trace 的观战可视化（数据均已落盘） | 观战视角页面 + 真人验收 |
| T3 | **12-15 人局**：MockBackend 选项池扩容（CLAUDE.md gotcha 5）+ 性能基准扩展 + 前端布局适配 | 12 人 mock/live 局 game_over + player_count 基准报告 |
| T4 | **并发多局**：房间/会话隔离（server 层多 GameOrchestrator 实例管理）+ 观战模式 | 2 局并发 mock 验证互不污染（数据/事件/记忆隔离） |
| T5 | **部署运维**：一键部署脚本完善、数据备份/恢复、运行监控（fallback 率/超时率告警阈值） | 云端部署演练 + 运维文档 |

### 8.2 DoD（要点）

全量门禁 + 12 人局基准 + 并发隔离测试 + 复盘/透明化真人验收；发布 Alpha 1.5。

---

## 9. Beta 2.0「开门」—— 公测发布

**目标**：面向外部玩家的第一个公开测试版本。**前置**：北极星指标 1-3（拟人度/对局质量/进化有效）必须收口，否则推迟发布补齐。

### 9.1 任务板（方向级）

| # | 任务 | 验收标准 |
|:-:|------|---------|
| T1 | **发布工程**：版本 `1.0.0bN`、PyPI/Docker 分发、安装与快速上手文档 | 全新环境按文档从零跑通 mock 局 |
| T2 | **玩家手册与新手引导**：规则速查 + AI 玩家说明 + 教程局 | 新玩家（非开发者）独立完成一局 |
| T3 | **安全加固**：API key 管理、发言内容过滤、滥用防护（限流） | 安全清单核对表全过 |
| T4 | **反馈闭环**：issue 模板、可选遥测（opt-in、隐私优先）、已知问题清单 | 反馈渠道可用 + 文档登记 |
| T5 | **公测看护**：错误监控、稳定 2 周观察期 | 无 P0/P1 级线上问题 |

### 9.2 DoD（要点）

发布 checklist 全绿（沿用 REL-009 模式）+ 北极星指标对照表 + 正式发布公告；tag `beta2.0-*`（用户确认）。

---

## 10. 跨阶段不变量（红线，任何任务不得违反）

1. **GameState 不可变**：迁移只用 `with_*` 工厂（global.md）；
2. **信息隔离**：Agent 只收 `AgentVisibleState`；TEAM_EVIL 永不入 PUBLIC；跨局/观点/记忆注入前过敏感过滤；
3. **确定性红线**：说书人真实信息计算、观点置信度/门控数值永远不经 LLM（D016/D018）；
4. **白天发言顺序处理**，禁 `asyncio.gather` 最终发言；
5. **三层前缀稳定**：system 全局静态 + user 首条 stable_context；动态内容只进 user 末段（D013/D014）；
6. **包装非重写**：重构走原语提取模式，既有测试为回归门禁（D019）;
7. **仅 mock 通过 ≠ 完成**：live 真实验收是 DoD 必选项（清洁状态第 6 项）；
8. **commit / push / tag 必须经用户确认**（铁律）；
9. **每个里程碑交付默认开启的能力**，不积累开关遗产（§3 取舍原则）。

---

## 11. 滚动规划机制

本路线图按以下机制保持活性，避免「计划赶不上变化」：

1. **里程碑启动细化**：每个里程碑启动时，执行 `PLN-045 §SOP-1`——核对现状 → 把该阶段任务板细化为独立 PLN 文档（frontmatter + 现状盘点 + 任务板 + DoD + 风险）→ 用户确认范围 → 进入执行。远期阶段（1.4/1.5/2.0）当前为方向级，细化时允许基于前序结果调整任务构成（方向变更须用户确认）。
2. **里程碑收尾回顾**：执行 `PLN-045 §SOP-5`——对照本文件 §4 总览表更新实际周期/交付/偏差，把下一阶段任务板从方向级升级为可执行级。
3. **触发式回顾**：出现以下情况随时回顾并提请用户决策——重大外部变化（LLM 供应商/官方规则）、RPT 发现动摇架构的问题、用户方向调整。
4. **版本号纪律**：Alpha 阶段 `0.x.y`（pyproject），里程碑递增次版本号；Beta 起 `1.0.0bN`；仅里程碑级发布打 tag。

---

## 12. 相关文档

- 执行手册：[pln045-execution-handbook.md](pln045-execution-handbook.md)（PLN-045）
- 前情：PLN-041（[血染钟楼_工作流与RAG融入计划_2026-08-12.md](血染钟楼_工作流与RAG融入计划_2026-08-12.md)）、PLN-042（[pln042-cognitive-workflow-plan.md](pln042-cognitive-workflow-plan.md)）、PLN-043（[pln043-all-action-workflow-plan.md](pln043-all-action-workflow-plan.md)）
- 决策链：DECISIONS D012-D019（根 `DECISIONS.md`）
- 最新实测：RPT-020（[pln041-043-live-effect-analysis-2026-08-14.md](../alpha-1.2-evidence/pln041-043-live-effect-analysis-2026-08-14.md)）
- 发布参照：REL-009（[alpha-1.2-release-checklist.md](../releases/alpha-1.2-release-checklist.md)）
