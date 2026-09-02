"""
子 Agent 派发：让主 Agent 能够 spawn 一个独立的子 Agent 去做"探查类"任务。

为什么要有子 Agent？
- 隔离上下文：子 Agent 跑完只把"最终答案"汇报给主 Agent，
  避免大量中间工具结果污染主上下文（这是 Claude Code Explore agent 的核心思想）
- 工具白名单：子 Agent 只能用只读工具，降低风险
- 可并行（本示例为简化只做串行；想并行可以用 asyncio.gather）
"""
from __future__ import annotations  # 延迟注解

from langchain_core.messages import HumanMessage, SystemMessage  # 子 Agent 消息类型
from langchain_core.tools import tool  # 把 spawn_subagent 注册为主 Agent 工具
from pydantic import BaseModel, Field  # 工具参数 schema

from tools import grep, list_dir, read_file  # 子 Agent 白名单工具

import sys  # 修改 import 路径
from pathlib import Path  # 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 项目根
from _common import get_llm  # noqa: E402  # LLM 工厂


SUBAGENT_TOOLS = [read_file, list_dir, grep]  # 子 Agent 可用只读工具列表
SUBAGENT_SYSTEM = (  # 子 Agent 系统提示
    "你是一个只读探查子 Agent。你只能读文件、列目录、grep。"  # 字符串/template 参数
    "完成调查后，用一段简洁中文给出结论，不要写代码、不要修改任何东西。"  # 字符串/template 参数
    "最多 8 轮工具调用。"  # 字符串/template 参数
)  # 闭合括号/元组/字典


class SpawnSubagentArgs(BaseModel):  # 定义类
    """spawn_subagent 工具的参数 schema。"""
    task: str = Field(..., description="要委派给子 Agent 的具体调查任务，越具体越好")  # 赋值给 str


@tool("spawn_subagent", args_schema=SpawnSubagentArgs)  # 声明 LangChain 工具
def spawn_subagent(task: str) -> str:  # 定义函数
    """派发一个只读探查子 Agent 去 workspace 里调查问题，返回它的最终结论。

    适用场景：需要在多个文件里找东西、确认某段代码是否存在、统计某类信息——
    这些操作会产生大量中间工具结果，子 Agent 帮你消化掉，主 Agent 只看结论。
    """
    llm = get_llm(temperature=0.0).bind_tools(SUBAGENT_TOOLS)  # 绑定只读工具的 LLM
    tool_map = {t.name: t for t in SUBAGENT_TOOLS}  # 工具名 → 可调用对象

    messages = [SystemMessage(content=SUBAGENT_SYSTEM), HumanMessage(content=task)]  # 子会话初始消息

    for _ in range(8):  # 最多 8 轮 ReAct 循环
        ai = llm.invoke(messages)  # 子 LLM 推理一步
        messages.append(ai)  # 追加 AI 消息到子上下文
        if not getattr(ai, "tool_calls", None):  # 无 tool_calls 表示给出最终答案
            return ai.content or "(子 Agent 没有返回内容)"  # 返回结论文本
        for call in ai.tool_calls:  # 执行每个 tool_call
            t = tool_map.get(call["name"])  # 查工具
            if t is None:  # 未知工具
                result = f"[error] 未知工具 {call['name']}"  # 错误文案
            else:  # else 分支
                try:  # 代码块起始
                    result = t.invoke(call["args"])  # 同步调用工具
                except Exception as e:  # 捕获异常
                    result = f"[error] {e}"  # 捕获异常为字符串
            from langchain_core.messages import ToolMessage  # 延迟 import 避免循环依赖
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))  # 回灌工具结果

    return "[子 Agent 用完 8 轮预算仍未给出结论，请缩小任务范围重试]"  # 预算耗尽
