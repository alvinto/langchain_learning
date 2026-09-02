"""
04-6 多查询 RAG（MultiQueryRetriever）
学到：让 LLM 把用户的一个问题改写成多个不同角度的问法，分别去检索后合并去重，召回率更高。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
import logging  # 导入 logging 日志
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_community.document_loaders import TextLoader  # 导入 LangChain 社区集成组件
from langchain_community.vectorstores import FAISS  # 导入 LangChain 社区集成组件
from langchain_text_splitters import RecursiveCharacterTextSplitter  # 导入文本切分器
# LangChain 1.x 把 MultiQueryRetriever 搬到了 langchain_classic；老版仍在 langchain
try:  # 代码块起始
    from langchain_classic.retrievers.multi_query import MultiQueryRetriever  # 执行本行逻辑
except ImportError:  # 捕获异常
    from langchain.retrievers.multi_query import MultiQueryRetriever  # 执行本行逻辑

from _common import get_llm, get_embeddings, banner  # 导入项目共享 LLM/Embedding 配置


def main() -> None:  # demo 入口函数
    banner("04-6 MultiQuery RAG")  # 打印章节标题分隔条
    # 看到 LLM 改写出的多个 query
    logging.basicConfig()  # 执行本行逻辑
    logging.getLogger("langchain.retrievers.multi_query").setLevel(logging.INFO)  # 执行本行逻辑

    docs = TextLoader(  # 赋值给 docs
        str(Path(__file__).parent / "data" / "sample.md"),  # 执行本行逻辑
        encoding="utf-8",  # 执行本行逻辑
    ).load()  # 执行本行逻辑
    chunks = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=30).split_documents(docs)  # 赋值给 chunks
    base_retriever = FAISS.from_documents(chunks, get_embeddings()).as_retriever(search_kwargs={"k": 2})  # 获取 Embedding 模型

    multi_retriever = MultiQueryRetriever.from_llm(  # 赋值给 multi_retriever
        retriever=base_retriever,  # 执行本行逻辑
        llm=get_llm(temperature=0),  # 获取 ChatOpenAI 兼容 LLM
    )  # 闭合括号/元组/字典

    docs = multi_retriever.invoke("它有哪些主要部分？")  # 同步调用链/图
    print(docs)  # 打印输出
    print(f"\n合并后命中 {len(docs)} 段：")  # 打印输出
    for i, d in enumerate(docs, 1):  # for 循环
        print(f"--- {i} ---\n{d.page_content[:120]}\n")  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
