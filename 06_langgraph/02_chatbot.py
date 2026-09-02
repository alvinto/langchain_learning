"""
06-2 用 LangGraph 写一个有记忆的 Chatbot
学到：
- MessagesState 内置 messages 字段（自动累加）
- MemorySaver 做 checkpoint，按 thread_id 隔离会话
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langgraph.graph import StateGraph, START, END, MessagesState  # 导入 LangGraph 图编排组件
from langgraph.checkpoint.memory import MemorySaver  # 导入 LangGraph 图编排组件
from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置


llm = get_llm()  # 获取 ChatOpenAI 兼容 LLM


def call_model(state: MessagesState) -> dict:  # 定义函数
    response = llm.invoke(state["messages"])  # 同步调用链/图
    return {"messages": [response]}  # 返回结果


def main() -> None:  # demo 入口函数
    banner("06-2 LangGraph Chatbot with memory")  # 打印章节标题分隔条
    graph = (  # 赋值给 graph
        StateGraph(MessagesState)  # 创建 LangGraph 状态图
        .add_node("model", call_model)  # 向图添加节点
        .add_edge(START, "model")  # 向图添加普通边
        .add_edge("model", END)  # 向图添加普通边
        .compile(checkpointer=MemorySaver())   # ← 关键：开启 checkpoint
    )  # 闭合括号/元组/字典

    cfg = {"configurable": {"thread_id": "thread-1"}}  # 赋值给 cfg
    for q in ["我叫小红", "我喜欢猫", "你还记得我叫什么、喜欢什么吗？"]:  # for 循环
        out = graph.invoke({"messages": [("user", q)]}, config=cfg)  # 同步调用链/图
        print(f"\n用户: {q}\n助手: {out['messages'][-1].content}")  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
