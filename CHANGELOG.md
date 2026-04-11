# Changelog

## [alpha0.2_dev] - 2026-04-11

本版本作为 Alpha 0.2 阶段的起始线，沉淀并加固了 Alpha 0.1 期间建立的引擎主流程。

### 🌟 新增特性 (New Features)
- **完备的长期计划管理体系**：新增 `docs/alpha-0.2-plan/` 目录，涵盖从 AI 玩家智能增强、前端迭代到说书人平衡裁量的详细路线图和任务看板。
- **说书人平衡裁量与日志框架**：
  - 新增 `storyteller_balance.py` 与专属平衡裁定验收体系。
  - 支持更好的后台日志生成、输出样本记录（`generate_storyteller_balance_samples.py`），优化模拟裁定体验。
  - 说书人智能已可对酒鬼、间谍等特殊角色的触发进行更高层维度的决策。
- **录像回放与解析器**：新增 `replay_parser.py` 解析器支持，增强了后端引擎回溯调试的能力。
- **自动化验收链路全面升级**：为不同子系统提供了针对性的独立验证脚本。
  - `night_info_acceptance.py`：负责夜晚私密信息链断言验证
  - `nomination_acceptance.py`：负责各类提名环节流转逻辑约束和断言
  - `role_acceptance.py` & `storyteller_acceptance.py`：负责角色能力及说书人裁断的综合判定
  - `frontend_acceptance.py`：负责验收前、后端 WebSocket 连接和 API 通信契约
  - Wave 1 & Wave 2 的总体流程测试套件完善。

### 🛠 修复与架构改进 (Fixes & Improvements)
- 根除了前端的局间状态污染机制，修正了 `index.html` 中的轮次历史缓存溢出和错误。
- 优化了 `game_loop.py` 主循环：细化了阶段（Phase）更迭、事件投递与死者信息的播报时机，减少了 AI 行为错位现象。
- 完善了核心 API 服务 (`server.py`) 中客户端掉线重连的状态处理，重开局状态彻底解耦。
- `test_orchestrator` 下增加大量单元与集成测试，覆盖说书人决策、夜间阶段等各类异常情况处理。
