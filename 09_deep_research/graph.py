"""Deep Research 主图（v2）。

支持两种模式：

[simple]   START → planner → fan_out → researcher × N (并行) → writer → END
           固定一次性 plan，教学清晰，但不会反思补研究

[supervisor] START → supervisor_subgraph → writer → END
             supervisor 自己用 ReAct 循环决定派几个 researcher、什么时候停
             ↑↓ 内部可能多轮调度，自带反思

外部接口：build_graph(mode="supervisor"|"simple")  默认 supervisor。

两种模式产出格式完全一致（findings + report），writer 节点共享，
切换 mode 不影响下游代码。
"""
from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from planner import plan
from researcher import arun_researcher
from state import ResearchState
from supervisor import arun_supervisor
from writer import awrite_report


# ============================================================
# 共享节点：writer
# ============================================================

async def writer_node(state: ResearchState) -> dict:
    report = await awrite_report(state["question"], state.get("findings", []))
    return {
        "report": report,
        "progress_events": [f"writer ✓ 报告 {len(report)} 字"],
    }


# ============================================================
# Simple 模式节点
# ============================================================

def planner_node(state: ResearchState) -> dict:
    sub_qs = plan(state["question"])
    return {
        "sub_questions": sub_qs,
        "progress_events": [f"planner ✓ 拆出 {len(sub_qs)} 子问题"],
    }


def _fan_out(state: ResearchState) -> list[Send]:
    return [
        Send("researcher", {"sub_question": q})
        for q in state.get("sub_questions", [])
    ]


async def researcher_node_simple(payload: dict) -> dict:
    """Simple 模式：每个 researcher 跑一个子问题。无 progress_cb（主图 stream 已经够细）。"""
    finding = await arun_researcher(payload["sub_question"])
    return {
        "findings": [finding],
        "progress_events": [
            f"researcher ✓ {finding.sub_question} → {len(finding.summary)} 字 · {len(finding.sources)} 引用"
        ],
    }


# ============================================================
# Supervisor 模式节点
# ============================================================

def _make_supervisor_node(max_iterations: int):
    """工厂：把 max_iterations 闭包进去，避免每次调用都从环境变量读。"""

    async def supervisor_node(state: ResearchState) -> dict:
        events: list[str] = []

        def cb(msg: str) -> None:
            events.append(msg)

        findings = await arun_supervisor(
            state["question"],
            progress_cb=cb,
            max_iterations=max_iterations,
        )
        return {
            "findings": {"__override__": True, "value": findings},  # 整体覆盖
            "progress_events": events + [f"supervisor ✓ 收集 {len(findings)} findings"],
        }

    return supervisor_node


# ============================================================
# 主图构建
# ============================================================

def build_graph(mode: Literal["simple", "supervisor"] = "supervisor", max_iterations: int = 3):
    """构建主图。

    mode="supervisor"（默认）：动态调度，自带反思
    mode="simple"            ：一次性 planner，教学清晰
    max_iterations：supervisor 模式下最多决策轮数（每轮可并发多个 researcher）
    """
    g = StateGraph(ResearchState)
    g.add_node("writer", writer_node)

    if mode == "simple":
        g.add_node("planner", planner_node)
        g.add_node("researcher", researcher_node_simple)

        g.add_edge(START, "planner")
        g.add_conditional_edges("planner", _fan_out, ["researcher"])
        g.add_edge("researcher", "writer")
        g.add_edge("writer", END)
    elif mode == "supervisor":
        g.add_node("supervisor", _make_supervisor_node(max_iterations))

        g.add_edge(START, "supervisor")
        g.add_edge("supervisor", "writer")
        g.add_edge("writer", END)
    else:
        raise ValueError(f"unknown mode: {mode}")

    return g.compile()
