"""搜索后端：Tavily 优先，无 key 时自动降级到 DuckDuckGo。

外部只暴露 `asearch(query, k)` 协程 —— researcher 完全不用关心底层用了哪个。

为什么是 async：deep research 主图会用 asyncio.gather 同时跑 N 个 researcher，
每个 researcher 内部又会并发触发搜索/抓取。串行的话总耗时 = N × 单个，
async 后 ≈ max(单个)，是这个项目"好用 vs 难用"的分水岭。

Tavily/DDG 的官方 SDK 都是同步的，所以我们用 asyncio.to_thread 把同步调用
扔到默认线程池里跑——这是 Python async 世界里 wrap 同步 IO 的标准姿势，
对调用方完全透明。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解

import asyncio  # 导入 asyncio 异步库
import os  # 导入 os 标准库
from dataclasses import dataclass  # 导入 dataclass 相关工具


@dataclass  # dataclass 装饰器
class SearchResult:  # 定义类
    url: str  # 执行本行逻辑
    title: str  # 执行本行逻辑
    snippet: str   # 搜索引擎自己给的简短摘要


async def asearch(query: str, k: int = 5) -> list[SearchResult]:  # 定义异步函数
    """统一搜索入口（异步）。"""
    if os.getenv("TAVILY_API_KEY"):  # 代码块起始
        try:  # 代码块起始
            return await asyncio.to_thread(_tavily_sync, query, k)  # 返回结果
        except Exception as e:  # 捕获异常
            print(f"[search] Tavily 失败，降级 DDG: {e}")  # 打印输出
    return await asyncio.to_thread(_ddg_sync, query, k)  # 返回结果


# ============================================================
# 兼容老的同步入口（planner 没动，simple 模式还会调）
# ============================================================

def search(query: str, k: int = 5) -> list[SearchResult]:  # 定义函数
    """同步入口（保留给非 async 调用者，比如 __main__ 自测）。"""
    if os.getenv("TAVILY_API_KEY"):  # 代码块起始
        try:  # 代码块起始
            return _tavily_sync(query, k)  # 返回结果
        except Exception as e:  # 捕获异常
            print(f"[search] Tavily 失败，降级 DDG: {e}")  # 打印输出
    return _ddg_sync(query, k)  # 返回结果


# ============================================================
# 实际后端
# ============================================================

def _tavily_sync(query: str, k: int) -> list[SearchResult]:  # 定义函数
    from tavily import TavilyClient  # 执行本行逻辑

    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])  # 赋值给 client
    resp = client.search(query=query, max_results=k, search_depth="basic")  # 赋值给 resp
    return [  # 返回结果
        SearchResult(  # 执行本行逻辑
            url=r.get("url", ""),  # 执行本行逻辑
            title=r.get("title", ""),  # 执行本行逻辑
            snippet=r.get("content", "")[:500],  # 执行本行逻辑
        )  # 闭合括号/元组/字典
        for r in resp.get("results", [])  # for 循环
    ]  # 闭合括号/元组/字典


def _ddg_sync(query: str, k: int) -> list[SearchResult]:  # 定义函数
    try:  # 代码块起始
        from ddgs import DDGS  # 执行本行逻辑
    except ImportError:  # 捕获异常
        from duckduckgo_search import DDGS  # type: ignore

    out: list[SearchResult] = []  # 赋值给 list[SearchResult]
    try:  # 代码块起始
        with DDGS() as d:  # with 上下文管理
            for r in d.text(query, max_results=k):  # for 循环
                out.append(  # 执行本行逻辑
                    SearchResult(  # 执行本行逻辑
                        url=r.get("href") or r.get("url", ""),  # 执行本行逻辑
                        title=r.get("title", ""),  # 执行本行逻辑
                        snippet=(r.get("body") or "")[:500],  # 执行本行逻辑
                    )  # 闭合括号/元组/字典
                )  # 闭合括号/元组/字典
    except Exception as e:  # 捕获异常
        print(f"[search] DDG 也失败了: {e}")  # 打印输出
    return out  # 返回结果


if __name__ == "__main__":  # 脚本直接运行时执行 main
    import sys  # 导入 sys 标准库

    q = " ".join(sys.argv[1:]) or "deep research agent"  # 赋值给 q
    for i, r in enumerate(search(q, k=5), 1):  # for 循环
        print(f"\n[{i}] {r.title}\n    {r.url}\n    {r.snippet[:120]}...")  # 打印输出
