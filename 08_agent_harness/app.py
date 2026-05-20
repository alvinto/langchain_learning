"""
REPL 入口：跑起来体验完整 harness。

用法：
    python 08_agent_harness/app.py

支持的斜杠命令：
    /todos         查看 Agent 当前的待办清单
    /policy        查看权限策略
    /allow <tool>  把某工具改成 auto（本会话）
    /deny  <tool>  把某工具改成 deny（本会话）
    /reset         开新会话（之前的对话历史丢弃）
    /quit          退出
"""
from __future__ import annotations

import sys
from pathlib import Path

# 确保子模块可以 import
sys.path.insert(0, str(Path(__file__).resolve().parent))

from langchain_core.messages import AIMessage, HumanMessage

from harness import build_harness, initial_state, new_session_id
from hooks import audit_logger


BANNER = """
============================================================
  Mini Agent Harness — 迷你版 Claude Code 风格代码助手
  workspace: ./08_agent_harness/workspace/
  /quit 退出，/help 看所有命令
============================================================
"""


def print_help():
    print(__doc__)


def print_todos(todos):
    if not todos:
        print("(还没有待办)")
        return
    icon = {"pending": "○", "in_progress": "▶", "done": "✔"}
    for t in todos:
        print(f"  {icon.get(t['status'], '?')} #{t['id']} {t['content']}")


def main():
    print(BANNER)
    app, hooks, policy = build_harness()

    session_id = new_session_id()
    hooks.register("pre_tool", audit_logger(session_id))
    hooks.register("post_tool", audit_logger(session_id))
    print(f"[session {session_id}] 日志写入 .sessions/{session_id}.jsonl\n")

    # LangGraph thread id —— checkpointer 用它区分不同 session
    config = {"configurable": {"thread_id": session_id}}
    first_turn = True

    while True:
        try:
            user = input("\n你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user:
            continue
        if user in {"/quit", "/exit"}:
            break
        if user == "/help":
            print_help()
            continue
        if user == "/todos":
            snap = app.get_state(config).values
            print_todos(snap.get("todos", []))
            continue
        if user == "/policy":
            print(f"default = {policy.default}")
            for k, v in policy.rules.items():
                print(f"  {k}: {v}")
            continue
        if user.startswith("/allow "):
            policy.set(user.split(" ", 1)[1].strip(), "auto")
            print("ok")
            continue
        if user.startswith("/deny "):
            policy.set(user.split(" ", 1)[1].strip(), "deny")
            print("ok")
            continue
        if user == "/reset":
            session_id = new_session_id()
            config = {"configurable": {"thread_id": session_id}}
            first_turn = True
            print(f"[session {session_id}] 新会话已开始")
            continue

        # ---- 真正跑 Agent ----
        if first_turn:
            inputs = initial_state(session_id, user)
            first_turn = False
        else:
            # 已有 thread，只追加新的 HumanMessage，state 由 checkpointer 续上
            inputs = {"messages": [HumanMessage(content=user)]}

        # 流式打印每个节点的输出
        try:
            for chunk in app.stream(inputs, config=config, stream_mode="values"):
                last = chunk["messages"][-1] if chunk.get("messages") else None
                if isinstance(last, AIMessage):
                    if last.tool_calls:
                        for c in last.tool_calls:
                            print(f"  ⚙ {c['name']}({_short(c['args'])})")
                    elif last.content:
                        print(f"\nAgent > {last.content}")
        except KeyboardInterrupt:
            print("\n[interrupted]")
            continue
        except Exception as e:
            print(f"\n[harness error] {type(e).__name__}: {e}")


def _short(d: dict, n: int = 80) -> str:
    s = ", ".join(f"{k}={_trunc(v, 30)}" for k, v in d.items())
    return s if len(s) <= n else s[:n] + "..."


def _trunc(v, n):
    s = str(v)
    return s if len(s) <= n else s[:n] + "..."


if __name__ == "__main__":
    main()
