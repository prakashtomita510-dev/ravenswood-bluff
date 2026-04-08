# BOTC 规则-实现矩阵

| Trace ID | 主题 | 规则来源 | 当前实现 | 主要改动 | 验收测试 |
|---|---|---|---|---|---|
| `BOTC-FLOW-SETUP` | setup 幂等与座位顺序 | `architecture.md` + Trouble Brewing 常规规则 | `src/orchestrator/game_loop.py` | 防重复 setup，强制写入 `seat_order`，同步私有身份视图 | `tests/test_orchestrator/test_game_loop.py` |
| `BOTC-FLOW-NOM` | 提名/投票/处决单一真相源 | `architecture.md` 提名与投票章节 | `src/engine/nomination.py` | 统一提名、投票、候选记录、同票无人处决、严格多数门槛 | `tests/test_engine/test_nomination_rules.py` |
| `BOTC-FLOW-SYNC` | 真实身份与感知身份同步 | `architecture.md` 信息隔离章节 | `src/state/game_state.py`, `src/agents/base_agent.py`, `src/orchestrator/information_broker.py` | 新增 `true_role_id/perceived_role_id/current_team` 等字段与私有视角同步 | `tests/test_state/test_game_state.py` |
| `BOTC-ST-INFO` | 夜晚私密信息分发 | Trouble Brewing 首夜/夜晚信息角色规则 | `src/agents/storyteller_agent.py`, `src/orchestrator/game_loop.py` | 夜晚先行动后发信息，支持醉酒/中毒失真 | `tests/test_orchestrator/test_game_loop.py` |
| `BOTC-RULE-DEATH` | 夜晚死亡公开结算 | 核心昼夜流程规则 | `src/engine/roles/demons.py`, `src/orchestrator/game_loop.py` | 恶魔击杀尊重保护/士兵/市长转移，并在天亮公开死亡 | `tests/test_engine/test_roles_victory.py` |
| `BOTC-RULE-SAINT` | 圣徒被处决邪恶获胜 | Trouble Brewing 圣徒规则 | `src/engine/nomination.py` | 处决结算中直接设置 `winning_team=evil` | `tests/test_engine/test_nomination_rules.py` |
| `BOTC-RULE-VIRGIN` | 圣女首提触发 | Trouble Brewing 圣女规则 | `src/orchestrator/game_loop.py` | 首位村民提名圣女时立即处决提名者 | `tests/test_engine/test_nomination_rules.py` |

## 角色技能审计矩阵（首批）

| Role | 规则关注点 | 当前状态 | 主要风险 / 缺口 | 首批测试 |
|---|---|---|---|---|
| `washerwoman` | 首夜固定信息，返回 2 人中 1 人是真村民 | 已覆盖 | 需要确认不会被夜晚目标选择链污染 | `tests/test_engine/test_role_skill_audit.py` |
| `librarian` | 首夜固定信息，检测外来者或无外来者 | 已覆盖 | 外来者分类需与术语表一致 | `tests/test_engine/test_role_skill_audit.py` |
| `investigator` | 首夜固定信息，检测爪牙 | 已覆盖 | 角色分类误差会影响结果稳定性 | `tests/test_engine/test_role_skill_audit.py` |
| `chef` | 首夜固定信息，统计相邻邪恶对数 | 已覆盖 | 座位顺序必须稳定写入 | `tests/test_engine/test_role_skill_audit.py` |
| `empath` | 夜间固定信息，统计左右活邻居的邪恶数 | 已覆盖 | 死亡邻座跳过逻辑需持续回归 | `tests/test_engine/test_role_skill_audit.py` |
| `undertaker` | 处决后夜间固定信息，返回被处决身份 | 已覆盖 | 需确认对中毒/醉酒的替换信息链 | `tests/test_engine/test_role_skill_audit.py` |
| `fortune_teller` | 选择双目标，能吃到红鲱鱼与恶魔判定 | 已覆盖 | 双目标记录与红鲱鱼来源是高风险点 | `tests/test_engine/test_role_skill_audit.py` |
| `spy` | 魔典视角固定信息 | 已覆盖 | 与说书人视角隔离必须持续保持 | `tests/test_engine/test_role_skill_audit.py` |
| `monk` | 目标保护，不能选自己 | 已覆盖 | 保护状态的清理时机需要回归 | `tests/test_engine/test_role_skill_audit.py` |
| `imp` | 夜晚击杀，保护/士兵免疫，自杀传递 | 已覆盖 | 市长转移、绯红女郎接管仍需更深回归 | `tests/test_engine/test_role_skill_audit.py`, `tests/test_engine/test_roles_victory.py` |
| `poisoner` | 夜晚投毒并标记中毒状态 | 已覆盖 | 中毒持续周期与信息扭曲链仍需全链路测试 | `tests/test_engine/test_role_skill_audit.py`, `tests/test_engine/test_roles_victory.py` |
| `ravenkeeper` | 夜死触发后看身份 | 已覆盖 | ON_DEATH 编排边界仍是高风险 | `tests/test_engine/test_role_skill_audit.py` |
| `slayer` | 白天一次性击杀恶魔 | 部分 | 一次性消耗/已使用标记仍待专门审计 | `tests/test_engine/test_role_skill_audit.py` |
| `mayor` | 夜死转移/白天无人处决处理 | 部分 | 被动结算逻辑分散，仍需端到端验证 | `tests/test_engine/test_role_skill_audit.py` |
| `butler` | 投票限制 | 部分 | 当前没有独立投票约束测试 | `tests/test_engine/test_role_skill_audit.py` |
| `recluse` | 身份误判 | 部分 | 侦测链路需与信息分发一起审计 | `tests/test_engine/test_role_skill_audit.py` |
| `drunken` | 虚假身份与信息失真 | 部分 | 需要与说书人视角联动测试 | `tests/test_engine/test_role_skill_audit.py` |
| `saint` | 被处决立即邪恶胜利 | 已有规则测试 | 需要保持提名链路与处决链一致 | `tests/test_engine/test_nomination_rules.py` |
| `scarlet_woman` | 恶魔死亡后的接管 | 缺口 | 当前缺少专门接管触发链测试 | 后续补齐 |
| `baron` | 外来者增量与 setup 影响 | 部分 | 需要与角色分发一起验证 | `tests/test_state/test_role_distribution.py` |

### 首批建议执行顺序

1. 先跑固定信息角色和主动夜晚角色的单测，锁定技能分类是否正确。
2. 再跑 `imp / monk / spy / ravenkeeper / fortune_teller` 的回归，覆盖夜晚主链。
3. 最后补 `slayer / mayor / butler / recluse / drunken / scarlet_woman` 的专门审计用例，作为后续业务修复的依据。
