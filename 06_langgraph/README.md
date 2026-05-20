# 06 · LangGraph

当你的 Agent 需要 **循环 / 条件分支 / 人在回路 / checkpoint** 时，LCEL 的"单向链"就不够了，要用 LangGraph 的状态图。

| 文件 | 学到什么 |
| --- | --- |
| [01_state_graph.py](01_state_graph.py) | `StateGraph` 三要素：State（TypedDict）/ Node（函数）/ Edge |
| [02_chatbot.py](02_chatbot.py) | `MessagesState + MemorySaver`：按 `thread_id` 隔离的多轮 chatbot |
| [03_tool_node.py](03_tool_node.py) | `ToolNode + tools_condition`：手写 ReAct 循环，理解 `create_react_agent` 的内部结构 |
| [04_human_in_loop.py](04_human_in_loop.py) | `interrupt_before=["tools"]`：危险动作前暂停等审批 |

> 学完这章你应该能回答："为什么生产级 Agent 都用 LangGraph 而不是裸 LCEL？"
> 接着进入 08 章看一个把这些能力组合起来的迷你 Claude Code。
