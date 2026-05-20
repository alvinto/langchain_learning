"""
01-5 流式输出
学到：用 .stream() 边生成边显示，体验更接近 ChatGPT。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from _common import get_llm, banner


def main() -> None:
    banner("01-5 Streaming")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个故事大王。"),
        ("human", "讲一个 100 字的睡前故事，主题：{topic}"),
    ])
    chain = prompt | get_llm() | StrOutputParser()

    # 注意：用 print(..., end="", flush=True) 才能看到流式效果
    for chunk in chain.stream({"topic": "勇敢的小兔子"}):
        print(chunk, end="", flush=True)
    print()


if __name__ == "__main__":
    main()
