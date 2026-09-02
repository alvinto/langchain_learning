from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_core.tools import tool  # 导入 @tool 装饰器
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage  # 导入消息类型 Human/AI/System
from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置
"""
05-2 bind_tools 手工 Tool Calling
学到：理解 Tool Calling 的底层原理 —— LLM 返回 tool_calls，你执行后把结果以 ToolMessage 回传，再让 LLM 总结。
（生产中用 LangGraph 的 create_react_agent 自动处理，但先看一遍手动流程很有帮助）
"""

@tool  # 声明 LangChain 工具
def add(a: int, b: int) -> int:  # 定义函数
    """两数相加。"""
    return a + b  # 返回结果


@tool  # 声明 LangChain 工具
def multiply(a: int, b: int) -> int:  # 定义函数
    """两数相乘。"""
    return a * b  # 返回结果


TOOLS = {"add": add, "multiply": multiply}  # 赋值给 TOOLS


def main() -> None:  # demo 入口函数
    banner("05-2 bind_tools (manual loop)")  # 打印章节标题分隔条
    llm_with_tools = get_llm(temperature=0).bind_tools(list(TOOLS.values()))  # 获取 ChatOpenAI 兼容 LLM

    # 增加系统提示，强制多步工具推理
    messages = [  # 赋值给 messages
        SystemMessage("你必须分步完成数学计算，拿到工具返回结果后，检查是否还有计算步骤未完成；只要还有运算就要继续调用工具，全部计算结束后再输出答案，不能中途停止。"),  # 构造系统消息
        HumanMessage("先算 3 + 4，再把结果乘以 5，两步都要执行")  # 构造用户消息
    ]  # 闭合括号/元组/字典
    ai = llm_with_tools.invoke(messages)  # 同步调用链/图

    # 改用while循环，逻辑更清晰
    max_round = 3  # 赋值给 max_round
    round_num = 1  # 赋值给 round_num
    while round_num <= max_round:  # while 循环
        print(f"\n第{round_num}轮 tool_calls: {ai.tool_calls}")  # 打印输出
        if not ai.tool_calls:  # 代码块起始
            break  # 跳出循环
        # 执行所有工具，tool的执行是在框架中，并不是大模型执行的
        for call in ai.tool_calls:  # for 循环
            res = TOOLS[call["name"]].invoke(call["args"])  # 同步调用链/图
            print(f"  执行 {call['name']}({call['args']}) = {res}")  # 打印输出
            messages.append(ToolMessage(content=str(res), tool_call_id=call["id"]))  # 构造工具返回消息
        # 重新请求模型
        ai = llm_with_tools.invoke(messages)  # 同步调用链/图
        round_num += 1  # 执行本行逻辑

    print("\n===== 最终输出 ====")  # 打印输出
    print(ai.content)  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数