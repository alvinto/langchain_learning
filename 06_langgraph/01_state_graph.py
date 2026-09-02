"""
06-1 StateGraph 入门
学到：LangGraph 的核心是"状态 + 节点 + 边"。
- State：用 TypedDict 定义共享数据结构
- Node：函数 (state) -> 部分 state 更新
- Edge：节点间的连接（含条件边）
- 从start state开始，沿着edge执行每个node，最终到end state结束
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from typing import TypedDict  # 导入 typing 类型注解
from langgraph.graph import StateGraph, START, END  # 导入 LangGraph 图编排组件
from _common import banner  # 导入项目共享 LLM/Embedding 配置


class State(TypedDict):  # 定义类
    text: str  # 执行本行逻辑
    word_count: int  # 执行本行逻辑
    upper: str  # 执行本行逻辑


def count_words(state: State) -> dict:  # 定义函数
    return {"word_count": len(state["text"].split())}  # 返回结果


def upper_case(state: State) -> dict:  # 定义函数
    return {"upper": state["text"].upper()}  # 返回结果


def main() -> None:  # demo 入口函数
    banner("06-1 StateGraph")  # 打印章节标题分隔条
    graph = (  # 赋值给 graph
        StateGraph(State)  # 创建 LangGraph 状态图
        .add_node("count", count_words)  # 向图添加节点
        .add_node("upper", upper_case)  # 向图添加节点
        .add_edge(START, "count")  # 向图添加普通边
        .add_edge("count", "upper")  # 向图添加普通边
        .add_edge("upper", END)  # 向图添加普通边
        .compile()  # 编译图为可执行应用
    )  # 闭合括号/元组/字典

    out = graph.invoke({"text": "hello langgraph world"})  # 同步调用链/图
    print(out)  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
