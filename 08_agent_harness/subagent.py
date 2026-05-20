"""
子 Agent 派发：让主 Agent 能够 spawn 一个独立的子 Agent 去做"探查类"任务。

为什么要有子 Agent？
- 隔离上下文：子 Agent 跑完只把"最终答案"汇报给主 Agent，
  避免大量中间工具结果污染主上下文（这是 Claude Code Explore agent 的核心思想）
- 工具白名单：子 Agent 只能用只读工具，降低风险
- 可并行（本示例为简化只做串行；想并行可以用 asyncio.gather）
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from tools import grep, list_dir, read_file

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _common import get_llm  # noqa: E402


SUBAGENT_TOOLS = [read_file, list_dir, grep]
SUBAGENT_SYSTEM = (
    "你是一个只读探查子 Agent。你只能读文件、列目录、grep。"
    "完成调查后，用一段简洁中文给出结论，不要写代码、不要修改任何东西。"
    "最多 8 轮工具调用。"
)


class SpawnSubagentArgs(BaseModel):
    task: str = Field(..., description="要委派给子 Agent 的具体调查任务，越具体越好")


@tool("spawn_subagent", args_schema=SpawnSubagentArgs)
def spawn_subagent(task: str) -> str:
    """派发一个只读探查子 Agent 去 workspace 里调查问题，返回它的最终结论。

    适用场景：需要在多个文件里找东西、确认某段代码是否存在、统计某类信息——
    这些操作会产生大量中间工具结果，子 Agent 帮你消化掉，主 Agent 只看结论。
    """
    llm = get_llm(temperature=0.0).bind_tools(SUBAGENT_TOOLS)
    tool_map = {t.name: t for t in SUBAGENT_TOOLS}

    messages = [SystemMessage(content=SUBAGENT_SYSTEM), HumanMessage(content=task)]

    for _ in range(8):
        ai = llm.invoke(messages)
        messages.append(ai)
        if not getattr(ai, "tool_calls", None):
            return ai.content or "(子 Agent 没有返回内容)"
        for call in ai.tool_calls:
            t = tool_map.get(call["name"])
            if t is None:
                result = f"[error] 未知工具 {call['name']}"
            else:
                try:
                    result = t.invoke(call["args"])
                except Exception as e:
                    result = f"[error] {e}"
            from langchain_core.messages import ToolMessage
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))

    return "[子 Agent 用完 8 轮预算仍未给出结论，请缩小任务范围重试]"
