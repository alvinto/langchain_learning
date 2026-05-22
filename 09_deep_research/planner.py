"""Planner：把研究问题拆成 3~6 个互不重叠的子问题。

这是 multi-agent 系统里最关键的一步——拆得好，后面 fan-out 出去的 researcher
能各管各的；拆得差，几个 researcher 会重复劳动甚至互相矛盾。
"""
from __future__ import annotations

import sys
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _common import get_llm  # noqa: E402


class Plan(BaseModel):
    sub_questions: list[str] = Field(
        description="3~6 个互不重叠、可独立搜索的子问题，中文"
    )


_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是研究规划专家。把用户的研究问题拆成 3~6 个子问题，要求：\n"
            "1. 子问题加起来能完整覆盖原问题，不重不漏\n"
            "2. 每条独立可搜索（不要互相依赖、不要套娃）\n"
            "3. 粒度适中：不要太宽泛（一个子问题等于原问题），也不要太细（10 个琐碎条目）\n"
            "4. 用中文输出\n"
            "5. 如果原问题已经足够具体（比如「Python 3.13 的 GIL 移除提案是什么」），"
            "可以只拆 2~3 个子问题，不必凑数",
        ),
        ("user", "研究问题：{question}"),
    ]
)


def plan(question: str) -> list[str]:
    """把 question 拆成子问题列表。

    注意 method="function_calling"：langchain-openai 新版默认用 json_schema 模式，
    但 OpenAI 兼容协议提供方（DeepSeek / Qwen / 智谱…）大多只支持老的 function_calling，
    不显式指定会让 LLM 直接返回 Markdown 文本，导致 OpenAI SDK 解析 JSON 失败。
    """
    llm = get_llm(temperature=0)
    chain = _PROMPT | llm.with_structured_output(Plan, method="function_calling")
    result: Plan = chain.invoke({"question": question})
    return result.sub_questions


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "对比 LangGraph 和 OpenAI Agents SDK 的差异和适用场景"
    for i, sq in enumerate(plan(q), 1):
        print(f"{i}. {sq}")
