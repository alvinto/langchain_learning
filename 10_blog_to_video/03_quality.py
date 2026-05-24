"""
10-3.5 幻灯片 HTML 视觉预检

目标不是替代人工审美，而是在进入 TTS/MP4 前拦住明显硬伤：
- 文本或组件被裁切到 slide 外
- 标题行数失控
- Mermaid / Lucide 没渲染出来
- diagram 主体过小

这一步仍然发生在 HTML/PNG 阶段，比视频合成后返工便宜得多。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from _common import banner


def _wait_for_frontend_ready(page) -> None:
    """等待模板里的前端增强完成，和 03_render.py 保持一致。"""
    try:
        page.wait_for_function(
            "() => document.body.dataset.renderReady === 'true'", timeout=10_000
        )
    except Exception:
        print("  [warn] 没收到 data-render-ready 标记，继续预检")

    try:
        page.wait_for_function(
            "() => document.querySelectorAll('i[data-lucide]').length === 0",
            timeout=8_000,
        )
    except Exception:
        print("  [warn] Lucide 图标可能未全部渲染，继续预检")

    try:
        page.wait_for_function(
            """() => {
                const all = document.querySelectorAll('.mermaid');
                return all.length === 0 || Array.from(all).every(el => el.querySelector('svg'));
            }""",
            timeout=15_000,
        )
    except Exception:
        print("  [warn] Mermaid 图可能未全部渲染，继续预检")

    page.wait_for_timeout(400)


def inspect_html(html_path: Path, report_path: Path | None = None, strict: bool = False) -> dict[str, Any]:
    """返回视觉预检报告。strict=True 时 warning 也会让 passed=false。"""
    from playwright.sync_api import sync_playwright

    file_url = f"file://{html_path.resolve()}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
        )
        page = ctx.new_page()
        page.goto(file_url, wait_until="load")
        _wait_for_frontend_ready(page)

        slides = page.evaluate(
            """
            () => {
              const CORE_SELECTORS = [
                '.h-title', '.subtitle', '.statement-text', '.stat', '.caption',
                '.card', '.layer', '.step', '.callout', '.code-window',
                '.code-notes', '.mermaid svg', 'table', '.quote', '.pattern-card',
                '.road', '.stack', '.grid', '.matrix-wrap', '.matrix', '.q',
                '.pname', '.sections', '.sec'
              ];
              const LAYOUTS_WITH_SMALL_BODY_OK = new Set(['layout-cover', 'layout-statement']);
              const rectObj = (r) => ({
                left: Math.round(r.left),
                top: Math.round(r.top),
                right: Math.round(r.right),
                bottom: Math.round(r.bottom),
                width: Math.round(r.width),
                height: Math.round(r.height)
              });
              const visible = (el) => {
                const style = window.getComputedStyle(el);
                const r = el.getBoundingClientRect();
                return style.display !== 'none'
                  && style.visibility !== 'hidden'
                  && Number(style.opacity || 1) > 0.01
                  && r.width > 1
                  && r.height > 1;
              };
              const labelOf = (el) => {
                const cls = Array.from(el.classList || []).slice(0, 4).join('.');
                const text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                const tag = el.tagName.toLowerCase();
                return `${tag}${cls ? '.' + cls : ''}${text ? ' "' + text.slice(0, 36) + '"' : ''}`;
              };
              const bboxOf = (elements) => {
                const boxes = elements
                  .filter(visible)
                  .map((el) => el.getBoundingClientRect())
                  .filter((r) => r.width > 1 && r.height > 1);
                if (!boxes.length) return null;
                const left = Math.min(...boxes.map((r) => r.left));
                const top = Math.min(...boxes.map((r) => r.top));
                const right = Math.max(...boxes.map((r) => r.right));
                const bottom = Math.max(...boxes.map((r) => r.bottom));
                return { left, top, right, bottom, width: right - left, height: bottom - top };
              };
              const hasOwnContent = (el) => {
                const tag = el.tagName.toLowerCase();
                if (['svg', 'img', 'canvas', 'table', 'pre', 'code'].includes(tag)) return true;
                const text = (el.innerText || el.textContent || '').trim();
                return text.length > 0;
              };

              return Array.from(document.querySelectorAll('.slide')).map((slide, index) => {
                const slideRect = slide.getBoundingClientRect();
                const layout = Array.from(slide.classList).find((c) => c.startsWith('layout-')) || 'layout-unknown';
                const issues = [];
                const warnings = [];

                if (slide.querySelectorAll('i[data-lucide]').length > 0) {
                  issues.push('Lucide 图标没有全部渲染成 SVG');
                }
                if (slide.querySelector('.mermaid') && !slide.querySelector('.mermaid svg')) {
                  issues.push('Mermaid 图没有渲染成 SVG');
                }

                const candidates = Array.from(slide.querySelectorAll('*'))
                  .filter((el) => visible(el) && hasOwnContent(el));
                for (const el of candidates) {
                  const tag = el.tagName.toLowerCase();
                  if (['script', 'style'].includes(tag)) continue;
                  const r = el.getBoundingClientRect();
                  const outside = r.left < slideRect.left - 4
                    || r.top < slideRect.top - 4
                    || r.right > slideRect.right + 4
                    || r.bottom > slideRect.bottom + 4;
                  if (outside) {
                    issues.push(`元素越界: ${labelOf(el)} @ ${JSON.stringify(rectObj(r))}`);
                    continue;
                  }

                  if (el instanceof HTMLElement) {
                    const style = window.getComputedStyle(el);
                    const overflowX = el.scrollWidth > el.clientWidth + 3;
                    const overflowY = el.scrollHeight > el.clientHeight + 3;
                    const clipsX = ['hidden', 'clip', 'auto', 'scroll'].includes(style.overflowX);
                    const clipsY = ['hidden', 'clip', 'auto', 'scroll'].includes(style.overflowY);
                    const clipsOwnContent = (overflowX && clipsX) || (overflowY && clipsY);
                    const isCodeBlock = tag === 'pre' || tag === 'code' || Boolean(el.closest('.code-window'));
                    const allowsOverflow = tag === 'svg' || el.classList.contains('slide') || isCodeBlock;
                    if (!allowsOverflow && clipsOwnContent) {
                      issues.push(`文本/内容溢出: ${labelOf(el)}`);
                    }
                  }
                }

                const title = slide.querySelector('.h-title');
                if (title && visible(title)) {
                  const tr = title.getBoundingClientRect();
                  const style = window.getComputedStyle(title);
                  const fontSize = Number.parseFloat(style.fontSize) || 60;
                  const lineHeight = Number.parseFloat(style.lineHeight) || fontSize * 1.12;
                  const lines = Math.max(1, Math.round(tr.height / lineHeight));
                  if (layout === 'layout-cover' && lines > 2) {
                    issues.push(`封面标题超过 2 行: ${lines} 行`);
                  } else if (layout !== 'layout-cover' && lines > 2) {
                    warnings.push(`标题超过 2 行: ${lines} 行`);
                  }
                }

                const coreElements = CORE_SELECTORS.flatMap((selector) => Array.from(slide.querySelectorAll(selector)));
                const coreBox = bboxOf(coreElements);
                if (!coreBox) {
                  issues.push('没有识别到主体视觉元素');
                } else if (!LAYOUTS_WITH_SMALL_BODY_OK.has(layout)) {
                  if (coreBox.width < 620 || coreBox.height < 220) {
                    warnings.push(`主体视觉区域偏小: ${Math.round(coreBox.width)}x${Math.round(coreBox.height)}`);
                  }
                }

                if (layout === 'layout-diagram') {
                  const svg = slide.querySelector('.mermaid svg');
                  if (svg && visible(svg)) {
                    const sr = svg.getBoundingClientRect();
                    if (sr.width < 780 || sr.height < 220) {
                      issues.push(`diagram 主体过小: ${Math.round(sr.width)}x${Math.round(sr.height)}`);
                    } else if (sr.width < 960 || sr.height < 250) {
                      warnings.push(`diagram 主体略小: ${Math.round(sr.width)}x${Math.round(sr.height)}`);
                    }
                  }
                }

                if (layout === 'layout-code') {
                  const pre = slide.querySelector('.code-window pre');
                  if (pre && visible(pre)) {
                    const pr = pre.getBoundingClientRect();
                    const bottomLimit = slideRect.bottom - 76;
                    if (pr.bottom > bottomLimit) {
                      issues.push(`代码块压到底部安全区: ${labelOf(pre)}`);
                    }
                    if (pre.scrollHeight > pre.clientHeight + 80) {
                      warnings.push(`代码行数偏多，底部可能被裁切: ${labelOf(pre)}`);
                    }
                  }
                }

                if (layout === 'layout-architecture') {
                  const layers = Array.from(slide.querySelectorAll('.layer')).filter(visible);
                  if (layers.length < 3) {
                    warnings.push(`architecture 层数偏少: ${layers.length}`);
                  }
                  const bottomLimit = slideRect.bottom - 76;
                  for (const layer of layers) {
                    const lr = layer.getBoundingClientRect();
                    if (lr.bottom > bottomLimit) {
                      issues.push(`architecture 层压到底部安全区: ${labelOf(layer)}`);
                    }
                  }
                }

                return {
                  page: index + 1,
                  layout,
                  issues,
                  warnings,
                  metrics: {
                    slide: rectObj(slideRect),
                    core: coreBox ? rectObj(coreBox) : null
                  }
                };
              });
            }
            """
        )
        browser.close()

    issue_count = sum(len(s["issues"]) for s in slides)
    warning_count = sum(len(s["warnings"]) for s in slides)
    report: dict[str, Any] = {
        "html": str(html_path),
        "strict": strict,
        "passed": issue_count == 0 and (warning_count == 0 if strict else True),
        "issue_count": issue_count,
        "warning_count": warning_count,
        "slides": slides,
    }

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return report


def print_report(report: dict[str, Any]) -> None:
    status = "通过" if report["passed"] else "未通过"
    print(
        f"  视觉预检{status}: {report['issue_count']} 个问题，"
        f"{report['warning_count']} 个警告"
    )
    for slide in report["slides"]:
        if not slide["issues"] and not slide["warnings"]:
            continue
        page = f"{slide['page']:02d}"
        print(f"  - page {page} [{slide['layout']}]")
        for issue in slide["issues"]:
            print(f"    [fail] {issue}")
        for warning in slide["warnings"]:
            print(f"    [warn] {warning}")


def main() -> None:
    parser = argparse.ArgumentParser(description="幻灯片 HTML 视觉预检")
    parser.add_argument(
        "html",
        nargs="?",
        default="10_blog_to_video/out/slides.html",
        help="slides.html 路径",
    )
    parser.add_argument(
        "-o",
        "--out",
        default=None,
        help="质量报告 JSON 输出路径，默认 <html_dir>/quality_report.json",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="warning 也视为失败",
    )
    args = parser.parse_args()

    html_path = Path(args.html)
    report_path = Path(args.out) if args.out else html_path.parent / "quality_report.json"

    banner("10-3.5 HTML 视觉预检")
    report = inspect_html(html_path, report_path=report_path, strict=args.strict)
    print_report(report)
    print(f"  报告：{report_path}")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
