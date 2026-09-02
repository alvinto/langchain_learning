"""
05-3 ReAct Agent（推荐）
学到：用 langgraph.prebuilt.create_react_agent 一行代码搞定"思考-调用工具-观察-再思考"循环。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_core.tools import tool  # 导入 @tool 装饰器

# LangChain 1.x: create_agent 在 langchain.agents；老版叫 create_react_agent 在 langgraph.prebuilt
try:  # 代码块起始
    from langchain.agents import create_agent as _create_agent  # 执行本行逻辑
    _PROMPT_KEY = "system_prompt"  # 赋值给 _PROMPT_KEY
except ImportError:  # 捕获异常
    from langgraph.prebuilt import create_react_agent as _create_agent  # 导入 LangGraph 图编排组件
    _PROMPT_KEY = "prompt"  # 赋值给 _PROMPT_KEY

from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置


@tool  # 声明 LangChain 工具
def add(a: float, b: float) -> float:  # 定义函数
    """加法"""
    return a + b  # 返回结果


@tool  # 声明 LangChain 工具
def multiply(a: float, b: float) -> float:  # 定义函数
    """乘法"""
    return a * b  # 返回结果


@tool  # 声明 LangChain 工具
def get_user_age(name: str) -> int:  # 定义函数
    """根据姓名查询年龄（演示用）"""
    db = {"张三": 28, "李四": 35, "王五": 19}  # 赋值给 db
    return db.get(name, -1)  # 返回结果


def main() -> None:  # demo 入口函数
    banner("05-3 ReAct Agent")  # 打印章节标题分隔条
    agent = _create_agent(  # 赋值给 agent
        model=get_llm(temperature=0),  # 获取 ChatOpenAI 兼容 LLM
        tools=[add, multiply, get_user_age],  # 执行本行逻辑
        **{_PROMPT_KEY: "你是一个会用工具的助手。需要计算或查询时，必须调用工具。"},  # 执行本行逻辑
    )  # 闭合括号/元组/字典

    out = agent.invoke({"messages": [  # 同步调用链/图
        ("user", "张三和李四的年龄之和是多少？再乘以 2 是多少？")  # 链式/容器表达式续行
    ]})  # 执行本行逻辑

    # out["messages"] 包含整段对话（含 tool 调用过程）
    for m in out["messages"]:  # for 循环
        # 不同消息类型用不同格式
        role = m.type  # 赋值给 role
        content = (m.content or "").strip()  # 赋值给 content
        tool_calls = getattr(m, "tool_calls", None)  # 赋值给 tool_calls
        if tool_calls:  # 代码块起始
            print(f"[{role}] -> tool_calls: {tool_calls}")  # 打印输出
        elif content:  # elif 分支
            print(f"[{role}] {content}")  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
