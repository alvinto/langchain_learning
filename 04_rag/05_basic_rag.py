"""
04-5 基础 RAG 链
学到：把"检索 + 拼 prompt + 调 LLM"用 LCEL 组装成一条链，端到端问答。
经典套路：retriever → context → prompt → llm → parser
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_community.document_loaders import TextLoader  # 导入 LangChain 社区集成组件
from langchain_community.vectorstores import FAISS  # 导入 LangChain 社区集成组件
from langchain_text_splitters import RecursiveCharacterTextSplitter  # 导入文本切分器
from langchain_core.prompts import ChatPromptTemplate  # 导入 LangChain 提示词模板
from langchain_core.output_parsers import StrOutputParser  # 导入输出解析器
from langchain_core.runnables import RunnablePassthrough  # 导入 LCEL Runnable 组件
from _common import get_llm, get_embeddings, banner  # 导入项目共享 LLM/Embedding 配置


def build_retriever():  # 定义函数
    docs = TextLoader(  # 赋值给 docs
        str(Path(__file__).parent / "data" / "sample.md"),  # 执行本行逻辑
        encoding="utf-8",  # 执行本行逻辑
    ).load()  # 执行本行逻辑
    chunks = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=30).split_documents(docs)  # 赋值给 chunks
    vs = FAISS.from_documents(chunks, get_embeddings())  # 获取 Embedding 模型
    return vs.as_retriever(search_kwargs={"k": 3})  # 返回结果


def format_docs(docs) -> str:  # 定义函数
    return "\n\n".join(d.page_content for d in docs)  # 返回结果


def main() -> None:  # demo 入口函数
    banner("04-5 Basic RAG")  # 打印章节标题分隔条
    retriever = build_retriever()  # 赋值给 retriever

    prompt = ChatPromptTemplate.from_template(  # 由模板创建 ChatPromptTemplate
        """你是一个严谨的助手，仅根据下面的"资料"回答问题。
若资料不足，明确说"资料中没有提到"，不要编造。

资料:
{context}

问题: {question}
"""
    )  # 闭合括号/元组/字典

    rag_chain = (  # 赋值给 rag_chain
        {  # 执行本行逻辑
            "context": retriever | format_docs,  # 字符串/template 参数
            "question": RunnablePassthrough(),  # 创建透传 Runnable
        }  # 闭合括号/元组/字典
        | prompt  # 执行本行逻辑
        | get_llm()  # 获取 ChatOpenAI 兼容 LLM
        | StrOutputParser()  # 创建字符串输出解析器
    )  # 闭合括号/元组/字典

    for q in [  # for 循环
        "LangChain 的核心组件有哪些？",  # 字符串/template 参数
        "LangGraph 和 LangChain 是什么关系？",  # 字符串/template 参数
        "LangChain 创始人是谁？",  # 资料里没有，看模型会不会幻觉
    ]:  # 代码块起始
        print(f"\n问: {q}\n答: {rag_chain.invoke(q)}")  # 同步调用链/图


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
