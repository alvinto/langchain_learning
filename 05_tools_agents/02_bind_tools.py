"""
05-2 bind_tools 手工 Tool Calling
学到：理解 Tool Calling 的底层原理 —— LLM 返回 tool_calls，你执行后把结果以 ToolMessage 回传，再让 LLM 总结。
（生产中用 LangGraph 的 create_react_agent 自动处理，但先看一遍手动流程很有帮助）
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage
from _common import get_llm, banner


@tool
def add(a: int, b: int) -> int:
    """两数相加。"""
    return a + b


@tool
def multiply(a: int, b: int) -> int:
    """两数相乘。"""
    return a * b


TOOLS = {"add": add, "multiply": multiply}


def main() -> None:
    banner("05-2 bind_tools (manual loop)")
    llm_with_tools = get_llm(temperature=0).bind_tools(list(TOOLS.values()))

    messages = [HumanMessage("先算 3 + 4，再把结果乘以 5")]
    ai = llm_with_tools.invoke(messages)
    messages.append(ai)
    print("第一轮 tool_calls:", ai.tool_calls)

    # 手动循环执行 tool_calls，最多 3 轮（防死循环）
    for _ in range(3):
        if not ai.tool_calls:
            break
        for call in ai.tool_calls:
            result = TOOLS[call["name"]].invoke(call["args"])
            print(f"  执行 {call['name']}({call['args']}) = {result}")
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
        ai = llm_with_tools.invoke(messages)
        messages.append(ai)

    print("\n最终回答:", ai.content)


if __name__ == "__main__":
    main()
