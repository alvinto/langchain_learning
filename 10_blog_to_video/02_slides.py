"""
10-2 脚本 JSON → 幻灯片 HTML
学到：把 LLM 输出的结构化数据通过 Jinja2 模板渲染成单文件 HTML。
     视觉精美度的天花板在 templates/slides.html.j2（CSS），不在 LLM。

为什么这样拆？
  - LLM 出错时（比如多了一个字段），CSS 不受影响，反之亦然
  - 想换视觉风格只改模板，不重跑 LLM —— 省钱
  - HTML 中间产物可以直接用浏览器打开预览，肉眼调试比看 PNG 快得多
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from _common import banner

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def _highlight(text: str, terms: list[str] | None) -> Markup:
    """Jinja 过滤器：把 text 转义后，将 terms 中命中的子串包装为 <mark class="hl">。

    顺序：先全文转义 → 再在转义后字符串里替换 → 返回 Markup（标记为 safe）。
    这样既阻挡 LLM 偶发的 <script> 注入，又能保证 highlight 部分被识别为 HTML。
    """
    if not text:
        return Markup("")
    if not terms:
        return escape(text)
    escaped = str(escape(text))
    # 长的优先替换，避免短词把长词切碎（"工程师" 先于 "工程"）
    for term in sorted({t for t in terms if t}, key=len, reverse=True):
        term_esc = str(escape(term))
        if term_esc and term_esc in escaped:
            escaped = escaped.replace(term_esc, f'<mark class="hl">{term_esc}</mark>')
    return Markup(escaped)


def render_slides(script: dict) -> str:
    """把脚本 dict 渲染成完整 HTML 字符串。"""
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "j2"]),
    )
    env.filters["hl"] = _highlight
    tmpl = env.get_template("slides.html.j2")
    return tmpl.render(
        title=script["title"],
        theme=script.get("theme", "studio-clean"),
        slides=script["slides"],
    )


def main(script_path: str, out_path: str) -> None:
    banner("10-2 渲染幻灯片 HTML")
    script = json.loads(Path(script_path).read_text(encoding="utf-8"))
    print(
        f"读入脚本：{script_path}（{len(script['slides'])} 张，"
        f"theme={script.get('theme', 'studio-clean')}）"
    )

    html = render_slides(script)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"已生成：{out_path}（{len(html)} 字节）")
    print(f"用浏览器打开预览：file://{out.resolve()}")


if __name__ == "__main__":
    script = sys.argv[1] if len(sys.argv) > 1 else "10_blog_to_video/out/script.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "10_blog_to_video/out/slides.html"
    main(script, out)
