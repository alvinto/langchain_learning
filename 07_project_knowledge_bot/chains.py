"""
定义两个核心 chain：
1. condense_chain   ：把"用户最新提问 + 历史"改写成一个独立、可检索的问题
2. answer_chain     ：根据检索到的 context 生成回答（带 [n] 引用标记）
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from typing import List
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

from _common import get_llm, get_embeddings
from config import INDEX_DIR, TOP_K


# ---------- 检索器 ----------
def load_retriever():
    if not INDEX_DIR.exists():
        raise FileNotFoundError(
            f"索引不存在：{INDEX_DIR}\n请先运行：python 07_project_knowledge_bot/ingest.py"
        )
    vs = FAISS.load_local(
        str(INDEX_DIR), get_embeddings(), allow_dangerous_deserialization=True,
    )
    return vs.as_retriever(search_kwargs={"k": TOP_K})


# ---------- 1) 改写问题 ----------
_CONDENSE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "你的任务：根据下面的对话历史，把用户的最新问题改写成一个独立的、不依赖上下文的问题。"
     "如果最新问题已经独立，原样返回。只返回改写后的问题，不要任何前缀。"),
    MessagesPlaceholder("history"),
    ("human", "{question}"),
])

condense_chain = _CONDENSE_PROMPT | get_llm(temperature=0) | StrOutputParser()


# ---------- 2) 生成答案 ----------
_ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "你是一个严谨的知识库助手，仅根据下面的「资料」回答用户问题。\n"
     "- 如果资料不足以回答，明确说『资料中未提及』，不要编造\n"
     "- 在引用了某段资料的句子末尾标注 [序号]，对应资料块的编号\n"
     "\n资料：\n{context}"),
    MessagesPlaceholder("history"),
    ("human", "{question}"),
])

answer_chain = _ANSWER_PROMPT | get_llm(temperature=0.2) | StrOutputParser()


def format_context(docs: List[Document]) -> str:
    parts = []
    for i, d in enumerate(docs, 1):
        src = d.metadata.get("source", "?")
        parts.append(f"[{i}] (来源: {Path(src).name})\n{d.page_content}")
    return "\n\n".join(parts)
