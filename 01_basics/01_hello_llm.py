"""
01-1 第一次调用 LLM
学到：怎么用 _common.get_llm() 拿模型，调用 .invoke() 单轮问答。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from _common import get_llm, banner


def main() -> None:
    banner("01-1 Hello LLM")
    llm = get_llm()
    # invoke 是最基础的同步调用，返回 AIMessage
    answer = llm.invoke("用一句话解释什么是 LangChain")
    print("内容字段:", answer.content)
    print("元信息:", answer.response_metadata)


if __name__ == "__main__":
    main()
