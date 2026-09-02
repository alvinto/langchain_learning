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
from __future__ import annotations  # 延迟注解

import json  # 预留：可序列化调试信息（当前未直接使用）
import uuid  # 生成 session_id
from typing import Literal  # 路由返回值类型

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage  # 消息类型
from langgraph.checkpoint.memory import MemorySaver  # 内存 checkpointer
from langgraph.graph import END, START, StateGraph  # 图构建 API

import sys  # 修改 import 路径
from pathlib import Path  # 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 项目根
from _common import get_llm  # noqa: E402  # LLM 工厂

from compression import maybe_compress  # 上下文压缩
from hooks import HookBus, audit_logger, block_dangerous_bash  # hook 总线与内置 hook
from permissions import PermissionPolicy, default_policy, prompt_user  # 权限网关
from state import AgentState, Todo  # 状态 schema
from subagent import spawn_subagent  # 子 Agent 工具
from tools import ALL_TOOLS  # 基础工具集

ALL_TOOLS_WITH_SUB = ALL_TOOLS + [spawn_subagent]  # 主 Agent 完整工具列表
TOOL_MAP = {t.name: t for t in ALL_TOOLS_WITH_SUB}  # 工具名 → 可 invoke 对象


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
"""  # 注入 agent 节点的系统人设


def build_harness(  # 定义函数
    policy: PermissionPolicy | None = None,  # 赋值给 None
    max_iterations: int = 25,  # 赋值给 int
    max_errors: int = 5,  # 赋值给 int
    compress_threshold: int = 30,  # 赋值给 int
):  # 代码块起始
    """构建并编译 LangGraph harness。返回 (app, hooks, policy)。"""
    policy = policy or default_policy()  # 使用传入策略或默认策略
    hooks = HookBus()  # 新建 hook 总线
    hooks.register("pre_tool", block_dangerous_bash)  # 注册危险 bash 拦截

    llm = get_llm(temperature=0.0).bind_tools(ALL_TOOLS_WITH_SUB)  # 绑定全部工具的 LLM

    # ---------- 节点：agent ----------
    def agent_node(state: AgentState) -> dict:  # 定义函数
        """调用 LLM 生成下一条 AIMessage（可能含 tool_calls）。"""
        msgs: list[BaseMessage] = state["messages"]  # 当前对话历史
        # 第一次进来若没有 system prompt，就插一条
        if not msgs or not isinstance(msgs[0], SystemMessage):  # 缺少 system 首条
            msgs = [SystemMessage(content=SYSTEM_PROMPT)] + msgs  #  prepend 人设

        ai = llm.invoke(msgs)  # LLM 推理
        return {  # 返回结果
            "messages": [ai],  # 追加 AI 消息（add_messages reducer）
            "iteration": state.get("iteration", 0) + 1,  # 迭代计数 +1
        }  # 闭合括号/元组/字典

    # ---------- 节点：tools（权限 + hooks + 错误处理） ----------
    def tool_node(state: AgentState) -> dict:  # 定义函数
        """执行 AIMessage 中的 tool_calls，返回 ToolMessage 列表。"""
        last = state["messages"][-1]  # 最后一条消息应为 AIMessage
        if not isinstance(last, AIMessage) or not last.tool_calls:  # 无 tool_calls
            return {}  # 不更新 state

        tool_messages: list[ToolMessage] = []  # 待追加的工具结果
        new_todos = state.get("todos", [])  # 当前 todos（可能被 todo_write 更新）
        new_errors = state.get("error_count", 0)  # 错误计数

        for call in last.tool_calls:  # 逐个处理 tool_call
            name = call["name"]  # 工具名
            args = call["args"]  # 工具参数
            tcid = call["id"]  # tool_call_id，必须与 ToolMessage 配对

            ctx = {  # hook / 日志上下文
                "session_id": state["session_id"],  # 字符串/template 参数
                "tool_name": name,  # 字符串/template 参数
                "tool_args": args,  # 字符串/template 参数
                "tool_call_id": tcid,  # 字符串/template 参数
            }  # 闭合括号/元组/字典

            # 1) 权限网关
            decision = policy.decide(name)  # 查 auto/ask/deny
            if decision == "deny":  # 策略禁用
                msg = f"[denied] 工具 {name} 已被策略禁用"  # 赋值给 msg
                tool_messages.append(ToolMessage(content=msg, tool_call_id=tcid))  # 回灌拒绝
                hooks.fire("post_tool", {**ctx, "result": msg, "blocked": True})  # 审计
                continue  # 下一个 tool_call
            if decision == "ask":  # 需用户确认
                approved, sticky = prompt_user(name, args)  # 同步询问
                if sticky:  # 用户选 a：本会话 auto
                    policy.set(name, "auto")  # 热更新策略
                if not approved:  # 用户拒绝
                    msg = f"[denied] 用户拒绝执行 {name}"  # 赋值给 msg
                    tool_messages.append(ToolMessage(content=msg, tool_call_id=tcid))  # 构造工具返回消息
                    hooks.fire("post_tool", {**ctx, "result": msg, "blocked": True})  # 执行本行逻辑
                    continue  # 跳过本次循环

            # 2) pre_tool hook（可阻断、可改写参数）
            pre = hooks.fire("pre_tool", ctx)  # 派发 pre_tool
            if pre.get("block"):  # hook 阻断
                msg = f"[blocked by hook] {pre.get('reason', '')}"  # 赋值给 msg
                tool_messages.append(ToolMessage(content=msg, tool_call_id=tcid))  # 构造工具返回消息
                hooks.fire("post_tool", {**ctx, "result": msg, "blocked": True})  # 执行本行逻辑
                continue  # 跳过本次循环
            if pre.get("override_args"):  # hook 改写参数
                args = pre["override_args"]  # 使用改写后的 args

            # 3) 执行
            tool = TOOL_MAP.get(name)  # 查工具实现
            if tool is None:  # 未知工具名
                result = f"[error] 未知工具: {name}"  # 赋值给 result
                new_errors += 1  # 错误 +1
            else:  # else 分支
                try:  # 代码块起始
                    result = tool.invoke(args)  # 调用 @tool 函数
                    if isinstance(result, str) and result.startswith("[error]"):  # 工具返回错误串
                        new_errors += 1  # 执行本行逻辑
                    else:  # else 分支
                        new_errors = 0  # 成功一次就清零，避免偶发错误累积
                except Exception as e:  # 捕获异常
                    result = f"[error] {type(e).__name__}: {e}"  # 异常转字符串
                    new_errors += 1  # 执行本行逻辑

            # 4) todo_write 的副作用：把状态写回 state.todos
            if name == "todo_write":  # 待办工具特殊处理
                items = args.get("items", [])  # 完整清单
                new_todos = [  # 覆盖式更新 todos
                    Todo(id=it["id"], content=it["content"], status=it["status"])  # 执行本行逻辑
                    for it in items  # for 循环
                ]  # 闭合括号/元组/字典

            tool_messages.append(ToolMessage(content=str(result), tool_call_id=tcid))  # 追加结果
            hooks.fire("post_tool", {**ctx, "result": str(result)[:500]})  # 审计（截断过长结果）

        return {  # 返回结果
            "messages": tool_messages,  # 批量追加 ToolMessage
            "todos": new_todos,  # 可能更新的 todos
            "error_count": new_errors,  # 更新错误计数
        }  # 闭合括号/元组/字典

    # ---------- 节点：compress ----------
    def compress_node(state: AgentState) -> dict:  # 定义函数
        """消息过多时压缩历史，替换 messages。"""
        msgs = state["messages"]  # 当前全量消息
        compressed = maybe_compress(msgs, threshold=compress_threshold)  # 尝试压缩
        if compressed is msgs or len(compressed) == len(msgs):  # 未发生压缩
            return {}  # 不更新
        # 用 RemoveMessage 替换会更干净，但需要每条消息有稳定 id；这里简单做法：
        # 直接把整个 messages 替换掉。注意 add_messages reducer 在传入带 id 的消息时
        # 会按 id 合并，否则 append。我们用 RemoveMessage + add 才能真正"替换"。
        from langchain_core.messages import RemoveMessage  # 延迟 import

        removals = [RemoveMessage(id=m.id) for m in msgs if getattr(m, "id", None)]  # 删除旧消息
        return {"messages": removals + compressed}  # 删旧 + 写新

    # ---------- 路由 ----------
    def route_after_agent(state: AgentState) -> Literal["tools", "end"]:  # 定义函数
        """agent 节点之后：继续 tools 或结束。"""
        last = state["messages"][-1]  # 最新 AI 消息
        if state.get("iteration", 0) >= state.get("max_iterations", max_iterations):  # 超迭代预算
            return "end"  # 返回结果
        if state.get("error_count", 0) >= state.get("max_errors", max_errors):  # 超错误预算
            return "end"  # 返回结果
        if isinstance(last, AIMessage) and last.tool_calls:  # 还有 tool_calls 待执行
            return "tools"  # 返回结果
        return "end"  # 无 tool_calls，任务结束

    # ---------- 组装图 ----------
    g = StateGraph(AgentState)  # 指定 state schema
    g.add_node("agent", agent_node)  # LLM 节点
    g.add_node("tools", tool_node)  # 工具执行节点
    g.add_node("compress", compress_node)  # 压缩节点

    g.add_edge(START, "agent")  # 入口 → agent
    g.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "end": END})  # 条件边
    g.add_edge("tools", "compress")  # tools → compress
    g.add_edge("compress", "agent")  # compress → agent 形成 ReAct 环

    app = g.compile(checkpointer=MemorySaver())  # 编译并启用内存 checkpoint
    return app, hooks, policy  # 返回三元组供 REPL 使用


def new_session_id() -> str:  # 定义函数
    """生成短 session id（12 位 hex）。"""
    return uuid.uuid4().hex[:12]  # 截断 UUID


def initial_state(session_id: str, user_input: str, max_iterations: int = 25, max_errors: int = 5) -> AgentState:  # 定义函数
    """构造新 thread 的完整初始 state。"""
    from langchain_core.messages import HumanMessage  # 延迟 import

    return {  # 返回结果
        "messages": [HumanMessage(content=user_input)],  # 首条用户消息
        "todos": [],  # 空待办
        "iteration": 0,  # 迭代从 0 开始
        "max_iterations": max_iterations,  # 迭代上限
        "error_count": 0,  # 错误计数清零
        "max_errors": max_errors,  # 错误上限
        "session_id": session_id,  # 会话标识
    }  # 闭合括号/元组/字典
