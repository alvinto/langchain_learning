"""
06-1 StateGraph 入门
学到：LangGraph 的核心是"状态 + 节点 + 边"。
- State：用 TypedDict 定义共享数据结构
- Node：函数 (state) -> 部分 state 更新
- Edge：节点间的连接（含条件边）
- 从start state开始，沿着edge执行每个node，最终到end state结束
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from _common import banner


class State(TypedDict):
    text: str
    word_count: int
    upper: str


def count_words(state: State) -> dict:
    return {"word_count": len(state["text"].split())}


def upper_case(state: State) -> dict:
    return {"upper": state["text"].upper()}


def main() -> None:
    banner("06-1 StateGraph")
    graph = (
        StateGraph(State)
        .add_node("count", count_words)
        .add_node("upper", upper_case)
        .add_edge(START, "count")
        .add_edge("count", "upper")
        .add_edge("upper", END)
        .compile()
    )

    out = graph.invoke({"text": "hello langgraph world"})
    print(out)


if __name__ == "__main__":
    main()
