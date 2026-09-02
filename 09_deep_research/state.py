"""Deep Research Agent 的状态结构。

v2 升级：从「一个 state 走天下」变成「按 scope 分层」——
- ResearchState   : 主图状态，全局可见（question/sub_questions/findings/report）
- SupervisorState : supervisor 子图独享，外部看不到它的内部 messages
- ResearcherState : 单个 researcher 子调用独享

这种分层不是为了好看，是为了**类型上禁止上下文越界**：你不可能把主图 state
误传给 researcher，也不会把 researcher 内部的 100 条 messages 污染到主图。
这是 multi-agent 系统不爆上下文的关键。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解

import operator  # 导入 operator 标准库
from typing import Annotated, Any, TypedDict  # 导入 typing 类型注解

from langchain_core.messages import BaseMessage  # 导入消息类型 Human/AI/System
from pydantic import BaseModel, Field  # 导入 pydantic 数据校验


# ============================================================
# 业务数据模型（跨 state 共享）
# ============================================================

class Source(BaseModel):  # 定义类
    """一条引用来源。"""
    url: str  # 执行本行逻辑
    title: str = ""  # 赋值给 str


class Finding(BaseModel):  # 定义类
    """一个子问题的研究结论。每个 researcher 产出一条。"""
    sub_question: str = Field(description="这条 finding 对应的子问题")  # 赋值给 str
    summary: str = Field(description="子问题的答案，中文，包含具体事实/数字")  # 赋值给 str
    sources: list[Source] = Field(default_factory=list, description="引用的网页列表")  # 赋值给 list[Source]


# ============================================================
# Reducer：override vs append
# ============================================================

def override_or_extend(current: list | None, new: Any) -> list:  # 定义函数
    """LangGraph reducer：默认 append；payload 是 `{"__override__": True, "value": [...]}` 时整体覆盖。

    没有 override 模式的话，supervisor 想"清空 findings 重新研究"就没法实现
    （operator.add 只能加，不能减）。这是从官方 open_deep_research 学的技巧。
    """
    current = list(current or [])  # 赋值给 current
    if isinstance(new, dict) and new.get("__override__"):  # 代码块起始
        return list(new.get("value", []))  # 返回结果
    if isinstance(new, list):  # 代码块起始
        return current + new  # 返回结果
    return current + [new]  # 返回结果


# ============================================================
# 主图状态
# ============================================================

class ResearchState(TypedDict, total=False):  # 定义类
    """主图（StateGraph 顶层）的状态。

    - question / report：单值，覆盖
    - sub_questions：simple 模式下 planner 写入
    - findings：N 个 researcher 并行写入，用 reducer 合并
    - progress_events：流式进度，前端实时打印用
    """
    question: str  # 执行本行逻辑
    sub_questions: list[str]  # 执行本行逻辑
    findings: Annotated[list[Finding], override_or_extend]  # 执行本行逻辑
    report: str  # 执行本行逻辑
    progress_events: Annotated[list[str], operator.add]  # 执行本行逻辑
    # supervisor 模式下用
    research_brief: str  # 执行本行逻辑
    iteration: int  # 执行本行逻辑


# ============================================================
# Supervisor 子图状态
# ============================================================

class SupervisorState(TypedDict, total=False):  # 定义类
    """Supervisor 自己的 ReAct 循环状态。

    main graph 只通过 research_brief（入参）和 findings（出参）跟它交互——
    supervisor 的所有 messages、决策过程外部看不到，避免污染主图上下文。
    """
    research_brief: str  # 执行本行逻辑
    supervisor_messages: Annotated[list[BaseMessage], operator.add]  # 执行本行逻辑
    findings: Annotated[list[Finding], override_or_extend]  # 执行本行逻辑
    iteration: int                      # supervisor 跑了几轮
    max_iterations: int  # 执行本行逻辑


# ============================================================
# Researcher 子调用状态（每个独立的 sub_question 一份）
# ============================================================

class ResearcherState(TypedDict, total=False):  # 定义类
    """单个 researcher 的独立工作区。

    跟主图、跟其它 researcher 都完全隔离。
    """
    sub_question: str  # 执行本行逻辑
    researcher_messages: Annotated[list[BaseMessage], operator.add]  # 执行本行逻辑
    tool_call_count: int  # 执行本行逻辑
