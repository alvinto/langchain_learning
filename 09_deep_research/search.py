"""搜索后端：Tavily 优先，无 key 时自动降级到 DuckDuckGo。

外部只暴露 `asearch(query, k)` 协程 —— researcher 完全不用关心底层用了哪个。

为什么是 async：deep research 主图会用 asyncio.gather 同时跑 N 个 researcher，
每个 researcher 内部又会并发触发搜索/抓取。串行的话总耗时 = N × 单个，
async 后 ≈ max(单个)，是这个项目"好用 vs 难用"的分水岭。

Tavily/DDG 的官方 SDK 都是同步的，所以我们用 asyncio.to_thread 把同步调用
扔到默认线程池里跑——这是 Python async 世界里 wrap 同步 IO 的标准姿势，
对调用方完全透明。
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str   # 搜索引擎自己给的简短摘要


async def asearch(query: str, k: int = 5) -> list[SearchResult]:
    """统一搜索入口（异步）。"""
    if os.getenv("TAVILY_API_KEY"):
        try:
            return await asyncio.to_thread(_tavily_sync, query, k)
        except Exception as e:
            print(f"[search] Tavily 失败，降级 DDG: {e}")
    return await asyncio.to_thread(_ddg_sync, query, k)


# ============================================================
# 兼容老的同步入口（planner 没动，simple 模式还会调）
# ============================================================

def search(query: str, k: int = 5) -> list[SearchResult]:
    """同步入口（保留给非 async 调用者，比如 __main__ 自测）。"""
    if os.getenv("TAVILY_API_KEY"):
        try:
            return _tavily_sync(query, k)
        except Exception as e:
            print(f"[search] Tavily 失败，降级 DDG: {e}")
    return _ddg_sync(query, k)


# ============================================================
# 实际后端
# ============================================================

def _tavily_sync(query: str, k: int) -> list[SearchResult]:
    from tavily import TavilyClient

    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    resp = client.search(query=query, max_results=k, search_depth="basic")
    return [
        SearchResult(
            url=r.get("url", ""),
            title=r.get("title", ""),
            snippet=r.get("content", "")[:500],
        )
        for r in resp.get("results", [])
    ]


def _ddg_sync(query: str, k: int) -> list[SearchResult]:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS  # type: ignore

    out: list[SearchResult] = []
    try:
        with DDGS() as d:
            for r in d.text(query, max_results=k):
                out.append(
                    SearchResult(
                        url=r.get("href") or r.get("url", ""),
                        title=r.get("title", ""),
                        snippet=(r.get("body") or "")[:500],
                    )
                )
    except Exception as e:
        print(f"[search] DDG 也失败了: {e}")
    return out


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "deep research agent"
    for i, r in enumerate(search(q, k=5), 1):
        print(f"\n[{i}] {r.title}\n    {r.url}\n    {r.snippet[:120]}...")
