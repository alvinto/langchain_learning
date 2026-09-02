"""
个人知识库问答机器人 · 命令行入口

用 LangGraph 编排：
  START → condense（改写问题） → retrieve（向量检索） → answer（生成回答） → END
全程通过 messages 字段维护多轮对话，按 thread_id 隔离会话。

直接运行：
    python 07_project_knowledge_bot/app.py
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
import uuid  # 导入 uuid 生成唯一 ID
import operator  # 导入 operator 标准库
from pathlib import Path  # 导入 Path 处理路径
from typing import TypedDict, List, Annotated  # 导入 typing 类型注解
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_core.documents import Document  # 导入 Document 文档类型
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage  # 导入消息类型 Human/AI/System
from langgraph.graph import StateGraph, START, END  # 导入 LangGraph 图编排组件
from langgraph.checkpoint.memory import MemorySaver  # 导入 LangGraph 图编排组件

from chains import condense_chain, answer_chain, load_retriever, format_context  # 执行本行逻辑


class State(TypedDict):  # 定义类
    # Annotated + operator.add 让 messages 字段自动累加（reducer 模式）
    messages: Annotated[List[BaseMessage], operator.add]  # 执行本行逻辑
    question: str  # 执行本行逻辑
    standalone: str  # 执行本行逻辑
    docs: List[Document]  # 执行本行逻辑
    context: str  # 执行本行逻辑
    answer: str  # 执行本行逻辑


retriever = load_retriever()  # 赋值给 retriever


def node_condense(state: State) -> dict:  # 定义函数
    history = state.get("messages") or []  # 赋值给 history
    if not history:  # 代码块起始
        return {"standalone": state["question"]}      # 第一轮不需改写
    standalone = condense_chain.invoke({  # 同步调用链/图
        "history": history,  # 字符串/template 参数
        "question": state["question"],  # 字符串/template 参数
    })  # 执行本行逻辑
    return {"standalone": standalone}  # 返回结果


def node_retrieve(state: State) -> dict:  # 定义函数
    docs = retriever.invoke(state["standalone"])  # 同步调用链/图
    return {"docs": docs, "context": format_context(docs)}  # 返回结果


def node_answer(state: State) -> dict:  # 定义函数
    answer = answer_chain.invoke({  # 同步调用链/图
        "history": state.get("messages") or [],  # 字符串/template 参数
        "question": state["question"],  # 字符串/template 参数
        "context": state["context"],  # 字符串/template 参数
    })  # 执行本行逻辑
    return {  # 返回结果
        "answer": answer,  # 字符串/template 参数
        "messages": [HumanMessage(state["question"]), AIMessage(answer)],  # 构造用户消息
    }  # 闭合括号/元组/字典


def build_graph():  # 定义函数
    return (  # 返回结果
        StateGraph(State)  # 创建 LangGraph 状态图
        .add_node("condense", node_condense)  # 向图添加节点
        .add_node("retrieve", node_retrieve)  # 向图添加节点
        .add_node("answer", node_answer)  # 向图添加节点
        .add_edge(START, "condense")  # 向图添加普通边
        .add_edge("condense", "retrieve")  # 向图添加普通边
        .add_edge("retrieve", "answer")  # 向图添加普通边
        .add_edge("answer", END)  # 向图添加普通边
        .compile(checkpointer=MemorySaver())  # 创建内存 Checkpointer
    )  # 闭合括号/元组/字典


def main() -> None:  # demo 入口函数
    print("=" * 60)  # 打印输出
    print("  个人知识库问答机器人  (/quit 退出, /new 开新会话)")  # 打印输出
    print("=" * 60)  # 打印输出

    graph = build_graph()  # 赋值给 graph
    thread_id = str(uuid.uuid4())[:8]  # 赋值给 thread_id
    cfg = {"configurable": {"thread_id": thread_id}}  # 赋值给 cfg
    print(f"[会话: {thread_id}]")  # 打印输出

    while True:  # while 循环
        try:  # 代码块起始
            q = input("\n你: ").strip()  # 赋值给 q
        except (EOFError, KeyboardInterrupt):  # 捕获异常
            print()  # 打印输出
            break  # 跳出循环
        if not q:  # 代码块起始
            continue  # 跳过本次循环
        if q in ("/quit", "/exit"):  # 代码块起始
            break  # 跳出循环
        if q == "/new":  # 代码块起始
            thread_id = str(uuid.uuid4())[:8]  # 赋值给 thread_id
            cfg = {"configurable": {"thread_id": thread_id}}  # 赋值给 cfg
            print(f"[已开启新会话: {thread_id}]")  # 打印输出
            continue  # 跳过本次循环

        out = graph.invoke({"question": q}, config=cfg)  # 同步调用链/图
        print(f"\n助手: {out['answer']}")  # 打印输出
        print("\n--- 引用 ---")  # 打印输出
        for i, d in enumerate(out["docs"], 1):  # for 循环
            src = Path(d.metadata.get("source", "?")).name  # 赋值给 src
            preview = d.page_content[:60].replace("\n", " ")  # 赋值给 preview
            print(f"  [{i}] {src}: {preview}…")  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
