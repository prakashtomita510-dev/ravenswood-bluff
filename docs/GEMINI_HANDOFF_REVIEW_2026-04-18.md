# Gemini 移交文档复核记录（2026-04-18）

## 复核对象

- 原始文档：
  [handoff_document.md.resolved](c:/Users/Administrator/.gemini/antigravity/brain/3c148675-4d2e-472a-a96f-73c3abf18428/handoff_document.md.resolved)

## 复核结论

总体判断：

- Gemini 这份移交文档没有大面积失实。
- 夜晚交互稳定化、强制目标重试、提名显式“不提名”等核心工作，大多已经真实落地。
- 但文档里存在：
  - 1 处明显过时项
  - 1 处实现与文档描述不完全一致
  - 若干把“阶段性完成”写得偏满的表述

---

## 已核实属实的部分

### 1. Night Phase Stabilization

- `_pending_night_action` 已真实存在于 [game_loop.py](d:/鸦木布拉夫小镇/src/orchestrator/game_loop.py)
- `/api/game/state` 已返回 `active_action_request`
- 夜间行动的 mandatory retry 已真实落地：
  - `while True`
  - `required_targets > 0` 时空选会触发 reminder 并重试

### 2. Interaction Improvements

- `InformationBroker.get_action_legal_context(...)` 已对提名加入 `"not_nominating"`
- 人类提名、投票、夜晚行动都已有 `reminder` 机制
- 空提交不会再悄悄落成模糊状态

### 3. Chronology & Day Counting

- [phase_manager.py](d:/鸦木布拉夫小镇/src/engine/phase_manager.py) 当前逻辑已经实现：
  - `FIRST_NIGHT -> day_number = 1`
  - 每次进入 `NIGHT` 时 `day_number += 1`
  - 白天与对应夜晚共享同一 `day_number`

---

## 发现的问题

### A. 文档已过时：Ravenkeeper ON_DEATH

Gemini 文档仍把 `Ravenkeeper ON_DEATH` 写成 pending。

但当前主线里已经有完整链路：

- `_resolve_on_death_triggers(...)`
- `death_trigger_requested`
- `death_trigger_resolved`
- 守鸦人私密信息发放

相关测试也已存在：

- [test_game_loop.py](d:/鸦木布拉夫小镇/tests/test_orchestrator/test_game_loop.py)
- [test_role_skill_audit.py](d:/鸦木布拉夫小镇/tests/test_engine/test_role_skill_audit.py)
- [test_high_risk_roles.py](d:/鸦木布拉夫小镇/tests/test_engine/test_high_risk_roles.py)

结论：

- 这是文档滞后，不是功能缺失。

### B. Butler 文档与实现曾存在不一致

Gemini 文档写的是：

- `ButlerRole` 的 `applies_on_day` 已从 `+1` 改为当前 `day_number`

复核时发现：

- 状态 payload / binding 生效逻辑已经使用当前 `day_number`
- 但 `butler_binding` 事件 payload 仍然残留旧语义 `day_number + 1`

这一点已在本次收尾中修正：

- [outsiders.py](d:/鸦木布拉夫小镇/src/engine/roles/outsiders.py)

并补充了回归测试：

- [test_high_risk_roles.py](d:/鸦木布拉夫小镇/tests/test_engine/test_high_risk_roles.py)

结论：

- 这不是主流程级漏洞
- 但属于“文档说完成，实际仍有语义残留”的典型例子

### C. Slayer 显式 Pass 仍未完成

Gemini 把这项列为 pending，这个判断目前仍成立。

当前 Slayer 已有：

- 一次性能力
- 击中恶魔即死
- 消耗 shot

但尚未完全做成和提名一样的：

- “使用能力 / 明确放弃” 显式二选一契约

结论：

- 这项确实还应保留在后续任务里。

---

## 结论归类

### 文档属实

- 夜晚 pending action 持久化
- `active_action_request` API 暴露
- mandatory retry
- nomination `"not_nominating"`
- reminder 机制
- day/night chronology 调整

### 文档过时

- `Ravenkeeper ON_DEATH` 仍写成 pending

### 文档与实现曾有偏差，但已修复

- Butler `applies_on_day` 事件 payload 与真实生效逻辑不一致

### 文档中仍然合理保留为 pending

- Slayer 白天显式 `Use Shot / Pass`
- 测试与持久化环境的进一步稳定化

---

## 当前建议

1. 不再把 `Ravenkeeper ON_DEATH` 视为待修项
2. 后续继续追踪 Slayer 显式交互契约
3. 未来所有移交文档应区分：
   - 已落地主链
   - 已有部分实现
   - 文档计划 / pending

这样可以避免把“阶段性结果”误读成“正式完成”。
