"""Writer：把所有 Finding 合成一篇带引用的 Markdown 报告。

v2 升级：
- 改 async（主图整体 async 化）
- 用 get_llm(role="writer")，让写作专用模型来写最后这段（质量优先）
- prompt 强化引用规范，避免 LLM 编号错位

为什么不让 LLM 自己编号引用？
LLM 给的引用经常错位（说 [3] 实际指向第 5 个 url）。先把 url 去重编号
固定下来，再把 (id, url) 表喂进 prompt 让它填 [^id]，准确率高很多。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解

import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径

from langchain_core.prompts import ChatPromptTemplate  # 导入 LangChain 提示词模板

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 执行本行逻辑
from _common import get_llm  # noqa: E402

from state import Finding  # 执行本行逻辑


_WRITER_PROMPT = ChatPromptTemplate.from_messages(  # 由消息列表创建 ChatPromptTemplate
    [  # 链式/容器表达式续行
        (  # 链式/容器表达式续行
            "system",  # 字符串/template 参数
            "你是一位研究报告撰写专家。基于研究员们对各子问题的回答，写一篇结构清晰、"  # 字符串/template 参数
            "可读性强的中文研究报告（Markdown 格式）。\n\n"  # 字符串/template 参数
            "硬性要求：\n"  # 字符串/template 参数
            "1. 写具体事实时**必须**加引用标注 [^N]，N 是「全部引用」表里的编号\n"  # 字符串/template 参数
            "2. 报告末尾**必须**有 `## References` 章节，按 [^1] [^2] ... 顺序列出，"  # 字符串/template 参数
            "每条格式：`[^N]: 标题 — <url>`（只列实际在正文中引用过的）\n"  # 字符串/template 参数
            "3. 只能用提供的 finding 和 sources，不要编造任何 sources 里没有的事实或 url\n"  # 字符串/template 参数
            "4. 结构建议：开头一段总览 → 按主题（不一定按 sub_question 顺序）分小节 → 结尾结论\n"  # 字符串/template 参数
            "5. 中文写作，避免「研究员A 说...」这种元话术，直接陈述事实\n"  # 字符串/template 参数
            "6. 报告整体不超过 2500 字，重点突出，不要凑字数",  # 字符串/template 参数
        ),  # 闭合括号/元组/字典
        (  # 链式/容器表达式续行
            "user",  # 字符串/template 参数
            "# 研究问题\n{question}\n\n"  # 字符串/template 参数
            "# 研究员产出的各 finding\n{findings}\n\n"  # 字符串/template 参数
            "# 全部可用引用（去重后编号）\n{sources_table}\n\n"  # 字符串/template 参数
            "请输出完整 Markdown 报告。",  # 字符串/template 参数
        ),  # 闭合括号/元组/字典
    ]  # 闭合括号/元组/字典
)  # 闭合括号/元组/字典


async def awrite_report(question: str, findings: list[Finding]) -> str:  # 定义异步函数
    """异步生成报告。"""
    if not findings:  # 代码块起始
        return (  # 返回结果
            f"# {question}\n\n"  # 字符串/template 参数
            "_本次研究未能获取到任何有效信息（可能是网络/搜索后端全部失败）。_\n"  # 字符串/template 参数
        )  # 闭合括号/元组/字典

    sources_table, url_to_id = _build_source_table(findings)  # 赋值给 url_to_id
    findings_block = _format_findings(findings, url_to_id)  # 赋值给 findings_block

    llm = get_llm(temperature=0.3, role="writer")  # 获取 ChatOpenAI 兼容 LLM
    chain = _WRITER_PROMPT | llm  # 赋值给 chain
    msg = await chain.ainvoke(  # 等待异步结果
        {  # 执行本行逻辑
            "question": question,  # 字符串/template 参数
            "findings": findings_block,  # 字符串/template 参数
            "sources_table": sources_table or "(无)",  # 字符串/template 参数
        }  # 闭合括号/元组/字典
    )  # 闭合括号/元组/字典
    return msg.content if hasattr(msg, "content") else str(msg)  # 返回结果


# 兼容旧调用方
def write_report(question: str, findings: list[Finding]) -> str:  # 定义函数
    import asyncio  # 导入 asyncio 异步库

    return asyncio.run(awrite_report(question, findings))  # 返回结果


# ============================================================
# Helpers
# ============================================================

def _build_source_table(findings: list[Finding]) -> tuple[str, dict[str, int]]:  # 定义函数
    """所有 finding 里的 url 去重 + 编号。返回 (展示用表格, url→id 字典)。"""
    url_to_id: dict[str, int] = {}  # 赋值给 int]
    rows: list[str] = []  # 赋值给 list[str]
    for f in findings:  # for 循环
        for s in f.sources:  # for 循环
            if not s.url or s.url in url_to_id:  # 代码块起始
                continue  # 跳过本次循环
            idx = len(url_to_id) + 1  # 赋值给 idx
            url_to_id[s.url] = idx  # 赋值给 url_to_id[s.url]
            rows.append(f"[^{idx}] {s.title or '(无标题)'} — {s.url}")  # 执行本行逻辑
    return "\n".join(rows), url_to_id  # 返回结果


def _format_findings(findings: list[Finding], url_to_id: dict[str, int]) -> str:  # 定义函数
    blocks: list[str] = []  # 赋值给 list[str]
    for f in findings:  # for 循环
        if f.sources:  # 代码块起始
            tags = ", ".join(  # 赋值给 tags
                f"[^{url_to_id[s.url]}]"  # 字符串/template 参数
                for s in f.sources  # for 循环
                if s.url and s.url in url_to_id  # 执行本行逻辑
            )  # 闭合括号/元组/字典
        else:  # else 分支
            tags = "(无引用)"  # 赋值给 tags
        blocks.append(  # 执行本行逻辑
            f"## 子问题：{f.sub_question}\n"  # 字符串/template 参数
            f"答案：{f.summary}\n"  # 字符串/template 参数
            f"涉及引用：{tags}"  # 字符串/template 参数
        )  # 闭合括号/元组/字典
    return "\n\n---\n\n".join(blocks)  # 返回结果


if __name__ == "__main__":  # 脚本直接运行时执行 main
    import asyncio  # 导入 asyncio 异步库

    from state import Source  # 执行本行逻辑

    demo = [  # 赋值给 demo
        Finding(  # 执行本行逻辑
            sub_question="LangGraph 是什么",  # 执行本行逻辑
            summary="LangGraph 是 LangChain 团队推出的状态图框架，用于构建可控的多步 Agent。",  # 执行本行逻辑
            sources=[Source(url="https://langchain-ai.github.io/langgraph/", title="LangGraph Docs")],  # 执行本行逻辑
        ),  # 闭合括号/元组/字典
        Finding(  # 执行本行逻辑
            sub_question="Send API 的作用",  # 执行本行逻辑
            summary="Send API 用于在节点之间动态派发任务，支持 fan-out 并行执行。",  # 执行本行逻辑
            sources=[Source(url="https://langchain-ai.github.io/langgraph/concepts/low_level/", title="LangGraph Low-Level")],  # 执行本行逻辑
        ),  # 闭合括号/元组/字典
    ]  # 闭合括号/元组/字典
    print(asyncio.run(awrite_report("LangGraph 的核心概念", demo)))  # 打印输出
