"""
06-4 人在回路（Human-in-the-loop）
学到：用 interrupt_before 让图在敏感节点暂停，等用户确认后再继续。
场景：Agent 准备调用"删除数据库"工具时，先停下来让人审批。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_core.tools import tool  # 导入 @tool 装饰器
from langgraph.graph import StateGraph, START, END, MessagesState  # 导入 LangGraph 图编排组件
from langgraph.prebuilt import ToolNode, tools_condition  # 导入 LangGraph 图编排组件
from langgraph.checkpoint.memory import MemorySaver  # 导入 LangGraph 图编排组件
from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置


@tool  # 声明 LangChain 工具
def delete_user(user_id: str) -> str:  # 定义函数
    """删除指定用户（危险操作）。"""
    return f"用户 {user_id} 已删除"  # 返回结果


tools = [delete_user]  # 赋值给 tools
llm = get_llm(temperature=0).bind_tools(tools)  # 获取 ChatOpenAI 兼容 LLM


def call_model(state: MessagesState) -> dict:  # 定义函数
    return {"messages": [llm.invoke(state["messages"])]}  # 同步调用链/图


def main() -> None:  # demo 入口函数
    banner("06-4 Human-in-the-loop")  # 打印章节标题分隔条
    graph = (  # 赋值给 graph
        StateGraph(MessagesState)  # 创建 LangGraph 状态图
        .add_node("model", call_model)  # 向图添加节点
        .add_node("tools", ToolNode(tools))  # 创建工具执行节点
        .add_edge(START, "model")  # 向图添加普通边
        .add_conditional_edges("model", tools_condition, {"tools": "tools", END: END})  # 根据 tool_calls 路由的条件函数
        .add_edge("tools", "model")  # 向图添加普通边
        .compile(  # 编译图为可执行应用
            checkpointer=MemorySaver(),  # 创建内存 Checkpointer
            interrupt_before=["tools"],   # ← 关键：在工具节点前暂停
        )  # 闭合括号/元组/字典
    )  # 闭合括号/元组/字典

    cfg = {"configurable": {"thread_id": "approval-1"}}  # 赋值给 cfg

    # 第一阶段：跑到 tools 之前停下
    state = graph.invoke({"messages": [("user", "请删除用户 u_42")]}, config=cfg)  # 同步调用链/图
    last = state["messages"][-1]  # 赋值给 last
    print("LLM 准备调用:", last.tool_calls)  # 打印输出

    # 模拟人工审批
    answer = input("\n是否批准执行？(y/N): ").strip().lower()  # 赋值给 answer
    if answer != "y":  # 代码块起始
        print("已拒绝，未执行。")  # 打印输出
        return  # 提前返回

    # 继续：传入 None 表示沿用 checkpoint 状态接着走
    state = graph.invoke(None, config=cfg)  # 同步调用链/图
    print("\n执行结果:", state["messages"][-1].content)  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
