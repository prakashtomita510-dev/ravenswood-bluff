# 验证与修复记录

## 本轮验证范围
- 局部回归测试
- MockBackend 快速模拟局
- API 入口下的全 AI 实际链路
- OpenAIBackend 短局验证

## 发现的问题
1. `simulate_game.py` 会因为 `.env` 中存在 `OPENAI_API_KEY` 而默认走真实 backend，无法承担“快速审计脚本”的职责。
2. AI 在 `nominate` / `vote` / `defense_speech` 阶段缺少合法动作兜底，模型返回非法结构时会导致白天链路空转。
3. `MockBackend` 只靠模糊关键词判断动作类型，而系统提示词中同时包含多个动作名，容易把提名/投票误判成夜晚行动。
4. API 缺少轻量级指标接口，难以快速判断是否真正发生了提名、投票和处决。
5. `/api/game/start` 会重复拉起游戏循环，存在并发推进同一局的风险。
6. 真实 backend 的 5 人短局在 60 秒内只能推进到首轮投票前后，说明 live 模式仍然偏慢。

## 已完成修复
- `simulate_game.py` 改为显式 `--backend mock|live`，默认 `mock`。
- `AIAgent` 增加动作类型提示、结构化校正和本地兜底策略。
- `MockBackend` 改为优先解析“当前需要执行的动作类型”。
- orchestrator 在提名阶段新增 `nomination_prompted` / `nomination_attempted` 审计事件，并支持 `max_nomination_rounds`。
- API 新增 `/api/game/metrics`，并把 `/api/game/start` 改为幂等。
- 说书人控制台接入 `/api/game/metrics` 与 `/api/storyteller/night/next`。

## 本轮结果
- `pytest tests -q`：`91 passed`
- Mock 模拟局：已稳定出现合法提名、投票、处决
- API 全 AI Mock 链路：已验证 `setup -> nomination -> voting/execution`
- Live 短局：已验证真实模型能推进到白天提名，但 60 秒内未稳定完成首次处决

## 下一步建议
- 优先优化 live 模式的白天行动耗时，特别是顺序投票阶段。
- 继续补完剩余角色边界，并把 `validation_report.md` 中的问题项绑定到更细的回归测试。
