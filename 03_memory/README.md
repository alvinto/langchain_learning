# 03 · 多轮记忆

LLM 自身是无状态的，多轮对话靠你把历史消息再传一次。这章给三种由浅到深的做法。

| 文件 | 学到什么 |
| --- | --- |
| [01_chat_history.py](01_chat_history.py) | `InMemoryChatMessageHistory`：手动 append 消息列表，最朴素的做法 |
| [02_runnable_with_history.py](02_runnable_with_history.py) | `RunnableWithMessageHistory`：包一层就能按 `session_id` 自动管理历史（**推荐**） |
| [03_agent_local_memory.py](03_agent_local_memory.py) | `create_agent + InMemorySaver`：Agent 短期记忆（内存，重启丢失） |
| [03_agent_db_memory.py](03_agent_db_memory.py) | `create_agent + SqliteSaver`：Agent 短期记忆持久化到 SQLite |
| [04_custom_agent_memory.py](04_custom_agent_memory.py) | 自定义 `AgentState` + checkpointer |
| [05_trim_messages.py](05_trim_messages.py) | **Trim**：`trim_messages` 按条数或 token 滑动窗口 |
| [06_delete_messages.py](06_delete_messages.py) | **Delete**：`RemoveMessage` + `add_messages` 按 id 删历史或整表替换 |
| [07_summarize_messages.py](07_summarize_messages.py) | **Summarize**：超 token 预算时用 LLM 摘要旧对话再拼接最近几轮 |

## Common patterns（上下文超长）

开启短记忆后，长对话可能超过模型上下文窗口。常见三种处理方式（本目录 05～07 各一个示例）：

1. **Trim messages** — 不删存储，只在调用模型前裁掉较早消息（最快、信息损失最大）。
2. **Delete messages** — 从状态里真正移除指定轮次（`RemoveMessage`）；常与「清空 + 重写」一起用。
3. **Summarize messages** — 旧对话压成摘要，再保留 system 与最近消息（信息保留最好，多一次 LLM 调用）。

> 06 章会用 LangGraph 的 `MessagesState + checkpointer` 实现等价能力，并支持持久化。Agent 侧可参考 `SummarizationMiddleware`（自动摘要）。
