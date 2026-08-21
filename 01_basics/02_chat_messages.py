"""
01-2 消息类型
学到：SystemMessage / HumanMessage / AIMessage 三种角色，多轮对话靠传消息列表实现。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from _common import get_llm, banner


def main() -> None:
    banner("01-2 Chat Messages")
    llm = get_llm()

    # 第一轮：给系统设定 + 用户提问
    messages = [
        SystemMessage("你是一个用河南话回答问题的助手。"),
        HumanMessage("讲讲冬天怎么穿衣服？"),
    ]
    reply1 = llm.invoke(messages)
    print("助手:", reply1.content, "\n")

    # 第二轮：把助手的回答作为 AIMessage 拼回去，继续问
    messages.extend([
        AIMessage(reply1.content),
        HumanMessage("那夏天呢？"),
    ])
    reply2 = llm.invoke(messages)
    print("助手:", reply2.content)


if __name__ == "__main__":
    main()
