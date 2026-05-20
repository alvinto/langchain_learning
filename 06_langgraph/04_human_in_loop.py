"""
06-4 人在回路（Human-in-the-loop）
学到：用 interrupt_before 让图在敏感节点暂停，等用户确认后再继续。
场景：Agent 准备调用"删除数据库"工具时，先停下来让人审批。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from _common import get_llm, banner


@tool
def delete_user(user_id: str) -> str:
    """删除指定用户（危险操作）。"""
    return f"用户 {user_id} 已删除"


tools = [delete_user]
llm = get_llm(temperature=0).bind_tools(tools)


def call_model(state: MessagesState) -> dict:
    return {"messages": [llm.invoke(state["messages"])]}


def main() -> None:
    banner("06-4 Human-in-the-loop")
    graph = (
        StateGraph(MessagesState)
        .add_node("model", call_model)
        .add_node("tools", ToolNode(tools))
        .add_edge(START, "model")
        .add_conditional_edges("model", tools_condition, {"tools": "tools", END: END})
        .add_edge("tools", "model")
        .compile(
            checkpointer=MemorySaver(),
            interrupt_before=["tools"],   # ← 关键：在工具节点前暂停
        )
    )

    cfg = {"configurable": {"thread_id": "approval-1"}}

    # 第一阶段：跑到 tools 之前停下
    state = graph.invoke({"messages": [("user", "请删除用户 u_42")]}, config=cfg)
    last = state["messages"][-1]
    print("LLM 准备调用:", last.tool_calls)

    # 模拟人工审批
    answer = input("\n是否批准执行？(y/N): ").strip().lower()
    if answer != "y":
        print("已拒绝，未执行。")
        return

    # 继续：传入 None 表示沿用 checkpoint 状态接着走
    state = graph.invoke(None, config=cfg)
    print("\n执行结果:", state["messages"][-1].content)


if __name__ == "__main__":
    main()
