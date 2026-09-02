"""
05-4 多工具组合：让 Agent 能上网搜 + 查文档
学到：自定义稍复杂的工具（含错误处理），把 Retriever 包成 Tool 复用 04 章的索引。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径

sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_community.document_loaders import TextLoader  # 导入 LangChain 社区集成组件
from langchain_community.vectorstores import FAISS  # 导入 LangChain 社区集成组件
from langchain_text_splitters import RecursiveCharacterTextSplitter  # 导入文本切分器
from langchain_core.tools import tool  # 导入 @tool 装饰器

# 兼容导入：LangGraph 新版 create_react_agent
try:  # 代码块起始
    from langgraph.prebuilt import create_react_agent  # 导入 LangGraph 图编排组件
    _create_agent = create_react_agent  # 赋值给 _create_agent
    _PROMPT_KEY = "prompt"  # 赋值给 _PROMPT_KEY
except ImportError:  # 捕获异常
    from langchain.agents import create_agent  # 执行本行逻辑
    _create_agent = create_agent  # 赋值给 _create_agent
    _PROMPT_KEY = "system_prompt"  # 赋值给 _PROMPT_KEY

from _common import get_llm, get_embeddings, banner  # 导入项目共享 LLM/Embedding 配置


# --- 工具1：RAG本地文档检索 ---
def _build_doc_retriever():  # 定义函数
    docs = TextLoader(  # 赋值给 docs
        str(Path(__file__).resolve().parents[1] / "04_rag" / "data" / "sample.md"),  # 执行本行逻辑
        encoding="utf-8",  # 执行本行逻辑
    ).load()  # 执行本行逻辑
    chunks = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=30).split_documents(docs)  # 赋值给 chunks
    return FAISS.from_documents(chunks, get_embeddings()).as_retriever(search_kwargs={"k": 3})  # 获取 Embedding 模型

_retriever = None  # 赋值给 _retriever

@tool  # 声明 LangChain 工具
def search_langchain_docs(query: str) -> str:  # 定义函数
    """在本地LangChain相关文档检索资料，仅当询问框架、Agent、RAG相关知识时使用。"""
    global _retriever  # 声明全局变量
    if _retriever is None:  # 代码块起始
        _retriever = _build_doc_retriever()  # 赋值给 _retriever
    docs = _retriever.invoke(query)  # 同步调用链/图
    return "\n---\n".join(d.page_content for d in docs)  # 返回结果

# --- 工具2：天气查询 ---
@tool  # 声明 LangChain 工具
def get_weather(city: str) -> str:  # 定义函数
    """查询指定城市当日天气，用户询问任意城市气温/天气必须调用此工具。
    参数city：中文城市名称，如北京、上海。
    """
    fake = {"北京": "晴 22℃", "上海": "多云 24℃", "广州": "雷阵雨 28℃"}  # 赋值给 fake
    return fake.get(city, "暂无该城市天气数据")  # 返回结果

# --- 工具3：数学计算器 ---
@tool  # 声明 LangChain 工具
def calc(expression: str) -> str:  # 定义函数
    """计算数学四则表达式，用户提问数字、算式、计算类问题必须调用。
    入参expression为纯数字运算字符串，示例 "(12+8)*5"。
    """
    try:  # 代码块起始
        allowed = set("0123456789+-*/.() ")  # 赋值给 allowed
        if not all(c in allowed for c in expression):  # for 循环
            return "表达式存在非法字符"  # 返回结果
        return str(eval(expression, {"__builtins__": {}}, {}))  # 返回结果
    except Exception as e:  # 捕获异常
        return f"计算失败：{str(e)}"  # 返回结果


def main() -> None:  # demo 入口函数
    banner("05-4 Multi-tool Agent")  # 打印章节标题分隔条
    llm = get_llm(temperature=0)  # 弱模型固定0，消除随机不稳定
    tools = [search_langchain_docs, get_weather, calc]  # 赋值给 tools

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

    agent = _create_agent(  # 赋值给 agent
        model=llm,  # 执行本行逻辑
        tools=tools,  # 执行本行逻辑
        **{_PROMPT_KEY: strong_system_prompt}  # 执行本行逻辑
    )  # 闭合括号/元组/字典

    test_queries = [  # 赋值给 test_queries
        "北京天气怎么样？",  # 字符串/template 参数
        "(12+8)*5 等于多少？",  # 字符串/template 参数
        "LangGraph 和 LangChain 有什么区别？"  # 字符串/template 参数
    ]  # 闭合括号/元组/字典
    for q in test_queries:  # for 循环
        print(f"\n>> 用户提问：{q}")  # 打印输出
        res = agent.invoke({"messages": [("user", q)]})  # 同步调用链/图
        answer = res["messages"][-1].content  # 赋值给 answer
        print(f">> 助手回答：{answer}")  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
