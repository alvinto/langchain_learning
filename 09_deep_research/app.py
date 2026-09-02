"""Deep Research Agent CLI（v2）。

用法：
    python 09_deep_research/app.py "你的研究问题"               # supervisor 模式（默认）
    python 09_deep_research/app.py -m simple "..."             # 旧的 planner 教学模式
    python 09_deep_research/app.py -i 4 "..."                  # supervisor 最多 4 轮
    python 09_deep_research/app.py                              # 交互输入

跑完后报告保存到 09_deep_research/reports/<时间戳>_<问题摘要>.md
并把全文打印到终端。

v2 改进：
- 真异步并行（asyncio.run + asyncio.gather inside supervisor）
- 实时流式进度：每条 progress_event 出现立刻打印
- supervisor 模式自带"反思补研究"（看官方课程同款的 ConductResearch/ResearchComplete 决策循环）
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解

import argparse  # 导入 argparse 命令行解析
import asyncio  # 导入 asyncio 异步库
import os  # 导入 os 标准库
import re  # 导入 re 正则模块
import sys  # 导入 sys 标准库
from datetime import datetime  # 导入 datetime 日期时间
from pathlib import Path  # 导入 Path 处理路径

# 子模块 + _common 都进 path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # 执行本行逻辑
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 执行本行逻辑

from _common import banner  # noqa: E402

from graph import build_graph  # noqa: E402


REPORTS_DIR = Path(__file__).parent / "reports"  # 赋值给 REPORTS_DIR


async def arun(question: str, mode: str, max_iterations: int) -> str:  # 定义异步函数
    """跑完整流水线，流式实时打印进度，返回最终 Markdown。"""
    banner(f"研究问题：{question}（mode={mode}）")  # 打印章节标题分隔条
    graph = build_graph(mode=mode, max_iterations=max_iterations)  # 赋值给 graph
    report = ""  # 赋值给 report
    seen_events: set[int] = set()  # 已打印过的 event 索引，避免 stream_mode="values" 重复

    # stream_mode="values" 每次给完整 state 快照（含累计的 progress_events）
    # 我们用索引去重保证每条事件只打印一次
    async for snapshot in graph.astream({"question": question}, stream_mode="values"):  # for 循环
        events = snapshot.get("progress_events") or []  # 赋值给 events
        for i, ev in enumerate(events):  # for 循环
            if i in seen_events:  # 代码块起始
                continue  # 跳过本次循环
            seen_events.add(i)  # 执行本行逻辑
            print(f"  · {ev}")  # 打印输出
        if snapshot.get("report"):  # 代码块起始
            report = snapshot["report"]  # 赋值给 report

    return report  # 返回结果


def save(question: str, report: str, mode: str) -> Path:  # 定义函数
    REPORTS_DIR.mkdir(exist_ok=True)  # 执行本行逻辑
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")  # 赋值给 ts
    safe = re.sub(r"[^\w一-龥-]+", "_", question)[:40].strip("_") or "report"  # 赋值给 safe
    path = REPORTS_DIR / f"{ts}_{mode}_{safe}.md"  # 赋值给 path
    header = (  # 赋值给 header
        f"# {question}\n\n"  # 字符串/template 参数
        f"*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*  ·  "  # 字符串/template 参数
        f"*模式：{mode}*\n\n---\n\n"  # 字符串/template 参数
    )  # 闭合括号/元组/字典
    path.write_text(header + report, encoding="utf-8")  # 执行本行逻辑
    return path  # 返回结果


def main():  # demo 入口函数
    ap = argparse.ArgumentParser(  # 赋值给 ap
        description="Deep Research Agent v2 —— LangGraph 多 Agent 并行研究"  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    ap.add_argument("question", nargs="*", help="研究问题（不带则交互输入）")  # 执行本行逻辑
    ap.add_argument(  # 执行本行逻辑
        "-m",  # 字符串/template 参数
        "--mode",  # 字符串/template 参数
        choices=["supervisor", "simple"],  # 执行本行逻辑
        default=os.getenv("RESEARCH_MODE", "supervisor"),  # 执行本行逻辑
        help="supervisor（默认）= 动态调度+反思 / simple = 一次性 planner（教学）",  # 赋值给 help
    )  # 闭合括号/元组/字典
    ap.add_argument(  # 执行本行逻辑
        "-i",  # 字符串/template 参数
        "--max-iterations",  # 字符串/template 参数
        type=int,  # 执行本行逻辑
        default=int(os.getenv("RESEARCH_MAX_ITERATIONS", "3")),  # 执行本行逻辑
        help="supervisor 模式下最多决策轮数（默认 3）",  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    args = ap.parse_args()  # 赋值给 args

    question = " ".join(args.question).strip()  # 赋值给 question
    if not question:  # 代码块起始
        try:  # 代码块起始
            question = input("研究问题 > ").strip()  # 赋值给 question
        except (EOFError, KeyboardInterrupt):  # 捕获异常
            print()  # 打印输出
            return  # 提前返回
    if not question:  # 代码块起始
        print("空问题，退出。")  # 打印输出
        return  # 提前返回

    try:  # 代码块起始
        report = asyncio.run(arun(question, mode=args.mode, max_iterations=args.max_iterations))  # 赋值给 report
    except KeyboardInterrupt:  # 捕获异常
        print("\n[interrupted]")  # 打印输出
        return  # 提前返回
    except Exception as e:  # 捕获异常
        print(f"\n[error] {type(e).__name__}: {e}")  # 打印输出
        return  # 提前返回

    if not report:  # 代码块起始
        print("[warn] 没有生成报告")  # 打印输出
        return  # 提前返回

    path = save(question, report, args.mode)  # 赋值给 path
    print(f"\n✓ 报告已保存：{path}\n")  # 打印输出
    print("=" * 60)  # 打印输出
    print(report)  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
