"""
03-2 RunnableWithMessageHistory（推荐）
学到：把任意 Runnable 包一层，自动按 session_id 维护多轮历史。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder  # 导入 LangChain 提示词模板
from langchain_core.chat_history import InMemoryChatMessageHistory  # 执行本行逻辑
from langchain_core.runnables.history import RunnableWithMessageHistory  # 执行本行逻辑
from langchain_core.output_parsers import StrOutputParser  # 导入输出解析器
from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置


# 用全局 dict 模拟 session 存储（生产环境换成 Redis / 数据库）
_store: dict = {}  # 赋值给 dict


def get_session_history(session_id: str) -> InMemoryChatMessageHistory:  # 定义函数
    if session_id not in _store:  # 代码块起始
        _store[session_id] = InMemoryChatMessageHistory()  # 赋值给 _store[session_id]
    return _store[session_id]  # 返回结果


def main() -> None:  # demo 入口函数
    banner("03-2 RunnableWithMessageHistory")  # 打印章节标题分隔条

    prompt = ChatPromptTemplate.from_messages([  # 由消息列表创建 ChatPromptTemplate
        ("system", "你是一个友好的助手，记住用户告诉过你的事情。"),  # 链式/容器表达式续行
        MessagesPlaceholder("history"),  # 执行本行逻辑
        ("human", "{input}"),  # 链式/容器表达式续行
    ])  # 执行本行逻辑
    chain = prompt | get_llm() | StrOutputParser()  # 获取 ChatOpenAI 兼容 LLM

    chatbot = RunnableWithMessageHistory(  # 赋值给 chatbot
        chain,  # 序列/元组元素
        get_session_history,  # 序列/元组元素
        input_messages_key="input",  # 执行本行逻辑
        history_messages_key="history",  # 执行本行逻辑
    )  # 闭合括号/元组/字典

    cfg = {"configurable": {"session_id": "user-zz"}}  # 赋值给 cfg

    for q in [  # for 循环
        "我叫张三，今年 28 岁",  # 字符串/template 参数
        "我喜欢吃火锅",  # 字符串/template 参数
        "你还记得我叫什么、喜欢吃什么吗？",  # 字符串/template 参数
    ]:  # 代码块起始
        print(f"\n用户: {q}")  # 打印输出
        print("助手:", chatbot.invoke({"input": q}, config=cfg))  # 同步调用链/图


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
