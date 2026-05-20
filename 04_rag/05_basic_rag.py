"""
04-5 基础 RAG 链
学到：把"检索 + 拼 prompt + 调 LLM"用 LCEL 组装成一条链，端到端问答。
经典套路：retriever → context → prompt → llm → parser
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from _common import get_llm, get_embeddings, banner


def build_retriever():
    docs = TextLoader(
        str(Path(__file__).parent / "data" / "sample.md"),
        encoding="utf-8",
    ).load()
    chunks = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=30).split_documents(docs)
    vs = FAISS.from_documents(chunks, get_embeddings())
    return vs.as_retriever(search_kwargs={"k": 3})


def format_docs(docs) -> str:
    return "\n\n".join(d.page_content for d in docs)


def main() -> None:
    banner("04-5 Basic RAG")
    retriever = build_retriever()

    prompt = ChatPromptTemplate.from_template(
        """你是一个严谨的助手，仅根据下面的"资料"回答问题。
若资料不足，明确说"资料中没有提到"，不要编造。

资料:
{context}

问题: {question}
"""
    )

    rag_chain = (
        {
            "context": retriever | format_docs,
            "question": RunnablePassthrough(),
        }
        | prompt
        | get_llm()
        | StrOutputParser()
    )

    for q in [
        "LangChain 的核心组件有哪些？",
        "LangGraph 和 LangChain 是什么关系？",
        "LangChain 创始人是谁？",  # 资料里没有，看模型会不会幻觉
    ]:
        print(f"\n问: {q}\n答: {rag_chain.invoke(q)}")


if __name__ == "__main__":
    main()
