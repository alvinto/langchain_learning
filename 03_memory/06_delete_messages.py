"""
03-6 删除历史消息（Delete messages）

Common pattern：短记忆开启后对话变长，与其整段送进模型，不如**按 id 删掉**不再需要的轮次。

学到：
- `RemoveMessage(id=...)` 表示「从状态里移除这条消息」，本身没有 content。
- LangGraph 的 `add_messages` reducer 会应用删除；Agent / MessagesState 里返回
  `[RemoveMessage(...), ...新消息]` 是官方惯用法。
- `REMOVE_ALL_MESSAGES` 可清空后再写入摘要 + 最近几轮（常与 summarize 搭配）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages

from _common import banner


def _demo_messages() -> list:
    """构造带稳定 id 的多轮历史（RemoveMessage 必须指向已存在的 id）。"""
    return [
        SystemMessage(content="你是一个助手", id="sys"),
        HumanMessage(content="我叫小明", id="h1"),
        AIMessage(content="你好，小明！", id="a1"),
        HumanMessage(content="我 25 岁，住在上海", id="h2"),
        AIMessage(content="好的，已了解。", id="a2"),
        HumanMessage(content="今天天气怎么样？", id="h3"),
    ]


def print_messages(title: str, messages: list) -> None:
    print(f"\n>> {title}")
    for m in messages:
        mid = getattr(m, "id", None)
        print(f"  [{m.type}] id={mid!r} {m.content!r}")


def main() -> None:
    banner("03-6 Delete messages (RemoveMessage)")

    base = _demo_messages()
    print_messages("原始历史", base)

    # --- 策略 1：删除单条（例如去掉某轮 AI，避免重复或敏感内容进上下文）---
    without_a1 = add_messages(base, [RemoveMessage(id="a1")])
    print_messages("删除 id=a1 的 AI 回复后", without_a1)

    # --- 策略 2：删除多条 ---
    trimmed = add_messages(
        base,
        [
            RemoveMessage(id="h1"),
            RemoveMessage(id="a1"),
            RemoveMessage(id="h2"),
            RemoveMessage(id="a2"),
        ],
    )
    print_messages("只保留 system + 最后一问", trimmed)

    # --- 策略 3：清空全部再写入新列表（summarize 后常用此模式）---
    replaced = add_messages(
        base,
        [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            SystemMessage(
                content="此前对话摘要：用户叫小明，25 岁，上海。",
                id="sys-summary",
            ),
            HumanMessage(content="我叫什么、住在哪？", id="h-ask"),
        ],
    )
    print_messages("REMOVE_ALL 后替换为「摘要 + 新问题」", replaced)


if __name__ == "__main__":
    main()
