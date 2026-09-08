# 鸦木布拉夫小镇 (Ravenswood Bluff) 项目长期记忆

> 最后更新：2026-09-08 | 仓库：`d:/ravenswood-bluff` | 分支：`main`
> **硬上限**：200 行。超出时精简 Auto Memory 历史，细节移入 DECISIONS/子文件。

## ⚠️ 启动链

```
MEMORY.md（本文件）→ AGENTS.md → PROGRESS.md → DECISIONS.md → docs/plans/pln044-long-term-roadmap.md（当前里程碑）→ 按模块读 .codebuddy/rules/（执行流程按 docs/plans/pln045-execution-handbook.md）
```

## 1. 项目定位

多 Agent + 状态机驱动的《血染钟楼》(Trouble Brewing) 社交推演引擎。当前 **Alpha 1.2「觉醒之鸦」**：AI 玩家为受控自主 Agent（行动工具化 + 世界感知查询化 + 记忆工具化 + 跨局玩家进化 + 工作流/RAG + 认知工作流 PLN-041/042）。

## 2. 技术栈

Python 3.11+ / FastAPI+WebSocket / Pydantic v2 / aiosqlite / LLMBackend 抽象（openai/mock）/ pytest+pytest-asyncio（auto）/ ruff。许可 MIT。

## 3. 模块速查

| 模块 | 路径 | 职责 |
|------|------|------|
| 智能体 | `src/agents/` | AI 玩家(storyteller)；`ai_agent.py`/`storyteller_agent.py` facade 委托子模块（decision/prompt/speech/memory/reasoning/workflow/…） |
| 规则引擎 | `src/engine/` | 阶段机、规则校验、角色能力、剧本、数据采集 |
| 编排 | `src/orchestrator/` | `game_loop.py` facade；EventBus、InformationBroker、阶段处理器 |
| 状态 | `src/state/` | 不可变 GameState、SQLite、事件日志、快照 |
| LLM | `src/llm/` | LLMBackend（openai/mock） |
| 内容 | `src/content/` | 剧本/术语/规则知识库（rule_knowledge.py，PLN-041） |
| 测试 | `tests/` | 替身唯一源 `tests/doubles.py`；深度参考 `docs/reference/test-system.md` |
| 脚本 | `scripts/` | 顶层 4 入口，其余 acceptance/benchmark/export/debug（子目录用 `parents[2]`） |

## 4. 核心基础设施

- 不可变状态机：GameState frozen，迁移经 `with_*` 工厂。
- EventBus + InformationBroker：按 Visibility 过滤产出 AgentVisibleState（Agent 绝不直接见 GameState）。
- 双 facade 仅路由：改行为进子模块。
- 难度系统：DifficultyPreset 五轴 × 4 预设。
- 前缀缓存体系（D013/D014）：三层前缀 = system 全局静态层 + user 首条 stable_context（规则书/跨局记忆，同局稳定）+ user 末条动态内容；观点/检索只进 user 段。
- 工作流（D016）：Workflow DSL/引擎/trace；说书人 LLM 仅限 choose_distortion；认知工作流（D018）recall→reason→speak→record 全确定性，开关 `BOTC_COGNITIVE_SPEAK` 默认 off。

## 5. 术语

```
GamePhase: SETUP → FIRST_NIGHT → DAY_DISCUSSION → NOMINATION → VOTING → EXECUTION → NIGHT → GAME_OVER
Visibility: PUBLIC / TEAM_EVIL / TEAM_GOOD / PRIVATE / STORYTELLER_ONLY
胜负: 恶魔全亡→GOOD；仅剩≤2活且含恶魔→EVIL；市长特例(3活且今日未处决→GOOD)
落盘约定: thoughts/viewpoints/action_trace 仅 live（BOTC_BACKEND!=mock）；BOTC_DATA_DIR 重定向
```

## 6. 硬约束

- GameState 不可变；Agent 只收 AgentVisibleState；事件 visibility 正确（TEAM_EVIL 不入 PUBLIC）。
- 白天发言顺序处理，禁 `asyncio.gather` 最终发言。
- 双超时预算：orchestrator > agent。Good AI 不得吃 evil 策略。
- 仅 mock 通过 ≠ 完成；live 需真人验收。
- **提交/推送必须经用户确认**（铁律）；完成后汇报清单与验证状态。

## 🤖 Auto Memory

<!-- AUTO_MEMORY_START -->
- 2026-08-07 用户提交/推送偏好（铁律）：提交/推送/tag 必须经用户明确确认，禁止习惯性 commit/push。
- 2026-08-03 进程管理偏好（铁律）：不重复开进程；任务完及时终止；跑测试用一次性阻塞 subprocess；结束核对端口释放。
- 2026-08-04 环境踩坑：本机 .venv 需 pydantic-core==2.46.4 + 重装 jiter；跑测试用 `.\.venv\Scripts\python.exe -m pytest`；PowerShell 输出重定向到文件再 read_file（CLIXML 干扰）；live 调试日志 `runtime_game_logs/recent_N/llm.jsonl`。
- 2026-08-04 PLN-039/alpha1.2 live 优化：双层 system + 全局静态层（tool 文本 1522 字符）+ 草稿复用；D015 关 speak/defense thinking（token -62%、fallback→0）；live 命中率 ≥43%；真实总 token 370,931 > 基线（输入膨胀，任务板标权衡）。
- 2026-08-12 PLN-041 完成（D016）：retrieval/（BM25 必装 + faiss 可选 + RRF + 敏感过滤 + type=rule 白名单）、workflow/（DSL/引擎/trace + 说书人试点 + ActionTrace 仅 live）、rule_knowledge.py（setup 期 stable_context 首段注入，防幻觉核心）、检索 gate（Recall@5=1.0/MRR=1.0）入 10/10 门禁。踩坑：rank_bm25 高频词 IDF=0 小语料必 miss（用真实 22 条规则语料）；「恶魔」裸词误杀规则文本（type=rule 白名单）；mock embeddings 污染 RRF（评测 BM25-only）；trace 开关按 BOTC_BACKEND 判定。
- 2026-08-13 D017 验收 flaky 根因：persona_vote_bias 只看随机 decision_style 文案 → vote 模糊带行为趋同。修复：good 分支先按 archetype.assertiveness（high→yes/low→no）。全量 676 全绿。教训：验收失败先查"行为是否真差异化"再放宽断言。
- 2026-08-13 PLN-042 完成（D018）：reasoning/（viewpoint 观点-证据 + viewpoint_engine 确定性置信度/门控 0.45/强断言降级）+ cognitive_workflow + act() 认知块（**orchestrator 全走 act()，挂 act_with_strategy 不生效**）+ build_memory_snapshot 排除阵营私密 + 观点摘要经 strategic_thought 进 user 段。live 5 人局实测：观点 5 玩家落盘、fallback=0、A/B 论证式 vs 断言式。踩坑：pytest-asyncio 需显式 marker；safe-delete 拦截 basetemp（>50 文件）→ 每次唯一 basetemp（时间戳）；simulate_game 用 `--backend live` 参数（env 不生效）+ `--timeout-seconds 600`；PowerShell 中文内联脚本乱码 → 文件 + `-X utf8`。
- 2026-08-13 CR + 验收（报告 `docs/reviews/cr-review-pln041-042-2026-08-13.md`）：六项验收全过。**3 项 P1 已随 PLN-042 commit 修复**：① extract_evidence 双重循环（1 条 hard 文本×8 source 置信度虚高）→ 去外循环 source=hard_memory；② 门控失效（2 条 soft=0.47≥0.45）→ passes_gate 改 hard_count≥1；③ BOTC_VIEWPOINTS 单独开不生效 → store 创建改 viewpoint_enabled()。10 项 P2 登记。pytest 9.1.1 `-q` 不打印 summary 行，计数用 `-rA` 行统计 + RC。
- 2026-08-14 PLN-043 全动作声明式工作流完成（D019，RPT-019）：① **决策原语化**——act() 提取 4 原语（`_decide_local_low_value`/`_decide_slayer_shot`/`_draft_reuse_decision`/`_decide_via_llm`），默认路径逐行等价（696 测试零回归门禁）；② **动作工作流工厂** `src/agents/workflow/action_workflows.py`——8 动作类型 Workflow（recall→decide→validate→record），decide 复用原语（包装非重写）；③ **路由**——act() 开头 `BOTC_WORKFLOW_ACTIONS=1`（默认 off，失败回退原路径）；④ **观点演化闭环**——record 把决策 reasoning 回写观点库：有激活观点 update/supersede，无则**创建软印象观点**（不 gate 不注入发言，演化起点）；⑤ token 分级：vote/nomination_intent 零 LLM。live 实测：52 trace 覆盖 4 动作、节点完整、fallback=0、**11 观点全由决策创建/6 条被更新**（闭环生效）。**踩坑**：record 只回写不创建致 live 观点库恒空（修复为决策创建）；DummyBackend 空 JSON 被 normalize 兜底致 validate 单测假阴（须 monkeypatch _decide_via_llm）；测试未隔离 BOTC_DATA_DIR 会把 agents/、storyteller/ 写入仓库根（已清）；mock 8 人局默认 20s 超时需 --timeout-seconds 120+。
- 2026-09-08 **长期路线图 PLN-044（`docs/plans/pln044-long-term-roadmap.md`）+ 执行手册 PLN-045（`docs/plans/pln045-execution-handbook.md`）** 已发布：五里程碑 = Alpha 1.2.x 淬火（稳定化/开关默认化）→ 1.3 深潜（认知统一管线+双向观点+动态 RAG+LLM 蒸馏）→ 1.4 新月（BMR 第二剧本+剧本抽象层）→ 1.5 广场（复盘 UI/AI 透明化/12 人局/并发局）→ Beta 2.0 开门（公测）；方向顺序 D 工程质量→A 认知纵深→B 内容广度→C 体验规模。**当前阶段 = Alpha 1.2.x 淬火**（T1 文档清账 → T2 decide 节点 10s 超时 P1 修复，RPT-020 §8）。启动链已更新：`AGENTS.md` 上班第 5 步读 PLN-044 定里程碑、第 6 步按 PLN-045 执行（SOP-1~5 + 四层门禁 L1-L4 + 决策升级规则）。doc health PASSED。
<!-- AUTO_MEMORY_END -->

## 下一步

读 `AGENTS.md` → `PROGRESS.md` → `DECISIONS.md` → `docs/plans/pln044-long-term-roadmap.md`（当前里程碑与任务板）。
