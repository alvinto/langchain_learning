"""
10-2 脚本 JSON → 幻灯片 HTML
学到：把 LLM 输出的结构化数据通过 Jinja2 模板渲染成单文件 HTML。
     视觉精美度的天花板在 templates/slides.html.j2（CSS），不在 LLM。

为什么这样拆？
  - LLM 出错时（比如多了一个字段），CSS 不受影响，反之亦然
  - 想换视觉风格只改模板，不重跑 LLM —— 省钱
  - HTML 中间产物可以直接用浏览器打开预览，肉眼调试比看 PNG 快得多
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import json  # 导入 json 标准库
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径

sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from jinja2 import Environment, FileSystemLoader, select_autoescape  # 执行本行逻辑
from markupsafe import Markup, escape  # 执行本行逻辑

from _common import banner  # 导入项目共享 LLM/Embedding 配置

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"  # 赋值给 TEMPLATE_DIR


def _highlight(text: str, terms: list[str] | None) -> Markup:  # 定义函数
    """Jinja 过滤器：把 text 转义后，将 terms 中命中的子串包装为 <mark class="hl">。

    顺序：先全文转义 → 再在转义后字符串里替换 → 返回 Markup（标记为 safe）。
    这样既阻挡 LLM 偶发的 <script> 注入，又能保证 highlight 部分被识别为 HTML。
    """
    if not text:  # 代码块起始
        return Markup("")  # 返回结果
    if not terms:  # 代码块起始
        return escape(text)  # 返回结果
    escaped = str(escape(text))  # 赋值给 escaped
    # 长的优先替换，避免短词把长词切碎（"工程师" 先于 "工程"）
    for term in sorted({t for t in terms if t}, key=len, reverse=True):  # for 循环
        term_esc = str(escape(term))  # 赋值给 term_esc
        if term_esc and term_esc in escaped:  # 代码块起始
            escaped = escaped.replace(term_esc, f'<mark class="hl">{term_esc}</mark>')  # 赋值给 escaped
    return Markup(escaped)  # 返回结果


def render_slides(script: dict) -> str:  # 定义函数
    """把脚本 dict 渲染成完整 HTML 字符串。"""
    env = Environment(  # 赋值给 env
        loader=FileSystemLoader(TEMPLATE_DIR),  # 执行本行逻辑
        autoescape=select_autoescape(["html", "j2"]),  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    env.filters["hl"] = _highlight  # 赋值给 env.filters["hl"]
    tmpl = env.get_template("slides.html.j2")  # 赋值给 tmpl
    return tmpl.render(  # 返回结果
        title=script["title"],  # 执行本行逻辑
        theme=script.get("theme", "studio-clean"),  # 执行本行逻辑
        slides=script["slides"],  # 执行本行逻辑
    )  # 闭合括号/元组/字典


def main(script_path: str, out_path: str) -> None:  # 定义函数
    banner("10-2 渲染幻灯片 HTML")  # 打印章节标题分隔条
    script = json.loads(Path(script_path).read_text(encoding="utf-8"))  # 赋值给 script
    print(  # 打印输出
        f"读入脚本：{script_path}（{len(script['slides'])} 张，"  # 字符串/template 参数
        f"theme={script.get('theme', 'studio-clean')}）"  # 字符串/template 参数
    )  # 闭合括号/元组/字典

    html = render_slides(script)  # 赋值给 html
    out = Path(out_path)  # 赋值给 out
    out.parent.mkdir(parents=True, exist_ok=True)  # 执行本行逻辑
    out.write_text(html, encoding="utf-8")  # 执行本行逻辑
    print(f"已生成：{out_path}（{len(html)} 字节）")  # 打印输出
    print(f"用浏览器打开预览：file://{out.resolve()}")  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    script = sys.argv[1] if len(sys.argv) > 1 else "10_blog_to_video/out/script.json"  # 赋值给 script
    out = sys.argv[2] if len(sys.argv) > 2 else "10_blog_to_video/out/slides.html"  # 赋值给 out
    main(script, out)  # 执行本行逻辑
