"""
10 · 博客 → 视频  端到端 pipeline
学到：5 个独立模块（脚本/幻灯片/截图/旁白/合成）按顺序串起来，
     每一步的产物都落盘，方便单独重跑、单独调试。

用法：
    python 10_blog_to_video/pipeline.py [blog.md] [-o out_dir] [-y] [--preview-only]

参数：
    blog.md     输入博客 Markdown，缺省用 examples/sample_blog.md
    -o, --out   输出目录，缺省 10_blog_to_video/out
    --style     视觉风格偏好，可填一个或多个逗号分隔的 theme
    -y, --yes   跳过大纲/脚本/HTML 预览暂停（CI / 不需要手动调时用）
    --preview-only 只生成 outline/script/slides.html，不进入截图、TTS、MP4
    --ignore-quality 视觉预检失败也继续进入 TTS/MP4

# 关键设计：先设计/预览，再产出 MP4
页面效果问题必须在 MP4 之前解决：
  ⓪ 先生成 outline.json：主题、叙事弧、每页 layout 和视觉意图
  ① 再按 outline 生成 script.json：短文案 + 旁白
  ② 渲染 slides.html 后暂停，确认页面效果
  ③ 截图并做 HTML 视觉预检
  ④-⑤ 只有页面通过预检后，才 TTS、合成视频

这对应 Presenta 的 Analyze/Design/Generate、HTMLSlides 的组件选择、Starry Slides 的
HTML 源文件可编辑路线。人的审核点放在"便宜且可修改"的位置，而不是视频合成后。

为什么这一版不用 LangGraph？
  - 当前仍是线性工作流，只是多了大纲和 HTML 冻结点
  - 等你想加 critic loop（"看渲染结果不满意就让 LLM 重写这页"），再升级
  - 当前的 input() 暂停就是最朴素的"人在回路"，已经覆盖 80% 场景
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import argparse  # 导入 argparse 命令行解析
import asyncio  # 导入 asyncio 异步库
import datetime as _dt  # 执行本行逻辑
import importlib  # 执行本行逻辑
import json  # 导入 json 标准库
import sys  # 导入 sys 标准库
import time  # 导入 time 时间模块
from pathlib import Path  # 导入 Path 处理路径

sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径
sys.path.insert(0, str(Path(__file__).resolve().parent))  # 执行本行逻辑

# 文件名以数字开头不能 import，用 importlib
_outline_mod = importlib.import_module("00_outline")  # 赋值给 _outline_mod
_script_mod = importlib.import_module("01_script")  # 赋值给 _script_mod
_slides_mod = importlib.import_module("02_slides")  # 赋值给 _slides_mod
_render_mod = importlib.import_module("03_render")  # 赋值给 _render_mod
_quality_mod = importlib.import_module("03_quality")  # 赋值给 _quality_mod
_narrate_mod = importlib.import_module("04_narrate")  # 赋值给 _narrate_mod
_compose_mod = importlib.import_module("05_compose")  # 赋值给 _compose_mod

from _common import banner  # 导入项目共享 LLM/Embedding 配置


def _parse_style_choices(raw: str | None) -> list[str] | None:  # 定义函数
    if not raw:  # 代码块起始
        return None  # 返回结果
    aliases = {  # 赋值给 aliases
        "1": "studio-clean",  # 字符串/template 参数
        "clean": "studio-clean",  # 字符串/template 参数
        "studio": "studio-clean",  # 字符串/template 参数
        "2": "midnight-tech",  # 字符串/template 参数
        "midnight": "midnight-tech",  # 字符串/template 参数
        "tech": "midnight-tech",  # 字符串/template 参数
        "3": "editorial-contrast",  # 字符串/template 参数
        "editorial": "editorial-contrast",  # 字符串/template 参数
        "contrast": "editorial-contrast",  # 字符串/template 参数
        "auto": "",  # 字符串/template 参数
        "a": "",  # 字符串/template 参数
    }  # 闭合括号/元组/字典
    values: list[str] = []  # 赋值给 list[str]
    for token in raw.replace("，", ",").replace(" ", ",").split(","):  # for 循环
        item = token.strip().lower()  # 赋值给 item
        if not item:  # 代码块起始
            continue  # 跳过本次循环
        item = aliases.get(item, item)  # 赋值给 item
        if item and item in _outline_mod.STYLE_PRESETS and item not in values:  # 代码块起始
            values.append(item)  # 执行本行逻辑
    return values or None  # 返回结果


def _prompt_style_choices(cli_style: str | None, skip_review: bool) -> list[str] | None:  # 定义函数
    choices = _parse_style_choices(cli_style)  # 赋值给 choices
    if choices or skip_review:  # 代码块起始
        return choices  # 返回结果

    print()  # 打印输出
    print("─" * 60)  # 打印输出
    print("  先选视觉风格。可输入编号/名称，可多选逗号分隔；直接回车=让模型自动选。")  # 打印输出
    for i, (name, desc) in enumerate(_outline_mod.STYLE_PRESETS.items(), 1):  # for 循环
        print(f"  {i}. {name:<18s} {desc}")  # 打印输出
    print("─" * 60)  # 打印输出
    try:  # 代码块起始
        raw = input("> ").strip()  # 赋值给 raw
    except EOFError:  # 捕获异常
        raw = ""  # 赋值给 raw
    return _parse_style_choices(raw)  # 返回结果


def _write_structured_json(path: Path, obj) -> None:  # 定义函数
    if hasattr(obj, "model_dump_json"):  # 代码块起始
        path.write_text(obj.model_dump_json(indent=2), encoding="utf-8")  # 执行本行逻辑
    else:  # else 分支
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")  # 执行本行逻辑


def _read_feedback(first_line: str = "") -> str:  # 定义函数
    if first_line:  # 代码块起始
        return first_line.strip()  # 返回结果
    print("  输入修改提示词（一句话即可）：")  # 打印输出
    try:  # 代码块起始
        return input("> ").strip()  # 返回结果
    except EOFError:  # 捕获异常
        return ""  # 返回结果


def _prompt_json_review(label: str, path: Path, regenerate, revise=None) -> dict:  # 定义函数
    """JSON 审核暂停。返回最终采用的 dict（可能被用户编辑过、或重新生成过）。"""
    while True:  # while 循环
        print()  # 打印输出
        print("─" * 60)  # 打印输出
        print(f"  {label}已生成：{path}")  # 打印输出
        print(f"  现在是你检查/编辑它的机会（编辑器随便用）。")  # 打印输出
        print("  [Enter] 继续  [r] 重新生成  [m] 用提示词修改  [Ctrl-C] 中止")  # 打印输出
        print("  也可以直接输入一句修改意见。")  # 打印输出
        print("─" * 60)  # 打印输出
        try:  # 代码块起始
            raw = input("> ").strip()  # 赋值给 raw
        except EOFError:  # 捕获异常
            raw = ""  # 赋值给 raw
        ans = raw.lower()  # 赋值给 ans

        if ans == "" or ans == "y":  # 代码块起始
            # 重新从磁盘读，拿到用户可能的编辑
            return json.loads(path.read_text(encoding="utf-8"))  # 返回结果

        if ans == "r":  # 代码块起始
            print("  重新生成中……")  # 打印输出
            _write_structured_json(path, regenerate())  # 执行本行逻辑
            print(f"  已覆盖：{path}")  # 打印输出
            continue  # 跳过本次循环

        if ans == "m" or (raw and ans not in {"s", "stop", "q", "quit"}):  # 代码块起始
            if not revise:  # 代码块起始
                print("  当前步骤没有配置提示词修改器，请手动编辑文件或重新生成")  # 打印输出
                continue  # 跳过本次循环
            feedback = _read_feedback("" if ans == "m" else raw)  # 赋值给 feedback
            if not feedback:  # 代码块起始
                print("  修改提示词为空，请重试")  # 打印输出
                continue  # 跳过本次循环
            current = json.loads(path.read_text(encoding="utf-8"))  # 赋值给 current
            print("  按反馈修改中……")  # 打印输出
            _write_structured_json(path, revise(current, feedback))  # 执行本行逻辑
            print(f"  已按反馈覆盖：{path}")  # 打印输出
            continue  # 跳过本次循环

        print("  无法识别的输入，请重试")  # 打印输出


def _prompt_html_review(html_path: Path, script_path: Path, revise_script=None) -> bool:  # 定义函数
    """HTML 预览暂停。True 表示继续进入视频产出，False 表示停在 HTML。"""
    while True:  # while 循环
        print()  # 打印输出
        print("─" * 60)  # 打印输出
        print(f"  HTML 预览已生成：{html_path}")  # 打印输出
        print(f"  先打开确认页面效果：file://{html_path.resolve()}")  # 打印输出
        print("  [Enter] 继续截图/TTS/MP4  [r] 重新渲染  [m] 用提示词修改  [s] 停在这里")  # 打印输出
        print("  也可以直接输入一句修改意见。")  # 打印输出
        print("─" * 60)  # 打印输出
        try:  # 代码块起始
            raw = input("> ").strip()  # 赋值给 raw
        except EOFError:  # 捕获异常
            raw = ""  # 赋值给 raw
        ans = raw.lower()  # 赋值给 ans

        if ans == "" or ans == "y":  # 代码块起始
            return True  # 返回结果
        if ans == "s":  # 代码块起始
            return False  # 返回结果
        if ans == "r":  # 代码块起始
            script = json.loads(script_path.read_text(encoding="utf-8"))  # 赋值给 script
            html_path.write_text(_slides_mod.render_slides(script), encoding="utf-8")  # 执行本行逻辑
            print(f"  已重新渲染：{html_path}")  # 打印输出
            continue  # 跳过本次循环

        if ans == "m" or (raw and ans not in {"s", "stop", "q", "quit"}):  # 代码块起始
            if not revise_script:  # 代码块起始
                print("  当前步骤没有配置提示词修改器，请手动编辑 script.json 或重新渲染")  # 打印输出
                continue  # 跳过本次循环
            feedback = _read_feedback("" if ans == "m" else raw)  # 赋值给 feedback
            if not feedback:  # 代码块起始
                print("  修改提示词为空，请重试")  # 打印输出
                continue  # 跳过本次循环
            current = json.loads(script_path.read_text(encoding="utf-8"))  # 赋值给 current
            print("  按反馈修改 script.json 并重新渲染 HTML……")  # 打印输出
            _write_structured_json(script_path, revise_script(current, feedback))  # 执行本行逻辑
            script = json.loads(script_path.read_text(encoding="utf-8"))  # 赋值给 script
            html_path.write_text(_slides_mod.render_slides(script), encoding="utf-8")  # 执行本行逻辑
            print(f"  已更新：{script_path}")  # 打印输出
            print(f"  已重新渲染：{html_path}")  # 打印输出
            continue  # 跳过本次循环

        print("  无法识别的输入，请重试")  # 打印输出


def _prompt_quality_repair(quality_report: dict, png_dir: Path) -> str:  # 定义函数
    print()  # 打印输出
    print("─" * 60)  # 打印输出
    print("  视觉预检未通过，已停在 MP4 之前。")  # 打印输出
    print(f"  先看截图目录：{png_dir}")  # 打印输出
    print("  [m] 输入提示词修改  [i] 忽略质量继续  [s] 停在这里")  # 打印输出
    print("─" * 60)  # 打印输出
    try:  # 代码块起始
        raw = input("> ").strip()  # 赋值给 raw
    except EOFError:  # 捕获异常
        raw = "s"  # 赋值给 raw
    ans = raw.lower()  # 赋值给 ans
    if ans in {"i", "ignore"}:  # 代码块起始
        return "__ignore__"  # 返回结果
    if ans in {"s", "stop", "q", "quit"}:  # 代码块起始
        return "__stop__"  # 返回结果
    if ans == "m":  # 代码块起始
        return _read_feedback()  # 返回结果
    if raw:  # 代码块起始
        return raw  # 返回结果
    return "__stop__"  # 返回结果


def run(  # 定义函数
    blog_path: Path,  # 执行本行逻辑
    out_dir: Path,  # 执行本行逻辑
    skip_review: bool = False,  # 赋值给 bool
    preview_only: bool = False,  # 赋值给 bool
    ignore_quality: bool = False,  # 赋值给 bool
    style_choices: list[str] | None = None,  # 赋值给 None
) -> Path:  # 代码块起始
    out_dir.mkdir(parents=True, exist_ok=True)  # 执行本行逻辑

    outline_path = out_dir / "outline.json"  # 赋值给 outline_path
    script_path = out_dir / "script.json"  # 赋值给 script_path
    html_path = out_dir / "slides.html"  # 赋值给 html_path
    quality_report_path = out_dir / "quality_report.json"  # 赋值给 quality_report_path
    png_dir = out_dir / "png"  # 赋值给 png_dir
    audio_dir = out_dir / "audio"  # 赋值给 audio_dir
    video_path = out_dir / "video.mp4"  # 赋值给 video_path

    t0 = time.time()  # 赋值给 t0

    # ⓪ 视觉大纲：先定主题、叙事弧和每页 layout
    banner("⓪ 生成视觉大纲")  # 打印章节标题分隔条
    blog = blog_path.read_text(encoding="utf-8")  # 赋值给 blog
    if style_choices:  # 代码块起始
        print(f"  视觉风格候选：{', '.join(style_choices)}")  # 打印输出
    outline_obj = _outline_mod.generate_outline(blog, style_choices=style_choices)  # 赋值给 outline_obj
    _write_structured_json(outline_path, outline_obj)  # 执行本行逻辑
    print(f"  {len(outline_obj.beats)} 页设计节拍，theme={outline_obj.theme} → {outline_path.name}")  # 打印输出
    t_outline = time.time()  # 赋值给 t_outline
    print(f"  耗时 {t_outline - t0:.1f}s")  # 打印输出

    if skip_review:  # 代码块起始
        outline = json.loads(outline_path.read_text(encoding="utf-8"))  # 赋值给 outline
    else:  # else 分支
        outline = _prompt_json_review(  # 赋值给 outline
            "视觉大纲",  # 字符串/template 参数
            outline_path,  # 序列/元组元素
            lambda: _outline_mod.generate_outline(blog, style_choices=style_choices),  # 执行本行逻辑
            lambda current, feedback: _outline_mod.revise_outline(  # lambda 匿名函数
                blog,  # 序列/元组元素
                current,  # 序列/元组元素
                feedback,  # 序列/元组元素
                style_choices=style_choices,  # 执行本行逻辑
            ),  # 闭合括号/元组/字典
        )  # 闭合括号/元组/字典

    # ① 脚本生成：按 outline 填字段和旁白
    banner("① 生成脚本")  # 打印章节标题分隔条
    script_obj = _script_mod.generate_script(blog, outline=outline)  # 赋值给 script_obj
    _write_structured_json(script_path, script_obj)  # 执行本行逻辑
    print(f"  {len(script_obj.slides)} 张幻灯片，theme={script_obj.theme} → {script_path.name}")  # 打印输出
    t1 = time.time()  # 赋值给 t1
    print(f"  耗时 {t1 - t_outline:.1f}s")  # 打印输出

    if skip_review:  # 代码块起始
        script = json.loads(script_path.read_text(encoding="utf-8"))  # 赋值给 script
    else:  # else 分支
        script = _prompt_json_review(  # 赋值给 script
            "脚本",  # 字符串/template 参数
            script_path,  # 序列/元组元素
            lambda: _script_mod.generate_script(  # 执行本行逻辑
                blog,  # 序列/元组元素
                outline=json.loads(outline_path.read_text(encoding="utf-8")),  # 执行本行逻辑
            ),  # 闭合括号/元组/字典
            lambda current, feedback: _script_mod.revise_script(  # lambda 匿名函数
                blog,  # 序列/元组元素
                current,  # 序列/元组元素
                feedback,  # 序列/元组元素
                outline=json.loads(outline_path.read_text(encoding="utf-8")),  # 执行本行逻辑
            ),  # 闭合括号/元组/字典
        )  # 闭合括号/元组/字典
    t_review = time.time()  # 赋值给 t_review

    # ② 渲染 HTML
    banner("② 渲染幻灯片 HTML")  # 打印章节标题分隔条
    html = _slides_mod.render_slides(script)  # 赋值给 html
    html_path.write_text(html, encoding="utf-8")  # 执行本行逻辑
    print(f"  {len(html)} 字节 → {html_path.name}")  # 打印输出
    t2 = time.time()  # 赋值给 t2
    print(f"  耗时 {t2 - t_review:.1f}s")  # 打印输出

    if preview_only:  # 代码块起始
        print(f"  --preview-only：停在 HTML 预览，不进入 MP4：file://{html_path.resolve()}")  # 打印输出
        return html_path  # 返回结果

    if not skip_review and not _prompt_html_review(  # 执行本行逻辑
        html_path,  # 序列/元组元素
        script_path,  # 序列/元组元素
        lambda current, feedback: _script_mod.revise_script(  # lambda 匿名函数
            blog,  # 序列/元组元素
            current,  # 序列/元组元素
            feedback,  # 序列/元组元素
            outline=json.loads(outline_path.read_text(encoding="utf-8")),  # 执行本行逻辑
        ),  # 闭合括号/元组/字典
    ):  # 代码块起始
        print(f"  已停在 HTML 预览阶段：file://{html_path.resolve()}")  # 打印输出
        return html_path  # 返回结果
    script = json.loads(script_path.read_text(encoding="utf-8"))  # 赋值给 script

    while True:  # while 循环
        # ③ 截图
        banner("③ Playwright 截图")  # 打印章节标题分隔条
        pngs = _render_mod.render_pngs(html_path, png_dir)  # 赋值给 pngs
        t3 = time.time()  # 赋值给 t3
        print(f"  {len(pngs)} 张 PNG，耗时 {t3 - t2:.1f}s")  # 打印输出

        # ③.5 HTML 视觉预检：失败时停在 PNG/HTML 阶段，不浪费 TTS 和 MP4 合成时间
        banner("③.5 HTML 视觉预检")  # 打印章节标题分隔条
        quality_report = _quality_mod.inspect_html(  # 赋值给 quality_report
            html_path,  # 序列/元组元素
            report_path=quality_report_path,  # 执行本行逻辑
        )  # 闭合括号/元组/字典
        _quality_mod.print_report(quality_report)  # 执行本行逻辑
        print(f"  报告：{quality_report_path}")  # 打印输出
        if quality_report["passed"]:  # 代码块起始
            break  # 跳出循环
        if ignore_quality:  # 代码块起始
            print("  [warn] 视觉预检未通过，但 --ignore-quality 已开启，继续生成视频")  # 打印输出
            break  # 跳出循环
        if skip_review:  # 代码块起始
            raise RuntimeError(  # 抛出异常
                "HTML 视觉预检未通过，已在 MP4 前停止。"  # 字符串/template 参数
                f"请先检查 {quality_report_path} 和 {png_dir}。"  # 字符串/template 参数
            )  # 闭合括号/元组/字典
        feedback = _prompt_quality_repair(quality_report, png_dir)  # 赋值给 feedback
        if feedback == "__ignore__":  # 代码块起始
            break  # 跳出循环
        if feedback == "__stop__":  # 代码块起始
            print(f"  已停在 PNG/HTML 阶段：file://{html_path.resolve()}")  # 打印输出
            return html_path  # 返回结果
        current = json.loads(script_path.read_text(encoding="utf-8"))  # 赋值给 current
        repair_prompt = (  # 赋值给 repair_prompt
            f"{feedback}\n\n"  # 字符串/template 参数
            "下面是自动视觉预检报告，请优先修复 fail 项；页面底部是字幕安全区，"  # 字符串/template 参数
            "不要把关键文字放到底部。\n"  # 字符串/template 参数
            f"{json.dumps(quality_report, ensure_ascii=False, indent=2)}"  # 字符串/template 参数
        )  # 闭合括号/元组/字典
        print("  按反馈修复 script.json 并重新渲染 HTML……")  # 打印输出
        _write_structured_json(  # 执行本行逻辑
            script_path,  # 序列/元组元素
            _script_mod.revise_script(  # 执行本行逻辑
                blog,  # 序列/元组元素
                current,  # 序列/元组元素
                repair_prompt,  # 序列/元组元素
                outline=json.loads(outline_path.read_text(encoding="utf-8")),  # 执行本行逻辑
            ),  # 闭合括号/元组/字典
        )  # 闭合括号/元组/字典
        script = json.loads(script_path.read_text(encoding="utf-8"))  # 赋值给 script
        html_path.write_text(_slides_mod.render_slides(script), encoding="utf-8")  # 执行本行逻辑
        print(f"  已重新渲染：{html_path}")  # 打印输出

    # ④ TTS + SRT（并发）
    banner("④ edge-tts 合成旁白 + SRT")  # 打印章节标题分隔条
    narrations = [s["narration"] for s in script["slides"]]  # for 循环
    pairs = asyncio.run(_narrate_mod.synthesize_all(narrations, audio_dir))  # 赋值给 pairs
    t4 = time.time()  # 赋值给 t4
    print(f"  {len(pairs)} 对 mp3+srt，耗时 {t4 - t3:.1f}s")  # 打印输出

    # ⑤ 视频合成（含烧字幕）
    banner("⑤ MoviePy 合成视频（含烧字幕）")  # 打印章节标题分隔条
    _compose_mod.compose_video(png_dir, audio_dir, video_path)  # 执行本行逻辑
    t5 = time.time()  # 赋值给 t5
    print(f"  耗时 {t5 - t4:.1f}s")  # 打印输出

    print()  # 打印输出
    print("=" * 60)  # 打印输出
    print(f"  ✓ 设计/脚本 {t1 - t0:.1f}s  +  渲染合成 {t5 - t_review:.1f}s")  # 打印输出
    print(f"  →  {video_path}")  # 打印输出
    print(f"  →  {video_path.with_suffix('.srt')}（软字幕）")  # 打印输出
    print("=" * 60)  # 打印输出
    return video_path  # 返回结果


def _make_run_dir(base: Path, name: str | None = None) -> Path:  # 定义函数
    """在 base/ 下建一个独立子目录给本次运行用，避免覆盖上一次产物。

    默认子目录名是 run-<时间戳>；--name 可以指定有意义的名字（例如 'harness-v2'）。
    顺便维护 base/latest -> <run_dir> 软链接，方便 `open out/latest/video.mp4`。
    """
    base.mkdir(parents=True, exist_ok=True)  # 执行本行逻辑
    if name:  # 代码块起始
        run_dir = base / name  # 赋值给 run_dir
    else:  # else 分支
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")  # 赋值给 stamp
        run_dir = base / f"run-{stamp}"  # 赋值给 run_dir
    run_dir.mkdir(parents=True, exist_ok=True)  # 执行本行逻辑

    # latest 软链（best-effort：Windows 普通用户可能没权限，失败就跳过）
    latest = base / "latest"  # 赋值给 latest
    try:  # 代码块起始
        if latest.is_symlink() or latest.exists():  # 代码块起始
            latest.unlink()  # 执行本行逻辑
        latest.symlink_to(run_dir.name)  # 指向相对路径，移动 base 整个目录也不会断
    except OSError:  # 捕获异常
        pass  # 占位语句
    return run_dir  # 返回结果


def main() -> None:  # demo 入口函数
    parser = argparse.ArgumentParser(description="博客 → 讲解视频 pipeline")  # 赋值给 parser
    parser.add_argument(  # 执行本行逻辑
        "blog",  # 字符串/template 参数
        nargs="?",  # 执行本行逻辑
        default=str(Path(__file__).parent / "examples" / "sample_blog.md"),  # 执行本行逻辑
        help="输入博客 markdown 路径",  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    parser.add_argument(  # 执行本行逻辑
        "-o", "--out",  # 字符串/template 参数
        default=str(Path(__file__).parent / "out"),  # 执行本行逻辑
        help="输出根目录（默认 10_blog_to_video/out），每次跑会在它下面建一个 run-时间戳/ 子目录",  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    parser.add_argument(  # 执行本行逻辑
        "-n", "--name",  # 字符串/template 参数
        default=None,  # 执行本行逻辑
        help="给本次运行起个有意义的子目录名（默认 run-YYYYMMDD-HHMMSS）",  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    parser.add_argument(  # 执行本行逻辑
        "--style",  # 字符串/template 参数
        default=None,  # 执行本行逻辑
        help=(  # 执行本行逻辑
            "视觉风格偏好：studio-clean / midnight-tech / editorial-contrast；"  # 字符串/template 参数
            "可用逗号多选，默认交互选择或自动选择"  # 字符串/template 参数
        ),  # 闭合括号/元组/字典
    )  # 闭合括号/元组/字典
    parser.add_argument(  # 执行本行逻辑
        "-y", "--yes",  # 字符串/template 参数
        action="store_true",  # 执行本行逻辑
        help="跳过大纲/脚本/HTML 预览暂停（CI 友好）",  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    parser.add_argument(  # 执行本行逻辑
        "--preview-only",  # 字符串/template 参数
        action="store_true",  # 执行本行逻辑
        help="只生成 outline.json、script.json、slides.html，不进入截图/TTS/MP4",  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    parser.add_argument(  # 执行本行逻辑
        "--ignore-quality",  # 字符串/template 参数
        action="store_true",  # 执行本行逻辑
        help="视觉预检失败也继续进入 TTS/MP4（默认失败即停）",  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    args = parser.parse_args()  # 赋值给 args

    blog = Path(args.blog)  # 赋值给 blog
    if not blog.exists():  # 代码块起始
        sys.exit(f"博客文件不存在：{blog}")  # 执行本行逻辑

    run_dir = _make_run_dir(Path(args.out), name=args.name)  # 赋值给 run_dir
    print(f"[pipeline] 本次输出目录：{run_dir}")  # 打印输出
    style_choices = _prompt_style_choices(args.style, skip_review=args.yes)  # 赋值给 style_choices
    run(  # 执行本行逻辑
        blog,  # 序列/元组元素
        run_dir,  # 序列/元组元素
        skip_review=args.yes,  # 执行本行逻辑
        preview_only=args.preview_only,  # 执行本行逻辑
        ignore_quality=args.ignore_quality,  # 执行本行逻辑
        style_choices=style_choices,  # 执行本行逻辑
    )  # 闭合括号/元组/字典


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
