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
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# 子模块 + _common 都进 path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import banner  # noqa: E402

from graph import build_graph  # noqa: E402


REPORTS_DIR = Path(__file__).parent / "reports"


async def arun(question: str, mode: str, max_iterations: int) -> str:
    """跑完整流水线，流式实时打印进度，返回最终 Markdown。"""
    banner(f"研究问题：{question}（mode={mode}）")
    graph = build_graph(mode=mode, max_iterations=max_iterations)
    report = ""
    seen_events: set[int] = set()  # 已打印过的 event 索引，避免 stream_mode="values" 重复

    # stream_mode="values" 每次给完整 state 快照（含累计的 progress_events）
    # 我们用索引去重保证每条事件只打印一次
    async for snapshot in graph.astream({"question": question}, stream_mode="values"):
        events = snapshot.get("progress_events") or []
        for i, ev in enumerate(events):
            if i in seen_events:
                continue
            seen_events.add(i)
            print(f"  · {ev}")
        if snapshot.get("report"):
            report = snapshot["report"]

    return report


def save(question: str, report: str, mode: str) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^\w一-龥-]+", "_", question)[:40].strip("_") or "report"
    path = REPORTS_DIR / f"{ts}_{mode}_{safe}.md"
    header = (
        f"# {question}\n\n"
        f"*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*  ·  "
        f"*模式：{mode}*\n\n---\n\n"
    )
    path.write_text(header + report, encoding="utf-8")
    return path


def main():
    ap = argparse.ArgumentParser(
        description="Deep Research Agent v2 —— LangGraph 多 Agent 并行研究"
    )
    ap.add_argument("question", nargs="*", help="研究问题（不带则交互输入）")
    ap.add_argument(
        "-m",
        "--mode",
        choices=["supervisor", "simple"],
        default=os.getenv("RESEARCH_MODE", "supervisor"),
        help="supervisor（默认）= 动态调度+反思 / simple = 一次性 planner（教学）",
    )
    ap.add_argument(
        "-i",
        "--max-iterations",
        type=int,
        default=int(os.getenv("RESEARCH_MAX_ITERATIONS", "3")),
        help="supervisor 模式下最多决策轮数（默认 3）",
    )
    args = ap.parse_args()

    question = " ".join(args.question).strip()
    if not question:
        try:
            question = input("研究问题 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
    if not question:
        print("空问题，退出。")
        return

    try:
        report = asyncio.run(arun(question, mode=args.mode, max_iterations=args.max_iterations))
    except KeyboardInterrupt:
        print("\n[interrupted]")
        return
    except Exception as e:
        print(f"\n[error] {type(e).__name__}: {e}")
        return

    if not report:
        print("[warn] 没有生成报告")
        return

    path = save(question, report, args.mode)
    print(f"\n✓ 报告已保存：{path}\n")
    print("=" * 60)
    print(report)


if __name__ == "__main__":
    main()
