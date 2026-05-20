"""
02-2 RunnableParallel
学到：把多个分支并行跑，结果合并成一个 dict，常用于"同时算多个东西"的场景。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableParallel
from _common import get_llm, banner


def main() -> None:
    banner("02-2 RunnableParallel")
    llm = get_llm()
    parser = StrOutputParser()

    joke_chain = ChatPromptTemplate.from_template("讲一个关于 {topic} 的笑话") | llm | parser
    poem_chain = ChatPromptTemplate.from_template("写一首关于 {topic} 的两句小诗") | llm | parser

    # 字典写法等价于 RunnableParallel(joke=..., poem=...)
    parallel = RunnableParallel(joke=joke_chain, poem=poem_chain)
    result = parallel.invoke({"topic": "程序员"})
    print("== 笑话 ==\n", result["joke"])
    print("\n== 小诗 ==\n", result["poem"])


if __name__ == "__main__":
    main()
