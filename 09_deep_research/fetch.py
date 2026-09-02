"""URL → 正文文本（async 版本）。

trafilatura 是 OSS 里抽得最干净的之一。失败时用 httpx + bs4 兜底。

为什么 async：见 search.py 的注释。trafilatura 和 bs4 都是同步的，
所以我们要么把它们 to_thread 包，要么直接用 httpx 异步取 HTML 再走同步的解析。
这里选后者——HTTP IO（最慢的那段）真正 async，解析在事件循环里跑也无所谓。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解

import asyncio  # 导入 asyncio 异步库


async def afetch_text(url: str, max_chars: int = 8000, timeout: float = 10.0) -> str:  # 定义异步函数
    """异步抓取并清洗一个 URL 的正文。

    HTTP 抓取最多重试 3 次（指数退避 0.5s / 1.5s）：DNS/TCP 抖动重试常常救活。
    抽取失败不重试：拿到同一段 HTML 再抽一次结果一样，纯属浪费。
    """
    html = ""  # 赋值给 html
    for attempt in range(3):  # for 循环
        html = await _try_httpx(url, timeout)  # 等待异步结果
        if html:  # 代码块起始
            break  # 跳出循环
        if attempt < 2:  # 最后一次失败不再睡了
            await asyncio.sleep(0.5 * (3**attempt))  # 等待异步结果

    if not html:  # 代码块起始
        return f"[fetch failed] {url}"  # 返回结果

    text = _extract_via_trafilatura(html) or _extract_via_bs4(html)  # 赋值给 text
    if not text:  # 代码块起始
        return f"[extract failed] {url}"  # 返回结果
    return text[:max_chars]  # 返回结果


# ============================================================
# 同步入口（保留给 simple 模式 / 自测）
# ============================================================

def fetch_text(url: str, max_chars: int = 8000, timeout: int = 10) -> str:  # 定义函数
    """同步版本。复用 trafilatura 自带的抓取（同步）。"""
    text = _try_trafilatura_sync(url, timeout) or _try_requests_bs4_sync(url, timeout)  # 赋值给 text
    if not text:  # 代码块起始
        return f"[fetch failed] {url}"  # 返回结果
    return text[:max_chars]  # 返回结果


# ============================================================
# 实际工具
# ============================================================

async def _try_httpx(url: str, timeout: float) -> str:  # 定义异步函数
    try:  # 代码块起始
        import httpx  # 导入 httpx HTTP 客户端

        async with httpx.AsyncClient(  # with 上下文管理
            timeout=timeout,  # 执行本行逻辑
            follow_redirects=True,  # 执行本行逻辑
            headers={"User-Agent": "Mozilla/5.0 (deep-research-agent)"},  # 执行本行逻辑
        ) as client:  # 代码块起始
            resp = await client.get(url)  # 等待异步结果
            resp.raise_for_status()  # 执行本行逻辑
            return resp.text  # 返回结果
    except Exception:  # 捕获异常
        return ""  # 返回结果


def _extract_via_trafilatura(html: str) -> str:  # 定义函数
    try:  # 代码块起始
        import trafilatura  # 执行本行逻辑

        return trafilatura.extract(  # 返回结果
            html, include_comments=False, include_tables=False, no_fallback=False  # 执行本行逻辑
        ) or ""  # 执行本行逻辑
    except Exception:  # 捕获异常
        return ""  # 返回结果


def _extract_via_bs4(html: str) -> str:  # 定义函数
    try:  # 代码块起始
        from bs4 import BeautifulSoup  # 执行本行逻辑

        soup = BeautifulSoup(html, "html.parser")  # 赋值给 soup
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):  # for 循环
            tag.decompose()  # 执行本行逻辑
        return soup.get_text(separator="\n", strip=True)  # 返回结果
    except Exception:  # 捕获异常
        return ""  # 返回结果


def _try_trafilatura_sync(url: str, timeout: int) -> str:  # 定义函数
    try:  # 代码块起始
        import trafilatura  # 执行本行逻辑

        downloaded = trafilatura.fetch_url(url)  # 赋值给 downloaded
        if not downloaded:  # 代码块起始
            return ""  # 返回结果
        return trafilatura.extract(  # 返回结果
            downloaded, include_comments=False, include_tables=False, no_fallback=False  # 执行本行逻辑
        ) or ""  # 执行本行逻辑
    except Exception:  # 捕获异常
        return ""  # 返回结果


def _try_requests_bs4_sync(url: str, timeout: int) -> str:  # 定义函数
    try:  # 代码块起始
        import requests  # 执行本行逻辑
        from bs4 import BeautifulSoup  # 执行本行逻辑

        resp = requests.get(  # 赋值给 resp
            url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"}  # 执行本行逻辑
        )  # 闭合括号/元组/字典
        resp.raise_for_status()  # 执行本行逻辑
        soup = BeautifulSoup(resp.text, "html.parser")  # 赋值给 soup
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):  # for 循环
            tag.decompose()  # 执行本行逻辑
        return soup.get_text(separator="\n", strip=True)  # 返回结果
    except Exception:  # 捕获异常
        return ""  # 返回结果


if __name__ == "__main__":  # 脚本直接运行时执行 main
    import sys  # 导入 sys 标准库

    url = sys.argv[1] if len(sys.argv) > 1 else "https://python.langchain.com/docs/introduction/"  # 赋值给 url
    print(asyncio.run(afetch_text(url, max_chars=2000)))  # 打印输出
