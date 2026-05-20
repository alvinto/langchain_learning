"""
05-3 ReAct Agent（推荐）
学到：用 langgraph.prebuilt.create_react_agent 一行代码搞定"思考-调用工具-观察-再思考"循环。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.tools import tool

# LangChain 1.x: create_agent 在 langchain.agents；老版叫 create_react_agent 在 langgraph.prebuilt
try:
    from langchain.agents import create_agent as _create_agent
    _PROMPT_KEY = "system_prompt"
except ImportError:
    from langgraph.prebuilt import create_react_agent as _create_agent
    _PROMPT_KEY = "prompt"

from _common import get_llm, banner


@tool
def add(a: float, b: float) -> float:
    """加法"""
    return a + b


@tool
def multiply(a: float, b: float) -> float:
    """乘法"""
    return a * b


@tool
def get_user_age(name: str) -> int:
    """根据姓名查询年龄（演示用）"""
    db = {"张三": 28, "李四": 35, "王五": 19}
    return db.get(name, -1)


def main() -> None:
    banner("05-3 ReAct Agent")
    agent = _create_agent(
        model=get_llm(temperature=0),
        tools=[add, multiply, get_user_age],
        **{_PROMPT_KEY: "你是一个会用工具的助手。需要计算或查询时，必须调用工具。"},
    )

    out = agent.invoke({"messages": [
        ("user", "张三和李四的年龄之和是多少？再乘以 2 是多少？")
    ]})

    # out["messages"] 包含整段对话（含 tool 调用过程）
    for m in out["messages"]:
        # 不同消息类型用不同格式
        role = m.type
        content = (m.content or "").strip()
        tool_calls = getattr(m, "tool_calls", None)
        if tool_calls:
            print(f"[{role}] -> tool_calls: {tool_calls}")
        elif content:
            print(f"[{role}] {content}")


if __name__ == "__main__":
    main()
