# 鸦木布拉夫小镇 (Ravenswood Bluff) AI 引擎

![Version](https://img.shields.io/badge/version-alpha--0.1-orange)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**鸦木布拉夫小镇** 是一个基于多智能体（Multi-Agent）与状态机驱动的《血染钟楼》（Blood on the Clocktower）社交推演引擎。它深度还原了官方剧本《暗流涌动》（Trouble Brewing），并利用大语言模型（LLM）赋予 AI 玩家独特的个性、逻辑推理与伪装能力。

---

## 🌟 核心特性

- **🧠 认知一致性 (Identity Alignment)**：AI 代理拥有真实的“认知层”。即使是**酒鬼**或**中毒**状态，代理也会基于其感知的虚假身份进行推演，确保社交博弈的真实性。
- **📖 全功能魔典 (Grimoire)**：集成式的说书人控制台。人类说书人可以实时查看全局真实状态（包括所有私密事件、中毒记录、恶魔传位等），掌控全局。
- **⚖️ 严谨的规则引擎**：
    - 完整实现 22 个角色逻辑。
    - 严格遵循官方 **Night Sheet** 的行动顺序（Night Order）。
    - 自动处理复杂的角色互动（如：小恶魔自杀传位、绯红女郎接班、预言家红鲱鱼等）。
- **🗳️ 交互式提名系统**：支持“提名阶段 -> 辩解发言 -> 实时投票”的完整昼间互动流程。
- **🛠️ 开发者审计工具**：提供 `MockBackend` 与全自动模拟脚本 `simulate_game.py`，支持在无需 API Key 的情况下进行规则合法性的大规模回归测试。

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
如果您希望使用真实的大模型（如 GPT-4o），请配置环境变量：

```powershell
$env:OPENAI_API_KEY="your_api_key"
$env:OPENAI_BASE_URL="https://api.openai.com/v1"
```

### 3. 启动服务器
```bash
python -m src.api.server
```
服务器默认运行在 `http://127.0.0.1:8000`。

### 4. 游玩与观测
- **玩家/说书人界面**: 访问 [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **人类玩家 ID**: 使用 `h1` 加入游戏。
- **说书人模式**: 在 UI 侧边栏开启“魔典”即可进入上帝视角。

---

## 🧪 自动化审计与测试

本项目内置了强大的自动化审计系统，用于验证规则执行的准确性。

```bash
# 使用 Mock 后端运行 8 人局全流程模拟
.venv\Scripts\python.exe simulate_game.py
```

该脚本会生成详细的阶段日志，验证身份同步、技能发动顺序以及胜利条件判定。

---

## 📂 项目结构

- `src/agents/`: AI 代理逻辑、认知同步、社交推演 Prompt 设计。
- `src/engine/`: 核心规则实现、角色技能定义、行动顺序管理。
- `src/orchestrator/`: 游戏主循环、信息分发器（Broker）、事件总线。
- `src/state/`: 基于 Pydantic 的不可变游戏快照模型。
- `public/`: 基于 HTML/JS 的前端交互界面。

---

## 📝 版本记录
详见 [VERSION_NOTES.md](./VERSION_NOTES.md)。

## 🛡️ 开源协议
本项目基于 MIT 协议开源。
