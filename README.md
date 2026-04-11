# 鸦木布拉夫小镇 (Ravenswood Bluff) AI 引擎

![Version](https://img.shields.io/badge/version-alpha--0.2_dev-orange)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**鸦木布拉夫小镇** 是一个基于多智能体（Multi-Agent）与状态机驱动的《血染钟楼》（Blood on the Clocktower）社交推演引擎。它深度还原了官方剧本《暗流涌动》（Trouble Brewing），并利用大语言模型（LLM）赋予 AI 玩家独特的个性、逻辑推理与伪装能力。当前处于 **Alpha 0.2** 研发阶段，聚焦于 AI 智能提升与说书人裁断系统的强化。

---

## 🌟 核心特性

- **🧠 认知一致性 (Identity Alignment)与智能增强**：AI 代理拥有真实的“认知层”。即使是**酒鬼**或**中毒**状态，代理也会基于其感知的虚假身份进行推演。Alpha 0.2 的重点在于推进更完善的社交图谱与长期记忆（Episodic Memory）。
- **📖 说书人智能决策框架**：具备平衡裁断判定体系（Balance Judgement），能自主评估当前的局势动态并控制红鲱鱼、酒鬼信息、解药机制，引导局势走向精彩。
- **⚖️ 严谨的规则引擎**：完整实现 Trouble Brewing 剧本 22 个角色逻辑。严格遵循官方 **Night Sheet** 行动顺序（Night Order），完美处理小恶魔传位、守鸦人死亡触发等复杂互动。
- **🗳️ 交互式提名网络**：支持高并发的昼间互动、多轮动态提名、以及幽灵票流转判定，自动清理残存记录消除状态污染。
- **🛠️ 开发者审计与自动化验收生态**：提供 `MockBackend`、验收脚本集群（Wave 1/2 Acceptance）和 `simulate_game.py`，支持在不调用真实大模型的前提下进行断言规模测试，甚至解析对局重播日志（Replay Parser）。

---

## 🚀 快速开始

### 1. 环境准备
推荐使用 **Python 3.11+**。

```bash
# 克隆仓库后进入目录
cd ravenswood-bluff

# 激活虚拟环境 (Windows)
.venv\Scripts\activate

# 安装依赖
pip install -e "."
```

### 2. 配置 API Key（可选）
如果希望以最高智力水平驱动 AI 角色运行，请配置相应的环境变量（支持主流兼容 OpenAI 格式的模型）：

```powershell
$env:OPENAI_API_KEY="your_api_key"
$env:OPENAI_BASE_URL="https://api.openai.com/v1"
```

### 3. 启动服务器
```bash
python -m src.api.server
```
服务器默认持续运行在 `http://127.0.0.1:8000`。

### 4. 游玩与全局观测
- **玩家/说书人界面**: 访问 [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **人类身份进入**: 输入 `h1` 作为主机 ID 加入游戏。
- **说书人魔典**: 随时可在 UI 中呼出“魔典(Grimoire)”，实时追踪系统真相与底层伪装分配状态。

---

## 🧪 自动化审计与测试体系

项目具备完备的测试生态支持，全面覆盖了从底层机制到前端契约的所有角落：

```bash
# 运行 pytest 核心基础单元/集成测试池
pytest tests/ -q

# 执行独立的自动化验收测试以验证业务场景断言，如：
python scripts/wave1_acceptance.py
python scripts/nomination_acceptance.py
python scripts/storyteller_balance_acceptance.py
```
这能有效排查身份发放、投票链条以及阶段转换的稳定性问题。

---

## 📂 项目架构

- `docs/alpha-0.2-plan/`: 最新版本的研发进展看板与专项提升计划（AI/前端/裁定等方案图）。
- `src/agents/`: AI 行动内核、认知层同步模块、记忆组件（工作记忆/情景记忆）。
- `src/engine/`: 剧本内核引擎、夜晚时间轴控制器。
- `src/orchestrator/`: 顶层通信控制、信息分发（Information Broker）及智能说书人逻辑（Storyteller Balance）。
- `src/state/`: 基于不可变状态机（Pydantic Snapshot）的数据链路结构。
- `public/`: 浏览器 UI，游戏控制台与魔典渲染前台。

---

## 📝 版本记录
此分支所有变动追踪至 [CHANGELOG.md](./CHANGELOG.md)。更多早期构架草图可看 `architecture.md`。

## 🛡️ 开源协议
本引擎及实现基于 MIT 协议，完全开源。
