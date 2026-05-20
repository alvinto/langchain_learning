"""
02-1 LCEL 管道
学到：用 `|` 把 prompt → llm → parser 串成一条 Runnable，统一接口（invoke/stream/batch/ainvoke）。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from _common import get_llm, banner


def main() -> None:
    banner("02-1 LCEL Pipe Chain")
    prompt = ChatPromptTemplate.from_template("用一个比喻解释 {concept}")
    chain = prompt | get_llm() | StrOutputParser()

    print(">> invoke:")
    print(chain.invoke({"concept": "递归"}))

    print("\n>> batch:")  # 批量并发
    for r in chain.batch([{"concept": "闭包"}, {"concept": "并发"}]):
        print("-", r[:60], "...")


if __name__ == "__main__":
    main()
