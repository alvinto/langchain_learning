"""
04-1 文档加载器
学到：怎么把外部文件/网页变成 Document 列表（page_content + metadata）。
常见 Loader：TextLoader / PyPDFLoader / WebBaseLoader / DirectoryLoader。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_community.document_loaders import TextLoader, DirectoryLoader  # 导入 LangChain 社区集成组件
from _common import banner  # 导入项目共享 LLM/Embedding 配置


def main() -> None:  # demo 入口函数
    banner("04-1 Document Loader")  # 打印章节标题分隔条
    data_dir = Path(__file__).parent / "data"  # 赋值给 data_dir

    # 单个文件
    docs = TextLoader(str(data_dir / "sample.md"), encoding="utf-8").load()  # 赋值给 docs
    print(f"加载 {len(docs)} 个文档")  # 打印输出
    print(f"第一段前 80 字: {docs[0].page_content[:80]}")  # 打印输出
    print(f"元信息: {docs[0].metadata}")  # 打印输出

    # 整个目录（按 glob 匹配）
    print("\n>> DirectoryLoader 加载目录：")  # 打印输出
    all_docs = DirectoryLoader(  # 赋值给 all_docs
        str(data_dir),  # 执行本行逻辑
        glob="**/*.md",  # 执行本行逻辑
        loader_cls=TextLoader,  # 执行本行逻辑
        loader_kwargs={"encoding": "utf-8"},  # 执行本行逻辑
    ).load()  # 执行本行逻辑
    for d in all_docs:  # for 循环
        print(f"- {d.metadata.get('source')} ({len(d.page_content)} 字)")  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
