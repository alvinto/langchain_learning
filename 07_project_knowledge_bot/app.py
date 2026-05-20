"""
个人知识库问答机器人 · 命令行入口

用 LangGraph 编排：
  START → condense（改写问题） → retrieve（向量检索） → answer（生成回答） → END
全程通过 messages 字段维护多轮对话，按 thread_id 隔离会话。

直接运行：
    python 07_project_knowledge_bot/app.py
"""
from __future__ import annotations
import sys
import uuid
import operator
from pathlib import Path
from typing import TypedDict, List, Annotated
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from chains import condense_chain, answer_chain, load_retriever, format_context


class State(TypedDict):
    # Annotated + operator.add 让 messages 字段自动累加（reducer 模式）
    messages: Annotated[List[BaseMessage], operator.add]
    question: str
    standalone: str
    docs: List[Document]
    context: str
    answer: str


retriever = load_retriever()


def node_condense(state: State) -> dict:
    history = state.get("messages") or []
    if not history:
        return {"standalone": state["question"]}      # 第一轮不需改写
    standalone = condense_chain.invoke({
        "history": history,
        "question": state["question"],
    })
    return {"standalone": standalone}


def node_retrieve(state: State) -> dict:
    docs = retriever.invoke(state["standalone"])
    return {"docs": docs, "context": format_context(docs)}


def node_answer(state: State) -> dict:
    answer = answer_chain.invoke({
        "history": state.get("messages") or [],
        "question": state["question"],
        "context": state["context"],
    })
    return {
        "answer": answer,
        "messages": [HumanMessage(state["question"]), AIMessage(answer)],
    }


def build_graph():
    return (
        StateGraph(State)
        .add_node("condense", node_condense)
        .add_node("retrieve", node_retrieve)
        .add_node("answer", node_answer)
        .add_edge(START, "condense")
        .add_edge("condense", "retrieve")
        .add_edge("retrieve", "answer")
        .add_edge("answer", END)
        .compile(checkpointer=MemorySaver())
    )


def main() -> None:
    print("=" * 60)
    print("  个人知识库问答机器人  (/quit 退出, /new 开新会话)")
    print("=" * 60)

    graph = build_graph()
    thread_id = str(uuid.uuid4())[:8]
    cfg = {"configurable": {"thread_id": thread_id}}
    print(f"[会话: {thread_id}]")

    while True:
        try:
            q = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            continue
        if q in ("/quit", "/exit"):
            break
        if q == "/new":
            thread_id = str(uuid.uuid4())[:8]
            cfg = {"configurable": {"thread_id": thread_id}}
            print(f"[已开启新会话: {thread_id}]")
            continue

        out = graph.invoke({"question": q}, config=cfg)
        print(f"\n助手: {out['answer']}")
        print("\n--- 引用 ---")
        for i, d in enumerate(out["docs"], 1):
            src = Path(d.metadata.get("source", "?")).name
            preview = d.page_content[:60].replace("\n", " ")
            print(f"  [{i}] {src}: {preview}…")


if __name__ == "__main__":
    main()
