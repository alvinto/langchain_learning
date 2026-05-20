"""
Agent Harness 主体——一个 LangGraph 状态机。

图的拓扑：

        ┌──────────┐
   ───▶ │  agent   │ ◀──────────┐
        └────┬─────┘            │
             │                  │
   has tool_calls?  ── no ──▶ END
             │ yes              │
             ▼                  │
        ┌──────────┐            │
        │  tools   │ (权限+hooks) │
        └────┬─────┘            │
             ▼                  │
        ┌──────────┐            │
        │ compress │            │
        └────┬─────┘            │
             └──────────────────┘

跟 LangChain 自带的 create_react_agent 比，多了：
- 权限网关：每个工具调用前查策略，可被用户/hook 阻断
- Hook 总线：审计日志、危险命令拦截
- 自管理 Todo：todo_write 工具的状态合并到 state.todos
- 上下文压缩：超过阈值自动摘要老消息
- 迭代/错误预算：避免无限循环和反复失败
- Checkpointing：MemorySaver 可以保存/恢复 thread
"""
from __future__ import annotations

import json
import uuid
from typing import Literal

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _common import get_llm  # noqa: E402

from compression import maybe_compress
from hooks import HookBus, audit_logger, block_dangerous_bash
from permissions import PermissionPolicy, default_policy, prompt_user
from state import AgentState, Todo
from subagent import spawn_subagent
from tools import ALL_TOOLS

ALL_TOOLS_WITH_SUB = ALL_TOOLS + [spawn_subagent]
TOOL_MAP = {t.name: t for t in ALL_TOOLS_WITH_SUB}


SYSTEM_PROMPT = """\
你是一个运行在沙箱里的代码助手。沙箱根目录是 ./workspace/。

你可以使用以下工具：
- read_file / write_file / list_dir / grep / run_bash：在 workspace 内操作文件和命令
- todo_write：把你的计划记到待办清单（用户能看到，你也能用来跟踪进度）
- spawn_subagent：当需要在多文件里调查某个问题时，派一个只读子 agent 去做，它只回传结论

工作守则：
1. 收到非平凡任务时先用 todo_write 写一份计划，再开始动手
2. 写文件前先看清楚现状（read_file / list_dir），不要凭空覆盖
3. 危险操作（rm、覆盖重要文件）先用一两句话说明你要做什么，再调用工具
4. 完成任务时用一两句话总结改动，不要把整个文件再粘贴一遍
"""


def build_harness(
    policy: PermissionPolicy | None = None,
    max_iterations: int = 25,
    max_errors: int = 5,
    compress_threshold: int = 30,
):
    """构建并编译 LangGraph harness。返回 (app, hooks, policy)。"""
    policy = policy or default_policy()
    hooks = HookBus()
    hooks.register("pre_tool", block_dangerous_bash)

    llm = get_llm(temperature=0.0).bind_tools(ALL_TOOLS_WITH_SUB)

    # ---------- 节点：agent ----------
    def agent_node(state: AgentState) -> dict:
        msgs: list[BaseMessage] = state["messages"]
        # 第一次进来若没有 system prompt，就插一条
        if not msgs or not isinstance(msgs[0], SystemMessage):
            msgs = [SystemMessage(content=SYSTEM_PROMPT)] + msgs

        ai = llm.invoke(msgs)
        return {
            "messages": [ai],
            "iteration": state.get("iteration", 0) + 1,
        }

    # ---------- 节点：tools（权限 + hooks + 错误处理） ----------
    def tool_node(state: AgentState) -> dict:
        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return {}

        tool_messages: list[ToolMessage] = []
        new_todos = state.get("todos", [])
        new_errors = state.get("error_count", 0)

        for call in last.tool_calls:
            name = call["name"]
            args = call["args"]
            tcid = call["id"]

            ctx = {
                "session_id": state["session_id"],
                "tool_name": name,
                "tool_args": args,
                "tool_call_id": tcid,
            }

            # 1) 权限网关
            decision = policy.decide(name)
            if decision == "deny":
                msg = f"[denied] 工具 {name} 已被策略禁用"
                tool_messages.append(ToolMessage(content=msg, tool_call_id=tcid))
                hooks.fire("post_tool", {**ctx, "result": msg, "blocked": True})
                continue
            if decision == "ask":
                approved, sticky = prompt_user(name, args)
                if sticky:
                    policy.set(name, "auto")
                if not approved:
                    msg = f"[denied] 用户拒绝执行 {name}"
                    tool_messages.append(ToolMessage(content=msg, tool_call_id=tcid))
                    hooks.fire("post_tool", {**ctx, "result": msg, "blocked": True})
                    continue

            # 2) pre_tool hook（可阻断、可改写参数）
            pre = hooks.fire("pre_tool", ctx)
            if pre.get("block"):
                msg = f"[blocked by hook] {pre.get('reason', '')}"
                tool_messages.append(ToolMessage(content=msg, tool_call_id=tcid))
                hooks.fire("post_tool", {**ctx, "result": msg, "blocked": True})
                continue
            if pre.get("override_args"):
                args = pre["override_args"]

            # 3) 执行
            tool = TOOL_MAP.get(name)
            if tool is None:
                result = f"[error] 未知工具: {name}"
                new_errors += 1
            else:
                try:
                    result = tool.invoke(args)
                    if isinstance(result, str) and result.startswith("[error]"):
                        new_errors += 1
                    else:
                        new_errors = 0  # 成功一次就清零，避免偶发错误累积
                except Exception as e:
                    result = f"[error] {type(e).__name__}: {e}"
                    new_errors += 1

            # 4) todo_write 的副作用：把状态写回 state.todos
            if name == "todo_write":
                items = args.get("items", [])
                new_todos = [
                    Todo(id=it["id"], content=it["content"], status=it["status"])
                    for it in items
                ]

            tool_messages.append(ToolMessage(content=str(result), tool_call_id=tcid))
            hooks.fire("post_tool", {**ctx, "result": str(result)[:500]})

        return {
            "messages": tool_messages,
            "todos": new_todos,
            "error_count": new_errors,
        }

    # ---------- 节点：compress ----------
    def compress_node(state: AgentState) -> dict:
        msgs = state["messages"]
        compressed = maybe_compress(msgs, threshold=compress_threshold)
        if compressed is msgs or len(compressed) == len(msgs):
            return {}
        # 用 RemoveMessage 替换会更干净，但需要每条消息有稳定 id；这里简单做法：
        # 直接把整个 messages 替换掉。注意 add_messages reducer 在传入带 id 的消息时
        # 会按 id 合并，否则 append。我们用 RemoveMessage + add 才能真正"替换"。
        from langchain_core.messages import RemoveMessage

        removals = [RemoveMessage(id=m.id) for m in msgs if getattr(m, "id", None)]
        return {"messages": removals + compressed}

    # ---------- 路由 ----------
    def route_after_agent(state: AgentState) -> Literal["tools", "end"]:
        last = state["messages"][-1]
        if state.get("iteration", 0) >= state.get("max_iterations", max_iterations):
            return "end"
        if state.get("error_count", 0) >= state.get("max_errors", max_errors):
            return "end"
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return "end"

    # ---------- 组装图 ----------
    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_node("tools", tool_node)
    g.add_node("compress", compress_node)

    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "end": END})
    g.add_edge("tools", "compress")
    g.add_edge("compress", "agent")

    app = g.compile(checkpointer=MemorySaver())
    return app, hooks, policy


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]


def initial_state(session_id: str, user_input: str, max_iterations: int = 25, max_errors: int = 5) -> AgentState:
    from langchain_core.messages import HumanMessage

    return {
        "messages": [HumanMessage(content=user_input)],
        "todos": [],
        "iteration": 0,
        "max_iterations": max_iterations,
        "error_count": 0,
        "max_errors": max_errors,
        "session_id": session_id,
    }
