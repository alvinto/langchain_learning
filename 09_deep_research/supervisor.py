"""Supervisor 子图 —— deep research v2 的核心架构升级。

跟 simple 模式（planner 一次性拆 N 个子问题）的本质差异：
**supervisor 自己决定要研究什么、什么时候停**。

形式：supervisor 是一个 ReAct 风格的 Agent，它的工具不是 web_search，而是：
- ConductResearch(topic)  → 派一个 researcher 去研究 topic
- ResearchComplete()      → 宣布研究完成，主图进入 writer

每一轮 LLM 调用，supervisor 可以同时调多个 ConductResearch（parallel tool calls），
我们用 asyncio.gather 真并行执行所有 researcher。结果回来后再交给 supervisor
看一眼——它可能再派、也可能调 ResearchComplete 收工。

这等于把"反思/补研究"内化到 supervisor 的决策里，不需要单独的 reflection 节点。

边界：
- max_iterations 防止 supervisor 自己跟自己玩死循环
- 每轮 ConductResearch 数量也截一下（一次开 50 个 researcher 没意义）
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Callable, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _common import get_llm  # noqa: E402

from researcher import arun_researcher
from state import Finding, SupervisorState


ProgressCallback = Callable[[str], None]


# ============================================================
# Supervisor 的工具 —— 不带逻辑，纯 schema
# ============================================================

class ConductResearch(BaseModel):
    """派一个 researcher 去研究指定的话题。"""

    topic: str = Field(
        description="要研究的具体子问题。粒度要够细（一个 researcher 一次能搞定），"
        "不要太宽（"
        "比如「分析 LangGraph」太宽，应该改成「LangGraph 的 Send API 解决了什么问题」）",
    )


class ResearchComplete(BaseModel):
    """所有需要的信息都收集齐了，可以开始写报告。"""


@tool(args_schema=ConductResearch)
def conduct_research(topic: str) -> str:
    """Stub —— supervisor 调它实际上不会执行，由 supervisor_tools 节点截获。"""
    return f"(队列中：{topic})"


@tool(args_schema=ResearchComplete)
def research_complete() -> str:
    """Stub —— 由 supervisor_tools 节点截获后路由到 END。"""
    return "research complete"


_TOOL_MAP = {"conduct_research": conduct_research, "research_complete": research_complete}


# ============================================================
# Prompts
# ============================================================

_SUPERVISOR_PROMPT = """你是研究项目的总指挥。你的任务：根据用户的研究问题，
派出若干名 researcher 去并行调研，最后判断信息够不够写报告。

你有两个工具：
- conduct_research(topic): 派 1 名 researcher 去研究 topic。你**可以一次调用多个**
  conduct_research（建议第一轮就开 3~5 个覆盖核心维度），它们会**并行执行**。
- research_complete(): 当你认为收集到的信息已足以回答用户的研究问题时调用。

工作策略：
1. **第一轮**：把研究问题拆成 3~5 个独立子方向，**同时**派出多个 researcher。
   不要一个一个派——并行才快。
2. **后续轮**：看回来的结果，判断有没有：
   - 关键空白（某个角度没人研究）
   - 矛盾（不同 researcher 结论冲突，需要复核）
   - 时效不够（搜到的资料太旧）
   有就再派 researcher 补；都没有就调 research_complete。
3. 最多研究 {max_iterations} 轮，请合理分配。
4. 派 researcher 时 topic 要写得**具体**——粒度太粗它会胡乱搜。

用户的研究问题：
{question}
"""


# ============================================================
# Supervisor 节点
# ============================================================

def _build_supervisor_subgraph(progress_cb: ProgressCallback | None):
    """构建 supervisor 子图。progress_cb 通过闭包传给内部节点和 researcher。"""

    llm = get_llm(temperature=0, role="smart").bind_tools(
        [conduct_research, research_complete],
        tool_choice="any",  # 强制每轮必须调一个工具，不让它纯文本输出
    )

    async def supervisor_node(state: SupervisorState) -> dict:
        """一轮 LLM 决策：派 N 个 researcher 或宣布完成。"""
        iteration = state.get("iteration", 0)
        max_iter = state.get("max_iterations", 3)

        # 第一轮才注入 system + user，后续轮 messages 会被 reducer 累加
        msgs = state.get("supervisor_messages") or []
        if not msgs:
            msgs = [
                SystemMessage(
                    content=_SUPERVISOR_PROMPT.format(
                        question=state["research_brief"],
                        max_iterations=max_iter,
                    )
                ),
                HumanMessage(content="请开始。"),
            ]
        elif iteration >= max_iter:
            # 用完预算了，强行收尾
            if progress_cb:
                progress_cb(f"已达最大轮数 {max_iter}，强制收尾")
            msgs = msgs + [
                HumanMessage(
                    content=f"已经研究了 {iteration} 轮。请立即调 research_complete 收尾，不要再派 researcher。"
                )
            ]

        if progress_cb:
            progress_cb(f"supervisor 决策 (第 {iteration + 1} 轮)")

        ai = await llm.ainvoke(msgs)
        return {
            "supervisor_messages": ([] if state.get("supervisor_messages") else msgs) + [ai],
            "iteration": iteration + 1,
        }

    async def supervisor_tools_node(state: SupervisorState) -> dict:
        """截获 supervisor 的 tool_calls：
        - conduct_research → asyncio.gather 并发跑 researcher
        - research_complete → 不做事，路由会把流程引到 END
        """
        last = state["supervisor_messages"][-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return {}

        research_calls = [c for c in last.tool_calls if c["name"] == "conduct_research"]
        complete_calls = [c for c in last.tool_calls if c["name"] == "research_complete"]

        new_findings: list[Finding] = []
        tool_messages: list[ToolMessage] = []

        # === 并发执行所有 conduct_research ===
        if research_calls:
            topics = [c["args"].get("topic", "") for c in research_calls]
            if progress_cb:
                progress_cb(f"并行派出 {len(topics)} 名 researcher")

            results = await asyncio.gather(
                *(
                    arun_researcher(
                        topic,
                        progress_cb=_indented_cb(progress_cb, f"#{i + 1}"),
                    )
                    for i, topic in enumerate(topics)
                ),
                return_exceptions=True,
            )
            for call, topic, result in zip(research_calls, topics, results):
                if isinstance(result, Exception):
                    msg = f"[研究失败] {type(result).__name__}: {result}"
                    if progress_cb:
                        progress_cb(f"⚠ '{topic}' {msg}")
                else:
                    new_findings.append(result)
                    msg = f"[研究完成] {topic}\nsummary: {result.summary[:500]}..."
                tool_messages.append(ToolMessage(content=msg, tool_call_id=call["id"]))

        # === 处理 research_complete（如果有） ===
        for call in complete_calls:
            tool_messages.append(
                ToolMessage(content="ok, proceeding to writer.", tool_call_id=call["id"])
            )

        return {
            "supervisor_messages": tool_messages,
            "findings": new_findings,
        }

    def route_after_supervisor(state: SupervisorState) -> Literal["tools", "end"]:
        last = state["supervisor_messages"][-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return "end"
        return "tools"

    def route_after_tools(state: SupervisorState) -> Literal["supervisor", "end"]:
        last = state["supervisor_messages"][-1]
        # 上一条 AIMessage（supervisor 决策）里有没有 research_complete？
        for m in reversed(state["supervisor_messages"]):
            if isinstance(m, AIMessage) and m.tool_calls:
                if any(c["name"] == "research_complete" for c in m.tool_calls):
                    return "end"
                break
        if state.get("iteration", 0) >= state.get("max_iterations", 3):
            return "end"
        return "supervisor"

    g = StateGraph(SupervisorState)
    g.add_node("supervisor", supervisor_node)
    g.add_node("tools", supervisor_tools_node)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", route_after_supervisor, {"tools": "tools", "end": END})
    g.add_conditional_edges("tools", route_after_tools, {"supervisor": "supervisor", "end": END})
    return g.compile()


def _indented_cb(parent: ProgressCallback | None, prefix: str) -> ProgressCallback | None:
    """给 researcher 用的回调加个前缀，CLI 上能看出"是哪个 researcher 在说话"。"""
    if parent is None:
        return None

    def cb(msg: str) -> None:
        parent(f"{prefix} {msg}")

    return cb


# ============================================================
# 顶层入口（被主图当作一个节点调）
# ============================================================

async def arun_supervisor(
    research_brief: str,
    progress_cb: ProgressCallback | None = None,
    max_iterations: int = 3,
) -> list[Finding]:
    """跑完整 supervisor 流程，返回所有 findings。"""
    sub = _build_supervisor_subgraph(progress_cb)
    state = await sub.ainvoke(
        {
            "research_brief": research_brief,
            "supervisor_messages": [],
            "findings": [],
            "iteration": 0,
            "max_iterations": max_iterations,
        },
        config={"recursion_limit": 50},  # 防 LangGraph 自己的 limit 提前 trip
    )
    return state.get("findings", [])
