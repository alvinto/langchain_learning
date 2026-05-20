"""
02-4 RunnableLambda
学到：把任意 Python 函数包成 Runnable，插进 LCEL 链路里做前/后处理。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from _common import get_llm, banner


def normalize(payload: dict) -> dict:
    """前处理：把输入文本去空白 + 截断。"""
    payload["text"] = payload["text"].strip()[:200]
    return payload


def add_meta(answer: str) -> dict:
    """后处理：在 LLM 回答上附加元数据。"""
    return {"answer": answer, "length": len(answer)}


def main() -> None:
    banner("02-4 RunnableLambda")

    prompt = ChatPromptTemplate.from_template("用一句话总结：{text}")
    chain = (
        RunnableLambda(normalize)
        | prompt
        | get_llm()
        | StrOutputParser()
        | RunnableLambda(add_meta)
    )

    result = chain.invoke({"text": "   LangChain 是一个用于构建 LLM 应用的框架，它把 prompt、模型、工具、记忆、检索等抽象成统一接口。   "})
    print(result)


if __name__ == "__main__":
    main()
