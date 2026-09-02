"""
06-3 ToolNode + 条件边：手写 ReAct 循环
学到：理解 create_react_agent 内部其实就是 model ↔ tools 两个节点 + 条件边。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_core.tools import tool  # 导入 @tool 装饰器
from langgraph.graph import StateGraph, START, END, MessagesState  # 导入 LangGraph 图编排组件
from langgraph.prebuilt import ToolNode, tools_condition  # 导入 LangGraph 图编排组件
from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置


@tool  # 声明 LangChain 工具
def add(a: int, b: int) -> int:  # 定义函数
    """两数相加"""
    return a + b  # 返回结果


@tool  # 声明 LangChain 工具
def square(x: int) -> int:  # 定义函数
    """求平方"""
    return x * x  # 返回结果


tools = [add, square]  # 赋值给 tools
llm = get_llm(temperature=0).bind_tools(tools)  # 获取 ChatOpenAI 兼容 LLM


def call_model(state: MessagesState) -> dict:  # 定义函数
    return {"messages": [llm.invoke(state["messages"])]}  # 同步调用链/图


def main() -> None:  # demo 入口函数
    banner("06-3 ToolNode + tools_condition")  # 打印章节标题分隔条
    graph = (  # 赋值给 graph
        StateGraph(MessagesState)  # 创建 LangGraph 状态图
        .add_node("model", call_model)  # 向图添加节点
        .add_node("tools", ToolNode(tools))  # 创建工具执行节点
        .add_edge(START, "model")  # 向图添加普通边
        # 条件边：如果 model 返回了 tool_calls 就去 tools 节点，否则结束
        .add_conditional_edges("model", tools_condition, {"tools": "tools", END: END})  # 根据 tool_calls 路由的条件函数
        .add_edge("tools", "model")  # 工具执行完回到 model 总结
        .compile()  # 编译图为可执行应用
    )  # 闭合括号/元组/字典

    out = graph.invoke({"messages": [("user", "把 (3+4) 平方")]})  # 同步调用链/图
    for m in out["messages"]:  # for 循环
        print(f"[{m.type}] {m.content or m.tool_calls if hasattr(m, 'tool_calls') else m.content}")  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
