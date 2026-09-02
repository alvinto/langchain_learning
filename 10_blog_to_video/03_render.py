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
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径

sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from _common import banner  # 导入项目共享 LLM/Embedding 配置


def render_pngs(html_path: Path, out_dir: Path) -> list[Path]:  # 定义函数
    """打开 HTML，按 .slide 元素逐个截图，返回所有 PNG 路径（按页码排序）。"""
    from playwright.sync_api import sync_playwright  # 执行本行逻辑

    out_dir.mkdir(parents=True, exist_ok=True)  # 执行本行逻辑
    file_url = f"file://{html_path.resolve()}"  # 赋值给 file_url
    paths: list[Path] = []  # 赋值给 list[Path]

    with sync_playwright() as p:  # with 上下文管理
        browser = p.chromium.launch()  # 赋值给 browser
        # device_scale_factor=1 保证 1920x1080 输出就是 1920x1080 像素，
        # 不要让 retina HiDPI 把图悄悄放大成 3840x2160
        ctx = browser.new_context(  # 赋值给 ctx
            viewport={"width": 1920, "height": 1080},  # 执行本行逻辑
            device_scale_factor=1,  # 执行本行逻辑
        )  # 闭合括号/元组/字典
        page = ctx.new_page()  # 赋值给 page
        page.goto(file_url, wait_until="load")  # 执行本行逻辑

        # 等模板里的初始化脚本跑完（Lucide / Mermaid 都通过 CDN 加载，需要等）
        try:  # 代码块起始
            page.wait_for_function(  # 执行本行逻辑
                "() => document.body.dataset.renderReady === 'true'", timeout=10_000  # 字符串/template 参数
            )  # 闭合括号/元组/字典
        except Exception:  # 捕获异常
            print("  [warn] 没收到 data-render-ready 标记（可能用了老模板），继续")  # 打印输出

        # 等 Lucide 把所有 <i data-lucide> 替换成 <svg>
        try:  # 代码块起始
            page.wait_for_function(  # 执行本行逻辑
                "() => document.querySelectorAll('i[data-lucide]').length === 0",  # 字符串/template 参数
                timeout=8_000,  # 执行本行逻辑
            )  # 闭合括号/元组/字典
        except Exception:  # 捕获异常
            print("  [warn] Lucide 图标可能未全部渲染（CDN 慢？）继续")  # 打印输出

        # 等 Mermaid 把所有 .mermaid 渲染成 svg（diagram 页才有，没有就秒过）
        try:  # 代码块起始
            page.wait_for_function(  # 执行本行逻辑
                """() => {
                    const all = document.querySelectorAll('.mermaid');
                    return all.length === 0 || Array.from(all).every(el => el.querySelector('svg'));
                }""",
                timeout=15_000,  # 执行本行逻辑
            )  # 闭合括号/元组/字典
        except Exception:  # 捕获异常
            print("  [warn] Mermaid 图可能未全部渲染（语法错误或 CDN 慢？）继续")  # 打印输出

        # 字体最终回稳
        page.wait_for_timeout(400)  # 执行本行逻辑

        slides = page.locator(".slide")  # 赋值给 slides
        count = slides.count()  # 赋值给 count
        if count == 0:  # 代码块起始
            raise RuntimeError(f"{html_path} 里没找到 .slide 元素，检查模板是否正确")  # 抛出异常

        for i in range(count):  # for 循环
            png = out_dir / f"page_{i+1:03d}.png"  # 赋值给 png
            # scroll_into_view 防止超高页面时某些 layout 还没进 viewport
            slides.nth(i).scroll_into_view_if_needed()  # 执行本行逻辑
            slides.nth(i).screenshot(path=str(png))  # 执行本行逻辑
            paths.append(png)  # 执行本行逻辑
            print(f"  截图 {png.name}")  # 打印输出

        browser.close()  # 执行本行逻辑
    return paths  # 返回结果


def main(html_path: str, out_dir: str) -> None:  # 定义函数
    banner("10-3 截图幻灯片")  # 打印章节标题分隔条
    pngs = render_pngs(Path(html_path), Path(out_dir))  # 赋值给 pngs
    print(f"\n已生成 {len(pngs)} 张 PNG → {out_dir}")  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    html = sys.argv[1] if len(sys.argv) > 1 else "10_blog_to_video/out/slides.html"  # 赋值给 html
    out = sys.argv[2] if len(sys.argv) > 2 else "10_blog_to_video/out/png"  # 赋值给 out
    main(html, out)  # 执行本行逻辑
