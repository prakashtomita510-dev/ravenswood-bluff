# Alpha 0.2 Wave 3 任务板

## Wave 3 目标

把项目从“说书人和规则底层稳定”推进到“AI 玩家的行为和推理更像真人”。
让 AI 玩家从机械式的“规则参与者”，进化为具备连续逻辑、多层次人格表现、能随着场上局势灵活调整决策的“社交推理体”。

Wave 3 聚焦五类问题：

1. 玩家视角包与真相数据彻底隔离
2. 提名、投票与发言策略去机械化
3. 多层人格系统扩展（脱离目前千篇一律的单一执行模式）
4. 社交图谱与情节记忆连贯性对接
5. AI 智能水平的可观测性与评估基准建设

---

## 当前优先级排序

### P0

1. 玩家视角彻底隔离，根除 AI 对全局状态/隐藏信息的“合法作弊”
2. 取消默认的提名排序，引入“不提名 (none)”逻辑，根除机械前置位提名行为
3. 建立并连通结构化的“社交图谱演化”机制，使 AI 具有最基本的社交倾向变化

### P1

4. 引入具体的多层人格模板（包含：原型、偏置、角色覆盖层）
5. 支持连续的工作记忆提取与白天/夜晚情节总结，降低模型幻觉
6. 完善基于发言脉络（而非纯凭阈值）判断的投票及辩解策略

### P2

7. 搭建基于指标的 AI 评估脚本（如：`ai_nomination_rate`、`persona_diversity_score`）
8. Wave 3 专项自动化验收打死角漏洞

---

## 任务拆分

## W3-A 玩家视角包重构与重度隔离

### 范围

- 取消对 `game_state` 内部隐藏字段的直接读取
- 重构对 `true_role_id` 及不可见状态（如中毒/酒鬼）的上下文遮蔽
- 明确划分 `storyteller_truth_view`、`player_identity_view` 和 `player_knowledge_inbox`

### 当前状态

- 尽管前后端已存在一定数据过滤，但在 Prompt 或 Context 中仍有可能无意中把说书人级别的判断透给 AI（如：知道自己其实是酒鬼）。

### 具体任务 [DONE]

1. 检查和清理 AI Agent 内部的所有信息通道，彻底移除 `true_role_id` 直接下发到 LLM 并替换为 `perceived_role_id`
2. 筛除不在 `player_knowledge_inbox` 中的私密信息
3. 写定测试：确保隐士、间谍等被污染的角色和中毒酒鬼的 Agent 决策时不带有真相层的影子

### 验收

- [x] `scripts/player_knowledge_acceptance.py` 已可作为正式自动化门禁运行
- [x] `AIAgent` 主决策链已收口到 `AgentVisibleState + AgentActionLegalContext`
- [x] `BaseAgent.act()` / `observe_event()` 的接口级输入已从 `GameState` 切走
- [ ] 仍建议补一条更强的 prompt 截获/断言脚本，作为增强项防止后续回退

---

## W3-B 提名/投票策略去机械化

### 范围

- 打破自动按前置位顺延选择的固有逻辑
- 加入明确“放弃提名/跳过操作”的评估决策
- 重塑投票机制从纯量化指标走向局势评估

### 当前状态

- Agent 经常默认寻找一个最先顺位的合法目标进行提名。
- 极少根据大盘局势去自主选择“保留态度”或不投票。

### 具体任务 [DONE]

1. 允许并训练 Agent 在怀疑度与证据不足够高时进行明确的 `none` 提名操作。
2. 为投票环节增加针对群体反应及当前已产生的候选人票数的感知系统。
3. 增加发表明确保人/踩人态度的对话风格及动作映射。

### 验收

- [x] 已补 `scripts/long_game_ai_acceptance.py`，覆盖跨日提名 / 投票 / 记忆 / 社交图谱长局门禁。
- [x] 已接入 `scripts/ai_evaluation.py` 的轻量门禁，覆盖 `ai_none_nomination_rate` 与强信号提名率。
- [x] 已补趋势观察，不再只看单次 `ai_none_nomination_rate`，当前已覆盖多局多轮压力档位。
- [x] 已补“机械顺位提名偏置”门禁，覆盖：
  - `front_position_nomination_bias_rate`
  - `ambiguous_nomination_diversity_score`
- [x] 已补人格化投票画像门槛，覆盖：
  - `aggressive_vote_push_rate`
  - `silent_vote_restraint_rate`
  - `cooperative_follow_rate`
- [x] 已补更完整的长局级行为画像回归，确认不同人格在跨日对局里保持稳定分歧与非机械化策略。

---

## W3-C 多层人格系统扩展

### 范围

- 配置不同的基础原型：谨慎、强势、圆滑、搅局等
- 与分配到的角色绑定，产生“职业与人格叠加的特殊发挥”

### 当前状态

- 已存在如 `voice_anchor` 和 `assertiveness` 等基础维度设定。
- 实际发言和倾向仍然高度趋同，多名 AI 发出的思考非常同步。

### 具体任务 [DONE]

1. 制定 5~6 种基础玩家人格模板与其初始设定偏重矩阵。
2. 提供一套覆盖角色特殊视角的融合 Prompt 架构。
3. 让这套人格影响它的怀疑阀值：强势人格容易乱提名，谨慎人格则频繁试探。

### 验收

- [x] 已补更大样本的人格分歧回归，当前由 `scripts/long_game_ai_acceptance.py` 覆盖长局稳定性与人格分歧。
- [x] 已落地 `persona_diversity_score` 轻量门禁。
- [x] 已补对局级人格多样性观察门禁，覆盖：
  - `long_game_persona_diversity_score`
  - `long_game_stability_score`

---

## W3-D 社交图谱与情节记忆连绵推演

### 范围

- 清理冗长过时的局部记录（Token浪费），提制摘要
- 事件响应自动化影响 `SocialGraph` 更新
- 长线多日的追溯引用

### 当前状态

- `WorkingMemory` 已有，但更像是个堆栈。
- 没有成体系的关键事件和“情节推演”抽象机制。

### 具体任务 [DONE]

1. 设计“阶段总结”抽象：比如每次晚上降临时，自动对全体白天发生的最重大争吵与暴露信息进行短文本蒸馏提取。
2. 为 Agent 提供动态修改与更新对场上别人“信任/敌视”图谱的基础算子。
3. 基于他人多次出现的言论矛盾扣除信用分，并在发言时直接引用。

### 验收

- [x] 已落地 `scripts/long_loop_memory_acceptance.py`，覆盖跨阶段情节记忆与社交图谱累积。
- [x] 已补 `tests/test_orchestrator/test_long_loop_memory_acceptance.py`，校验 episode 递增、跨日摘要、trust 累积和工作记忆清理。
- [x] 已补更完整的跨日 / 跨局趋势回归，当前由 `scripts/long_game_ai_acceptance.py` 校验跨日摘要保留与社交轨迹一致性。
- [x] 已补图谱转移轨迹断言门禁，覆盖：
  - `long_game_social_consistency_rate`
  - `bob/eve vs cathy` 的跨日 trust 关系
- [x] 会话隔离与跨局稳定性已纳入长局脚本的多局重复验收。

---

## W3-E 评估体系与门禁搭建

### 范围

- 专项指标设定
- 日志系统针对怀疑度、投票轨迹扩展追踪
- W3 专属测试通过率守护

### 当前状态

- 前两波 Wave 已构建设基础设施和断言，但主要集中规则合乎性校验，没有 AI 拟人化/智能化质量判定机制。

### 具体任务 [DONE]

1. 增加 AI Agent 指向目标的多维评价得分打分器 (`ai_evaluation.py`)。
2. 针对 W3 增加自动回归入口：用模拟场景强制检查它的判定机制。

### 验收

- [x] 已落地 `scripts/wave3_acceptance.py` 与 `scripts/ai_eval_acceptance.py`
- [x] 已落地 `scripts/long_game_ai_acceptance.py`，并接入 `wave3_acceptance.py`
- [x] 已落地 `scripts/ai_evaluation.py`，覆盖多局多轮趋势指标：
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
- [x] 已补更长局、更大样本的趋势门禁，Wave 3 现同时具备短局趋势门禁与长局行为门禁。

---

## 建议执行顺序

本规划基于极强的前后依赖，优先推荐下列步骤：

1. **`W3-B` 提名与投票去机械化：** 最容易继续出成效，迅速改善真人体感的顽疾痛点。
2. **`W3-C` 多层人格系统：** 给 Agent 提供行为背后的逻辑支架。
3. **`W3-D` 社交图谱对接：** 使这种多变的框架能够获得多日的推理持久力支撑。
4. **`W3-E` 评估体系：** 将阶段性的测试成果量化并建立版本拦截器。

---

## 完成标准

Wave 3 视为完成，需要同时满足：

1. 不再发生由于 AI 直接读懂 `true_role_id` (酒鬼身份、间谍身份等) 导致的超维操作及隐患。
2. 发言和提名具备强烈的真人对战临场感（弃票和策略性挂机合理呈现）。
3. 人格化和长期追凶能力（哪怕出错也是基于其预设立场而合规出错）肉眼可见且数据验证一致。
4. 新增的 `wave3_acceptance.py` / `ai_eval_acceptance.py` / `long_game_ai_acceptance.py` 脚本全部通过，并补上更细的指标级门禁。
5. 可以宣告项目准备好进入 Wave 4（前端封版打磨）流程。

---

## 当前结论

Wave 3 当前已完成。

剩余工作若继续推进，属于增强项而非阻塞项，例如：

- 更长的真人前端整局 playtest
- 更细的 persona 漂移可视化
- 更复杂的长局统计面板
