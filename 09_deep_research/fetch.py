"""URL → 正文文本（async 版本）。

trafilatura 是 OSS 里抽得最干净的之一。失败时用 httpx + bs4 兜底。

为什么 async：见 search.py 的注释。trafilatura 和 bs4 都是同步的，
所以我们要么把它们 to_thread 包，要么直接用 httpx 异步取 HTML 再走同步的解析。
这里选后者——HTTP IO（最慢的那段）真正 async，解析在事件循环里跑也无所谓。
"""
from __future__ import annotations

import asyncio


async def afetch_text(url: str, max_chars: int = 8000, timeout: float = 10.0) -> str:
    """异步抓取并清洗一个 URL 的正文。

    HTTP 抓取最多重试 3 次（指数退避 0.5s / 1.5s）：DNS/TCP 抖动重试常常救活。
    抽取失败不重试：拿到同一段 HTML 再抽一次结果一样，纯属浪费。
    """
    html = ""
    for attempt in range(3):
        html = await _try_httpx(url, timeout)
        if html:
            break
        if attempt < 2:  # 最后一次失败不再睡了
            await asyncio.sleep(0.5 * (3**attempt))

    if not html:
        return f"[fetch failed] {url}"

    text = _extract_via_trafilatura(html) or _extract_via_bs4(html)
    if not text:
        return f"[extract failed] {url}"
    return text[:max_chars]


# ============================================================
# 同步入口（保留给 simple 模式 / 自测）
# ============================================================

def fetch_text(url: str, max_chars: int = 8000, timeout: int = 10) -> str:
    """同步版本。复用 trafilatura 自带的抓取（同步）。"""
    text = _try_trafilatura_sync(url, timeout) or _try_requests_bs4_sync(url, timeout)
    if not text:
        return f"[fetch failed] {url}"
    return text[:max_chars]


# ============================================================
# 实际工具
# ============================================================

async def _try_httpx(url: str, timeout: float) -> str:
    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (deep-research-agent)"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
    except Exception:
        return ""


def _extract_via_trafilatura(html: str) -> str:
    try:
        import trafilatura

        return trafilatura.extract(
            html, include_comments=False, include_tables=False, no_fallback=False
        ) or ""
    except Exception:
        return ""


def _extract_via_bs4(html: str) -> str:
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except Exception:
        return ""


def _try_trafilatura_sync(url: str, timeout: int) -> str:
    try:
        import trafilatura

        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return ""
        return trafilatura.extract(
            downloaded, include_comments=False, include_tables=False, no_fallback=False
        ) or ""
    except Exception:
        return ""


def _try_requests_bs4_sync(url: str, timeout: int) -> str:
    try:
        import requests
        from bs4 import BeautifulSoup

        resp = requests.get(
            url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"}
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except Exception:
        return ""


if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else "https://python.langchain.com/docs/introduction/"
    print(asyncio.run(afetch_text(url, max_chars=2000)))
