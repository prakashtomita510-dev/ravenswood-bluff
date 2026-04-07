# 🏰 鸦木布拉夫小镇 — Ravenswood Bluff

> 基于多Agent的社交推理桌游系统，以「血染钟楼」(Blood on the Clocktower) 为核心玩法。

用户可作为**玩家**或**说书人（管理员）**，与AI Agent们展开一场智慧与谎言的较量。

## 特性

- 🤖 基于LLM的智能Agent，具备推理、欺骗、说服能力
- 🎮 完整的血染钟楼游戏流程
- 👥 支持人机混合对局
- 📊 完善的事件日志与回放系统

## 快速开始

```bash
# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate  # Windows

# 安装依赖
pip install -e ".[dev]"

# 运行测试
pytest
```

## 项目结构

详见 [architecture.md](./architecture.md)

## License

MIT
