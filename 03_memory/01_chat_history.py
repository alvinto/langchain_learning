"""
03-1 ChatMessageHistory（最底层）
学到：手工维护一份消息列表，每轮对话往里 append。
适合理解原理，实际项目用 03-2 的 RunnableWithMessageHistory 更省事。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import HumanMessage
from _common import get_llm, banner


def main() -> None:
    banner("03-1 ChatMessageHistory")
    llm = get_llm()
    history = InMemoryChatMessageHistory()

    def chat(user_input: str) -> str:
        history.add_user_message(user_input)
        ai = llm.invoke(history.messages)  # 把整段历史交给模型
        history.add_ai_message(ai.content)
        return ai.content

    print("用户: 我叫小明")
    print("助手:", chat("我叫小明"))
    print("\n用户: 你还记得我叫什么吗？")
    print("助手:", chat("你还记得我叫什么吗？"))


if __name__ == "__main__":
    main()
