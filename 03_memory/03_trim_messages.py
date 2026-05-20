"""
03-3 trim_messages 裁剪历史
学到：长对话会爆 token，用 trim_messages 按 token 数或条数滑动窗口。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import (
    SystemMessage, HumanMessage, AIMessage, trim_messages,
)
from _common import get_llm, banner


def main() -> None:
    banner("03-3 trim_messages")

    msgs = [
        SystemMessage("你是一个助手"),
        HumanMessage("我叫小明"),
        AIMessage("好的，小明"),
        HumanMessage("我 25 岁"),
        AIMessage("记下了"),
        HumanMessage("我住在上海"),
        AIMessage("收到"),
        HumanMessage("我叫什么名字、住哪？"),
    ]

    # 策略 1：按消息条数（保留最后 4 条 + 必带 system）
    trimmed_count = trim_messages(
        msgs,
        max_tokens=4,                      # 这里把"条数"当 token 用
        token_counter=len,                 # len 即一条算 1
        strategy="last",
        include_system=True,
        start_on="human",
    )
    print(">> 按条数裁剪后：")
    for m in trimmed_count:
        print(f"  [{m.type}] {m.content}")

    # 策略 2：按真实 token 数裁
    trimmed_tokens = trim_messages(
        msgs,
        max_tokens=80,
        token_counter=get_llm(),           # 用 LLM 自己的 tokenizer
        strategy="last",
        include_system=True,
        start_on="human",
    )
    print("\n>> 按 token 裁剪后：")
    for m in trimmed_tokens:
        print(f"  [{m.type}] {m.content}")


if __name__ == "__main__":
    main()
