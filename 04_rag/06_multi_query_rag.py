"""
04-6 多查询 RAG（MultiQueryRetriever）
学到：让 LLM 把用户的一个问题改写成多个不同角度的问法，分别去检索后合并去重，召回率更高。
"""
from __future__ import annotations
import sys
import logging
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
# LangChain 1.x 把 MultiQueryRetriever 搬到了 langchain_classic；老版仍在 langchain
try:
    from langchain_classic.retrievers.multi_query import MultiQueryRetriever
except ImportError:
    from langchain.retrievers.multi_query import MultiQueryRetriever

from _common import get_llm, get_embeddings, banner


def main() -> None:
    banner("04-6 MultiQuery RAG")
    # 看到 LLM 改写出的多个 query
    logging.basicConfig()
    logging.getLogger("langchain.retrievers.multi_query").setLevel(logging.INFO)

    docs = TextLoader(
        str(Path(__file__).parent / "data" / "sample.md"),
        encoding="utf-8",
    ).load()
    chunks = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=30).split_documents(docs)
    base_retriever = FAISS.from_documents(chunks, get_embeddings()).as_retriever(search_kwargs={"k": 2})

    multi_retriever = MultiQueryRetriever.from_llm(
        retriever=base_retriever,
        llm=get_llm(temperature=0),
    )

    docs = multi_retriever.invoke("它有哪些主要部分？")
    print(f"\n合并后命中 {len(docs)} 段：")
    for i, d in enumerate(docs, 1):
        print(f"--- {i} ---\n{d.page_content[:120]}\n")


if __name__ == "__main__":
    main()
