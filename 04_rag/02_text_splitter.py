"""
04-2 文本切分
学到：长文档要切成小块（chunk）才能塞进 prompt。
RecursiveCharacterTextSplitter 是最常用的：按 \\n\\n / \\n / 空格 / 字符 递归切。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_community.document_loaders import TextLoader  # 导入 LangChain 社区集成组件
from langchain_text_splitters import RecursiveCharacterTextSplitter  # 导入文本切分器
from _common import banner  # 导入项目共享 LLM/Embedding 配置


def main() -> None:  # demo 入口函数
    banner("04-2 Text Splitter")  # 打印章节标题分隔条
    docs = TextLoader(  # 赋值给 docs
        str(Path(__file__).parent / "data" / "sample.md"),  # 执行本行逻辑
        encoding="utf-8",  # 执行本行逻辑
    ).load()  # 执行本行逻辑

    splitter = RecursiveCharacterTextSplitter(  # 赋值给 splitter
        chunk_size=120,        # 每块字符数
        chunk_overlap=20,      # 块之间的重叠（防止关键句被切断）
        separators=["\n\n", "\n", "。", "，", " ", ""],  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    chunks = splitter.split_documents(docs)  # 赋值给 chunks
    print(f"切分出 {len(chunks)} 块\n")  # 打印输出
    for i, c in enumerate(chunks, 1):  # for 循环
        print(f"--- chunk {i} ({len(c.page_content)} 字) ---")  # 打印输出
        print(c.page_content)  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
