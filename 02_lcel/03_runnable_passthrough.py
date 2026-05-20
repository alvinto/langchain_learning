"""
02-3 RunnablePassthrough
学到：
- RunnablePassthrough() 把输入原样传下去
- .assign(...) 在原 dict 上加新字段
典型用法：RAG 里把 question 透传，同时新增 context 字段。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from _common import get_llm, banner


def fake_retrieve(question: str) -> str:
    """模拟一个检索器，返回相关文档。"""
    return f"[模拟检索结果] 关于'{question}'的资料：太阳系有八大行星。"


def main() -> None:
    banner("02-3 RunnablePassthrough.assign")

    prompt = ChatPromptTemplate.from_template(
        "根据下面的资料回答问题。\n资料: {context}\n问题: {question}"
    )

    # assign 在输入 dict 上"追加" context 字段，保留原有的 question
    chain = (
        RunnablePassthrough.assign(context=lambda x: fake_retrieve(x["question"]))
        | prompt
        | get_llm()
        | StrOutputParser()
    )
    print(chain.invoke({"question": "太阳系有几颗行星？"}))


if __name__ == "__main__":
    main()
