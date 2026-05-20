"""
上下文压缩：当历史消息过长时，把"较老的一半"摘要成一条 SystemMessage。

策略：
- 触发阈值用消息条数（简单直观；想严谨可以换 tiktoken 计 token）
- 始终保留：第一条 SystemMessage（人设）、最近 N 条消息（保持工具调用上下文连贯）
- 中间的消息送给小一档的 LLM 摘要

注意：不要把还没 tool_response 的 AI tool_call 切成"已摘要"——会让 OpenAI
报错"tool_call_id 找不到对应 assistant message"。这里的策略是：先找到一个
"安全切点"（既不是 ToolMessage、上一条也不是带 tool_calls 的 AIMessage），
再做切割。
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _common import get_llm  # noqa: E402


def _is_safe_cut(prev: BaseMessage | None, cur: BaseMessage) -> bool:
    if isinstance(cur, ToolMessage):
        return False
    if isinstance(prev, AIMessage) and getattr(prev, "tool_calls", None):
        return False
    return True


def maybe_compress(messages: list[BaseMessage], threshold: int = 30, keep_recent: int = 10) -> list[BaseMessage]:
    """超过 threshold 条就压缩，否则原样返回。"""
    if len(messages) <= threshold:
        return messages

    # 第 0 条若是 SystemMessage 永远保留
    head: list[BaseMessage] = []
    body_start = 0
    if messages and isinstance(messages[0], SystemMessage):
        head = [messages[0]]
        body_start = 1

    # 找一个安全切点：从倒数第 keep_recent 个开始往前找
    cut = max(body_start, len(messages) - keep_recent)
    while cut > body_start:
        prev = messages[cut - 1] if cut > 0 else None
        if _is_safe_cut(prev, messages[cut]):
            break
        cut -= 1

    to_summarize = messages[body_start:cut]
    tail = messages[cut:]
    if not to_summarize:
        return messages

    # 用 temperature=0 的 LLM 做摘要，避免胡编
    llm = get_llm(temperature=0.0)
    transcript = "\n\n".join(
        f"[{type(m).__name__}] {getattr(m, 'content', '') or ''}" for m in to_summarize
    )
    prompt = (
        "你是一个会话压缩助手。把下面的多轮 Agent 对话压缩成简洁的中文摘要，"
        "包含：用户目标、Agent 已采取的关键步骤与工具调用、目前已知事实、未完成的事项。"
        "不要丢失文件路径、命令、错误信息这些具体细节。\n\n"
        f"---\n{transcript}\n---"
    )
    summary = llm.invoke(prompt).content

    summary_msg = SystemMessage(
        content=f"[历史摘要 — 压缩了 {len(to_summarize)} 条消息]\n{summary}"
    )
    return head + [summary_msg] + tail
