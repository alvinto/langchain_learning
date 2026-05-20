"""
04-2 文本切分
学到：长文档要切成小块（chunk）才能塞进 prompt。
RecursiveCharacterTextSplitter 是最常用的：按 \\n\\n / \\n / 空格 / 字符 递归切。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from _common import banner


def main() -> None:
    banner("04-2 Text Splitter")
    docs = TextLoader(
        str(Path(__file__).parent / "data" / "sample.md"),
        encoding="utf-8",
    ).load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=120,        # 每块字符数
        chunk_overlap=20,      # 块之间的重叠（防止关键句被切断）
        separators=["\n\n", "\n", "。", "，", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    print(f"切分出 {len(chunks)} 块\n")
    for i, c in enumerate(chunks, 1):
        print(f"--- chunk {i} ({len(c.page_content)} 字) ---")
        print(c.page_content)


if __name__ == "__main__":
    main()
