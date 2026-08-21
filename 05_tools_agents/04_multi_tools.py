"""
05-4 多工具组合：让 Agent 能上网搜 + 查文档
学到：自定义稍复杂的工具（含错误处理），把 Retriever 包成 Tool 复用 04 章的索引。
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.tools import tool

# 兼容导入：LangGraph 新版 create_react_agent
try:
    from langgraph.prebuilt import create_react_agent
    _create_agent = create_react_agent
    _PROMPT_KEY = "prompt"
except ImportError:
    from langchain.agents import create_agent
    _create_agent = create_agent
    _PROMPT_KEY = "system_prompt"

from _common import get_llm, get_embeddings, banner


# --- 工具1：RAG本地文档检索 ---
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
    """在本地LangChain相关文档检索资料，仅当询问框架、Agent、RAG相关知识时使用。"""
    global _retriever
    if _retriever is None:
        _retriever = _build_doc_retriever()
    docs = _retriever.invoke(query)
    return "\n---\n".join(d.page_content for d in docs)

# --- 工具2：天气查询 ---
@tool
def get_weather(city: str) -> str:
    """查询指定城市当日天气，用户询问任意城市气温/天气必须调用此工具。
    参数city：中文城市名称，如北京、上海。
    """
    fake = {"北京": "晴 22℃", "上海": "多云 24℃", "广州": "雷阵雨 28℃"}
    return fake.get(city, "暂无该城市天气数据")

# --- 工具3：数学计算器 ---
@tool
def calc(expression: str) -> str:
    """计算数学四则表达式，用户提问数字、算式、计算类问题必须调用。
    入参expression为纯数字运算字符串，示例 "(12+8)*5"。
    """
    try:
        allowed = set("0123456789+-*/.() ")
        if not all(c in allowed for c in expression):
            return "表达式存在非法字符"
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"计算失败：{str(e)}"


def main() -> None:
    banner("05-4 Multi-tool Agent")
    llm = get_llm(temperature=0)  # 弱模型固定0，消除随机不稳定
    tools = [search_langchain_docs, get_weather, calc]

    # 【重点修复：增强强制系统提示词】
    strong_system_prompt = """
你是严格的工具调用智能助手，遵循铁则：
1. 绝对禁止直接文字回答用户问题，必须先判断是否匹配工具场景，调用对应工具获取结果后再生成答案；
2. 场景匹配规则：
    - 问LangChain/LangGraph/RAG技术文档 → 调用search_langchain_docs
    - 问任意城市天气、温度 → 调用get_weather，参数填城市名
    - 所有数学算式、数字计算 → 调用calc，传入完整表达式
3. 只能输出标准OpenAI工具调用JSON格式，不允许空白回复；
4. 执行完工具拿到返回内容后，再整理自然语言给用户。
"""

    agent = _create_agent(
        model=llm,
        tools=tools,
        **{_PROMPT_KEY: strong_system_prompt}
    )

    test_queries = [
        "北京天气怎么样？",
        "(12+8)*5 等于多少？",
        "LangGraph 和 LangChain 有什么区别？"
    ]
    for q in test_queries:
        print(f"\n>> 用户提问：{q}")
        res = agent.invoke({"messages": [("user", q)]})
        answer = res["messages"][-1].content
        print(f">> 助手回答：{answer}")


if __name__ == "__main__":
    main()
