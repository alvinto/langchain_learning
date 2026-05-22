"""Researcher 子 Agent —— 每个子问题派一个，自己跑一个 ReAct 循环。

v2 升级：
1. 全程 async（asyncio.gather 并行才有意义）
2. 接受 `progress_cb` 回调，每次 search/read 时实时上报到主图
   → 主图 stream 时 CLI 能打印「[researcher #2] 正在搜：xxx」这种实时反馈
3. 模型分层：研究循环用 smart，最后的 finalize 压缩用 cheap

注：以前 langgraph.prebuilt.create_react_agent，langchain 1.x 起搬到
langchain.agents.create_agent；两套都做了软导入。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _common import get_llm  # noqa: E402

from fetch import afetch_text
from search import asearch
from state import Finding, Source

try:
    from langchain.agents import create_agent  # langchain 1.x
except ImportError:  # pragma: no cover
    from langgraph.prebuilt import create_react_agent as create_agent  # 0.3 兜底


ProgressCallback = Callable[[str], None]


# ============================================================
# Prompt
# ============================================================

_RESEARCHER_PROMPT = """你是一个研究员，负责回答一个具体的子问题。

工作流程：
1. 先用 web_search 搜（中文问题如果你判断英文资料更权威/丰富，可以翻译成英文 query）
2. 看 snippet 判断要不要 read_url 读全文（snippet 通常只有一两句）
3. 必要时换 query 再搜
4. 综合后给答案，必须基于真实搜到的信息，**不要编造**

要求：
- 答案中文，包含具体事实、数字、版本号、日期
- 多个来源时优先权威的（官方文档 > 大公司博客 > 个人博客）
- **最多调用工具 6 次**，足够回答就停
- 答案末尾不要列 sources，外层会自动从工具调用记录里抽

子问题：{sub_question}
"""


class _FindingDraft(BaseModel):
    summary: str = Field(description="对子问题的中文答案，含具体事实")
    sources: list[Source] = Field(
        default_factory=list,
        description="实际搜到/引用过的 url，按 summary 中真正依据的来挑",
    )


_FINALIZE_PROMPT = """根据下面 Agent 的研究过程，输出结构化结论。

要求：
- summary：对子问题的最终中文答案，包含具体事实
- sources：只列 Agent 实际搜到/读到并在 summary 中用上的 url

子问题：{sub_question}

Agent 的工作记录：
{trace}
"""


# ============================================================
# 工具工厂：让工具能访问 progress_cb 又不破坏 @tool 签名
# ============================================================

def _build_tools(progress_cb: ProgressCallback | None):
    """每个 researcher 实例化自己的工具，工具内部闭包持有它的 progress_cb。
    这样并发的多个 researcher 不会串了进度回调。"""

    @tool
    async def web_search(query: str) -> str:
        """搜索互联网。返回最多 5 条结果（url/title/snippet）。
        中文问题用中文 query，英文问题用英文 query。"""
        if progress_cb:
            progress_cb(f"搜索：{query}")
        results = await asearch(query, k=5)
        if not results:
            return "(没有搜到结果，换个 query 试试)"
        return "\n\n".join(
            f"[{i + 1}] {r.title}\n  url: {r.url}\n  snippet: {r.snippet}"
            for i, r in enumerate(results)
        )

    @tool
    async def read_url(url: str) -> str:
        """抓取一个 URL 的正文（最多 8000 字符）。search snippet 不够时用。"""
        if progress_cb:
            progress_cb(f"阅读：{url}")
        return await afetch_text(url, max_chars=8000)

    return [web_search, read_url]


# ============================================================
# 主入口
# ============================================================

async def arun_researcher(
    sub_question: str,
    progress_cb: ProgressCallback | None = None,
    recursion_limit: int = 15,
) -> Finding:
    """对一个子问题跑完整研究循环（异步），返回结构化 Finding。

    progress_cb 是给主图发"我正在干嘛"的回调。注意只能是同步函数（在 async
    工具里同步调用），不阻塞——否则会拖慢整个循环。常见用法是 append 到
    一个 list / 写日志。
    """
    if progress_cb:
        progress_cb(f"开始研究：{sub_question}")

    smart_llm = get_llm(temperature=0, role="smart")
    cheap_llm = get_llm(temperature=0, role="cheap")
    tools = _build_tools(progress_cb)

    agent = create_agent(smart_llm, tools=tools)
    try:
        result = await agent.ainvoke(
            {"messages": [("user", _RESEARCHER_PROMPT.format(sub_question=sub_question))]},
            config={"recursion_limit": recursion_limit},
        )
    except Exception as e:
        if progress_cb:
            progress_cb(f"⚠ 研究失败：{type(e).__name__}: {e}")
        return Finding(
            sub_question=sub_question,
            summary=f"[研究失败] {type(e).__name__}: {e}",
            sources=[],
        )

    trace = _format_trace(result.get("messages", []))
    draft = await _afinalize(sub_question, trace, cheap_llm)

    if progress_cb:
        progress_cb(f"✓ 结论 {len(draft.summary)} 字 · {len(draft.sources)} 引用")

    return Finding(
        sub_question=sub_question,
        summary=draft.summary,
        sources=draft.sources,
    )


# ============================================================
# 同步入口（保留给 simple 模式和 __main__ 自测）
# ============================================================

def run_researcher(sub_question: str, recursion_limit: int = 15) -> Finding:
    """同步包装。"""
    import asyncio

    return asyncio.run(arun_researcher(sub_question, recursion_limit=recursion_limit))


# ============================================================
# Helpers
# ============================================================

async def _afinalize(sub_question: str, trace: str, llm) -> _FindingDraft:
    """让 LLM 把 trace 压缩成结构化 Finding。失败给最小可用回退。

    method="function_calling" 的原因：OpenAI 兼容协议（DeepSeek/Qwen）不支持
    langchain-openai 新版默认的 json_schema 模式。
    """
    try:
        chain = llm.with_structured_output(_FindingDraft, method="function_calling")
        return await chain.ainvoke(
            _FINALIZE_PROMPT.format(sub_question=sub_question, trace=trace)
        )
    except Exception as e:
        return _FindingDraft(
            summary=f"[结构化失败] {type(e).__name__}: {e}\n原始 trace:\n{trace[:1500]}",
            sources=[],
        )


def _format_trace(messages: list[BaseMessage]) -> str:
    """把 Agent 的 messages 压成给 finalize LLM 看的纯文本。"""
    lines: list[str] = []
    for m in messages:
        if isinstance(m, AIMessage):
            if m.tool_calls:
                for c in m.tool_calls:
                    lines.append(f"[tool_call] {c['name']}({c.get('args', {})})")
            if m.content:
                lines.append(f"[ai] {m.content}")
        elif isinstance(m, ToolMessage):
            content = str(m.content)
            if len(content) > 2000:
                content = content[:2000] + " ...(截断)"
            lines.append(f"[tool_result] {content}")
    return "\n".join(lines)


if __name__ == "__main__":
    import asyncio
    import sys

    q = " ".join(sys.argv[1:]) or "LangGraph 的 Send API 是用来做什么的"
    print(f"研究子问题：{q}\n")

    def cb(msg: str) -> None:
        print(f"  · {msg}")

    f = asyncio.run(arun_researcher(q, progress_cb=cb))
    print("\n" + "=" * 60)
    print(f.summary)
    print("\n引用：")
    for s in f.sources:
        print(f"  - {s.title or '(无标题)'}  {s.url}")
