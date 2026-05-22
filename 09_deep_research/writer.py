"""Writer：把所有 Finding 合成一篇带引用的 Markdown 报告。

v2 升级：
- 改 async（主图整体 async 化）
- 用 get_llm(role="writer")，让写作专用模型来写最后这段（质量优先）
- prompt 强化引用规范，避免 LLM 编号错位

为什么不让 LLM 自己编号引用？
LLM 给的引用经常错位（说 [3] 实际指向第 5 个 url）。先把 url 去重编号
固定下来，再把 (id, url) 表喂进 prompt 让它填 [^id]，准确率高很多。
"""
from __future__ import annotations

import sys
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _common import get_llm  # noqa: E402

from state import Finding


_WRITER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是一位研究报告撰写专家。基于研究员们对各子问题的回答，写一篇结构清晰、"
            "可读性强的中文研究报告（Markdown 格式）。\n\n"
            "硬性要求：\n"
            "1. 写具体事实时**必须**加引用标注 [^N]，N 是「全部引用」表里的编号\n"
            "2. 报告末尾**必须**有 `## References` 章节，按 [^1] [^2] ... 顺序列出，"
            "每条格式：`[^N]: 标题 — <url>`（只列实际在正文中引用过的）\n"
            "3. 只能用提供的 finding 和 sources，不要编造任何 sources 里没有的事实或 url\n"
            "4. 结构建议：开头一段总览 → 按主题（不一定按 sub_question 顺序）分小节 → 结尾结论\n"
            "5. 中文写作，避免「研究员A 说...」这种元话术，直接陈述事实\n"
            "6. 报告整体不超过 2500 字，重点突出，不要凑字数",
        ),
        (
            "user",
            "# 研究问题\n{question}\n\n"
            "# 研究员产出的各 finding\n{findings}\n\n"
            "# 全部可用引用（去重后编号）\n{sources_table}\n\n"
            "请输出完整 Markdown 报告。",
        ),
    ]
)


async def awrite_report(question: str, findings: list[Finding]) -> str:
    """异步生成报告。"""
    if not findings:
        return (
            f"# {question}\n\n"
            "_本次研究未能获取到任何有效信息（可能是网络/搜索后端全部失败）。_\n"
        )

    sources_table, url_to_id = _build_source_table(findings)
    findings_block = _format_findings(findings, url_to_id)

    llm = get_llm(temperature=0.3, role="writer")
    chain = _WRITER_PROMPT | llm
    msg = await chain.ainvoke(
        {
            "question": question,
            "findings": findings_block,
            "sources_table": sources_table or "(无)",
        }
    )
    return msg.content if hasattr(msg, "content") else str(msg)


# 兼容旧调用方
def write_report(question: str, findings: list[Finding]) -> str:
    import asyncio

    return asyncio.run(awrite_report(question, findings))


# ============================================================
# Helpers
# ============================================================

def _build_source_table(findings: list[Finding]) -> tuple[str, dict[str, int]]:
    """所有 finding 里的 url 去重 + 编号。返回 (展示用表格, url→id 字典)。"""
    url_to_id: dict[str, int] = {}
    rows: list[str] = []
    for f in findings:
        for s in f.sources:
            if not s.url or s.url in url_to_id:
                continue
            idx = len(url_to_id) + 1
            url_to_id[s.url] = idx
            rows.append(f"[^{idx}] {s.title or '(无标题)'} — {s.url}")
    return "\n".join(rows), url_to_id


def _format_findings(findings: list[Finding], url_to_id: dict[str, int]) -> str:
    blocks: list[str] = []
    for f in findings:
        if f.sources:
            tags = ", ".join(
                f"[^{url_to_id[s.url]}]"
                for s in f.sources
                if s.url and s.url in url_to_id
            )
        else:
            tags = "(无引用)"
        blocks.append(
            f"## 子问题：{f.sub_question}\n"
            f"答案：{f.summary}\n"
            f"涉及引用：{tags}"
        )
    return "\n\n---\n\n".join(blocks)


if __name__ == "__main__":
    import asyncio

    from state import Source

    demo = [
        Finding(
            sub_question="LangGraph 是什么",
            summary="LangGraph 是 LangChain 团队推出的状态图框架，用于构建可控的多步 Agent。",
            sources=[Source(url="https://langchain-ai.github.io/langgraph/", title="LangGraph Docs")],
        ),
        Finding(
            sub_question="Send API 的作用",
            summary="Send API 用于在节点之间动态派发任务，支持 fan-out 并行执行。",
            sources=[Source(url="https://langchain-ai.github.io/langgraph/concepts/low_level/", title="LangGraph Low-Level")],
        ),
    ]
    print(asyncio.run(awrite_report("LangGraph 的核心概念", demo)))
