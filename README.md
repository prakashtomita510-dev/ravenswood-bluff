# 鸦木布拉夫小镇 (Ravenswood Bluff) AI 引擎

![Version](https://img.shields.io/badge/version-alpha--0.3-orange)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**鸦木布拉夫小镇** 是一个基于多智能体（Multi-Agent）与状态机驱动的《血染钟楼》（Blood on the Clocktower）社交推演引擎。它深度还原了官方剧本《暗流涌动》（Trouble Brewing），并利用大语言模型（LLM）赋予 AI 玩家独特的个性、逻辑推理与伪装能力。当前处于 **Alpha 0.3** 研发阶段，聚焦于 **可观测性 (Observability)** 与 **战略智能 (Strategic Intelligence)** 的系统性提升。

---

## 🌟 核心特性

- **🧠 结构化认知与高保真记忆**：AI 代理拥有真实的“认知层”。Alpha 0.3 引入了 **三层记忆架构 (Objective/High-Confidence/Public)** 与 **向量记忆 (Vector Memory/RAG)**，确保 AI 在长局对局中依然能保持逻辑一致性。
- **🎭 导演级说书人智能**：具备 **战略平衡逻辑 (Smart Balancing)**，能根据实时局势（优势分值）动态调整信息干扰策略，并提供“内心独白”以解释决策动机。
- **⚖️ 严谨的规则引擎与复杂角色**：完整实现 Trouble Brewing 剧本 22 个角色逻辑。Alpha 0.3 补完了 **圣女 (Virgin)**、**猎手 (Slayer)** 等复杂角色的联动，并支持小恶魔传位等邪恶阵营高级战术。
- **📊 全量数据资产化**：支持对局历史、AI 思维链、说书人裁量账本的一键全量导出（`scripts/export_all_assets.py`），为模型微调提供高质量语料。
- **🛠️ 完善的验收生态**：提供 `alpha3_acceptance.py` 聚合门禁，涵盖从底层 RAG 检索到顶层战略平衡的全量验证。

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

- `docs/alpha-0.3-plan/`: 最新版本的研发进展看板与专项提升计划（数据工程/战略说书人/RAG 记忆等方案图）。
- `src/agents/`: AI 行动内核、认知层同步模块、记忆组件（三层分级记忆/向量检索）。
- `src/engine/`: 剧本内核引擎、夜晚时间轴控制器、对局数据采集器。
- `src/orchestrator/`: 顶层通信控制、信息分发及导演级说书人逻辑（Strategic Adjudication）。
- `src/state/`: 基于不可变状态机（Pydantic Snapshot）的数据链路结构与持久化存储。
- `public/`: 浏览器 UI，游戏控制台与魔典渲染前台。

---

## 📝 版本记录
此分支所有变动追踪至 [CHANGELOG.md](./CHANGELOG.md)。更多早期构架草图可看 `architecture.md`。

## 🛡️ 开源协议
本引擎及实现基于 MIT 协议，完全开源。
