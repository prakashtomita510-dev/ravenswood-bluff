# Alpha 0.2 开发总结与发布梳理

## 目的

这份文档用于汇总 `alpha 0.2` 开发阶段自启动以来的主要工作成果，方便后续进行：

- 版本发布说明撰写
- 内部里程碑回顾
- 封板前验收对照
- 已完成内容与已知边界的统一口径整理

它和 [current-status.md](D:/鸦木布拉夫小镇/docs/alpha-0.2-plan/current-status.md) 的区别是：

- `current-status.md` 更强调“现在还剩什么、当前推进到哪”
- 本文档更强调“这一整个版本做成了什么”

---

## 版本定位

`alpha 0.2` 是在 `alpha 0.1` 基础上的一次系统性迭代，核心目标不是单点修 bug，而是把整个项目从“可玩原型”推进到“具备更稳定规则主链、更可信说书人、更强 AI 记忆与推理、更完整结算复盘”的阶段。

本版本的主线可以概括为四件事：

1. 把规则主链和夜晚/白天流程做稳
2. 把说书人裁定与角色信息链做可信
3. 把 AI 玩家从“会动”推进到“有视角、有记忆、有推理”
4. 把结算、历史、复盘与封板验收体系补齐

---

## 总体开发结果

截至当前，`alpha 0.2` 已完成的整体结果可以概括为：

- `Wave 1`：规则主链稳定化，基本完成
- `Wave 2`：说书人与角色一致性增强，基本完成
- `Wave 3`：AI 玩家智能增强，基本完成
- `Wave 4`：结算、历史、复盘与封板体验，已进入后半段并建立聚合门禁

从工程角度看，这一版本已经完成了：

- 核心游戏回合主链的第一轮系统性稳定化
- 说书人裁量记录、样本导出、验收门禁
- AI 玩家视角隔离、记忆分层、声明账本、社交图谱与基础长期记忆
- 结算、历史、复盘、Rematch 与 Wave 4 聚合验收入口

从体验角度看，这一版本已经明显推进了：

- 提名 / 投票 / 处决的连续可玩性
- 夜晚信息和私密信息的正确性与可见性
- 说书人控制台的可用性
- 玩家端结算与历史回看能力
- AI 在“身份认知、私密信息保留、冲突声明处理”上的稳定性

---

## Wave 1：规则主链稳定化

### 目标

建立稳定的夜晚、白天、提名、投票、处决、死亡触发与局间隔离主链。

### 已完成内容

- 死亡触发链打通
  - 包括 `Ravenkeeper` 的 `death_trigger` 触发与结果回传
- 提名 / 投票 / 处决流程稳定化
  - 多轮提名
  - 顺序投票
  - 历史提名保留
  - 提名状态清理
- `game_id` 驱动的局间状态隔离
  - 聊天记录
  - 私密信息
  - 提名历史
  - 当前动作上下文
- 夜晚固定信息与私密信息链接通
- 前端动作重试提醒链建立
  - 空目标
  - 无效选择
  - night action / nomination / vote 错误提示

### 代表性修复

- `fortune_teller` 多目标嵌套列表导致死循环重试
- 提名选择器被轮询刷新重建
- 玩家端 `Join` 无反应、前端脚本重复声明导致初始化失败
- `reminder / retry_count / last_error` 未传达人类玩家
- 人类动作提交链静默失败

### 自动化门禁

- `frontend_acceptance.py`
- `nomination_acceptance.py`
- `night_info_acceptance.py`
- `wave1_acceptance.py`

---

## Wave 2：说书人与角色一致性增强

### 目标

把说书人从“零散信息提供者”推进成“规则内的真相源与裁量记录者”，同时提升角色技能实现与说书人信息链一致性。

### 已完成内容

- judgement ledger 建立
- 说书人裁定 bucket 分类完善
  - `fixed_info`
  - `storyteller_info`
  - `suppressed`
  - `legacy_fallback`
- 样本导出与评估基础设施建立
  - 静态样本
  - curated 节点样本
  - full-game 样本
  - full-game 聚合索引
- 说书人平衡裁量样本方向正式纳入规划
- 角色技能一致性增强第一轮

### 代表性修复

- `Undertaker` 误读旧轮次处决结果
- `Butler` 生效逻辑与事件 payload 语义不一致
- 说书人控制台 grimoire 请求缺 `player_id` 导致魔典快照为空
- `fortune_teller / investigator / librarian / washerwoman / chef / empath` 等信息角色的说书人结果链收口

### 自动化门禁

- `storyteller_acceptance.py`
- `role_acceptance.py`
- `storyteller_balance_acceptance.py`
- `wave2_acceptance.py`

---

## Wave 3：AI 玩家智能增强

### 目标

让 AI 玩家不只是“会返回动作 JSON”，而是拥有：

- 玩家视角边界
- 长短期记忆
- 社交图谱
- 身份声明认知
- 私密信息保留
- 基础人格差异

### 已完成内容

#### 1. 玩家视角隔离

- 主决策链从完整 `GameState` 收口到：
  - `AgentVisibleState`
  - `AgentActionLegalContext`
- 公开事件与私密视角分离
- “软隔离”推进到“接口级硬边界”

#### 2. 记忆系统接通

- `WorkingMemory`
- `EpisodicMemory`
- `SocialGraph`
- 阶段归档
- 长局记忆门禁

#### 3. 公开身份声明认知重构

- 不再用粗暴正则把“否认 / 质问 / 转述”误记成自报身份
- 建立结构化声明账本
  - `ClaimRecord`
  - `claim_history`
  - `self_claim / denial / question / accusation`
- 声明冲突会提升怀疑分

#### 4. 记忆分层可信度体系

正式建立三档记忆：

1. `OBJECTIVE`
   - 邪恶队友
   - bluff
   - 间谍魔典
   - 客观事件（提名、投票结果、死亡、处决等）

2. `HIGH_CONFIDENCE`
   - 角色私密信息
   - 夜晚结果
   - 可能受醉酒 / 中毒 / 说书人误导影响的信息

3. `PUBLIC`
   - 公开发言
   - 跳身份
   - 指认 / 质疑

#### 5. 关键私密结果开始真正影响推理

已经接入推理或上下文优先级的包括：

- 邪恶队友 / bluff / spy book
- `fortune_teller_info`
- `investigator_info`
- `washerwoman_info`
- `librarian_info`
- `undertaker_info`
- `ravenkeeper_info`
- `empath_info`
- `chef_info`

#### 6. 高可信信息优先于公开噪声

当公开声明与高可信私密结果冲突时：

- 高可信结果会被优先用于怀疑/信任判断
- 一致声明会降低疑点
- 冲突声明会提高疑点

### 代表性修复

- “我什么时候说我是士兵了” 被误记成跳士兵
- “我跳调查员并点名别人” 被错误记成被点名的人都是调查员
- 邪恶玩家对已确认队友仍产生高怀疑度
- 私密信息只存为普通文本锚点，无法跨阶段稳定使用
- 高可信夜晚结果容易被第二天公开噪声冲掉

### 自动化门禁

- `ai_evaluation.py`
- `ai_eval_acceptance.py`
- `long_loop_memory_acceptance.py`
- `long_game_ai_acceptance.py`
- `wave3_acceptance.py`

### 新增专项回归

- `test_claim_memory_regression.py`
- `test_numeric_info_memory_regression.py`

---

## Wave 4：结算、历史、复盘与封板体验

### 目标

把项目从“单局可玩”推进到“可结算、可复盘、可回看、可重复开局、可封板验收”。

### 已完成内容

#### W4-A 结算与复盘后端主链

- 游戏结束后生成 `settlement_report`
- 发布 `game_settlement`
- 持久化到 `GameRecordStore`
- `get_player_history(...)`

#### W4-B API 契约

- `/api/game/settlement`
- `/api/game/history`
- `/api/game/history/{game_id}`
- `/api/game/history/player/{player_name}`
- `/api/game/rematch`

#### W4-C 玩家端 Game Over Overlay 与 Rematch

- settlement overlay
- 角色揭示
- 时间线
- 统计区
- rematch hook
- setup / rematch 配置状态区分

#### W4-D 历史列表与详情

- 玩家端历史入口
- 历史列表
- 单局详情
- 从结算页跳转历史

#### W4-E 说书人端结算与复盘骨架

- 当前结算 / 封盘结果
- 历史对局
- 单局详情
- 复盘入口
- 魔典 / 夜晚信息入口修复

#### W4-F 聚合门禁

- `wave4_acceptance.py`
- `wave-4-release-checklist.md`

### 代表性修复

- `gameover_acceptance.py` 误把整份 API 长测拖进来导致长时间无结果
- SQLite 共享内存 keeper 连接未收尾导致测试进程无法退出
- `async with await self._connect()` 触发 `aiosqlite` 线程重复启动
- rematch 后错误回到 setup 配置流程
- 玩家端历史/结算入口收口
- 说书人页结算 / 历史 / 魔典可见性问题

---

## 这一版本中建立的验收体系

`alpha 0.2` 的一个重要成果，不只是写了很多功能，而是把大量能力沉淀成了脚本与测试门禁。

### Wave 聚合门禁

- `wave1_acceptance.py`
- `wave2_acceptance.py`
- `wave3_acceptance.py`
- `wave4_acceptance.py`

### 主题门禁

- `frontend_acceptance.py`
- `nomination_acceptance.py`
- `night_info_acceptance.py`
- `storyteller_acceptance.py`
- `storyteller_balance_acceptance.py`
- `role_acceptance.py`
- `gameover_acceptance.py`
- `ai_eval_acceptance.py`
- `long_loop_memory_acceptance.py`
- `long_game_ai_acceptance.py`

### 新增专项测试方向

- 身份声明长期稳定性
- 数值型高可信信息保留
- 高可信 vs 公开噪声冲突
- 守鸦人 / 送葬者 / 占卜师 / 调查员等私密结果链
- 结算 / 历史 / rematch / 说书人端 UI 契约

---

## 关键工程改进总结

这一版本里，最重要的工程性改进有：

### 1. 规则与流程不再只靠“能跑”

而是开始有：

- 明确的主链状态
- 重试提示
- 行为纠错
- 历史保留
- 独立验收入口

### 2. 说书人开始成为真相源

而不是角色各自零散给信息。  
现在说书人裁定已经拥有：

- judgement ledger
- 样本导出
- curated/full-game 样本
- 第一版验收门槛

### 3. AI 玩家开始拥有真正的“认知结构”

而不是只有 prompt 文本和一点短期上下文。  
现在已经有：

- 受限视角
- 分层记忆
- 情节归档
- 社交图谱
- 声明账本
- 基础人格画像

### 4. 项目开始具备“版本封板”基础

Wave 4 建立之后，项目已经具备：

- 单局结算
- 历史回放入口
- rematch
- 说书人端结算与复盘骨架
- Wave 级聚合验收

---

## 当前最适合在发布说明中强调的亮点

如果后续你要写对外发布说明，最值得提炼成亮点的内容是：

1. **规则主链稳定化**
   - 提名 / 投票 / 处决 / 夜晚流程更稳定

2. **说书人系统增强**
   - 说书人裁定记录、魔典、信息链与样本评估体系

3. **AI 玩家智能增强**
   - 视角隔离
   - 身份声明识别
   - 私密信息长期保留
   - 社交图谱与人格差异

4. **结算与复盘系统建立**
   - 结算页
   - 历史列表
   - 单局详情
   - rematch
   - 说书人端复盘骨架

5. **自动化验收体系成熟**
   - Wave 级门禁
   - 主题门禁
   - 角色 / 说书人 / AI / Game Over / History / UI 契约测试

---

## 仍应在发布时诚实说明的边界

`alpha 0.2` 已经进入“主结构完成、持续打磨”的阶段，但仍然有几类问题值得在发布时保持诚实：

1. AI 玩家虽然已经有更强的记忆和推理结构，但真人体验仍然在继续增强
2. 某些角色在复杂实战里的边界问题，仍可能继续被打出来并需要补丁
3. 说书人控制台与历史复盘虽然已有主骨架，但仍处于收尾阶段
4. 浏览器级最终封板验收仍应在发布前继续完成

---

## 一句话总结

`alpha 0.2` 的核心成果，不只是增加了更多功能，而是把项目从“能玩的一局游戏”推进成了一个：

**拥有稳定规则主链、可追踪说书人裁定、具备结构化 AI 认知、并开始拥有结算/历史/复盘体系的可持续迭代版本。**
