"""
定义两个核心 chain：
1. condense_chain   ：把"用户最新提问 + 历史"改写成一个独立、可检索的问题
2. answer_chain     ：根据检索到的 context 生成回答（带 [n] 引用标记）
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from typing import List  # 导入 typing 类型注解
from langchain_community.vectorstores import FAISS  # 导入 LangChain 社区集成组件
from langchain_core.documents import Document  # 导入 Document 文档类型
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder  # 导入 LangChain 提示词模板
from langchain_core.output_parsers import StrOutputParser  # 导入输出解析器

from _common import get_llm, get_embeddings  # 导入项目共享 LLM/Embedding 配置
from config import INDEX_DIR, TOP_K  # 执行本行逻辑


# ---------- 检索器 ----------
def load_retriever():  # 定义函数
    if not INDEX_DIR.exists():  # 代码块起始
        raise FileNotFoundError(  # 抛出异常
            f"索引不存在：{INDEX_DIR}\n请先运行：python 07_project_knowledge_bot/ingest.py"  # 字符串/template 参数
        )  # 闭合括号/元组/字典
    vs = FAISS.load_local(  # 赋值给 vs
        str(INDEX_DIR), get_embeddings(), allow_dangerous_deserialization=True,  # 获取 Embedding 模型
    )  # 闭合括号/元组/字典
    return vs.as_retriever(search_kwargs={"k": TOP_K})  # 返回结果


# ---------- 1) 改写问题 ----------
_CONDENSE_PROMPT = ChatPromptTemplate.from_messages([  # 由消息列表创建 ChatPromptTemplate
    ("system",  # 链式/容器表达式续行
     "你的任务：根据下面的对话历史，把用户的最新问题改写成一个独立的、不依赖上下文的问题。"  # 字符串/template 参数
     "如果最新问题已经独立，原样返回。只返回改写后的问题，不要任何前缀。"),  # 字符串/template 参数
    MessagesPlaceholder("history"),  # 执行本行逻辑
    ("human", "{question}"),  # 链式/容器表达式续行
])  # 执行本行逻辑

condense_chain = _CONDENSE_PROMPT | get_llm(temperature=0) | StrOutputParser()  # 获取 ChatOpenAI 兼容 LLM


# ---------- 2) 生成答案 ----------
_ANSWER_PROMPT = ChatPromptTemplate.from_messages([  # 由消息列表创建 ChatPromptTemplate
    ("system",  # 链式/容器表达式续行
     "你是一个严谨的知识库助手，仅根据下面的「资料」回答用户问题。\n"  # 字符串/template 参数
     "- 如果资料不足以回答，明确说『资料中未提及』，不要编造\n"  # 字符串/template 参数
     "- 在引用了某段资料的句子末尾标注 [序号]，对应资料块的编号\n"  # 字符串/template 参数
     "\n资料：\n{context}"),  # 字符串/template 参数
    MessagesPlaceholder("history"),  # 执行本行逻辑
    ("human", "{question}"),  # 链式/容器表达式续行
])  # 执行本行逻辑

answer_chain = _ANSWER_PROMPT | get_llm(temperature=0.2) | StrOutputParser()  # 获取 ChatOpenAI 兼容 LLM


def format_context(docs: List[Document]) -> str:  # 定义函数
    parts = []  # 赋值给 parts
    for i, d in enumerate(docs, 1):  # for 循环
        src = d.metadata.get("source", "?")  # 赋值给 src
        parts.append(f"[{i}] (来源: {Path(src).name})\n{d.page_content}")  # 执行本行逻辑
    return "\n\n".join(parts)  # 返回结果
