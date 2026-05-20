"""
Agent harness 的运行时状态。

LangGraph 把 state 在节点之间传来传去，每个节点返回一个 dict 表示要更新的字段，
框架根据 reducer (Annotated[..., add_messages] 等) 合并到全局 state。
"""
from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class Todo(TypedDict):
    """Agent 自管理的任务项。"""
    id: int
    content: str
    status: Literal["pending", "in_progress", "done"]


class AgentState(TypedDict):
    # add_messages reducer：append 而不是覆盖
    messages: Annotated[list[BaseMessage], add_messages]

    # Agent 自己写入的待办清单（todo_write 工具更新）
    todos: list[Todo]

    # 当前迭代次数，超过 max_iterations 强制停机，避免无限循环
    iteration: int
    max_iterations: int

    # 错误重试预算：连续工具失败超过这个数就停机
    error_count: int
    max_errors: int

    # 会话 id，用于日志和 checkpointing
    session_id: str
