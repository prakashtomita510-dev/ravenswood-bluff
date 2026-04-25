# Mission: A3-GAME 游戏逻辑与交互体验任务板

## 当前定位

- **当前阶段**: `Hardened & Verified`
- **目标**: 补完游戏核心规则的确定性、特殊技能全链路和邪恶阵营战术智能。已完成全量审计与漏洞修复。
- **关联文档**:
  - [full_plan.md](D:/鸦木布拉夫小镇/docs/alpha-0.3-plan/full_plan.md) §7
  - [execution_summary.md](D:/鸦木布拉夫小镇/docs/alpha-0.3-plan/execution_summary.md)

---

## 状态总览

| 子任务 | 状态 | 说明 |
| :--- | :--- | :--- |
| GAME-1：规则确定性保证 | `Done` | 夜晚排序、ON_DEATH、统一存活校验、投票幽灵票校验已全部钉实 |
| GAME-2：特殊技能全链路 | `Done` | 猎手主动触发（含 AI）已落地；圣女触发逻辑已钉实并修复了提名中断漏洞 |
| GAME-3：邪恶阵营战术智能 | `Done` | 防御感应、哑刀分析、Star-pass、投毒者 AI 及夜间/白天协作智能已全部落地 |

---

## GAME-1：规则确定性保证

### GAME-1.1：夜晚行动顺序

- [x] 所有角色定义包含 `night_order` 字段
- [x] `StorytellerAgent.build_night_order()` 按 `night_order` 排序
- [x] `_execute_night_actions()` 中已死亡玩家跳过行动（ON_DEATH 除外）
- [x] ON_DEATH 触发器（守鸦人）独立处理流程 `_resolve_on_death_triggers()`
- [x] 补齐 `night_order` 与官方规则书的精确对齐校验
- [x] 增加 night_order 冲突检测日志

### GAME-1.2：存活状态实时性

- [x] `_execute_night_actions()` 中对已死亡玩家做存活检查后跳过
- [x] `ImpRole.execute_ability()` 中检查目标是否存活
- [x] 统一抽象 `_ensure_player_alive(...)` 工具方法，并已接入猎手与提名主链
- [x] 投票阶段对已死亡玩家（幽灵票）的合法性校验增强 (`nomination.py`)
- [x] 提名阶段对被提名人的二次存活检查（提名发起后、投票开始前如果目标因猎手技能死亡）

--- [x] **GAME-1: 游戏主循环稳定性修复** (已完成)
- [x] **GAME-2: 多 Agent 协作与状态同步验证** (已完成)
- [x] **GAME-3: AI 策略感知与动态调整 (Strategic Awareness)** (已完成)
- [x] **GAME-4: 游戏结束逻辑与统计导出** (已完成)

### 2. 验收状态 (Hardened & Verified)
- **状态**: ✅ 已完成 (2026-04-23)
- **验收工具**: `scripts/a3_memory_acceptance.py`, `scripts/storyteller_acceptance.py`
- **结果**: AI 能够基于分层记忆做出合理决策，说书人平衡逻辑已埋点并可导出。
- **最终审计**: 修复了 `ai_agent.py` 中的 `AttributeError` 和说书人判定类别名称不匹配问题。

---

## GAME-2：特殊技能全链路

### GAME-2.1：猎手（Slayer）白天主动触发

- [x] SlayerRole 角色定义与 `execute_ability()` 实现
- [x] `_execute_slayer_shot()` 原子化执行方法
- [x] 白天讨论/提名阶段 `slayer_shot` 动作识别与执行
- [x] AI 猎手主动决策：根据局势（怀疑度 > 阈值）自主发动技能

### GAME-2.2：其他白天主动技能

- [x] 贞洁者（Virgin）被提名时的自动触发逻辑 (`nomination.py`)
- [x] **[BUGFIX]** 修复了提名阶段在触发圣女处决后未中断循环的漏洞 (`game_loop.py`)

---

## GAME-3：邪恶阵营战术智能

### GAME-3.1：防御感应

- [x] `_get_evil_strategic_summary()` 提取僧侣/士兵/市长的公开声明
- [x] **[ENHANCED]** 增加“隐性保护推断”：基于连续平安夜与无人跳僧侣推测隐形防御位
- [x] **[ENHANCED]** 防御位优先级排序：在建议中明确标注高风险目标，引导 AI 避开

### GAME-3.2：反馈闭环（哑刀分析）

- [x] 恶魔攻击失败时记录 `failed: True` 事件
- [x] 连续失败追踪：针对同一目标的连续 2+ 次失败发出“高危警报”并强制建议换人
- [x] **[ENHANCED]** 市长转位场景分析：检测“目标未死但其他人死亡”的特征，精准识别市长存在

### GAME-3.3：高级战术 — Imp Star-pass

- [x] `ImpRole.execute_ability()` 支持自杀选项与爪牙继承
- [x] 绯红女郎优先接管，无绯红女郎时普通爪牙接管
- [x] Star-pass 后继承者的 `perceived_role_id` 与 bluffs 信息同步更新

### GAME-3.4：邪恶阵营协作智能

- [x] 爪牙在白天发言中配合恶魔伪装：`_evil_coordination_line` 实现对队友身份的兜底支持
- [x] 投毒者智能选毒：`_poisoner_priority_for_target` 优先攻击核心信息位
- [x] 邪恶阵营夜间私聊同步：`build_evil_night_coordination_message` 在关键行动后发送战术同步

---

## 当前阻塞与风险

1. **审计结论**: GAME 部分工作已完成 100%，此前存在的任务板描述与代码不完全一致的问题（如市长分析仅有文字无逻辑、提名循环漏洞）已通过本次专项修复补完。
2. **性能观察**: 大量 AI 决策上下文注入（如战略建议）会增加 Prompt 长度，需关注 Token 消耗。

---

## 变更记录

- **2026-04-23**: 专项审计：修复了 `game_loop.py` 中圣女处决后不中断提名循环的漏洞。
- **2026-04-23**: 逻辑补全：增强了 `ai_agent.py` 中的市长转位识别逻辑和隐性保护推断算法。
- **2026-04-23**: 任务板同步：清理了已过时的代码行号引用，基于最新审计结果重置状态。
