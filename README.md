# 鸦木布拉夫小镇 (Ravenswood Bluff) AI 引擎

基于多 Agent 与状态机驱动的《血染钟楼》游戏引擎。支持 人类玩家接入、LLM自动博弈以及基于事件溯源的复盘。

## 🚀 从零开始运行流程

### 1. 环境准备
本项目需要至少 **Python 3.11** 及以上版本。建议使用虚拟环境运行。

```bash
# 在项目根目录下打开终端，激活虚拟环境
.venv\Scripts\activate

# (如果尚未安装) 安装项目及所有依赖项
pip install -e "."
```

### 2. 配置大模型 API Key 
由于项目中涉及到 AI Agent 分析局势，必须配置 OpenAPI 或兼容格式的 API KEY：
```bash
# Windows (命令行)
set OPENAI_API_KEY=your_key_here
set OPENAI_BASE_URL=https://api.openai.com/v1 # 或配置你使用的镜像/大模型厂商地址

# Windows (PowerShell)
$env:OPENAI_API_KEY="your_key_here"
$env:OPENAI_BASE_URL="https://api.openai.com/v1"
```

### 3. 运行游戏后端服务器
直接执行 `server.py`，FastAPI 后端将启动在 8000 端口：
```bash
python -m src.api.server
```
看到 `Uvicorn running on http://127.0.0.1:8000` 表示启动成功。

### 4. 打开前端控制台 (Web UI)
服务启动后，在你的**浏览器**中就可以游玩和观测了：

1. **玩家视角: [http://127.0.0.1:8000](http://127.0.0.1:8000)** (会自动跳转到 `/ui/index.html`)
   - 在左上角输入 `h1` (这是当前演示代码中默认的人类玩家身份)
   - 点击 **连接服务器**。

2. **上帝视角 (说书人): [http://127.0.0.1:8000/ui/storyteller.html](http://127.0.0.1:8000/ui/storyteller.html)**
   - 此页面会纵览全场角色、身份和中毒/存活状态。
   - 点击右上角的 **“▶ 启动游戏循环”**。

此时，引擎开始根据规则进行运转，AI 玩家会自动分析局势，你（玩家 h1）将会在界面中收到对应的询问和游戏进程事件！

---

## 🛠 开发与测试
运行完整的自动化单元测试与 AI 推理验证：
```bash
python -m pytest tests/ -v
```

生成游戏回放（如果你在一局游戏完成后导出了 `events.json` 记录）：
```bash
python -m src.orchestrator.replay_parser <目录名>
```
