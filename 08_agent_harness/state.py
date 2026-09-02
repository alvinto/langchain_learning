"""
Agent harness 的运行时状态。

LangGraph 把 state 在节点之间传来传去，每个节点返回一个 dict 表示要更新的字段，
框架根据 reducer (Annotated[..., add_messages] 等) 合并到全局 state。
"""
from __future__ import annotations  # 延迟注解，支持前向引用

from typing import Annotated, Literal, TypedDict  # 类型注解工具

from langchain_core.messages import BaseMessage  # 消息基类
from langgraph.graph.message import add_messages  # messages 字段的 append reducer


class Todo(TypedDict):  # 定义类
    """Agent 自管理的任务项。"""
    id: int  # 待办序号
    content: str  # 待办描述
    status: Literal["pending", "in_progress", "done"]  # 待办状态枚举


class AgentState(TypedDict):  # 定义类
    """LangGraph 全局状态 schema。"""

    # add_messages reducer：append 而不是覆盖
    messages: Annotated[list[BaseMessage], add_messages]  # 对话历史，按 id 合并/追加

    # Agent 自己写入的待办清单（todo_write 工具更新）
    todos: list[Todo]  # 当前待办列表

    # 当前迭代次数，超过 max_iterations 强制停机，避免无限循环
    iteration: int  # agent 节点已执行次数
    max_iterations: int  # 最大允许迭代次数

    # 错误重试预算：连续工具失败超过这个数就停机
    error_count: int  # 连续/累计错误计数（成功会清零）
    max_errors: int  # 允许的最大错误次数

    # 会话 id，用于日志和 checkpointing
    session_id: str  # 关联 .sessions/<id>.jsonl 与 thread_id
