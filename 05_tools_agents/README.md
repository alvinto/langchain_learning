# 05 · 工具与 Agent

进入主线：让 LLM 调外部工具。Agent = LLM + 一组工具 + 一个"看到 tool_calls 就去执行再回灌"的循环。

| 文件 | 学到什么 |
| --- | --- |
| [01_define_tools.py](01_define_tools.py) | `@tool` 装饰器把 Python 函数变成 Tool；docstring 就是给 LLM 的说明书 |
| [02_bind_tools.py](02_bind_tools.py) | **手写** tool-calling 循环：理解底层原理（`tool_calls → ToolMessage → 再 invoke`） |
| [03_react_agent.py](03_react_agent.py) | `create_agent / create_react_agent` 一行替你跑循环（**生产推荐**） |
| [04_multi_tools.py](04_multi_tools.py) | 多工具组合：RAG 检索 + 计算器 + 天气，让 Agent 自主选择 |

> 03/04 同时兼容 LangChain 0.3（`langgraph.prebuilt.create_react_agent`）和 1.x（`langchain.agents.create_agent`），代码用 try/except 自动适配。
>
> 看完这章再去看 06，理解"prebuilt agent 内部其实就是状态图"。
