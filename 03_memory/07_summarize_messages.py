"""
03-7 摘要压缩历史（Summarize messages）

Common pattern：快触达上下文上限时，用 LLM 把**较早的对话**压成一段摘要，
再与 system、最近几轮一起发给模型（LangChain Agent 里对应 `SummarizationMiddleware`）。

学到：
- 先估算 token（`count_tokens_approximately`），超阈值再摘要，避免每轮都调 LLM。
- 摘要 + `trim_messages` / 保留最近 N 条，是生产里最常见的组合。
- 在 LangGraph 状态里更新历史时，常与 `RemoveMessage(REMOVE_ALL_MESSAGES)` 一起用
  （见 06_delete_messages.py）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    trim_messages,
)
from langchain_core.messages.utils import count_tokens_approximately, get_buffer_string
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from _common import banner, get_llm

# demo 阈值设低，便于本地一眼看到「触发摘要」分支（不调用 API 时用近似 token 判断）
TOKEN_BUDGET = 70
KEEP_RECENT_MESSAGES = 4


def build_long_history() -> list:
    """模拟多轮短记忆累积后的消息列表。"""
    return [
        SystemMessage(content="你是一个助手，回答简洁。"),
        HumanMessage(content="我叫小明，是后端工程师。"),
        AIMessage(content="你好小明，已记住你的职业。"),
        HumanMessage(content="我在学 LangChain 的 memory。"),
        AIMessage(content="Memory 通常指把历史消息再传给模型。"),
        HumanMessage(content="LangChain memory 有什么用？"),
        AIMessage(content="LangChain memory 可以用来记住历史消息，以便后续轮次继续使用。"),
        HumanMessage(content="上下文太长怎么办？"),
        AIMessage(content="常见做法：裁剪、删除或摘要历史。"),
        HumanMessage(content="请用一句话总结我们聊过的主题。"),
    ]


def split_for_summary(messages: list) -> tuple[list, list, list]:
    """保留 system；中间部分可摘要；末尾保留最近若干条 human/ai。"""
    system_msgs = [m for m in messages if m.type == "system"]
    dialogue = [m for m in messages if m.type != "system"]

    if len(dialogue) <= KEEP_RECENT_MESSAGES:
        return system_msgs, dialogue, []

    to_summarize = dialogue[:-KEEP_RECENT_MESSAGES]
    recent = dialogue[-KEEP_RECENT_MESSAGES:]
    return system_msgs, recent, to_summarize


def summarize_dialogue(to_summarize: list) -> str:
    """调用 LLM 生成简短中文摘要（需配置 .env 中的模型 API）。"""
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是会话压缩助手。根据下面的对话，用 2～4 句中文写出要点摘要，"
                "包含用户身份、讨论主题和已达成结论，供后续轮次继续使用。",
            ),
            ("human", "{history}"),
        ]
    )
    chain = prompt | get_llm() | StrOutputParser()
    return chain.invoke({"history": get_buffer_string(to_summarize)})


def compress_if_needed(messages: list) -> list:
    """超 token 预算则摘要旧对话，否则仅做尾部 trim。"""
    approx = count_tokens_approximately(messages)
    print(f"当前近似 token 数: {approx}（预算 {TOKEN_BUDGET}）")

    if approx <= TOKEN_BUDGET:
        print("未超预算，仅演示 trim_messages 保留尾部。")
        return trim_messages(
            messages,
            max_tokens=KEEP_RECENT_MESSAGES,
            token_counter=len,
            strategy="last",
            include_system=True,
            start_on="human",
        )

    system_msgs, recent, to_summarize = split_for_summary(messages)
    print(f"将摘要 {len(to_summarize)} 条，保留最近 {len(recent)} 条。")

    summary_text = summarize_dialogue(to_summarize)
    summary_msg = SystemMessage(content=f"此前对话摘要：{summary_text}")

    merged = system_msgs + [summary_msg] + recent
    print(f"合并后的消息: {merged}")
    print(f"合并后的消息长度: {len(merged)}")
    print(f"合并后的消息token数: {count_tokens_approximately(merged)}")
    return trim_messages(
        merged,
        max_tokens=TOKEN_BUDGET,
        token_counter=count_tokens_approximately,
        strategy="last",
        include_system=True,
        start_on="human",
    )


def main() -> None:
    banner("03-7 Summarize messages")

    history = build_long_history()
    print(">> 压缩前：")
    for m in history:
        print(f"  [{m.type}] {m.content[:60]}...")

    compressed = compress_if_needed(history)
    print("\n>> 压缩后（送入模型的消息）：")
    for m in compressed:
        text = m.content if isinstance(m.content, str) else str(m.content)
        preview = text if len(text) <= 80 else text[:80] + "..."
        print(f"  [{m.type}] {preview}")


if __name__ == "__main__":
    main()
