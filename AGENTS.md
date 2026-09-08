# 鸦木布拉夫小镇 (Ravenswood Bluff) — Agent 操作手册

> **角色**：AI 玩家 / 说书人 facade。已演进为**受控自主 Agent**：行动工具化（`GameActionToolRegistry`）+ 世界感知查询化（`WorldTools`）+ 记忆工具化（`MemoryTools`）+ 跨局玩家进化（`PlayerProfileStore`）。orchestrator 保留规则裁判与调度职责；facade 仅路由、逻辑在子模块（详见 `CLAUDE.md` 与 `.codebuddy/rules/`，决策见 `DECISIONS.md` D012/D013/D014）。
> **当前版本**：Alpha 1.2「觉醒之鸦」(The Awakening) — `alpha1.2-awakening`（发布记录 `docs/releases/alpha-1.2-agent-native-release.md`，门禁 `docs/releases/alpha-1.2-release-checklist.md`）
> **上下文预算**：32768 字节
> **最后更新**：2026-08-07

## Setup & Commands

```bash
pip install -e ".[dev]"                  # 安装（Python 3.11+，建议 venv）
pytest tests -q                          # 运行全部测试（默认 MockBackend，离线）
ruff check src tests                     # lint（规则集见 pyproject.toml [tool.ruff.lint]）
ruff format --check src tests            # 格式一致性检查
BOTC_BACKEND=mock python -m src.api.server   # 启动服务（mock 模式，无需 API key）→ http://127.0.0.1:8000
python scripts/alpha1.1_acceptance.py        # Alpha 1.1 聚合验收（9 个 gate）
python scripts/benchmark/token_budget_benchmark.py  # Token 预算基准（离线验证策略表/前缀/草稿复用）
python scripts/check_doc_health.py           # 文档 frontmatter + 链接健康门禁
```

> Windows PowerShell：先 `.\.venv\Scripts\activate`，用 `$env:BOTC_BACKEND="mock"`，再 `python -m src.api.server`。
> 单测示例：`pytest tests/test_agents/test_agent_reasoning.py -q`；lint：`ruff check src tests`。

## 会话工作流

### 上班（每次新会话开始，强制按此顺序）
1. 读 `.codebuddy/memory/MEMORY.md`（项目认知 + 上次记忆）
2. 读本文件（操作手册 + 硬约束 + 上下文预算）
3. 读 `PROGRESS.md`（进度、活跃任务看板、未提交改动、blocker）
4. 读 `DECISIONS.md`（已有决策，勿推翻）
5. 读 `docs/plans/pln044-long-term-roadmap.md`（PLN-044：当前里程碑与阶段任务板）
6. 按当前任务模块，读 `.codebuddy/rules/` 下对应规则；**迭代执行流程按 `docs/plans/pln045-execution-handbook.md`（PLN-045）**

### 下班（缺一不可）
1. 更新 `PROGRESS.md`（完成内容、仍存问题、下一步）
2. 新决策 → `DECISIONS.md`
3. 重要发现 → `MEMORY.md` 的 Auto Memory 区
4. 填 `.codebuddy/harness/session-handoff.md`（禁止留空占位符）
5. 查 `git status`：clean 或登记到「未提交改动清单」
6. WIP 显式登记到活跃任务看板（切换前写回状态与下一步）

### 清洁状态检查（"做完"的硬性定义）

| # | 检查项 | 方式 |
|:--|------|------|
| 1 | 安装/导入通过 | `pip install -e ".[dev]"` |
| 2 | 测试通过（基线一致，已知失败须具名） | `pytest tests -q` |
| 3 | 无 lint 告警 | `ruff check src tests` |
| 4 | git clean 或已登记未提交清单 | `git status` |
| 5 | PROGRESS.md 已更新 | 检查日期 |
| 6 | 部署后/E2E 验证闭环（或显式记录未验证原因 + 预计验证时间） | 部署/接口验证 |

## 项目结构（核心）

```
src/
  agents/         AI 玩家(storyteller) — ai_agent.py / storyteller_agent.py 为 facade，各自委托 9 子模块
  engine/         规则引擎、角色能力、阶段机、数据采集
  orchestrator/   对局循环 game_loop.py 为 facade；EventBus / InformationBroker / 各阶段处理器
  state/          不可变 GameState + SQLite 持久化 + 事件日志 + 快照
  llm/            LLMBackend 抽象（OpenAI / Mock）
  api/            FastAPI + WebSocket server
  content/        剧本与术语
tests/            单元/集成/验收；替身唯一来源 tests/doubles.py；按被测模块分 test_*/ 子目录
scripts/          顶层=入口（alpha1.1_acceptance / alpha1_acceptance / alpha3_acceptance / check_doc_health）
  acceptance/     被聚合调用的 gate 脚本（main() -> int）
  benchmark/      延迟/吞吐基准与指标解析
  export/         对局资产 / AI trace / 平衡性样本导出
  debug/          prompt 抽取等人工调试工具
docs/             plans/ releases/ reviews/ guides/ reference/ + alpha-1.1-evidence/（脚本写入，原地）
public/  data/
```
> 详见 `CLAUDE.md` §4 完整目录 + §3 连接图；脚本约定见 `scripts/README.md`，文档索引见 `docs/README.md`。
> **子目录脚本注意**：`REPO_ROOT = Path(__file__).resolve().parents[2]`（顶层入口用 `parents[1]`）。

## 分层规则加载

| 规则文件 | 生效条件 | 路径 |
|---------|---------|------|
| global.md | 始终生效 | `.codebuddy/rules/global.md` |
| agents.md | `src/agents/**` | `.codebuddy/rules/agents.md` |
| engine.md | `src/engine/**` | `.codebuddy/rules/engine.md` |
| orchestrator.md | `src/orchestrator/**` | `.codebuddy/rules/orchestrator.md` |
| state.md | `src/state/**` | `.codebuddy/rules/state.md` |
| llm.md | `src/llm/**` | `.codebuddy/rules/llm.md` |
| api.md | `src/api/**` | `.codebuddy/rules/api.md` |
| tests.md | `tests/**`, `scripts/**/*acceptance*.py` | `.codebuddy/rules/tests.md` |

**加载策略**：命中多个模块时取规则文件的并集。

## Coding Standards

详见 `CLAUDE.md` §8（状态管理、Agent 接口、信息隔离、难度系统、AI 兜底、测试模式）。要点：
- `GameState` 不可变，迁移一律用 `with_update / with_player_update / with_event / with_message`。
- 任何 Agent 只接收 `AgentVisibleState`，绝不直接传 `GameState`。
- 发布事件必须设正确 `visibility`；`TEAM_EVIL` 不得泄露给 `PUBLIC`。
- 白天发言顺序处理，禁止 `asyncio.gather` 最终发言。

## Do Not（硬约束）

每条遵循 why-when-when_remove。
- ❌ 直接修改 `GameState`（`state.players[i].x = y`）；用 `with_player_update`。**why**：破坏快照一致性。**when_remove**：重构为可变模型时。
- ❌ 将 `GameState` 直传 Agent；用 `InformationBroker.get_visible_state()`。**why**：信息隔离。**when_remove**：设计支持全知 Agent 时。
- ❌ 泄露 evil 信息到 PUBLIC 可见事件。**why**：破坏游戏。**when_remove**：调试开关开启时。
- ❌ 在 `ai_agent.py` / `game_loop.py` 内堆逻辑（二者是 facade）；改对应子模块。**why**：可维护性。**when_remove**：子模块合并时。
- ❌ 用 `asyncio.gather` 并行生成白天最终发言。**why**：后发言者需先发言者事件上下文。**when_remove**：设计支持并行时。
- ❌ 仅以 mock 通过就宣称完成；live 模式需真人验收。**why**：MockBackend 毫秒级掩盖超时。**when_remove**：项目明确只跑 mock 时。

## 专题文档索引

- `docs/plans/pln044-long-term-roadmap.md`(PLN-044) — **长期路线图**：当前里程碑方向 + 分阶段任务板（起步先看这里定阶段）
- `docs/plans/pln045-execution-handbook.md`(PLN-045) — **迭代执行手册**：SOP-1~5 / 四层质量门禁 / 登记规范 / 陷阱速查 / 决策升级规则
- `CLAUDE.md` — 深度 agent 指南（架构 / 约定 / gotchas / 常见任务）
- `architecture.md` — 33KB 详细架构
- `docs/plans/agent-native-redesign-plan.md`(PLN-037) + `docs/plans/token-budget-optimization-plan.md`(PLN-038) — 当前 Agent 重构计划；`docs/releases/alpha-1.2-agent-native-release.md` — 本版发布记录
- `docs/reference/rule_matrix.md` — 角色能力矩阵；`CHANGELOG.md` / `VERSION_NOTES.md`
- `.codebuddy/rules/` — 分层规则（含 `tests.md` 测试系统规则）；`.codebuddy/memory/MEMORY.md` — 项目认知
- `docs/reference/test-system.md` — 测试系统深度参考（目录/约定/替身/conftest/9 gate 验收）
- `docs/reference/tech-traps.md` — 技术陷阱清单；`docs/README.md` — 文档总索引；`scripts/README.md` — 脚本目录约定

## 上下文预算

本文件 + MEMORY.md + 规则文件总加载 ≤ 32768 字节。超出时优先精简 MEMORY.md 历史记录，其次按需加载规则。
