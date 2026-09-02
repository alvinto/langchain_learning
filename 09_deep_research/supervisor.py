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
from __future__ import annotations  # 启用 PEP 563 延迟注解

import asyncio  # 导入 asyncio 异步库
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
from typing import Callable, Literal  # 导入 typing 类型注解

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage  # 导入消息类型 Human/AI/System
from langchain_core.tools import tool  # 导入 @tool 装饰器
from langgraph.graph import END, START, StateGraph  # 导入 LangGraph 图编排组件
from pydantic import BaseModel, Field  # 导入 pydantic 数据校验

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 执行本行逻辑
from _common import get_llm  # noqa: E402

from researcher import arun_researcher  # 执行本行逻辑
from state import Finding, SupervisorState  # 执行本行逻辑


ProgressCallback = Callable[[str], None]  # 赋值给 ProgressCallback


# ============================================================
# Supervisor 的工具 —— 不带逻辑，纯 schema
# ============================================================

class ConductResearch(BaseModel):  # 定义类
    """派一个 researcher 去研究指定的话题。"""

    topic: str = Field(  # 赋值给 str
        description="要研究的具体子问题。粒度要够细（一个 researcher 一次能搞定），"  # 执行本行逻辑
        "不要太宽（"  # 字符串/template 参数
        "比如「分析 LangGraph」太宽，应该改成「LangGraph 的 Send API 解决了什么问题」）",  # 字符串/template 参数
    )  # 闭合括号/元组/字典


class ResearchComplete(BaseModel):  # 定义类
    """所有需要的信息都收集齐了，可以开始写报告。"""


@tool(args_schema=ConductResearch)  # 声明 LangChain 工具
def conduct_research(topic: str) -> str:  # 定义函数
    """Stub —— supervisor 调它实际上不会执行，由 supervisor_tools 节点截获。"""
    return f"(队列中：{topic})"  # 返回结果


@tool(args_schema=ResearchComplete)  # 声明 LangChain 工具
def research_complete() -> str:  # 定义函数
    """Stub —— 由 supervisor_tools 节点截获后路由到 END。"""
    return "research complete"  # 返回结果


_TOOL_MAP = {"conduct_research": conduct_research, "research_complete": research_complete}  # 赋值给 _TOOL_MAP


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

def _build_supervisor_subgraph(progress_cb: ProgressCallback | None):  # 定义函数
    """构建 supervisor 子图。progress_cb 通过闭包传给内部节点和 researcher。"""

    llm = get_llm(temperature=0, role="smart").bind_tools(  # 获取 ChatOpenAI 兼容 LLM
        [conduct_research, research_complete],  # 链式/容器表达式续行
        tool_choice="any",  # 强制每轮必须调一个工具，不让它纯文本输出
    )  # 闭合括号/元组/字典

    async def supervisor_node(state: SupervisorState) -> dict:  # 定义异步函数
        """一轮 LLM 决策：派 N 个 researcher 或宣布完成。"""
        iteration = state.get("iteration", 0)  # 赋值给 iteration
        max_iter = state.get("max_iterations", 3)  # 赋值给 max_iter

        # 第一轮才注入 system + user，后续轮 messages 会被 reducer 累加
        msgs = state.get("supervisor_messages") or []  # 赋值给 msgs
        if not msgs:  # 代码块起始
            msgs = [  # 赋值给 msgs
                SystemMessage(  # 构造系统消息
                    content=_SUPERVISOR_PROMPT.format(  # 执行本行逻辑
                        question=state["research_brief"],  # 执行本行逻辑
                        max_iterations=max_iter,  # 执行本行逻辑
                    )  # 闭合括号/元组/字典
                ),  # 闭合括号/元组/字典
                HumanMessage(content="请开始。"),  # 构造用户消息
            ]  # 闭合括号/元组/字典
        elif iteration >= max_iter:  # elif 分支
            # 用完预算了，强行收尾
            if progress_cb:  # 代码块起始
                progress_cb(f"已达最大轮数 {max_iter}，强制收尾")  # 执行本行逻辑
            msgs = msgs + [  # 赋值给 msgs
                HumanMessage(  # 构造用户消息
                    content=f"已经研究了 {iteration} 轮。请立即调 research_complete 收尾，不要再派 researcher。"  # 执行本行逻辑
                )  # 闭合括号/元组/字典
            ]  # 闭合括号/元组/字典

        if progress_cb:  # 代码块起始
            progress_cb(f"supervisor 决策 (第 {iteration + 1} 轮)")  # 执行本行逻辑

        ai = await llm.ainvoke(msgs)  # 等待异步结果
        return {  # 返回结果
            "supervisor_messages": ([] if state.get("supervisor_messages") else msgs) + [ai],  # 字符串/template 参数
            "iteration": iteration + 1,  # 字符串/template 参数
        }  # 闭合括号/元组/字典

    async def supervisor_tools_node(state: SupervisorState) -> dict:  # 定义异步函数
        """截获 supervisor 的 tool_calls：
        - conduct_research → asyncio.gather 并发跑 researcher
        - research_complete → 不做事，路由会把流程引到 END
        """
        last = state["supervisor_messages"][-1]  # 赋值给 last
        if not isinstance(last, AIMessage) or not last.tool_calls:  # 代码块起始
            return {}  # 返回结果

        research_calls = [c for c in last.tool_calls if c["name"] == "conduct_research"]  # for 循环
        complete_calls = [c for c in last.tool_calls if c["name"] == "research_complete"]  # for 循环

        new_findings: list[Finding] = []  # 赋值给 list[Finding]
        tool_messages: list[ToolMessage] = []  # 赋值给 list[ToolMessage]

        # === 并发执行所有 conduct_research ===
        if research_calls:  # 代码块起始
            topics = [c["args"].get("topic", "") for c in research_calls]  # for 循环
            if progress_cb:  # 代码块起始
                progress_cb(f"并行派出 {len(topics)} 名 researcher")  # 执行本行逻辑

            results = await asyncio.gather(  # 等待异步结果
                *(  # 执行本行逻辑
                    arun_researcher(  # 执行本行逻辑
                        topic,  # 序列/元组元素
                        progress_cb=_indented_cb(progress_cb, f"#{i + 1}"),  # 执行本行逻辑
                    )  # 闭合括号/元组/字典
                    for i, topic in enumerate(topics)  # for 循环
                ),  # 闭合括号/元组/字典
                return_exceptions=True,  # 执行本行逻辑
            )  # 闭合括号/元组/字典
            for call, topic, result in zip(research_calls, topics, results):  # for 循环
                if isinstance(result, Exception):  # 代码块起始
                    msg = f"[研究失败] {type(result).__name__}: {result}"  # 赋值给 msg
                    if progress_cb:  # 代码块起始
                        progress_cb(f"⚠ '{topic}' {msg}")  # 执行本行逻辑
                else:  # else 分支
                    new_findings.append(result)  # 执行本行逻辑
                    msg = f"[研究完成] {topic}\nsummary: {result.summary[:500]}..."  # 赋值给 msg
                tool_messages.append(ToolMessage(content=msg, tool_call_id=call["id"]))  # 构造工具返回消息

        # === 处理 research_complete（如果有） ===
        for call in complete_calls:  # for 循环
            tool_messages.append(  # 执行本行逻辑
                ToolMessage(content="ok, proceeding to writer.", tool_call_id=call["id"])  # 构造工具返回消息
            )  # 闭合括号/元组/字典

        return {  # 返回结果
            "supervisor_messages": tool_messages,  # 字符串/template 参数
            "findings": new_findings,  # 字符串/template 参数
        }  # 闭合括号/元组/字典

    def route_after_supervisor(state: SupervisorState) -> Literal["tools", "end"]:  # 定义函数
        last = state["supervisor_messages"][-1]  # 赋值给 last
        if not isinstance(last, AIMessage) or not last.tool_calls:  # 代码块起始
            return "end"  # 返回结果
        return "tools"  # 返回结果

    def route_after_tools(state: SupervisorState) -> Literal["supervisor", "end"]:  # 定义函数
        last = state["supervisor_messages"][-1]  # 赋值给 last
        # 上一条 AIMessage（supervisor 决策）里有没有 research_complete？
        for m in reversed(state["supervisor_messages"]):  # for 循环
            if isinstance(m, AIMessage) and m.tool_calls:  # 代码块起始
                if any(c["name"] == "research_complete" for c in m.tool_calls):  # for 循环
                    return "end"  # 返回结果
                break  # 跳出循环
        if state.get("iteration", 0) >= state.get("max_iterations", 3):  # 代码块起始
            return "end"  # 返回结果
        return "supervisor"  # 返回结果

    g = StateGraph(SupervisorState)  # 创建 LangGraph 状态图
    g.add_node("supervisor", supervisor_node)  # 向图添加节点
    g.add_node("tools", supervisor_tools_node)  # 向图添加节点
    g.add_edge(START, "supervisor")  # 向图添加普通边
    g.add_conditional_edges("supervisor", route_after_supervisor, {"tools": "tools", "end": END})  # 向图添加条件边
    g.add_conditional_edges("tools", route_after_tools, {"supervisor": "supervisor", "end": END})  # 向图添加条件边
    return g.compile()  # 编译图为可执行应用


def _indented_cb(parent: ProgressCallback | None, prefix: str) -> ProgressCallback | None:  # 定义函数
    """给 researcher 用的回调加个前缀，CLI 上能看出"是哪个 researcher 在说话"。"""
    if parent is None:  # 代码块起始
        return None  # 返回结果

    def cb(msg: str) -> None:  # 定义函数
        parent(f"{prefix} {msg}")  # 执行本行逻辑

    return cb  # 返回结果


# ============================================================
# 顶层入口（被主图当作一个节点调）
# ============================================================

async def arun_supervisor(  # 定义异步函数
    research_brief: str,  # 执行本行逻辑
    progress_cb: ProgressCallback | None = None,  # 赋值给 None
    max_iterations: int = 3,  # 赋值给 int
) -> list[Finding]:  # 代码块起始
    """跑完整 supervisor 流程，返回所有 findings。"""
    sub = _build_supervisor_subgraph(progress_cb)  # 赋值给 sub
    state = await sub.ainvoke(  # 等待异步结果
        {  # 执行本行逻辑
            "research_brief": research_brief,  # 字符串/template 参数
            "supervisor_messages": [],  # 字符串/template 参数
            "findings": [],  # 字符串/template 参数
            "iteration": 0,  # 字符串/template 参数
            "max_iterations": max_iterations,  # 字符串/template 参数
        },  # 执行本行逻辑
        config={"recursion_limit": 50},  # 防 LangGraph 自己的 limit 提前 trip
    )  # 闭合括号/元组/字典
    return state.get("findings", [])  # 返回结果
