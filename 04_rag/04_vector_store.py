"""
04-4 向量库（FAISS）
学到：把 chunk + 向量存进 FAISS，再做相似度检索。
FAISS 不需要外部服务，本地一个文件夹就能跑。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from _common import get_embeddings, banner


INDEX_DIR = Path(__file__).parent / "_faiss_index"


def build_index() -> FAISS:
    docs = TextLoader(
        str(Path(__file__).parent / "data" / "sample.md"),
        encoding="utf-8",
    ).load()
    chunks = RecursiveCharacterTextSplitter(chunk_size=150, chunk_overlap=20).split_documents(docs)
    vs = FAISS.from_documents(chunks, get_embeddings())
    vs.save_local(str(INDEX_DIR))
    return vs


def main() -> None:
    banner("04-4 FAISS Vector Store")

    if INDEX_DIR.exists():
        print("[载入已有索引]")
        vs = FAISS.load_local(str(INDEX_DIR), get_embeddings(), allow_dangerous_deserialization=True)
    else:
        print("[首次构建索引]")
        vs = build_index()

    query = "LangChain 的核心组件有哪些？"
    print(f"\n查询: {query}\n")
    for i, doc in enumerate(vs.similarity_search(query, k=3), 1):
        print(f"--- 命中 {i} ---")
        print(doc.page_content)


if __name__ == "__main__":
    main()
