# Gemini Alpha 0.3 审计记录

## 1. 审计范围

本次审计覆盖以下文档与对应实现：

- [alpha-0.3-plan.md](D:/鸦木布拉夫小镇/docs/alpha-0.3-plan.md)
- [full_plan.md](D:/鸦木布拉夫小镇/docs/alpha-0.3-plan/full_plan.md)
- [execution_summary.md](D:/鸦木布拉夫小镇/docs/alpha-0.3-plan/execution_summary.md)

重点对照以下代码：

- `src/agents/ai_agent.py`
- `src/agents/memory/working_memory.py`
- `src/agents/memory/social_graph.py`
- `src/agents/memory/vector_memory.py`
- `src/engine/data_collector.py`
- `src/agents/storyteller_agent.py`
- `src/state/game_record.py`
- `src/llm/base_backend.py`
- `src/llm/openai_backend.py`

---

## 2. 计划合理性评估

### 合理

- 把 `alpha 0.3` 的重点放在 AI 记忆、历史数据沉淀、说书人裁量可复盘，这个方向与当前项目真实痛点一致。
- 动态记忆扩容、结构化历史留存、向量检索作为辅助能力，这些都属于合理的下一阶段工程目标。
- 把“短期上下文”提升为“跨天保留、可检索、可复盘的长期状态”，方向正确。

### 过度承诺

- `零遗忘`
- `无限天数`
- `记忆置信度不得随天数衰减`
- `已形成完整 RAG 闭环`

这些表达更像研究愿景，不适合作为当前仓库的工程验收口径。

### 不完整

- RAG 方案没有认真描述摄入链、降级策略、无 embedding 时的行为与延迟成本。
- 数据工程文档把“可训练资产”说得过早，但没有把快照时机、字段规范、game_id 关联和导出链路讲清楚。
- 说书人优化只强调能力增强，没有先把“输入边界、分类、裁量记录、可复盘性”立稳。

---

## 3. 已真实落实项

### 动态记忆扩容：已落实

已在以下文件中落地：

- `src/agents/ai_agent.py`
- `src/agents/memory/working_memory.py`
- `src/agents/memory/social_graph.py`

当前实现情况：

- `AIAgent` 会按 `player_count` 动态配置观察、事实、反思和社交图谱容量。
- `WorkingMemory` 已支持参数化的 observation / fact / thought / impression / storage limits。
- `SocialGraph` 已支持参数化的 note / claim / summary limits。

结论：

- 这部分属于真正落地，不是文档夸大。

### VectorMemory 基础设施：已落实

已在以下文件中落地：

- `src/agents/memory/vector_memory.py`
- `src/agents/ai_agent.py`

当前实现情况：

- 已有 `VectorMemory` 类。
- 已封装 `faiss.IndexFlatL2`。
- 已有 `add_text`、`add_event`、`add_message`、`search`。
- `AIAgent.act()` 已在行动前执行检索并把结果注入 prompt。

结论：

- “向量检索基础设施存在”是事实。

### GameDataCollector 基础落盘：已落实

已在以下文件中落地：

- `src/engine/data_collector.py`
- `src/orchestrator/game_loop.py`
- `src/agents/ai_agent.py`

当前实现情况：

- `GameDataCollector` 已能按 `game_id + timestamp` 写 JSONL。
- `AIAgent.act()` 已能记录最小 thought trace。
- `GameOrchestrator` 已会给 AI agent 注入 collector。

结论：

- “开始采集 AI 行为数据”是事实。

### freeze/thaw 第一版：已落实

已在以下文件中落地：

- `src/agents/memory/social_graph.py`
- `src/agents/ai_agent.py`

当前实现情况：

- `PlayerProfile` 已有 `is_frozen` 与 `frozen_summary`。
- `SocialGraph` 已有 `freeze_player()` 与 `thaw_player()`。
- AI 已在死亡、身份冲突等场景下开始调用冻结/解冻。

结论：

- 这是第一版真实实现，不是文档虚构。

---

## 4. 部分落实但被夸大的项

### RAG 持续摄入闭环：未落实

现状：

- 检索入口已经接入 `AIAgent.act()`。
- 但主线里没有形成稳定、系统的事件流和聊天消息摄入闭环。
- 当前代码更接近“可以搜”，不是“已经一直在被喂数据”。

结论：

- `VectorMemory` 基础设施已落实。
- `RAG 持续摄入闭环` 未落实。

### 完整训练数据闭环：未落实

现状：

- `GameDataCollector` 能写最小 JSONL。
- 但还没有稳定的：
  - 阶段快照主线调用
  - social graph 快照
  - retrieval 命中记录
  - 统一导出 / 查询接口

结论：

- 基础落盘已落实。
- `完整训练数据闭环` 未落实。

### 成熟 layered memory 系统：未落实

现状：

- 已有 freeze/thaw。
- 但还不是成熟的“稳定层 / 重燃 / 置信度管理 / 跨阶段推理”体系。

结论：

- `freeze/thaw 第一版` 已落实。
- `成熟 layered memory 系统` 未落实。

---

## 5. 代码级漏洞与不一致

### 真实漏洞：`VectorMemory.add_message()` 与 `ChatMessage` 字段不一致

已确认：

- `src/agents/memory/vector_memory.py` 使用：
  - `msg.sender_name`
  - `msg.sender_id`
- `src/state/game_state.py` 中的 `ChatMessage` 实际字段是：
  - `speaker`
  - 不存在 `sender_name`
  - 不存在 `sender_id`

结论：

- 这是一个真实实现漏洞。
- 该漏洞意味着聊天消息向量摄入链当前不可被视为可靠。

### 真实漏洞：`social_graph.py` 中 logger 使用不完整

已确认：

- `src/agents/memory/social_graph.py` 中存在 `logger.info(...)`
- 但文件头部没有：
  - `import logging`
  - `logger = logging.getLogger(__name__)`

结论：

- 这是一个真实实现漏洞。
- 相关逻辑一旦运行到对应路径，将直接触发名称未定义问题。

### 口径不一致：执行总结把“基础设施已接入”写成“能力已闭环”

最典型的是：

- `execution_summary.md` 写成：
  - `RAG 基础设施 ✅ 已交付`
  - `打破 128k 窗口限制`
  - `Alpha 0.3 的核心“始终在线记忆”逻辑已全部闭环`

而仓库现状更准确的说法应是：

- 动态记忆扩容已落地
- 向量检索基础设施已接入
- 数据采集器基础落盘已接入
- 但 RAG 摄入、快照闭环、训练资产整理、长期记忆稳定性都还未闭环

---

## 6. 审计结论

### 可以保留

- 动态记忆扩容方向
- 向量记忆作为辅助检索能力
- 数据采集器与 JSONL 资产沉淀方向
- freeze/thaw 作为第一版记忆压缩机制
- 剧本与中文术语对齐

### 必须重写

- 所有带有绝对化承诺的验收标准
- 对 RAG、训练数据闭环、layered memory 成熟度的过度表述
- 执行总结中把“基础设施存在”写成“完整闭环已完成”的口径

### 最终判断

Gemini 的 `alpha 0.3` 工作不是空的，但更准确地说属于：

- **方向正确**
- **基础设施已搭好一部分**
- **闭环能力被文档夸大**

因此，`alpha 0.3` 不应继续沿用原始口径推进，而应基于当前仓库真实完成度，重制为：

1. AI 记忆优化
2. 历史数据保存与训练资产
3. AI 说书人优化
4. 验收、评估与发布门禁
