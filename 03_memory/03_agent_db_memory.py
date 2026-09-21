"""
03-3 create_agent + SQLite Checkpointer
学到：用 create_agent 的 checkpointer 把短期记忆持久化到 SQLite。
- 同一 thread_id → 多轮共享 messages
- 进程重启后，只要复用同一 .sqlite 文件 + thread_id，上下文仍可恢复
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain.agents import create_agent
from langchain_core.tools import tool

from _common import banner, get_llm

try:
    from langgraph.checkpoint.sqlite import SqliteSaver
except ImportError as exc:
    raise ImportError(
        "缺少 SQLite checkpointer，请安装：pip install langgraph-checkpoint-sqlite"
    ) from exc

# checkpoint 落盘路径（相对本文件，便于 demo 观察）
DB_PATH = Path(__file__).resolve().parent / ".checkpoints" / "agent_memory.sqlite"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@tool
def get_user_info() -> str:
    """查询当前用户档案（演示用固定返回值）。"""
    return "No user profile on file."


def build_agent(memorysaver : SqliteSaver):
    """创建带 checkpointer 的 agent（图在 compile 时已绑定持久化）。"""
    return create_agent(
        model=get_llm(temperature=0),
        tools=[get_user_info],
        checkpointer=memorysaver,
    )


def last_reply(agent, user_text: str, thread_config: dict) -> str:
    out = agent.invoke(
        {"messages": [{"role": "user", "content": user_text}]},
        thread_config,
    )
    return out["messages"][-1].content


def main() -> None:
    banner("03-3 create_agent · SQLite Checkpointer")
    print(f"checkpoint 文件: {DB_PATH}\n")

    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    agent = build_agent(checkpointer)

    thread_config = {"configurable": {"thread_id": "demo-user-1"}}

    # ---- 第一轮对话：写入名字 ----
    q1 = "Hi! My name is Bob."
    r1 = last_reply(agent, q1, thread_config)
    print(f"用户: {q1}\n助手: {r1}\n")

    # ---- 第二轮：同 thread_id，应能记住 Bob ----
    q2 = "What's my name?"
    r2 = last_reply(agent, q2, thread_config)
    print(f"用户: {q2}\n助手: {r2}\n")

    # ---- 模拟进程重启：新建连接 + 新 agent，复用同一 DB 与 thread_id ----
    print("── 模拟重启：重新连接 SQLite，复用 thread_id ──")
    conn.close()

    conn2 = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    agent2 = build_agent(SqliteSaver(conn2))
    q3 = "Do you still remember my name?"
    r3 = last_reply(agent2, q3, thread_config)
    print(f"用户: {q3}\n助手: {r3}\n")

    # ---- 不同 thread_id：隔离会话 ----
    other_thread = {"configurable": {"thread_id": "demo-user-2"}}
    q4 = "What's my name?"
    r4 = last_reply(agent2, q4, other_thread)
    print(f"[thread demo-user-2] 用户: {q4}\n助手: {r4}")

    conn2.close()


if __name__ == "__main__":
    main()
