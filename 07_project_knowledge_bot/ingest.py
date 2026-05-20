"""
数据导入：把 data/ 下的所有 .md/.txt 切片、向量化、存进 FAISS。
重新跑一次会重建索引（覆盖）。
"""
from __future__ import annotations
import sys
import shutil
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

from _common import get_embeddings, banner
from config import DATA_DIR, INDEX_DIR, CHUNK_SIZE, CHUNK_OVERLAP


def load_documents():
    loaders = []
    for pattern in ("**/*.md", "**/*.txt"):
        loaders.append(DirectoryLoader(
            str(DATA_DIR),
            glob=pattern,
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
            show_progress=False,
        ))
    docs = []
    for loader in loaders:
        docs.extend(loader.load())
    return docs


def main() -> None:
    banner("Knowledge Bot · Ingest")

    if not DATA_DIR.exists() or not any(DATA_DIR.iterdir()):
        print(f"[!] {DATA_DIR} 是空的，请先放入 .md / .txt 文件。")
        return

    docs = load_documents()
    print(f"加载 {len(docs)} 个文档")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", "！", "？", "，", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    print(f"切分出 {len(chunks)} 个 chunk")

    if INDEX_DIR.exists():
        shutil.rmtree(INDEX_DIR)

    print("正在向量化并写入 FAISS …")
    vs = FAISS.from_documents(chunks, get_embeddings())
    vs.save_local(str(INDEX_DIR))
    print(f"[√] 索引已保存到 {INDEX_DIR}")


if __name__ == "__main__":
    main()
