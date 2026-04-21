# 游戏结算与复盘系统开发计划

## Alpha 0.2 阶段归属

本计划已纳入 `alpha 0.2` 总体规划，建议安排在 **Wave 4：前端体验与封版验收** 中实施，作为 Wave 4 的核心工作包之一。

### 为什么放在 Wave 4

游戏结算与复盘系统虽然涉及后端、存储、API 和前端，但它本质上是一个“汇总层”和“封版层”能力，强依赖前面阶段已经稳定的基础设施：

1. **依赖 Wave 1 的规则主链稳定化**
   - 结算报告需要依赖稳定的提名、投票、死亡、夜晚信息与胜负判定
   - 如果前置流程仍在变化，结算格式和统计口径会反复返工

2. **依赖 Wave 2 的说书人与角色一致性**
   - 复盘系统必须展示可信的角色真相、关键裁定与事件时间线
   - 说书人真相源和高风险角色逻辑未稳定前，不适合固化复盘结构

3. **依赖 Wave 3 的 AI 与日志体系增强**
   - 如果后续要支持更丰富的复盘内容，如 AI 赛后感言、关键行为解释、思考摘要，必须先有稳定的 AI 记忆/评估基础
   - 事件日志、裁定日志、玩家可见信息链都在 Wave 3 之后更适合被沉淀为复盘资产

### 建议定位

建议将本计划作为：

- **Wave 4-A：结算与复盘系统**

放在 Wave 4 的前半段执行，再与：

- 前端体验优化
- 自动化验收与封版检查

一起组成 `alpha 0.2` 的最终收尾工作。

### 与 Alpha 0.2 其他计划的关系

- 与 [路线图](d:/鸦木布拉夫小镇/docs/alpha-0.2-plan/roadmap.md) 对齐：归属 `Wave 4`
- 与 [自动化验收与测试计划](d:/鸦木布拉夫小镇/docs/alpha-0.2-plan/acceptance-and-testing-plan.md) 对齐：结算与复盘 API、持久化和前端 Overlay 都应纳入最终 release gate
- 与 [前端界面优化计划](d:/鸦木布拉夫小镇/docs/alpha-0.2-plan/frontend-ui-optimization-plan.md) 对齐：Game Over Overlay 属于 Wave 4 的重要 UI 模块

## 背景与问题

当前游戏结束后仅显示 `阶段切换: 游戏结束`，存在以下缺失：
1. **无结算数据**：`GameOrchestrator` 在进入 `GAME_OVER` 时没有组装胜负/角色揭示/关键事件等结算包
2. **无持久化**：整个对局信息仅存在内存中（`SnapshotManager` / `EventLog`），服务重启即丢失
3. **无复盘界面**：前端没有 Game Over Overlay，人类玩家看不到角色真相、关键时间线和统计
4. **无重开机制**：对局结束后只能手动刷新页面或调 `/api/game/reset`

---

## User Review Required

> [!IMPORTANT]
> **数据库选型**：计划使用 **SQLite**（通过 Python 内置 `sqlite3` + `aiosqlite`），无需外部数据库服务。SQLite 文件存放在项目根目录 `data/games.db`。如果您希望使用 PostgreSQL 或其他方案，请告知。

> [!IMPORTANT]
> **复盘深度**：当前计划的复盘仅包含"结算总览 + 角色揭示 + 关键事件时间线 + 基础统计"。是否需要更高级的"回放模式"（逐回合重播每步决策）？这会显著增加工作量。

---

## Proposed Changes

### Stage 1: 后端结算数据组装

在 `GameOrchestrator` 进入 `GAME_OVER` 阶段时，自动生成完整的结算报告数据。

#### [MODIFY] [game_loop.py](file:///d:/鸦木布拉夫小镇/src/orchestrator/game_loop.py)

在 `_transition_and_run` 中的 `GAME_OVER` 分支内，新增对 `_build_settlement_report()` 的调用：

```python
if target_phase == GamePhase.GAME_OVER:
    self.settlement_report = self._build_settlement_report()
    await self._publish_event(GameEvent(
        event_type="game_settlement",
        phase=GamePhase.GAME_OVER,
        round_number=self.phase_manager.round_number,
        trace_id=self._make_trace_id("BOTC-SETTLEMENT"),
        visibility=Visibility.PUBLIC,
        payload=self.settlement_report,
    ))
```

新增方法 `_build_settlement_report() -> dict`，负责：
- **胜负判定**：`winning_team`, `victory_reason` (demon_killed / last_two / mayor_win)
- **角色揭示**：每个玩家的 `true_role_id`, `perceived_role_id`, `team`, `is_alive`（Game Over后所有信息公开）
- **关键事件时间线**：从 `event_log` 中提取所有 `execution_resolved`, `player_death`, `nomination_started`, `vote_cast` 事件，按时间排列
- **基础统计**：总回合数、总投票次数、处决次数、每个玩家的提名次数/被提名次数/投票倾向

---

### Stage 2: SQLite 持久化层

#### [NEW] [game_record.py](file:///d:/鸦木布拉夫小镇/src/state/game_record.py)

新建数据持久化模块，包含：

**数据库 Schema (两张核心表)**：

```sql
-- 对局总表
CREATE TABLE IF NOT EXISTS game_records (
    game_id       TEXT PRIMARY KEY,
    started_at    TEXT NOT NULL,
    ended_at      TEXT NOT NULL,
    winning_team  TEXT NOT NULL,       -- 'good' | 'evil'
    victory_reason TEXT,               -- 'demon_killed' | 'last_two' | 'mayor_win'
    player_count  INTEGER NOT NULL,
    round_count   INTEGER NOT NULL,
    script_id     TEXT DEFAULT 'trouble_brewing',
    settlement    TEXT NOT NULL,       -- JSON: 完整的 settlement_report
    config        TEXT                 -- JSON: GameConfig
);

-- 玩家明细表 (支持按玩家查询历史)
CREATE TABLE IF NOT EXISTS game_players (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id       TEXT NOT NULL REFERENCES game_records(game_id),
    player_id     TEXT NOT NULL,
    player_name   TEXT NOT NULL,
    true_role_id  TEXT NOT NULL,
    perceived_role_id TEXT,
    team          TEXT NOT NULL,
    is_alive      BOOLEAN NOT NULL,    -- 结局时存活状态
    is_human      BOOLEAN DEFAULT FALSE
);
```

**核心类**：

```python
class GameRecordStore:
    def __init__(self, db_path: str = "data/games.db"):
        ...

    async def initialize(self) -> None:
        """创建表（如不存在）"""

    async def save_game(self, game_id: str, state: GameState, settlement: dict) -> None:
        """保存完整对局记录"""

    async def get_game(self, game_id: str) -> dict | None:
        """获取单局记录"""

    async def list_games(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """分页获取历史对局列表"""

    async def get_player_history(self, player_name: str) -> list[dict]:
        """按玩家名查询参与过的对局"""
```

#### [MODIFY] [game_loop.py](file:///d:/鸦木布拉夫小镇/src/orchestrator/game_loop.py)

- 在 `GameOrchestrator.__init__` 中初始化 `self.record_store = GameRecordStore()`
- 在 `_build_settlement_report()` 完成后立即调用 `await self.record_store.save_game(...)`

#### [MODIFY] [pyproject.toml](file:///d:/鸦木布拉夫小镇/pyproject.toml)

新增依赖项：
```toml
"aiosqlite>=0.19",
```

---

### Stage 3: API 层（结算查询 & 重开）

#### [MODIFY] [server.py](file:///d:/鸦木布拉夫小镇/src/api/server.py)

新增 4 个 API 端点：

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/game/settlement` | GET | 获取当前对局的结算报告（仅 `GAME_OVER` 阶段可用） |
| `/api/game/history` | GET | 分页查询历史对局列表 (`?limit=20&offset=0`) |
| `/api/game/history/{game_id}` | GET | 获取指定对局的完整结算详情 |
| `/api/game/rematch` | POST | 使用相同配置快速重开新一局 |

**`/api/game/settlement` 响应格式**：
```json
{
  "status": "ok",
  "game_id": "abc-123",
  "winning_team": "good",
  "victory_reason": "demon_killed",
  "duration_rounds": 5,
  "players": [
    {
      "player_id": "p1",
      "name": "Player 1",
      "true_role_id": "washerwoman",
      "perceived_role_id": "washerwoman",
      "team": "good",
      "is_alive": true,
      "stats": {
        "nominations_made": 1,
        "times_nominated": 0,
        "votes_cast": 3,
        "votes_yes": 2
      }
    }
  ],
  "timeline": [
    {
      "round": 1,
      "phase": "day_discussion",
      "event_type": "nomination_started",
      "actor": "p3",
      "target": "p5",
      "summary": "Player 3 提名了 Player 5"
    }
  ],
  "statistics": {
    "total_nominations": 4,
    "total_executions": 2,
    "total_votes": 18,
    "days_played": 3
  }
}
```

**`/api/game/rematch` 逻辑**：
1. 从当前对局中提取 `GameConfig`（player_count, human_mode 等）
2. 调用 `stop_game_loop_task()` → `build_fresh_orchestrator()` → `run_setup_with_options(...)` → `ensure_game_loop_running()`
3. 通过 WebSocket 向所有连接的客户端广播 `{ type: "game_rematch", new_game_id: "..." }`

---

### Stage 4: 前端结算 Overlay

#### [MODIFY] [index.html](file:///d:/鸦木布拉夫小镇/public/index.html)

**新增 HTML 结构**：在现有 `grimoireOverlay` 之后插入 `settlementOverlay`：

```
┌──────────────────────────────────────────────────┐
│              🏆 游戏结束                          │
│         正义阵营获胜 / 邪恶阵营获胜                  │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │  角色揭示 (Role Reveal)                    │    │
│  │  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐    │    │
│  │  │P1  │ │P2  │ │P3  │ │P4  │ │P5  │    │    │
│  │  │洗衣│ │厨师│ │醉鬼│ │间谍│ │小鬼│    │    │
│  │  │🟢  │ │🟢  │ │💀  │ │🔴  │ │💀  │    │    │
│  │  └────┘ └────┘ └────┘ └────┘ └────┘    │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │  关键事件时间线                              │    │
│  │  D1: P3提名P5 → 投票通过 → 处决P5           │    │
│  │  N1: P5(小鬼) 攻击 P2                      │    │
│  │  D2: P4提名P1 → 投票未通过                   │    │
│  │  ...                                       │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │  对局统计                                   │    │
│  │  回合数: 5  |  处决: 2  |  投票: 18         │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  [ 🔄 再来一局 ]          [ 📋 查看历史 ]          │
└──────────────────────────────────────────────────┘
```

**核心前端逻辑**：
1. 在 `updateGameState()` 的轮询逻辑中，当检测到 `phase === 'game_over'` 时，自动 fetch `/api/game/settlement` 并显示 Overlay
2. 角色揭示区：遍历 `settlement.players`，用卡片展示每个玩家的真实角色、阵营、存活状态。善良用绿色边框，邪恶用红色，死亡用半透明
3. 时间线区：时间线用竖向 CSS Timeline 组件呈现
4. "再来一局"按钮：POST `/api/game/rematch`，成功后关闭 Overlay，页面自动进入新一局 SETUP
5. i18n：新增 `settlement_*` 系列翻译键

**新增 CSS**：
- `.settlement-overlay` — 全屏半透明背景 + 居中弹窗
- `.role-reveal-grid` — 角色卡片网格布局
- `.timeline-item` — 时间线节点样式
- `.settlement-stats` — 统计区块
- `.btn-rematch` — 再来一局按钮（带脉冲动画）

---

### Stage 5: 重开 (Rematch) 流程

#### [MODIFY] [server.py](file:///d:/鸦木布拉夫小镇/src/api/server.py)

在 `/api/game/rematch` handler 中：
```python
@app.post("/api/game/rematch")
async def rematch_game():
    # 1. 保留当前配置
    config = global_orchestrator.state.config
    # 2. 停止旧循环
    await stop_game_loop_task()
    # 3. 重建 orchestrator
    global_orchestrator = build_fresh_orchestrator()
    # 4. 使用旧配置重新 setup
    await global_orchestrator.run_setup_with_options(
        player_count=config.player_count,
        host_id=config.human_client_id or "h1",
        human_mode=config.human_mode,
        ...
    )
    # 5. 重连已有的 human_agents
    for pid, agent in human_agents.items():
        global_orchestrator.register_agent(agent)
    # 6. 启动新循环
    ensure_game_loop_running()
    # 7. 广播 rematch 事件
    for pid in manager.active_connections:
        await manager.send_personal_message(
            json.dumps({"type": "game_rematch", "new_game_id": global_orchestrator.state.game_id}),
            pid
        )
    return {"status": "ok", "new_game_id": global_orchestrator.state.game_id}
```

#### [MODIFY] [index.html](file:///d:/鸦木布拉夫小镇/public/index.html)

前端 WebSocket 消息处理：
```javascript
case 'game_rematch':
    // 关闭结算界面，重置本地状态
    closeSettlementOverlay();
    currentGameId = data.new_game_id;
    resetLocalUI();
    break;
```

---

## Open Questions

> [!IMPORTANT]
> **历史对局 UI**：是否需要专门的"历史对局列表"页面？当前计划仅提供 API，前端结算界面中有一个"查看历史"按钮但暂不实现完整的历史浏览页面。如果需要可以在后续迭代中加入。

> [!NOTE]
> **AI 复盘**：是否需要在结算时让每个 AI 玩家产出一段"赛后感言"（调用 LLM 总结本局表现）？这可以增加趣味性但会增加 API 调用成本。

---

## Verification Plan

### Automated Tests

1. **单元测试** — `tests/test_game_record.py`：
   - 测试 `GameRecordStore` 的 CRUD 操作（save/get/list）
   - 测试 `_build_settlement_report()` 在不同胜负条件下的输出格式

2. **集成测试** — 使用 MockBackend 运行完整对局至 `GAME_OVER`，验证：
   - `game_settlement` 事件是否正确发布
   - SQLite 中是否正确写入了记录
   - `/api/game/settlement` 返回的数据格式是否完整

3. **Rematch 测试** — 调用 `/api/game/rematch` 后验证：
   - 新 `game_id` 不同于旧的
   - 游戏状态重置为 `SETUP`
   - WebSocket 客户端收到 `game_rematch` 消息

### Manual Verification

1. 用浏览器打开前端，走完一局对局
2. 确认 Game Over 时自动弹出结算界面
3. 检查角色揭示是否正确显示所有玩家的真实角色
4. 点击"再来一局"按钮，确认新对局正常启动
5. 检查 `data/games.db` 文件中是否有记录

### 预期开发工时

| Stage | 内容 | 估时 |
|---|---|---|
| 1 | 后端结算数据组装 | 30min |
| 2 | SQLite 持久化层 | 45min |
| 3 | API 层 | 30min |
| 4 | 前端结算 Overlay | 60min |
| 5 | 重开流程 | 20min |
| - | 测试与调试 | 30min |
| **总计** | | **~3.5h** |
