# 03 · 多轮记忆

LLM 自身是无状态的，多轮对话靠你把历史消息再传一次。这章给三种由浅到深的做法。

| 文件 | 学到什么 |
| --- | --- |
| [01_chat_history.py](01_chat_history.py) | `InMemoryChatMessageHistory`：手动 append 消息列表，最朴素的做法 |
| [02_runnable_with_history.py](02_runnable_with_history.py) | `RunnableWithMessageHistory`：包一层就能按 `session_id` 自动管理历史（**推荐**） |
| [03_trim_messages.py](03_trim_messages.py) | `trim_messages` 按条数或 token 裁剪，避免上下文爆炸 |

> 06 章会用 LangGraph 的 `MessagesState + checkpointer` 实现等价能力，并支持持久化。
