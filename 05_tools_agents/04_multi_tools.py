"""
05-4 多工具组合：让 Agent 能上网搜 + 查文档
学到：自定义稍复杂的工具（含错误处理），把 Retriever 包成 Tool 复用 04 章的索引。
"""
from __future__ import annotations
import sys
import urllib.parse
import urllib.request
import json
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.tools import tool

# LangChain 1.x: create_agent 在 langchain.agents；老版叫 create_react_agent 在 langgraph.prebuilt
try:
    from langchain.agents import create_agent as _create_agent
    _PROMPT_KEY = "system_prompt"
except ImportError:
    from langgraph.prebuilt import create_react_agent as _create_agent
    _PROMPT_KEY = "prompt"

from _common import get_llm, get_embeddings, banner


# --- 工具 1：把 04 章的 RAG 检索包成工具 ---
def _build_doc_retriever():
    docs = TextLoader(
        str(Path(__file__).resolve().parents[1] / "04_rag" / "data" / "sample.md"),
        encoding="utf-8",
    ).load()
    chunks = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=30).split_documents(docs)
    return FAISS.from_documents(chunks, get_embeddings()).as_retriever(search_kwargs={"k": 3})


_retriever = None


@tool
def search_langchain_docs(query: str) -> str:
    """在本地 LangChain 文档中检索相关内容。"""
    global _retriever
    if _retriever is None:
        _retriever = _build_doc_retriever()
    docs = _retriever.invoke(query)
    return "\n---\n".join(d.page_content for d in docs)


# --- 工具 2：天气（演示固定值；真实接 API 时记得 try/except） ---
@tool
def get_weather(city: str) -> str:
    """查询城市天气。"""
    fake = {"北京": "晴 22℃", "上海": "多云 24℃", "广州": "雷阵雨 28℃"}
    return fake.get(city, "未知城市")


# --- 工具 3：计算器（用 Python 表达式，注意安全 —— 真实场景不建议这么写） ---
@tool
def calc(expression: str) -> str:
    """计算简单数学表达式，例如 "2*(3+4)"。"""
    try:
        # 仅允许数字与基本运算符，简单防注入
        allowed = set("0123456789+-*/.() ")
        if not all(c in allowed for c in expression):
            return "表达式包含不允许的字符"
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"计算错误: {e}"


def main() -> None:
    banner("05-4 Multi-tool Agent")
    agent = _create_agent(
        model=get_llm(temperature=0),
        tools=[search_langchain_docs, get_weather, calc],
        **{_PROMPT_KEY: (
            "你是一个多功能助手。"
            "涉及 LangChain 知识 → 用 search_langchain_docs；"
            "涉及天气 → 用 get_weather；"
            "涉及数学 → 用 calc。"
        )},
    )

    for q in [
        "LangGraph 和 LangChain 是什么关系？",
        "北京天气怎么样？",
        "(12+8)*5 等于多少？",
    ]:
        print(f"\n>> 用户: {q}")
        out = agent.invoke({"messages": [("user", q)]})
        print(">> 助手:", out["messages"][-1].content)


if __name__ == "__main__":
    main()
