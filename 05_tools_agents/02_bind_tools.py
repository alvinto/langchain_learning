from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage
from _common import get_llm, banner
"""
05-2 bind_tools 手工 Tool Calling
学到：理解 Tool Calling 的底层原理 —— LLM 返回 tool_calls，你执行后把结果以 ToolMessage 回传，再让 LLM 总结。
（生产中用 LangGraph 的 create_react_agent 自动处理，但先看一遍手动流程很有帮助）
"""

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

    # 增加系统提示，强制多步工具推理
    messages = [
        SystemMessage("你必须分步完成数学计算，拿到工具返回结果后，检查是否还有计算步骤未完成；只要还有运算就要继续调用工具，全部计算结束后再输出答案，不能中途停止。"),
        HumanMessage("先算 3 + 4，再把结果乘以 5，两步都要执行")
    ]
    ai = llm_with_tools.invoke(messages)

    # 改用while循环，逻辑更清晰
    max_round = 3
    round_num = 1
    while round_num <= max_round:
        print(f"\n第{round_num}轮 tool_calls: {ai.tool_calls}")
        if not ai.tool_calls:
            break
        # 执行所有工具
        for call in ai.tool_calls:
            res = TOOLS[call["name"]].invoke(call["args"])
            print(f"  执行 {call['name']}({call['args']}) = {res}")
            messages.append(ToolMessage(content=str(res), tool_call_id=call["id"]))
        # 重新请求模型
        ai = llm_with_tools.invoke(messages)
        round_num += 1

    print("\n===== 最终输出 ====")
    print(ai.content)


if __name__ == "__main__":
    main()