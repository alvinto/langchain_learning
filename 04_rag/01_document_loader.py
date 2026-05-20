"""
04-1 文档加载器
学到：怎么把外部文件/网页变成 Document 列表（page_content + metadata）。
常见 Loader：TextLoader / PyPDFLoader / WebBaseLoader / DirectoryLoader。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_community.document_loaders import TextLoader, DirectoryLoader
from _common import banner


def main() -> None:
    banner("04-1 Document Loader")
    data_dir = Path(__file__).parent / "data"

    # 单个文件
    docs = TextLoader(str(data_dir / "sample.md"), encoding="utf-8").load()
    print(f"加载 {len(docs)} 个文档")
    print(f"第一段前 80 字: {docs[0].page_content[:80]}")
    print(f"元信息: {docs[0].metadata}")

    # 整个目录（按 glob 匹配）
    print("\n>> DirectoryLoader 加载目录：")
    all_docs = DirectoryLoader(
        str(data_dir),
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    ).load()
    for d in all_docs:
        print(f"- {d.metadata.get('source')} ({len(d.page_content)} 字)")


if __name__ == "__main__":
    main()
