"""
06-3 ToolNode + 条件边：手写 ReAct 循环
学到：理解 create_react_agent 内部其实就是 model ↔ tools 两个节点 + 条件边。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from _common import get_llm, banner


@tool
def add(a: int, b: int) -> int:
    """两数相加"""
    return a + b


@tool
def square(x: int) -> int:
    """求平方"""
    return x * x


tools = [add, square]
llm = get_llm(temperature=0).bind_tools(tools)


def call_model(state: MessagesState) -> dict:
    return {"messages": [llm.invoke(state["messages"])]}


def main() -> None:
    banner("06-3 ToolNode + tools_condition")
    graph = (
        StateGraph(MessagesState)
        .add_node("model", call_model)
        .add_node("tools", ToolNode(tools))
        .add_edge(START, "model")
        # 条件边：如果 model 返回了 tool_calls 就去 tools 节点，否则结束
        .add_conditional_edges("model", tools_condition, {"tools": "tools", END: END})
        .add_edge("tools", "model")  # 工具执行完回到 model 总结
        .compile()
    )

    out = graph.invoke({"messages": [("user", "把 (3+4) 平方")]})
    for m in out["messages"]:
        print(f"[{m.type}] {m.content or m.tool_calls if hasattr(m, 'tool_calls') else m.content}")


if __name__ == "__main__":
    main()
