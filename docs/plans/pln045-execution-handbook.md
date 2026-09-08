---
doc_id: "PLN-045"
title: "Agent 迭代执行手册：里程碑与任务的标准执行流程"
category: "planning"
role: "[Delta]"
status: "published"
date: "2026-09-08"
updated: "2026-09-08"
author: "Ravenswood Bluff"
tags: ["handbook", "sop", "process", "acceptance", "agent-native"]
related:
  - "pln044-long-term-roadmap.md"
  - "../reference/tech-traps.md"
  - "../reference/test-system.md"
---

# Agent 迭代执行手册（PLN-045）

> **目的**：让任何后续 agent 会话按「[pln044-long-term-roadmap.md](pln044-long-term-roadmap.md)（PLN-044）定方向 → 本手册定流程」即可自主完成项目迭代升级，无需重新摸索。
> **适用**：AI 玩家/说书人能力迭代、引擎与剧本扩展、体验与规模工程、版本发布。
> **关系**：本手册是流程规范；`AGENTS.md`/`CLAUDE.md` 是环境与代码规范（本手册引用不重复）。
>
> **目录**：§1 总则（启动链/红线）· §2 迭代生命周期 · §3 SOP-1 里程碑启动 · §4 SOP-2 任务执行循环 · §5 SOP-3 四层质量门禁 · §6 SOP-4 收尾与发布 · §7 SOP-5 路线图回顾 · §8 文档登记规范 · §9 陷阱速查 · §10 决策升级规则 · §11 附录（PLN 模板/基线/相关文档）

---

## 1. 总则

### 1.1 启动链（每个会话必读，顺序不可省）

```text
1. .codebuddy/memory/MEMORY.md        项目长期认知 + 踩坑
2. AGENTS.md                         操作手册 + 硬约束
3. PROGRESS.md                       进度/活跃任务看板/未提交清单
4. DECISIONS.md                      既有决策（勿推翻）
5. docs/plans/pln044-long-term-roadmap.md   当前里程碑与阶段任务板  ← 新增
6. .codebuddy/rules/<模块>.md         按本次涉及模块加载
```

### 1.2 不可违反的红线

| # | 红线 | 违反后果 |
|:-:|------|---------|
| 1 | GameState 不可变，迁移只用 `with_*` 工厂 | 快照一致性破裂 |
| 2 | Agent 只收 `AgentVisibleState`；TEAM_EVIL 永不入 PUBLIC | 游戏平衡崩坏 |
| 3 | 确定性红线：说书人真实信息、观点置信度/门控数值不经 LLM | 结果不可审计 |
| 4 | 白天发言顺序处理，禁 `asyncio.gather` 最终发言 | 后发言者丢失上下文 |
| 5 | 三层前缀稳定（system 静态 + user 首条 stable_context） | 缓存命中崩塌 |
| 6 | 包装非重写：重构走原语提取，既有测试为门禁 | 热路径回归 |
| 7 | 仅 mock 通过 ≠ 完成；live 真实验收为 DoD 必选项 | 虚假完成 |
| 8 | **commit / push / tag 必须经用户确认** | 铁律 |
| 9 | 每里程碑交付「默认开启的能力」，不留开关遗产 | 能力悬空 |

---

## 2. 迭代生命周期总览

```text
里程碑启动  → SOP-1：核对现状 + 细化任务板为 PLN + 用户确认范围
   ↓
任务循环    → SOP-2：认领 → 读规则 → TDD(RED→GREEN) → 局部验收 → 登记
   ↓（每个任务）
里程碑收尾  → SOP-3：四层质量门禁（含 live）→ SOP-4：文档收尾 + 版本发布
   ↓
路线图回顾  → SOP-5：更新 PLN-044 总览表 + 细化下一阶段
```

---

## 3. SOP-1：里程碑启动

**输入**：`PLN-044` 对应阶段（§5-§9）+ 前序 RPT/DECISIONS。

**步骤**：

1. **核对现状**：逐条核对阶段任务板的前提条件——代码可能已变化（前序里程碑/live 反馈/依赖升级）。发现前提失效立即回到 `PLN-044 §11` 触发式回顾。
2. **细化任务板**：把方向级任务板（1.4/1.5/2.0）升级为可执行级——每项含「任务描述 + 验收标准（可测）」，参照 `PLN-043 §3` 格式。
3. **建 PLN 文档**：新建 `docs/plans/pln04X-<主题>-plan.md`，frontmatter 完整（`doc_id/title/category/role/status/date/updated/author`），正文含：现状盘点、目标架构、任务板、DoD、风险与缓解、相关文档。
4. **登记索引**：在 `docs/README.md` §3 计划/任务表追加一行。
5. **用户确认**：提请用户确认范围、优先级、周期估算（避免方向性返工）。
6. **登记看板**：`PROGRESS.md` 活跃任务板新增一行（状态 🟢 进行中）。

**产出**：published PLN 文档 + docs 索引 + PROGRESS 看板行。

---

## 4. SOP-2：任务执行循环（每任务）

### 4.1 循环步骤

| 步 | 动作 | 要点 |
|:-:|------|------|
| 1 | **认领** | `PROGRESS.md` 活跃任务板登记（WIP 显式登记）；切换前写回状态与下一步 |
| 2 | **读规则** | 按涉及模块加载 `.codebuddy/rules/{agents,engine,orchestrator,state,llm,api,tests}.md` |
| 3 | **判断规模** | 小改动（单模块、<100 行）直接实施；架构级/跨模块先写设计要点，必要时登记 DECISIONS |
| 4 | **TDD** | 先写失败测试（RED）→ 实现（GREEN）→ 重构；测试用 `MockBackend`，每测试自建 SQLite DB |
| 5 | **局部验收** | 相关测试子集 + `ruff check` + `ruff format --check` |
| 6 | **登记** | `PROGRESS.md` 更新状态 + 当日 `.codebuddy/memory/YYYY-MM-DD.md` 追加记录 |

### 4.2 编码规范要点

- 新增能力放对应子模块（`src/agents/` 或 `src/orchestrator/` 子目录），facade 只路由（global.md）；
- 新动作类型：先注册 ToolDef/Workflow，再接策略表（D012 约束）；
- 新开关：默认 off + 保留回退路径，且必须在同里程碑内完成默认化或废弃（PLN-044 §3）；
- 硬编码路径、脚本互调走「相对 `scripts/` 根」完整路径（D011）；
- 子进程一律用 `sys.executable`（跨平台 CI 陷阱 T13/T14）。

### 4.3 提交粒度

按任务/主题原子提交，禁止大杂烩：

```
feat(module): 一句话描述（PLN-04X Tn）
docs(pln04x): 计划/报告/决策文档收尾
fix(module): 修复描述
refactor(module): 重构描述（行为零变更）
chore(memory): 工作记忆更新
```

---

## 5. SOP-3：质量门禁（四层）

| 层 | 时机 | 内容 | 通过标准 |
|:-:|------|------|---------|
| **L1 快速** | 每任务局部验收 | 快速单测 + ruff | 0 失败 / 0 告警 |
| **L2 全量** | 任务完成（提交前） | 全量单测 + format + 聚合 gate + doc health | 全绿 / 10/10 / RC=0 |
| **L3 mock 端到端** | 里程碑收尾 | mock 8 人局 game_over + 开关双态验证 | game_over + 开关 off 零污染 |
| **L4 live 真人** | 里程碑收尾（必选） | 真实 LLM 5 人局 day_1/完整局 + 涉及 UX 的真人验收 | DoD 各项数值达标 |

### 5.1 命令速查（Windows PowerShell）

```powershell
# L1
.\.venv\Scripts\python.exe -m pytest tests -q -m "not slow"
ruff check src tests scripts
ruff format --check src tests scripts

# L2
.\.venv\Scripts\python.exe -m pytest tests -q              # 全量（含 slow）
.\.venv\Scripts\python.exe scripts\alpha1.1_acceptance.py   # 10/10
.\.venv\Scripts\python.exe scripts\check_doc_health.py      # RC=0
.\.venv\Scripts\python.exe scripts\benchmark\token_budget_benchmark.py   # PASS

# L3（mock 8 人局，注意超时）
.\.venv\Scripts\python.exe simulate_game.py --backend mock --player-count 8 --timeout-seconds 120

# L4（live 5 人局）
.\.venv\Scripts\python.exe simulate_game.py --backend live --player-count 5 --timeout-seconds 600
```

### 5.2 门禁纪律

- 失败**先查「行为是否真差异化/真修复」**，再考虑放宽断言（D017 教训）；
- pytest 9.x 的 `-q` 不打印 summary 行——用 `-rA` 行统计 + RC 判成败；
- 验收失败禁止直接 `skip`：先定位根因（二级引用断链/超时/路径）。

---

## 6. SOP-4：里程碑收尾与版本发布

### 6.1 收尾 checklist

1. DoD 全部满足（PLN-044 各阶段 §DoD）；
2. **CR 审查**：重要里程碑（架构级/跨模块）生成 review 类文档（`docs/reviews/REV-XXX`）并修复 P0/P1；
3. **RPT 报告**：live 实测/验收数据（`docs/alpha-1.2-evidence/` 或 `docs/reviews/`），含遗留问题清单；
4. **DECISIONS 登记**：本阶段架构决策（格式：日期/决策/原因/否决方案/回退方案/约束）；
5. **状态更新**：`PROGRESS.md`（任务板 ✅ + 验证状态表 + 会话记录）、`MEMORY.md`（长期事实/踩坑）、daily memory、`.codebuddy/harness/session-handoff.md`（禁占位符）；
6. **git**：`git status` 核对，未提交改动登记到「未提交清单」，提交经用户确认。

### 6.2 版本发布 SOP

1. 版本号：Alpha 阶段 `0.x.y`（pyproject `version`），里程碑递增次版本号；Beta 起 `1.0.0bN`；
2. 更新 `README.md` / `CHANGELOG.md` / `VERSION_NOTES.md`，新建 `docs/releases/REL-XXX` checklist（参照 REL-009）；
3. `docs/README.md` 索引登记；
4. 跑 L2 全量门禁 + L3/L4（不得降级）；
5. **提交 + 打 tag（必须用户确认）**，push 由用户决定。

---

## 7. SOP-5：路线图回顾

里程碑收尾后执行（PLN-044 §11）：

1. 对照 `PLN-044 §4` 总览表更新「实际周期 / 交付 / 偏差」；
2. 把下一阶段任务板从方向级升级为可执行级（就地更新 `PLN-044` 对应章节）；
3. 更新 `PLN-044 §2` 北极星指标当前值；
4. 若出现方向性变化（用户调整/外部变化/重大发现），先与用户确认再改章节，并在 §11 记录变更原因。

---

## 8. 文档与登记规范

| 时机 | 文档 | 要点 |
|------|------|------|
| 里程碑启动 | `PLN-04X` | 现状盘点 + 任务板（每项含可测验收）+ DoD + 风险；登记 `docs/README.md` §3 |
| 架构决策 | `DECISIONS.md` D0XX | 六要素：日期/决策/原因/否决方案/回退可逆方案/约束 |
| live 实测 / 验收 | `RPT-0XX` | 数据对照 + 结论 + **遗留问题清单**（分级 P1/P2/P3） |
| 代码审查 | `REV-0XX` | issues 分级 + 修复指引 |
| 版本发布 | `REL-0XX` + CHANGELOG + VERSION_NOTES | 发布门禁记录 |
| 每次会话结束 | `PROGRESS.md` + 当日 memory | 三行摘要（做了什么/验证/下一步） |
| 长期事实 / 踩坑 | `MEMORY.md` Auto Memory 区 | 硬上限 200 行，超出精简历史 |
| 会话切换 | `.codebuddy/harness/session-handoff.md` | 禁止占位符 |

**frontmatter 规范**（D011）：所有人文档必带 `doc_id / title / category / role / status / date / author`；
`role ∈ {[State],[Delta],[Cold]}`、`category ∈ {architecture,planning,review,release,report,reference,api,template,spec}`、`status ∈ {draft,review,published,archived,superseded}`；脚本产物目录（`alpha-1.1-evidence/`）豁免；链接一律相对路径。

---

## 9. 陷阱速查（高频踩坑，详见 [tech-traps.md](../reference/tech-traps.md)）

| 类别 | 陷阱 | 规避 |
|------|------|------|
| 测试 | pytest-asyncio 需显式 marker | 异步测试加 `@pytest.mark.asyncio` |
| 测试 | safe-delete 拦截 basetemp（>50 文件） | 每次唯一 basetemp（时间戳） |
| 测试 | 未隔离 `BOTC_DATA_DIR` → 仓库根被写入 `agents/`、`storyteller/` | 测试显式设置临时数据目录 |
| 测试 | `DummyBackend` 空 JSON 被 normalize 兜底 → 假阴 | 用 monkeypatch 直击被测函数 |
| 测试 | aiosqlite 锁竞争 | 每测试自建 DB |
| 运行 | mock 8 人局默认 20s 超时不够 | `--timeout-seconds 120+` |
| 运行 | live 模式 env 不生效 | 必须用 `--backend live` 参数 |
| 检索 | 小语料高频词 IDF=0 必 miss；类型白名单未放行致误杀 | 用真实语料评测；`type=rule` 白名单 |
| 环境 | PowerShell 输出/中文内联脚本乱码 + CLIXML 干扰 | 输出重定向到文件再 read_file；脚本文件 + `-X utf8` |
| 环境 | 进程占用导致打包失败 / 端口未释放 | 任务完及时终止进程，结束核对端口 |
| CI | 硬编码 `.venv/Scripts/python.exe` 拉子进程 | 一律 `sys.executable` |

---

## 10. 决策升级规则（何时必须停下来问用户）

1. **commit / push / tag**（铁律，任何情况下先确认）；
2. 里程碑**范围或优先级变更**（如跳过 A 主线先做 B）；
3. 触碰架构红线（§1.2）或需要新 DECISIONS 的架构决策；
4. **成本/周期显著偏离**：per-action token 超基线 +10%、周期超估算 2 倍；
5. **live 真人验收环节**（盲测标注、UX 真人体验必须由人完成）；
6. 外部依赖变更（LLM 供应商、模型、部署环境）；
7. RPT 发现**动摇架构**的 P1 问题（而非局部缺陷）。

---

## 11. 附录

### A. PLN 文档骨架（新建计划时复制）

```markdown
---
doc_id: "PLN-04X"
title: "<主题>"
category: "planning"
role: "[Delta]"
status: "published"
date: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
author: "Ravenswood Bluff"
---

# <主题>（PLN-04X）

> 日期 / 状态 / 诉求（用户原话）/ 前情

## 1. 现状盘点
## 2. 目标架构
## 3. 任务板（TDD：每项先 RED 后 GREEN）—— 表格：# / 任务 / 验收标准
## 4. DoD（完成定义）
## 5. 风险与缓解
## 6. 相关文档
```

### B. 基线数字（回归对照，以 `PROGRESS.md` 最新登记为准）

| 项 | 基线 |
|----|------|
| 快速单测 | 710 passed / 0 failed |
| 全量单测（含 slow） | 676 passed / 0 failed（2026-08-13 口径） |
| 聚合门禁 | 10/10 |
| live per-action token | 1,660.9 |
| live fallback | 2.5% |
| 前缀缓存命中 | 53.83% |

### C. 相关文档

- 路线图：[pln044-long-term-roadmap.md](pln044-long-term-roadmap.md)（PLN-044）
- 环境/代码规范：根 `AGENTS.md`、`CLAUDE.md`、[tech-traps.md](../reference/tech-traps.md)、[test-system.md](../reference/test-system.md)
- 分层规则：`.codebuddy/rules/`
