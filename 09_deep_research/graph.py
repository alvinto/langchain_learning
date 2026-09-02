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
from __future__ import annotations  # 启用 PEP 563 延迟注解

from typing import Literal  # 导入 typing 类型注解

from langgraph.graph import END, START, StateGraph  # 导入 LangGraph 图编排组件
from langgraph.types import Send  # 导入 LangGraph 图编排组件

from planner import plan  # 执行本行逻辑
from researcher import arun_researcher  # 执行本行逻辑
from state import ResearchState  # 执行本行逻辑
from supervisor import arun_supervisor  # 执行本行逻辑
from writer import awrite_report  # 执行本行逻辑


# ============================================================
# 共享节点：writer
# ============================================================

async def writer_node(state: ResearchState) -> dict:  # 定义异步函数
    report = await awrite_report(state["question"], state.get("findings", []))  # 等待异步结果
    return {  # 返回结果
        "report": report,  # 字符串/template 参数
        "progress_events": [f"writer ✓ 报告 {len(report)} 字"],  # 字符串/template 参数
    }  # 闭合括号/元组/字典


# ============================================================
# Simple 模式节点
# ============================================================

def planner_node(state: ResearchState) -> dict:  # 定义函数
    sub_qs = plan(state["question"])  # 赋值给 sub_qs
    return {  # 返回结果
        "sub_questions": sub_qs,  # 字符串/template 参数
        "progress_events": [f"planner ✓ 拆出 {len(sub_qs)} 子问题"],  # 字符串/template 参数
    }  # 闭合括号/元组/字典


def _fan_out(state: ResearchState) -> list[Send]:  # 定义函数
    return [  # 返回结果
        Send("researcher", {"sub_question": q})  # 执行本行逻辑
        for q in state.get("sub_questions", [])  # for 循环
    ]  # 闭合括号/元组/字典


async def researcher_node_simple(payload: dict) -> dict:  # 定义异步函数
    """Simple 模式：每个 researcher 跑一个子问题。无 progress_cb（主图 stream 已经够细）。"""
    finding = await arun_researcher(payload["sub_question"])  # 等待异步结果
    return {  # 返回结果
        "findings": [finding],  # 字符串/template 参数
        "progress_events": [  # 字符串/template 参数
            f"researcher ✓ {finding.sub_question} → {len(finding.summary)} 字 · {len(finding.sources)} 引用"  # 字符串/template 参数
        ],  # 闭合括号/元组/字典
    }  # 闭合括号/元组/字典


# ============================================================
# Supervisor 模式节点
# ============================================================

def _make_supervisor_node(max_iterations: int):  # 定义函数
    """工厂：把 max_iterations 闭包进去，避免每次调用都从环境变量读。"""

    async def supervisor_node(state: ResearchState) -> dict:  # 定义异步函数
        events: list[str] = []  # 赋值给 list[str]

        def cb(msg: str) -> None:  # 定义函数
            events.append(msg)  # 执行本行逻辑

        findings = await arun_supervisor(  # 等待异步结果
            state["question"],  # 序列/元组元素
            progress_cb=cb,  # 执行本行逻辑
            max_iterations=max_iterations,  # 执行本行逻辑
        )  # 闭合括号/元组/字典
        return {  # 返回结果
            "findings": {"__override__": True, "value": findings},  # 整体覆盖
            "progress_events": events + [f"supervisor ✓ 收集 {len(findings)} findings"],  # 字符串/template 参数
        }  # 闭合括号/元组/字典

    return supervisor_node  # 返回结果


# ============================================================
# 主图构建
# ============================================================

def build_graph(mode: Literal["simple", "supervisor"] = "supervisor", max_iterations: int = 3):  # 定义函数
    """构建主图。

    mode="supervisor"（默认）：动态调度，自带反思
    mode="simple"            ：一次性 planner，教学清晰
    max_iterations：supervisor 模式下最多决策轮数（每轮可并发多个 researcher）
    """
    g = StateGraph(ResearchState)  # 创建 LangGraph 状态图
    g.add_node("writer", writer_node)  # 向图添加节点

    if mode == "simple":  # 代码块起始
        g.add_node("planner", planner_node)  # 向图添加节点
        g.add_node("researcher", researcher_node_simple)  # 向图添加节点

        g.add_edge(START, "planner")  # 向图添加普通边
        g.add_conditional_edges("planner", _fan_out, ["researcher"])  # 向图添加条件边
        g.add_edge("researcher", "writer")  # 向图添加普通边
        g.add_edge("writer", END)  # 向图添加普通边
    elif mode == "supervisor":  # elif 分支
        g.add_node("supervisor", _make_supervisor_node(max_iterations))  # 向图添加节点

        g.add_edge(START, "supervisor")  # 向图添加普通边
        g.add_edge("supervisor", "writer")  # 向图添加普通边
        g.add_edge("writer", END)  # 向图添加普通边
    else:  # else 分支
        raise ValueError(f"unknown mode: {mode}")  # 抛出异常

    return g.compile()  # 编译图为可执行应用
