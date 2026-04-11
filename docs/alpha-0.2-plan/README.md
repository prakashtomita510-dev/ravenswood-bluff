# Alpha 0.2 规划总览

## 目标

`alpha 0.2` 的目标不是单纯“继续补功能”，而是把 `alpha 0.1` 已经建立起来的完整游戏骨架，推进到一个“更像真人对局、更接近规则书、更适合持续演进”的阶段。

本阶段的重点方向分为四条主线：

1. AI 玩家智能增强
2. 说书人裁定能力增强
3. 规则一致性继续收口
4. 前端体验与自动化验收增强

其中，AI 玩家智能增强会作为本阶段的重要专项推进，因为它会直接影响：

- 提名是否自然
- 投票是否可信
- 发言是否像真人
- 邪恶阵营伪装是否合理
- 好人阵营信息整合是否有连续性

---

## 当前已建文档

- [Alpha 0.2 路线图](/d:/鸦木布拉夫小镇/docs/alpha-0.2-plan/roadmap.md)
- [Wave 1 任务板](/d:/鸦木布拉夫小镇/docs/alpha-0.2-plan/wave-1-task-board.md)
- [Wave 2 任务板](/d:/鸦木布拉夫小镇/docs/alpha-0.2-plan/wave-2-task-board.md)
- [AI 玩家智能增强计划](/d:/鸦木布拉夫小镇/docs/alpha-0.2-plan/ai-player-intelligence-plan.md)
- [说书人智能优化计划](/d:/鸦木布拉夫小镇/docs/alpha-0.2-plan/storyteller-intelligence-plan.md)
- [说书人平衡裁量模拟与评估计划](/d:/鸦木布拉夫小镇/docs/alpha-0.2-plan/storyteller-balance-simulation-plan.md)
- [角色业务实现与验证计划](/d:/鸦木布拉夫小镇/docs/alpha-0.2-plan/role-implementation-and-validation-plan.md)
- [前端界面优化计划](/d:/鸦木布拉夫小镇/docs/alpha-0.2-plan/frontend-ui-optimization-plan.md)
- [自动化验收与测试计划](/d:/鸦木布拉夫小镇/docs/alpha-0.2-plan/acceptance-and-testing-plan.md)

---

## 推荐推进顺序

### 第一阶段

- 修复当前高优先规则与流程问题
- 稳定提名、投票、死亡触发、夜晚信息链
- 保证 `alpha 0.1` 基线稳定

### 第二阶段

- 推进 AI 玩家智能增强专项
- 建立更严格的玩家视角包
- 增强人格系统、记忆系统、社交推理

### 第三阶段

- 推进更强的说书人主观裁定能力
- 做前端自动化验收与体验收敛
- 为后续 beta 版本打基础

---

## 使用方式

这个目录下的文档建议作为：

- 版本路线图
- 设计对齐文档
- 任务拆分前的依据
- 回归验收的基准说明

后续如果继续推进 `alpha 0.2`，建议在本目录下继续补：

- `player-knowledge-boundary-plan.md`
- `release-readiness-checklist.md`
- `performance-and-observability-plan.md`
