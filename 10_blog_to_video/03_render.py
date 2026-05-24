"""
10-3 幻灯片 HTML → PNG 序列
学到：Playwright 启一个 headless Chromium，对每个 .slide 元素逐个截图。

首次运行需要装浏览器：
    playwright install chromium

为什么不用 puppeteer / selenium？
  - playwright python 绑定的 sync API 写起来比 selenium 直观
  - .locator(...).nth(i).screenshot(path=...) 一行搞定按元素截屏，
    不用算坐标、不用滚动到 viewport，自带 retry 等待元素就绪
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from _common import banner


def render_pngs(html_path: Path, out_dir: Path) -> list[Path]:
    """打开 HTML，按 .slide 元素逐个截图，返回所有 PNG 路径（按页码排序）。"""
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    file_url = f"file://{html_path.resolve()}"
    paths: list[Path] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        # device_scale_factor=1 保证 1920x1080 输出就是 1920x1080 像素，
        # 不要让 retina HiDPI 把图悄悄放大成 3840x2160
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
        )
        page = ctx.new_page()
        page.goto(file_url, wait_until="load")

        # 等模板里的初始化脚本跑完（Lucide / Mermaid 都通过 CDN 加载，需要等）
        try:
            page.wait_for_function(
                "() => document.body.dataset.renderReady === 'true'", timeout=10_000
            )
        except Exception:
            print("  [warn] 没收到 data-render-ready 标记（可能用了老模板），继续")

        # 等 Lucide 把所有 <i data-lucide> 替换成 <svg>
        try:
            page.wait_for_function(
                "() => document.querySelectorAll('i[data-lucide]').length === 0",
                timeout=8_000,
            )
        except Exception:
            print("  [warn] Lucide 图标可能未全部渲染（CDN 慢？）继续")

        # 等 Mermaid 把所有 .mermaid 渲染成 svg（diagram 页才有，没有就秒过）
        try:
            page.wait_for_function(
                """() => {
                    const all = document.querySelectorAll('.mermaid');
                    return all.length === 0 || Array.from(all).every(el => el.querySelector('svg'));
                }""",
                timeout=15_000,
            )
        except Exception:
            print("  [warn] Mermaid 图可能未全部渲染（语法错误或 CDN 慢？）继续")

        # 字体最终回稳
        page.wait_for_timeout(400)

        slides = page.locator(".slide")
        count = slides.count()
        if count == 0:
            raise RuntimeError(f"{html_path} 里没找到 .slide 元素，检查模板是否正确")

        for i in range(count):
            png = out_dir / f"page_{i+1:03d}.png"
            # scroll_into_view 防止超高页面时某些 layout 还没进 viewport
            slides.nth(i).scroll_into_view_if_needed()
            slides.nth(i).screenshot(path=str(png))
            paths.append(png)
            print(f"  截图 {png.name}")

        browser.close()
    return paths


def main(html_path: str, out_dir: str) -> None:
    banner("10-3 截图幻灯片")
    pngs = render_pngs(Path(html_path), Path(out_dir))
    print(f"\n已生成 {len(pngs)} 张 PNG → {out_dir}")


if __name__ == "__main__":
    html = sys.argv[1] if len(sys.argv) > 1 else "10_blog_to_video/out/slides.html"
    out = sys.argv[2] if len(sys.argv) > 2 else "10_blog_to_video/out/png"
    main(html, out)
