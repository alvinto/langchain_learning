"""
03-2 RunnableWithMessageHistory（推荐）
学到：把任意 Runnable 包一层，自动按 session_id 维护多轮历史。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.output_parsers import StrOutputParser
from _common import get_llm, banner


# 用全局 dict 模拟 session 存储（生产环境换成 Redis / 数据库）
_store: dict = {}


def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in _store:
        _store[session_id] = InMemoryChatMessageHistory()
    return _store[session_id]


def main() -> None:
    banner("03-2 RunnableWithMessageHistory")

    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个友好的助手，记住用户告诉过你的事情。"),
        MessagesPlaceholder("history"),
        ("human", "{input}"),
    ])
    chain = prompt | get_llm() | StrOutputParser()

    chatbot = RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="history",
    )

    cfg = {"configurable": {"session_id": "user-zz"}}

    for q in [
        "我叫张三，今年 28 岁",
        "我喜欢吃火锅",
        "你还记得我叫什么、喜欢吃什么吗？",
    ]:
        print(f"\n用户: {q}")
        print("助手:", chatbot.invoke({"input": q}, config=cfg))


if __name__ == "__main__":
    main()
