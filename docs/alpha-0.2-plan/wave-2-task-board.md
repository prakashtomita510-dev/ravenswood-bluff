# Alpha 0.2 Wave 2 任务板

## Wave 2 目标

把项目从“主流程稳定可跑”推进到“说书人与角色实现基本可信”，让系统在规则一致性、说书人裁定和高风险角色交互上建立更强的真相源。

Wave 2 聚焦四类问题：

1. 说书人真相源统一
2. 固定信息与自由裁量收口
3. 剩余高风险角色与组合交互补齐
4. Wave 2 自动化门禁建立

---

## 当前优先级排序

### P0

1. 说书人固定信息统一裁定
2. 高风险角色缺口补齐
3. 角色组合交互回归

### P1

4. 自由裁量场景建模与日志增强
5. 人类说书人辅助接口继续增强

### P2

6. Wave 2 聚合验收脚本化

---

## 任务拆分

## W2-A 说书人真相源统一

### 范围

- 固定信息角色统一走说书人裁定链
- 角色 helper 与说书人 adjudication 职责分离
- `storyteller_run.log` / judgement ledger 继续增强
- 建立说书人平衡裁量样本与评估基础设施

### 当前状态

- 说书人已经具备 `judgement ledger`
- 夜晚私密信息分发链已存在
- 固定信息角色已有较多回归，但仍需要统一化验收

### 具体任务

1. 固定信息角色输出格式继续统一
2. 明确 `build_storyteller_info` 与 `get_night_info` 的优先关系
3. 建立 Wave 2 说书人一致性验收入口
4. 为自由裁量场景补标准日志字段
5. 建立一批包含整局上下文的说书人裁量模拟样本
6. 为“尽量避免游戏过早结束 / 尽量维持双方悬念”建立基础观测指标

### 验收

- 说书人一致性验收脚本通过
- judgement ledger 能解释关键固定信息和压制信息
- 说书人裁量样本能够导出并复盘
- 至少能观测过早结束风险与单边碾压风险

### 当前结论

- `W2-A` 已完成
- 当前已具备：
  - 固定信息 / 说书人信息 / legacy fallback 的显式裁量路径
  - 静态样本、curated 节点样本、curated full-game 样本、mock full-game 样本
  - 分布级聚合指标与局部 `sample_index.json`
  - `storyteller_balance_acceptance.py` 的裁量质量门槛

---

## W2-B 高风险角色补齐

### 范围

- 绯红女郎
- 男爵
- 管家
- 市长
- 杀手
- 隐士
- 酒鬼边界

### 当前状态

- 第一批高风险角色已有实现和回归
- 仍需继续扩展到剩余高风险角色与边界

### 具体任务

1. 明确剩余高风险角色当前实现状态
2. 为每个高风险角色补至少 1 条规则回归
3. 把高风险角色主链纳入统一 acceptance gate

### 验收

- 高风险角色 acceptance gate 通过
- 规则矩阵中高风险角色覆盖继续扩大

---

## W2-C 角色组合交互测试

### 范围

- 投毒者 + 信息位
- 僧侣 + 小恶魔
- 隐士 / 间谍 + 侦测角色
- 圣女 / 圣徒 + 处决链
- 绯红女郎 + 恶魔死亡

### 当前状态

- 已有部分散落在回归中的覆盖
- 还没有作为 Wave 2 独立主题收口

### 具体任务

1. 整理现有组合交互回归覆盖空白
2. 补首批高风险组合交互测试
3. 将组合交互纳入 Wave 2 验收

### 验收

- 首批组合交互回归通过
- Wave 2 验收脚本能覆盖角色组合场景

---

## W2-D Wave 2 自动化门禁

### 范围

- 说书人一致性验收
- 高风险角色验收
- 组合交互验收
- Wave 2 总验收入口

### 当前状态

- Wave 1 已经建立了聚合验收思路
- Wave 2 还没有独立门禁入口

### 具体任务

1. 建立 `storyteller_acceptance.py`
2. 建立 `role_acceptance.py`
3. 建立 `wave2_acceptance.py`
4. 为上述脚本补测试

### 验收

- 3 条脚本可直接运行
- Wave 2 总验收入口可重复执行

---

## 建议执行顺序

1. `W2-D`
2. `W2-A`
3. `W2-B`
4. `W2-C`

原因：

- 先建立 Wave 2 自动化门禁，后续每轮增强都有抓手
- 再统一说书人真相源，避免角色实现和裁定链继续分叉
- 然后补角色和角色交互

---

## 完成标准

Wave 2 视为完成，需要同时满足：

1. 说书人固定信息与压制信息链有统一验收
2. 剩余高风险角色主链有自动化覆盖
3. 首批角色组合交互测试通过
4. Wave 2 有独立聚合验收入口
5. 规则矩阵与专项计划同步更新

---

## 当前进度快照（2026-04-09）

### 已启动

- Wave 2 任务板已建立
- 正在建立 Wave 2 初始验收门禁
- `storyteller_acceptance.py` 已建立
- `role_acceptance.py` 已建立
- `wave2_acceptance.py` 已建立
- `W2-A` 第一批代码实现已完成：说书人裁定现已显式记录 `contract_mode / adjudication_path / distortion_strategy`
- `W2-A` 现已显式区分 `fixed_info` 与 `storyteller_info` 的压制路径，并为 `fortune_teller` 与 `legacy fallback` 补了专项回归
- `W2-A` 已补充“说书人平衡裁量模拟数据与评估”作为第二批工作目标
- `W2-A` 第二批基础设施已起步：`storyteller_eval_samples/` 现已包含 3 个静态样本与 1 局完整 mock 对局导出的 17 个裁量节点样本
- `W2-A` 样本导出与验收入口已做轻量化：测试默认使用静态样本或短 trace，整局/多局样本导出通过脚本参数显式触发
- `W2-A` 节点样本索引现已包含按节点累计的 `aggregate_balance_summary`，可直接观测 `node_count / judgement_entry_count / event_node_fallback_count / private_info_delivery_node_count` 等指标
- `W2-A` 已补上首条“节点事件 -> 真实 night_info judgement”匹配规则，`private_info_delivered` 节点不再只能依赖 `event_node` fallback
- `W2-A` 样本导出现已包含一批策划好的 `curated_nodes`，用于稳定覆盖 `night_info judgement`，避免整局短 trace 因随机阵容而完全看不到说书人裁定节点
- `W2-A` 现已加入策划好的 `empath_suppressed / legacy_fallback / daytime_resolution` 样本，`sample_index.json` 中的 `suppressed_info_count / distorted_info_count / legacy_fallback_count` 已不再为 0
- `W2-A` 白天节点匹配规则已细化到事件类型级别，`nomination_started / voting_resolved / execution_resolved` 不再共享同一个 trace 就互相错挂
- `W2-A` full-game 节点样本已开始稳定绑定真实 judgement；当前主输出索引中的 full-game `event_node_fallback_count` 已降到 `0`
- `W2-A` 现在会为每个 `full_game_nodes/<game_id>` 与 `curated_nodes/<scenario>` 额外写入局部 `sample_index.json`，便于逐局/逐场景检查
- `W2-A` 聚合摘要已扩展到分布级指标：`judgement_category_counts / judgement_bucket_counts / distortion_strategy_counts / adjudication_path_counts / phase_counts / event_type_counts`
- `W2-A` 现已把这些分布级指标正式接入 `storyteller_balance_acceptance.py`，当前 acceptance 会检查：
  - 至少存在 `night_info / suppressed / distorted / legacy_fallback` 样本
  - 至少存在 full-game 样本
  - 首个 full-game 样本的 `event_node_fallback_count == 0`
  - 首个 full-game 样本已覆盖 `private_info / night_action / nomination_started / voting_resolution / execution`

### 下一步

- 切换到 `W2-B`：高风险角色与组合交互补齐
- `W2-A` 后续若再增强，归类为增量优化而不是阻塞项：
  - 扩充更多离线长局样本
  - 继续提升 full-game `night_info` 密度
  - 补更细的平衡指标与裁量评分函数

### 当前基线

- `scripts/storyteller_acceptance.py`：`storyteller acceptance: ok`
- `scripts/role_acceptance.py`：`role acceptance: ok`
- `scripts/wave2_acceptance.py`：`wave2 acceptance: ok`
- `pytest tests -q`：`189 passed`
