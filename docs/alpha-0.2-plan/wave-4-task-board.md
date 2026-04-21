# Alpha 0.2 Wave 4 任务板

## Wave 4 目标

把项目从“规则、说书人、AI 主链可用”推进到“可结算、可复盘、可封版验收”的状态。

Wave 4 的核心不是继续补底层规则，而是把已经稳定下来的系统能力沉淀成：

1. 游戏结束后的可信结算
2. 历史对局与复盘资产
3. 玩家端 / 说书人端最终体验收口
4. 自动化验收与最终封版门禁

---

## 当前优先级排序

### P0

1. `W4-A` 结算与复盘系统后端主链
2. `W4-B` Game Over 与历史查询 API 契约
3. `W4-C` Game Over Overlay 与 Rematch 交互

### P1

4. `W4-D` 历史对局列表与详情浏览
5. `W4-E` 说书人端收尾体验
6. `W4-F` Wave 4 验收聚合与封版门禁

---

## 任务拆分

## W4-A 结算与复盘系统后端主链

### 范围

- 游戏结束时生成结构化结算报告
- 将对局记录持久化到 SQLite
- 支持按 `game_id` / 玩家名查询历史

### 当前状态

- [game_loop.py](d:/鸦木布拉夫小镇/src/orchestrator/game_loop.py) 已有 `settlement_report` 骨架
- [game_record.py](d:/鸦木布拉夫小镇/src/state/game_record.py) 已有基础 SQLite store
- `get_player_history(...)` 已落地
- 已补 [test_game_record.py](d:/鸦木布拉夫小镇/tests/test_state/test_game_record.py)
- 已建立 [gameover_acceptance.py](d:/鸦木布拉夫小镇/scripts/gameover_acceptance.py)
- 当前主要剩余项是：让这条门禁稳定通过并完成 Wave 4 专用验收收口

### 具体任务 [PARTIAL]

1. 校验并补齐 `GameRecordStore` 的 CRUD 能力
2. 稳定共享内存 SQLite 测试路径，避免环境型文件库噪声
3. 为 settlement persistence 建立独立门禁并完成收口

### 验收

- [x] [test_game_record.py](d:/鸦木布拉夫小镇/tests/test_state/test_game_record.py) 通过
- [x] [gameover_acceptance.py](d:/鸦木布拉夫小镇/scripts/gameover_acceptance.py) 通过
- [x] 可稳定查询单局记录、列表记录和玩家历史

---

## W4-B 结算与历史 API 契约

### 范围

- `/api/game/settlement`
- `/api/game/history`
- `/api/game/history/{game_id}`
- `/api/game/rematch`

### 当前状态

- 这些端点大多已存在
- 结算/历史接口测试已从通用 API 大文件中拆出
- 已新增 [test_gameover_api.py](d:/鸦木布拉夫小镇/tests/test_orchestrator/test_gameover_api.py)
- 当前还缺 rematch 契约与完整 Wave 4 聚合门禁

### 具体任务 [PARTIAL]

1. 补 Game Over 场景 API 测试
2. 校验 settlement 响应字段完整性
3. 校验 rematch 基本契约

### 验收

- [x] [test_gameover_api.py](d:/鸦木布拉夫小镇/tests/test_orchestrator/test_gameover_api.py) 通过
- [x] `game_over -> settlement -> history detail` 主链稳定

---

## W4-C Game Over Overlay 与 Rematch 交互

### 范围

- Game Over 弹层
- 角色揭示
- 时间线与统计
- 再来一局

### 当前状态

- 已有前端骨架和主要渲染逻辑
- [index.html](d:/鸦木布拉夫小镇/public/index.html) 已包含：
  - `settlementOverlay`
  - 角色揭示
  - 时间线
  - 统计区
  - `requestRematch()`
- 已补自动化契约：
  - [test_gameover_ui.py](d:/鸦木布拉夫小镇/tests/test_orchestrator/test_gameover_ui.py)
  - [test_gameover_api.py](d:/鸦木布拉夫小镇/tests/test_orchestrator/test_gameover_api.py)
  - [gameover_acceptance.py](d:/鸦木布拉夫小镇/scripts/gameover_acceptance.py)
- 当前主要剩余项是：浏览器级最终封板与更完整的历史/复盘入口联动

### 具体任务 [PARTIAL]

1. 前端 overlay 结构和样式
2. settlement 数据渲染
3. rematch 按钮与 websocket 通知

### 验收

- [x] 结算层骨架与渲染 hooks 已建立自动化契约
- [x] rematch API 与前端重开 hooks 已建立自动化契约
- [ ] 浏览器级 `game_over -> settlement overlay -> rematch` 最终封板验收

### 近期稳定性修复

- [x] 修复 `fortune_teller` / 双目标夜晚行动在嵌套 `targets` 结构下可能进入无效重试循环的问题
  - [game_loop.py](d:/鸦木布拉夫小镇/src/orchestrator/game_loop.py) 现会展平嵌套目标列表后再执行角色能力
  - 已补专项回归：
    - [test_game_loop.py](d:/鸦木布拉夫小镇/tests/test_orchestrator/test_game_loop.py)
- [x] 修复“无效动作只在后端重试、人类玩家前端无感知”的问题
  - [human_agent.py](d:/鸦木布拉夫小镇/src/agents/human_agent.py) 现在会把 `required_targets / can_target_self / reminder / retry_count / last_error` 一并透传给前端
  - [index.html](d:/鸦木布拉夫小镇/public/index.html) 现在会将 `reminder` 明确显示给人类玩家，避免看起来像游戏卡死
  - 已补专项回归：
    - [test_human_agent.py](d:/鸦木布拉夫小镇/tests/test_agents/test_human_agent.py)

---

## W4-D 历史对局与复盘体验

### 范围

- 历史列表
- 单局详情
- 后续回放入口预留

### 当前状态

- 历史 API 已可用：
  - `/api/game/history`
  - `/api/game/history/{game_id}`
  - `/api/game/history/player/{player_name}`
- [index.html](d:/鸦木布拉夫小镇/public/index.html) 已新增：
  - 历史入口按钮
  - 历史列表弹层
  - 单局详情浏览
- 已补自动化契约：
  - [test_gameover_api.py](d:/鸦木布拉夫小镇/tests/test_orchestrator/test_gameover_api.py)
  - [test_gameover_ui.py](d:/鸦木布拉夫小镇/tests/test_orchestrator/test_gameover_ui.py)

### 具体任务 [PARTIAL]

1. 历史列表入口
2. 单局结算详情页或弹层
3. 复盘信息结构整理

### 验收

- [x] 历史列表与单局详情已有前后端最小闭环
- [x] 玩家名历史查询契约已落地
- [ ] 浏览器级历史浏览与复盘入口联动验收

---

## W4-E 说书人端封版体验

### 范围

- 说书人工作台收口
- 关键裁定与魔典展示优化

### 当前状态

- [storyteller.html](d:/鸦木布拉夫小镇/public/storyteller.html) 已新增：
  - 当前结算 / 封盘结果面板
  - 历史对局列表
  - 单局复盘详情面板
- 已补静态契约测试：
  - [test_storyteller_gameover_ui.py](d:/鸦木布拉夫小镇/tests/test_orchestrator/test_storyteller_gameover_ui.py)

### 具体任务 [PARTIAL]

1. 说书人端状态与历史面板整理
2. 结算后说书人复盘视图

### 验收

- [x] 说书人端已有结算与历史复盘视图骨架
- [x] 说书人端结算 / 历史 API hooks 已建立静态契约
- [ ] 浏览器级说书人复盘视图最终封板验收

---

## W4-F Wave 4 验收聚合与封版门禁

### 范围

- 后端 settlement 门禁
- 前端 Game Over 门禁
- rematch 门禁
- 文档与 release readiness

### 当前状态

- 已新增聚合门禁脚本：
  - [wave4_acceptance.py](d:/鸦木布拉夫小镇/scripts/wave4_acceptance.py)
- 已新增对应测试：
  - [test_wave4_acceptance.py](d:/鸦木布拉夫小镇/tests/test_orchestrator/test_wave4_acceptance.py)
- 已新增封版检查清单：
  - [wave-4-release-checklist.md](d:/鸦木布拉夫小镇/docs/alpha-0.2-plan/wave-4-release-checklist.md)

### 具体任务 [PARTIAL]

1. `wave4_acceptance.py`
2. 封版检查清单
3. Wave 4 发布前总回归

### 验收

- [x] `wave4_acceptance.py` 已建立
- [x] Wave 4 封版检查清单已建立
- [ ] 最终浏览器级封板验收与总回归仍待完成

---

## 建议执行顺序

1. **`W4-A`**：先把结算与持久化后端主链做实
2. **`W4-B`**：补 API 契约测试，锁死后端接口
3. **`W4-C`**：再做 Game Over Overlay 与 Rematch
4. **`W4-D` / `W4-E`**：补历史复盘体验与说书人端收尾
5. **`W4-F`**：最后聚合验收并准备封版

---

## 当前执行点

当前正式进入：

- **`W4-E`：说书人端封版体验收口**
