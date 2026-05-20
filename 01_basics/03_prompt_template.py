"""
01-3 提示词模板
学到：
- PromptTemplate：纯文本占位符
- ChatPromptTemplate：带角色的占位符（推荐）
- MessagesPlaceholder：占位一段历史消息
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.prompts import (
    PromptTemplate,
    ChatPromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.messages import HumanMessage
from _common import get_llm, banner


def demo_prompt_template() -> None:
    banner("PromptTemplate（纯文本）")
    tpl = PromptTemplate.from_template("把这句话翻译成{lang}：{text}")
    rendered = tpl.format(lang="英文", text="今天天气真好")
    print("渲染结果:", rendered)


def demo_chat_prompt() -> None:
    banner("ChatPromptTemplate（带角色）")
    tpl = ChatPromptTemplate.from_messages([
        ("system", "你是一名 {role}，回答要简洁。"),
        ("human", "{question}"),
    ])
    msgs = tpl.format_messages(role="Python 老师", question="装饰器是什么？")
    for m in msgs:
        print(f"[{m.type}] {m.content}")

    print("\n--- 调用 LLM ---")
    llm = get_llm()
    print(llm.invoke(msgs).content)


def demo_messages_placeholder() -> None:
    banner("MessagesPlaceholder（占位历史）")
    tpl = ChatPromptTemplate.from_messages([
        ("system", "你是一个聊天机器人。"),
        MessagesPlaceholder("history"),
        ("human", "{question}"),
    ])
    history = [HumanMessage("我叫小明")]
    msgs = tpl.format_messages(history=history, question="我叫什么名字？")
    print(get_llm().invoke(msgs).content)


def main() -> None:
    demo_prompt_template()
    demo_chat_prompt()
    demo_messages_placeholder()


if __name__ == "__main__":
    main()
