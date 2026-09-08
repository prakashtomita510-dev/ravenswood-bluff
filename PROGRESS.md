# PROGRESS — 项目当前进度

> 最后更新：2026-09-08
> **上班必读**：本文件 + DECISIONS.md + `docs/plans/pln044-long-term-roadmap.md`（当前里程碑）

## 活跃任务看板（WIP 显式登记）

> 允许并行，但每个活跃任务必须在此登记一行；切换前写回状态与下一步。

| # | 任务 | 阶段 | 状态 | 下一步 | 阻塞 |
|:--:|------|------|:--:|------|------|
| 1 | 搭建 coding agent harness 环境 | 首次搭建 | ✅ 已完成并提交 | — | 无 |
| 2 | 按 harness 治理体系整理测试系统 | 治理 | ✅ 已完成并提交 | — | 无 |
| 3 | 代码与文件规范化整理（P0-P5） | 整理 | ✅ 已完成并提交（447 全绿 + ruff 零告警 + 9-gate exit=0） | — | 无 |
| 4 | 文档体系治理收尾（增强 + 健康核对） | 治理 | ✅ 已完成并提交；`check_doc_health.py` 已纳入 CI（2026-08-03） | — | 无 |
| 5 | 修复 GitHub Actions lint-and-test 全红 | 修复 | ✅ 已提交推送；CI 三轮修复完成（ruff format / storyteller 日志测试 / CI 提速） | 看 CI 最终转绿 | 无 |
| 6 | P1 上帝对象拆分 + P2 日志/文档治理 | 重构+治理 | ✅ 已提交推送 | — | 无 |
| 7 | CI 提速：慢验收测试标 slow + job 超时上限 | 性能 | 🟢 已提交推送（`26df4f4`+`d8bb347`） | 看 CI run 是否快速通过 | 无 |
| 8 | Agent 原生重构（PLN-038 阶段 A/B/S/C/D + PLN-037 P0/P1/P2） | 重构 | 🟢 已完成（2026-08-03，476 全绿 + 9-gate exit=0 + token 基准 PASS） | 待 live 验收 LLM 策略介入 | 无 |
| 9 | 记忆对局隔离 + 玩家/说书人进化机制（PLN-038 阶段 E） | 重构 | 🟢 已完成（2026-08-04，新增 10 进化测试 + 端到端落盘验证） | 可选：局末 LLM 蒸馏经验；进化影响人格参数 | 无 |
| 10 | 拟人化进化增强（局中反思/局后复盘/学习他人/调整策略） | 重构 | 🟢 已完成（2026-08-04，新增 6 拟人化测试 + 端到端验证 reviews/lessons/strategies 自动落盘） | 可选：局中反思引擎级自动触发；LLM 蒸馏复盘 | 无 |
| 11 | alpha1.2 文档整理 + 真实 LLM live 对局验收 | 文档+验收 | 🟢 已完成（2026-08-04，3 局 DeepSeek live 验证功能 + token -62% + fallback 归零） | — | 无 |
| 12 | speak/defense_speech 关 thinking（D015 live 实测优化） | 优化 | 🟢 已完成（2026-08-04，token 7365→2848，fallback 5.9%→0%） | 切非推理模型需重估 | 无 |
| 13 | Prompt 前缀缓存命中率优化（PLN-039 T1-T6 + 精简 + REV-008 F1-F7 + R1/R2/R3） | 优化 | 🟢 已完成并提交（2026-08-04，480 passed + ruff 0 + token 基准 PASS + mock 8 人局 game_over + live 命中率 53.19%/46.00%/43.14% + 精简全局层 2361→1522 + REV-008 全部修复；commit `c79a7ae`）；⚠️ T6 DoD#5（真实总 token ≤187,423）部分达成（短局 177,828），任务板已标注权衡 | 无 | 无 |
| 14 | **发布 Alpha 1.2「觉醒之鸦」(The Awakening)**：起代号 + README/CHANGELOG/VERSION_NOTES/REL-007/AGENTS 更新 + 新建 REL-009 Release Checklist + docs 索引登记 + pyproject 版本 0.1.0→0.2.0 | 发布 | ✅ 已完成并提交（commit `fd320a1` + tag `alpha1.2-awakening`，2026-08-07；doc health PASS）；未 push | push 由用户决定 | 无 |
| 15 | **PLN-040 差异化玩家进化 + 量化基准**：候选方向留档 + 方向 A 规划文档（任务板 T1-T6 / 量化指标 M1-M5 / DoD / 风险） | 规划 | ✅ 已完成并提交（2026-08-07，commit `0164cac`） | — | 无 |
| 16 | **PLN-040 T1 行为指纹基准**：`scripts/benchmark/player_distinctness_benchmark.py`（12 维指纹 + 两两距离矩阵 + 报告）+ 18 单测 + 基线报告归档 | 实施 | ✅ 已完成（commit `2300181`，ruff 0 + 18 测试全绿 + 5 局 8 人基线 mean_distance=0.3212，证据 `docs/alpha-1.2-evidence/pln040-t1-...json`）；⚠️ 洞察：mock 噪声使 M1 绝对值失真，T3 验收改相对对照 | — | 无 |
| 17 | **PLN-040 T2 共享经验池**：`src/agents/memory/shared_pool.py`（deposit 去私密化沉淀 + retrieve 角色/阵营/新鲜度检索 + build_shared_context 注入摘要）+ game_loop 沉淀钩子 + AIAgent 注入合并 + 12 单测 | 实施 | ✅ 已完成并提交推送（commit `c425233` + `7f3986f` + `d3000af`，2026-08-07 push origin/main，含 2 个发布遗留 P2 修复） | — | 无 |
| 18 | **PLN-040 T3 差异化注入**：`tendency_behavior_overrides`（四维→行为标签覆盖，中性不覆盖）+ 连续画像文案 + `BOTC_TENDENCY_STEP` 标定步长 + 标定实验脚本 + 11 单测 | 实施 | ✅ 已完成待提交（ruff 0 + 全量测试 0 回归 + **M5 标定验证通过**：baseline 0.3127 vs polarized 0.3430/mixed 0.3482，Δ+0.03 差异化生效，证据 `docs/alpha-1.2-evidence/pln040-t3-tendency-calibration-2026-08-07.md`）；⚠️ 关键修复：默认 tendency 强制覆盖导致提名测试回归，改为中性区间不覆盖 | 提交（等待用户确认） | 无 |
| 19 | **PLN-040 T3.5 mock fallback 根因修复**：`mock_backend.py` action_type 提取补扫 messages（修复 vote/nomination 100% fallback）+ 标定脚本对齐 live 本地判定路径 + 6 单测 | 实施 | ✅ 已完成待提交（ruff 0 + 回归通过 + fallback_rate 57%→2.4~11.9% + 方案 3 验证 polarized Δ+0.0092/mixed Δ+0.0226）；**关键发现**：mock 返回固定合法决策绕过 threshold 路径导致 tendency 差异不可测，必须走本地判定路径（与 live 一致） | 提交（等待用户确认） | 无 |
| 20 | **PLN-040 T4 进化有效性 A/B**：`evolution_ab_benchmark.py`（程序化对局循环 + 胜率/Elo 统计 + 对照组隔离）+ 6 单测 | 实施 | ✅ 已完成并提交推送（commit `d3de356` + `68e55e8`，2026-08-07 push；诚实负结果：Δ+2.00pp/Elo+8 未达 M4 目标；证据 RPT-016） | — | 无 |
| 21 | **PLN-040 T5 盲测验证**：`export_blind_test_samples.py`（export 导出匿名样本 + score 统计猜中率）+ 单测 | 实施 | 🟢 代码完成已推送（shuffle 防分组泄露 + TSV 换行清洗 + min-length 过滤 + 双匿名化，2026-08-10 commits `c8a8e24`/`def06af`/`7eaa277`）；**待真人标注**（≥3 人 × ≥30 次标注）后才能判 M3 | 真人标注后跑 score 判 M3 | 无 |
| 22 | **PLN-040 T6 收尾验证**：全量回归 + mock 8 人局 + live 抽查 + 文档 published | 实施 | 🟢 已完成（2026-08-10：pytest 全绿 + ruff 0 + alpha1.1 9/9 + token 基准 PASS + doc health PASS + mock 8 人局 game_over + live 5 人局 day_1 fallback=0 发言自然差异化明显；PLN-040 status→published） | — | 无 |
| 23 | **修复说书人档案 await bug**：`game_loop.py` 局末 `await` 同步方法 `finalize_game_profile`（dict 不可 await，TypeError 被吞，说书人档案从未经 game_loop 落盘；2026-08-04 PLN-038 阶段 E 引入） | 修复 | 🟡 已验证待提交（去掉 await 后 mock 8 人局说书人档案成功落盘 games_conducted=110，无 warning） | 提交（等待用户确认） | 无 |
| 24 | **PLN-041 工作流 + RAG 融入**：检索基础设施（chunker/BM25/Faiss+RRF/持久化/统一管线）+ 规则知识库 setup 静态注入 + Workflow DSL/引擎/trace + 说书人裁决工作流试点 + 玩家行动轨迹（live 落盘）+ 检索质量 gate + 10/10 聚合 gate | 实施 | ✅ 已完成（2026-08-13，676 全量全绿 + ruff 0 + format 0 + doc health PASS + mock 8 人局 game_over + 检索 gate Recall@5=1.0/MRR=1.0；DECISIONS D016/D017 已登记） | —（已提交，见 git log） | 无 |
| 25 | **PLN-042 认知工作流**：观点-证据模型 + 认知工作流（recall→reason→speak→record）+ speak 试点开关 + 严格回归 + live 实测 | 实施 | ✅ 已完成（2026-08-13，692 快速单测全绿 + ruff 0 + format 0 + doc health PASS + mock 8 人局 game_over + **live 实测**：观点 5 玩家落盘、分级正确、fallback=0、A/B 论证式 vs 断言式；DECISIONS D018 + RPT-018） | —（已提交，见 git log） | 无 |
| 26 | **PLN-043 全动作声明式工作流**：act() 决策原语化（4 原语，行为零变更）+ 8 动作类型 Workflow（recall→decide→validate→record）+ BOTC_WORKFLOW_ACTIONS 开关 + 观点演化闭环（决策创建/更新观点）+ 严格回归 + live 实测 | 实施 | ✅ 已完成（2026-08-14，710 快速单测全绿 + ruff 0 + 10/10 gate + mock 开关 off 零 trace/on 26 trace + **live 实测**：52 trace 覆盖 4 动作、观点闭环 11 创建/6 更新、fallback=0；DECISIONS D019 + RPT-019） | —（已提交，见 git log） | 无 |
| 27 | **长期路线图 + Agent 执行手册制定（PLN-044 / PLN-045）**：项目全景梳理（能力资产 / 遗留问题 12 项 / 短板与机会）+ 愿景与 6 项北极星指标 + 五里程碑分阶段计划（Alpha 1.2.x 淬火 / 1.3 深潜 / 1.4 新月 / 1.5 广场 / Beta 2.0 开门）+ 执行手册（启动链 / 9 条红线 / SOP-1~5 / 四层门禁 / 登记规范 / 陷阱速查 / 决策升级规则） | 规划 | ✅ 已完成并提交（2026-09-08；doc health PASSED） | 按 PLN-044 §5 启动 Alpha 1.2.x「淬火」（T1 文档清账 → T2 decide 超时 P1） | 无 |
| 28 | **文档治理审计（doc-governance skill，REV-014）**：docs 全量 138 篇诊断（巨型单文件 / 幽灵文档 / role 一致性）+ PLN-044/045 合规修复（补 `tags`+`related` / TOC / 代码块语言标注 / 同目录相对链接）+ 幽灵文档与编号治理（`CR-PLN041-042`→REV-012、`CR-043`→REV-013、PLN-037 双占 → 新分配 PLN-046、补 REL-008）+ 代码一致性抽查（ToolCallNode 10s 与 PLN-044 T2 前提吻合） | 治理 | ✅ 已完成并提交（doc health PASSED 96 文件；REV-014 报告 + 5 条索引登记；临时脚本已清理） | — | 无 |
| 29 | **文档治理检查常驻 CI**：`scripts/check_doc_health.py` 新增①**幽灵文档检测**（未被 `docs/README.md` 引用 → HARD failure，RC=1 阻断 CI）②**巨型单文件检测**（>500 行 → warning，`--strict` 升级为 failure）；docstring 与 PASSED 文案同步 | 工程 | ✅ 已完成待提交（验证：默认模式 PASSED/RC=0（4 warnings）· 植入幽灵探针 FAILED/RC=1 · `--strict` RC=1 · 探针删除后恢复 RC=0；`ruff check scripts` 0 告警） | 提交 + push（用户已授权） | 无 |

## 当前验证状态

| 检查项 | 状态 |
|------|------|
| `pip install -e ".[dev]"` | ✅ 已验证（受管 Python 3.13.12 + 项目根 `.venv` + dev 依赖全部安装） |
| `pytest tests -q`（基线：447 passed / 0 failed） | ✅ **676 passed / 0 failed**（2026-08-13 全量含 slow，D017 修复后 6 项既有 flaky 恢复）；`-m "not slow"` 快速单测 657 全绿 |
| `ruff check src tests scripts` | ✅ 零告警（阶段一规则集 E4/E7/E9/F/W，忽略 E501；F401/F541 经 `--fix` 收敛，E402 由 `scripts/**` per-file-ignores 覆盖，F841/E712 手工清理） |
| `ruff format --check src tests scripts` | ✅ 182 文件全部已归一；pre-commit `ruff-format` 钩子已启用，CI 该步骤已移除 `continue-on-error` |
| `python scripts/alpha1.1_acceptance.py`（9 gate） | ✅ exit=0，9/9 全绿 |
| 文档链接健康（`python scripts/check_doc_health.py`） | ✅ RC=0（68 md 扫描；1 个非致命绝对路径 warning）；已纳入 CI（2026-08-03） |
| 静态引用审计（脚本路径 / import / REPO_ROOT 深度） | ✅ 无残留旧路径，子目录脚本 `parents[2]` 全覆盖 |
| git status / 未提交改动 | ✅ 工作区 clean，与 origin/main 同步 |
| Agent 原生重构（PLN-038 + PLN-037 协同）验收 | ✅ 476 全绿 + ruff 零告警 + format 通过 + `alpha1.1_acceptance.py` 9/9 + `token_budget_benchmark.py` PASS + `simulate_game --stop-after day_1` 通过 + `check_doc_health.py` RC=0；审查报告 `docs/reviews/agent-native-redesign-cr-review-2026-08-03.md` |
| 玩家进化机制（PLN-038 阶段 E）验收 | ✅ 快速回归 RC=0（含 10 个新进化测试）+ ruff/format 0 告警 + `simulate_game day_1` 通过 + 局末落盘端到端验证（5 玩家战绩 + 说书人主持局数） |
| 拟人化进化增强（任务 10）验收 | ✅ 全量 `pytest -m "not slow"` = 477 passed / 0 failed（全量含 slow 共 495；2026-08-04 独立复核修正，原文档 483 为口径差）+ ruff check 0 告警 + format 197 files 全绿 + 端到端验证局末自动触发 reviews/lessons/strategies |
| alpha1.2 live 验收（任务 11/12） | ✅ 3 局 DeepSeek live day_1 全跑通：工具调用主导 + 草稿复用 + 本地策略判定 + JSON fallback 兜底；token 7365→2848（-62%）、fallback 5.9%→0%；简单动作关 thinking reasoning 40→0；证据 `docs/alpha-1.2-evidence/live-agent-native-verification-2026-08-04.md` |
| 缓存命中优化（2026-08-04）验收 | ✅ `pytest -m "not slow"` = 477 passed / 0 failed + ruff/format/doc 全绿 + token 基准 PASS（system 前缀 1722→1363 仍逐 token 稳定）+ live 8 人局完整对局真实 token 252,999→187,423（-25.9%）、metrics 64,262→40,771（-36.5%）、reasoning 3650→0、fallback 0%；缓存命中率 11.9%→12.7%（DeepSeek 前缀缓存为尽力而为：同一玩家 system 完全一致时实测命中 0-29%，受 LRU/容量限制，前缀一致为必要不充分条件） |
| Prompt 缓存优化二轮（PLN-039，2026-08-04）验收 | ✅ `pytest -m "not slow"` = 480 passed / 0 failed + `ruff check src tests scripts` 0 告警 + format 全绿 + `check_doc_health.py` PASS + `token_budget_benchmark.py` RESULT: PASS（全局静态层 1522 字符跨 Agent 逐 token 一致 + three_tier 稳定 + draft 复用）+ mock 8 人局 game_over + **live 8 人局完整局实测（RPT-014，多局）**：命中率 41.63%→53.19%→46.00%→**43.14%（REV-008 修复后）**，均 ≥40%；reasoning=0、fallback≈0；archive/storyteller 前置后 0%→57-62%；**evil_coord 0%→75.89%（F5）**；⚠️ 真实总 token 370,931 > 基线 187,423（输入膨胀），计费当量 +12.8%，T6 任务板标 🟨 部分完成。归档：`docs/alpha-1.2-evidence/pln039-live-2026-08-04-rev.llm.jsonl`（REV-008 F1） |
| 当前 blocker | ✅ 无 |

> **CI 跨平台修复（2026-07-31，commit `ad4e974`）**：GitHub Actions（ubuntu runner）报 20 个失败。
> 根因一（19 个）：测试/脚本硬编码 `repo_root/".venv"/"Scripts"/"python.exe"` 拉子进程，Windows-only
> → 全部改用 `sys.executable`（35 文件）。根因二（1 个）：`tests/test_runs/` 被 gitignore，CI 全新 checkout
> 不存在，而 `mkdir(exist_ok=True)` 不建父目录 → 改 `mkdir(parents=True, exist_ok=True)`。
> 陷阱已固化为 `docs/reference/tech-traps.md` T13/T14。另将验收 subprocess 测试超时统一提到 300s
> （本机全量并发下 `storyteller_balance`/`alpha3` 曾偶发超时，CI runner 更慢）。

> **P3 二级引用回归修复（2026-07-31 收尾）**：分目录后「叶子 gate 调用兄弟 gate」的路径未同步，导致 9 个测试报
> `can't open file ...\scripts\<name>.py`。已修 `wave1~4_acceptance.py`、`a3_memory_acceptance.py`（`run_script`
> 参数改为带子目录前缀，并在 docstring 固化"相对 `scripts/` 根"语义）、`ai_eval_acceptance.py`、
> `storyteller_acceptance.py`、`storyteller_balance_acceptance.py` 及 2 个测试文件的 `export/` 路径。决策见 D011。
>
> **超时时限放宽**：`test_storyteller_balance_sample_export.py` 第二个用例与 `storyteller_balance_acceptance.py`
> 的 `_run` 均为真跑整局 mock 对局，原 `timeout=60` 在全量 pytest 并发下稳定超时（单跑 <20s），已统一放宽至 180s。
>
> **此前记录的「9-gate 7/9 + 2 门禁 flaky」已不复现**：修复二级引用后连续两轮 `pytest tests -q` 447 passed、
> `alpha1.1_acceptance.py` exit=0。原 flaky 判断部分源于路径断链的连锁失败。

### 规范化整理剩余待办

1. ~~四条验证命令跑通~~ ✅ 已完成（ruff check / ruff format --check / pytest / 9-gate 全绿）。
2. ~~启用 format 门禁~~ ✅ 已完成（pre-commit `ruff-format` 钩子 + CI 移除 `continue-on-error`）。
3. **按 P0-P5 分阶段 commit**（240 项改动，建议 6 个 commit，commit message 标注阶段号以便单独 `git revert`）。
4. 逐族启用 ruff 阶段二规则（I → UP → B → SIM），每族先 `--statistics` 摸底再单独提交（见 D009）。
5. ~~将 `scripts/check_doc_health.py` 纳入 `.github/workflows/ci.yml`（任务 4 遗留）~~ ✅ 已完成（2026-08-03）；顺带补 `docs/releases/v0.8/AGENTS_refactor.md` 缺失 frontmatter 使门禁通过。

## 未提交改动清单（与 git 强一致）

> 规则：标记 ✅ 完成的任务，其代码**必须已 commit**；仅本地验证未提交的，状态写「🟡 已验证待提交」并登记于此。

> **2026-08-03 说明**：2026-07-31 登记的以下改动已全部 commit 并推送到 `origin/main`（工作区 clean）：
> harness 文件、测试治理、P0-P5 规范化、lint 收敛、P1/P2 上帝对象拆分与 print→logging。
> 当前未提交改动见下表。

> **2026-08-04 提交完成**：本清单既有登记已按分组分 3 个 commit 全部提交（工作区 clean）。commit hash 以 `git log --oneline -3` 为准（2026-08-04 三组：token-opt-cache / 阶段 E / alpha1.2）。
>
> 既有登记项（`public/index.html` 修复、`m5l_live_speech_deepseek_20260803.md`、`.gitignore` 等）已在历史 commit 中入库，本清单无遗留。
>
> **2026-09-08 登记（当前未提交改动）**：
> ① 上次会话 RPT-020 收尾：`docs/alpha-1.2-evidence/pln041-043-live-effect-analysis-2026-08-14.md`、
> `docs/reviews/live-analysis-prompt-pln041-043-2026-08-14.md`、`data/blind_ready3/`、`.codebuddy/memory/2026-08-14.md`。
> ② 本次会话规划产出：`docs/plans/pln044-long-term-roadmap.md`、`docs/plans/pln045-execution-handbook.md`、
> `PROGRESS.md`、`docs/README.md`、`.codebuddy/memory/2026-09-08.md`。
> 提交须用户确认（铁律）。**另**：PLN-041/042/043 主体代码已在 `1543cea`~`42714c1` 区间全部提交，任务 24/25/26 状态已同步。

## 整体进度

| Phase | 内容 | 状态 | 完成日期 |
|:--|:--|:--:|:--:|
| 项目初始化(git) | 仓库已存在（main，与 origin/main 同步） | ✅ | 既有 |
| 代码架构 | Alpha 1.1：难度系统 + 速度优化 + 模块化重构 | ✅ | 2026-05-08 |
| Harness 环境搭建 | AGENTS/MEMORY/PROGRESS/DECISIONS + 分层规则 | 🟢 进行中 | 2026-07-30 |

## 阻塞项

无当前阻塞。

## 最近会话记录（三行摘要，详情见 daily memory）

| 日期 | 做了什么（一行） | 验证 | 下一步 | 日志 |
|------|---------|:--:|------|
| 2026-07-30 | 按 harness-setup 生成全套 harness（含整合 CODEBUDDY.md 内容） | 文件已落盘 | 用户决定是否 commit | .codebuddy/memory/2026-07-30.md |
| 2026-07-31 | 测试系统治理：替身统一至 tests/doubles.py + 新增 tests.md/test-system.md/tech-traps T10-T12 + 接入 AGENTS/DECISIONS(D007/D008)/MEMORY | 文档+代码去重完成；ruff/pytest 因无 Python 环境未运行 | 装环境后跑 `pytest tests` + `ruff check tests` | .codebuddy/memory/2026-07-31.md |
| 2026-07-31 | 代码与文件规范化整理 P0-P5：ruff/pytest 配置补全 + pre-commit/CI、根目录清理、tests 归位、scripts 四类分目录、docs 五类重组、agents 子包归属 | 静态审计通过（引用零断链、链接回落基线）；ruff/pytest/9 gate 因无 Python 未运行 | 装环境后跑四条验证命令 + `ruff format` 归一 | .codebuddy/memory/2026-07-31.md |
| 2026-07-31 | 文档治理收尾：清理临时脚本 + docs/README.md §7 登记证据文件名 + 新增 scripts/check_doc_health.py（CI 门禁）+ 核对并修复 harness 文档与历史文档绝对路径断链（→相对路径） | harness 文档路径均有效；61 处空链接已修复为相对链接并验证目标存在 | 纳入 CI；用户跑环境后随 P0-P5 一并 commit | .codebuddy/memory/2026-07-31.md |
| 2026-07-31 | 环境就绪后按 PROGRESS/DECISIONS/handoff 修复：ruff 阶段一零告警（406→0）+ pytest 17→0 全绿 + 9-gate 7/9 稳定；修 data_collector 双装饰器、vector_memory reload、GBK 解码、两处 F821 | pytest 全绿、ruff 零告警；9-gate 2 门禁为预存 flaky（非回归） | 用户决定是否 commit + 逐族启用 ruff 阶段二（I→UP→B→SIM） | .codebuddy/memory/2026-07-31.md |
| 2026-07-31 | 规范化整理收尾：补修 P3 遗漏的 9 处叶子脚本二级互调路径（D011）+ lint 收敛至零告警 + 两处 timeout 60→180 消除 flaky + 启用 format 硬门禁 | ✅ 四条命令全绿：ruff check 0、`ruff format --check` 182 已归一、pytest 447 passed（连跑两轮）、9-gate exit=0 | 按 P0-P5 分 6 个 commit 提交 240 项改动 | .codebuddy/memory/2026-07-31.md |
| 2026-07-31 | **P1 上帝对象拆分**：ai_agent/game_loop/storyteller_agent 三 facade 抽取委托模块（行数 1429/842/1369 → 802/497/25），行为零变更；**P2** 生产 print→logging（server.py/replay_parser.py）+ AGENTS.md facade 描述修正；修正测试 `random` 打桩指向 delegation 模块；顺手修 `alpha1.1_acceptance.py` 的 `PYTHON.exists()` 既存 bug（`sys.executable` 是 str，改 `Path(sys.executable)`）以跑通 9-gate | ruff 零告警；`alpha1.1_acceptance.py` 9/9 全绿；wave1/alpha3 隔离运行 exit 0；全量 pytest 仅 1 个 subprocess 验收测试偶发 240s 超时（既存测试隔离脆弱性，非回归） | 用户决定是否按 P1/P2 分阶段 commit | .codebuddy/memory/2026-07-31.md |
| 2026-08-03 | **CI 三轮修复**：① ruff format 检查失败（facade 拆分引入，3 文件规范化）；② storyteller 日志测试干净环境失败（handler 重绑 workspace，`_bind_storyteller_log_handler`）；③ CI 提速（16 个验收包装测试标 `slow` 排除 + job `timeout-minutes: 25`）；④ `check_doc_health.py` 纳入 CI + 补 `AGENTS_refactor.md` frontmatter | ruff check/format 全过；`-m "not slow"` 快速单测 3.1s RC=0；全量 447 passed；doc health RC=0 | 看 GitHub CI run 是否快速转绿 | .codebuddy/memory/2026-08-03.md |
| 2026-08-03 | **M5-L 真实 live 真人验收（DeepSeek）**：`.env` 配置 DeepSeek live；playwright-cli 以真人玩家身份跑通 2 局完整 5 人局至 GAME_OVER；speech fallback 6.7% / LLM 成功 93.3% / orchestrator 0 超时（达标）；信息隔离（玩家 grimoire 403 / 邪恶频道对好人不可见）PASS；说书人控制台 PASS；修复结算 overlay i18n 崩溃 BUG（`ui-welcome` 空值保护） | 2 局完整对局验收通过；结算修复后 console 0 errors；验收报告已写入 evidence 目录 | 提交 3 项改动；后续补 8 人局/高难度真人复测 + vote/nomination 预算放宽 | .codebuddy/memory/2026-08-03.md |
| 2026-08-05 | **Alpha 1.2 live 深度优化**：7 个原子提交推送（白天发言按座次+方案B、提名修复、游戏结束按钮、邪恶频道清洗、深度思考分级+per-player 落盘+Scavenge、max_tokens 定稿并实测 fallback 清零、测试与 chore） | 工作区 clean；live 确认局 fallback 清零、命中率 54-58% | 用户确认发布 Alpha 1.2 | .codebuddy/memory/2026-08-05.md |
| 2026-08-07 | **发布 Alpha 1.2「觉醒之鸦」**：代号 The Awakening；更新 README/CHANGELOG/VERSION_NOTES/REL-007/AGENTS/docs 索引；新建 REL-009 Release Checklist；pyproject 0.1.0→0.2.0 | doc health PASS（78 md，1 历史非致命 warning） | commit + tag `alpha1.2-awakening` | 本文件 |
| 2026-08-12 | **PLN-041 工作流 + RAG 融入可行性分析**：读计划文档 + 逐条核对代码（数据语料 2652/29163 属实；纠偏：Faiss 依赖未装实际不可用、玩家侧已有防幻觉防线、网络经验为新知识源）；重排落地顺序为规则静态注入 > 检索注入 > 工作流化；计划文档补 frontmatter + §5-§8 章节并入 docs 索引 | doc health PASS | 按 §7 实施 | .codebuddy/memory/2026-08-12.md |
| 2026-08-12 | **PLN-041 全量实施完成**：检索基础设施（chunker/BM25/Faiss+RRF/持久化/统一管线）+ 规则知识库 setup 静态注入（stable_context 首段）+ Workflow DSL/引擎/trace + 说书人裁决工作流试点（包装非重写）+ 玩家行动轨迹（live 落盘 mock 零污染）+ 检索质量 gate（Recall@5=1.0/MRR=1.0）+ 聚合门禁 10/10 | 657 全绿 + ruff 0 + format 0 + doc health PASS + mock 8 人局 game_over | 用户确认后 commit | 本文件 |
| 2026-08-13 | **验收 flaky 根因修复（D017）**：6 项 slow 验收失败根因 = `persona_vote_bias` 只看随机 pick 的 decision_style 文案、与 archetype 无关 → vote 模糊带内 aggressive/silent 行为趋同（1.0<=1.0、persona_diversity 0.2）。修复：good 分支先按 `archetype.assertiveness`（high→yes/low→no）定倾向。**全量 676（含 slow）/0 failed** + ruff 0 + 10/10 gate + mock 8 人局 game_over | 676 全量全绿 + 10/10 gate PASS + mock 8 人局 game_over | 用户确认后 commit（含 PLN-041 全部改动） | 本文件 |
| 2026-08-13 | **PLN-042 认知工作流全量完成**：观点-证据模型（hard/soft 分级 + 置信度门控）+ 认知工作流（recall→reason→speak→record）+ AIAgent act() 接入（开关默认 off）+ **live 实测**（DeepSeek 5 人局：观点 5 玩家落盘、fallback=0、A/B 论证式发言）；DECISIONS D018 + RPT-018 | 692 快速单测全绿 + ruff 0 + doc health PASS + mock 8 人局 game_over + live 五条验收全过 | 用户确认后 commit | 本文件 |
| 2026-08-14 | **PLN-043 全动作声明式工作流全量完成**：act() 决策原语化（_decide_local_low_value/_decide_slayer_shot/_draft_reuse_decision/_decide_via_llm 四原语，696 零回归）+ 8 动作 Workflow（recall→decide→validate→record）+ 开关路由 + 观点演化闭环（record 创建/更新观点）；**live 实测**（DeepSeek 5 人局：52 trace 覆盖 4 动作、观点 11 创建/6 更新、fallback=0）；DECISIONS D019 + RPT-019 | 710 快速单测全绿 + ruff 0 + 10/10 gate + mock 双态验证 + live 六条验收全过 | 用户确认后 commit | 本文件 |
| 2026-08-14 | **PLN-041/042/043 live 效果分析（RPT-020）**：两局 DeepSeek live 5 人完整局对照（基线 off `673cd086` vs 改进 on `7341fec5`）；PLN-043 观点演化闭环真实生效（26 观点、置信度 0.41→0.77 跨天递增、80/80 trace）；**P1 发现**：ToolCallNode 默认 10s 超时 < live LLM 延迟 → 4/80 decide 失败回退重试；P2：观点 day_number 不随演化更新、deepseek length 空响应致 fallback、机械复述发言 | 分析报告 RPT-020 + doc health PASS | P1 修复 decide 超时参数（待用户决定） | .codebuddy/memory/2026-08-14.md |
| 2026-09-08 | **文档治理审计（REV-014，doc-governance skill）**：docs 138 篇诊断（巨型单文件 3 / 幽灵文档 4 / role 偏差 4）+ 编号治理（PLN-037 双占 → PLN-046；CR-* → REV-012/013；补 REL-008）+ PLN-044/045 合规修复（tags+related / TOC / 代码块语言 / 相对链接），评分 Agent 友好度 100、人类可读性 92、体系综合 89 | doc health PASSED（96 文件，1 历史 warning）；REV-014 + 4 条索引登记；临时脚本已清理 | 提交（等待用户确认）→ Alpha 1.2.x「淬火」T1/T2 | .codebuddy/memory/2026-09-08.md |
| 2026-09-08 | **制定长期路线图（PLN-044）+ Agent 迭代执行手册（PLN-045）**：项目全景梳理（能力资产 7 类 / 遗留问题 12 项 / 短板与机会 / 6 项北极星指标）+ 五里程碑分阶段计划（1.2.x 淬火 T1-T9 / 1.3 深潜 T1-T8 / 1.4 新月 T1-T7 / 1.5 广场 T1-T5 / 2.0 开门 T1-T5）+ 执行手册（启动链 / 9 条红线 / SOP-1~5 / 四层门禁 L1-L4 / 文档登记规范 / 陷阱速查 / 决策升级规则） | PLN-044/045 落盘 + docs 索引登记；PROGRESS 任务板同步（24/25/26 已提交状态修正） | 用户确认提交 → 启动 Alpha 1.2.x「淬火」T1（文档清账）→ T2（decide 超时 P1） | .codebuddy/memory/2026-09-08.md |
