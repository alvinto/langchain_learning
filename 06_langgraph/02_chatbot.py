"""
06-2 用 LangGraph 写一个有记忆的 Chatbot
学到：
- MessagesState 内置 messages 字段（自动累加）
- MemorySaver 做 checkpoint，按 thread_id 隔离会话
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from _common import get_llm, banner


llm = get_llm()


def call_model(state: MessagesState) -> dict:
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


def main() -> None:
    banner("06-2 LangGraph Chatbot with memory")
    graph = (
        StateGraph(MessagesState)
        .add_node("model", call_model)
        .add_edge(START, "model")
        .add_edge("model", END)
        .compile(checkpointer=MemorySaver())   # ← 关键：开启 checkpoint
    )

    cfg = {"configurable": {"thread_id": "thread-1"}}
    for q in ["我叫小红", "我喜欢猫", "你还记得我叫什么、喜欢什么吗？"]:
        out = graph.invoke({"messages": [("user", q)]}, config=cfg)
        print(f"\n用户: {q}\n助手: {out['messages'][-1].content}")


if __name__ == "__main__":
    main()
