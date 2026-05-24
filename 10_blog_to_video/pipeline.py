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
from __future__ import annotations
import argparse
import asyncio
import datetime as _dt
import importlib
import json
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# 文件名以数字开头不能 import，用 importlib
_outline_mod = importlib.import_module("00_outline")
_script_mod = importlib.import_module("01_script")
_slides_mod = importlib.import_module("02_slides")
_render_mod = importlib.import_module("03_render")
_quality_mod = importlib.import_module("03_quality")
_narrate_mod = importlib.import_module("04_narrate")
_compose_mod = importlib.import_module("05_compose")

from _common import banner


def _parse_style_choices(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    aliases = {
        "1": "studio-clean",
        "clean": "studio-clean",
        "studio": "studio-clean",
        "2": "midnight-tech",
        "midnight": "midnight-tech",
        "tech": "midnight-tech",
        "3": "editorial-contrast",
        "editorial": "editorial-contrast",
        "contrast": "editorial-contrast",
        "auto": "",
        "a": "",
    }
    values: list[str] = []
    for token in raw.replace("，", ",").replace(" ", ",").split(","):
        item = token.strip().lower()
        if not item:
            continue
        item = aliases.get(item, item)
        if item and item in _outline_mod.STYLE_PRESETS and item not in values:
            values.append(item)
    return values or None


def _prompt_style_choices(cli_style: str | None, skip_review: bool) -> list[str] | None:
    choices = _parse_style_choices(cli_style)
    if choices or skip_review:
        return choices

    print()
    print("─" * 60)
    print("  先选视觉风格。可输入编号/名称，可多选逗号分隔；直接回车=让模型自动选。")
    for i, (name, desc) in enumerate(_outline_mod.STYLE_PRESETS.items(), 1):
        print(f"  {i}. {name:<18s} {desc}")
    print("─" * 60)
    try:
        raw = input("> ").strip()
    except EOFError:
        raw = ""
    return _parse_style_choices(raw)


def _write_structured_json(path: Path, obj) -> None:
    if hasattr(obj, "model_dump_json"):
        path.write_text(obj.model_dump_json(indent=2), encoding="utf-8")
    else:
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_feedback(first_line: str = "") -> str:
    if first_line:
        return first_line.strip()
    print("  输入修改提示词（一句话即可）：")
    try:
        return input("> ").strip()
    except EOFError:
        return ""


def _prompt_json_review(label: str, path: Path, regenerate, revise=None) -> dict:
    """JSON 审核暂停。返回最终采用的 dict（可能被用户编辑过、或重新生成过）。"""
    while True:
        print()
        print("─" * 60)
        print(f"  {label}已生成：{path}")
        print(f"  现在是你检查/编辑它的机会（编辑器随便用）。")
        print("  [Enter] 继续  [r] 重新生成  [m] 用提示词修改  [Ctrl-C] 中止")
        print("  也可以直接输入一句修改意见。")
        print("─" * 60)
        try:
            raw = input("> ").strip()
        except EOFError:
            raw = ""
        ans = raw.lower()

        if ans == "" or ans == "y":
            # 重新从磁盘读，拿到用户可能的编辑
            return json.loads(path.read_text(encoding="utf-8"))

        if ans == "r":
            print("  重新生成中……")
            _write_structured_json(path, regenerate())
            print(f"  已覆盖：{path}")
            continue

        if ans == "m" or (raw and ans not in {"s", "stop", "q", "quit"}):
            if not revise:
                print("  当前步骤没有配置提示词修改器，请手动编辑文件或重新生成")
                continue
            feedback = _read_feedback("" if ans == "m" else raw)
            if not feedback:
                print("  修改提示词为空，请重试")
                continue
            current = json.loads(path.read_text(encoding="utf-8"))
            print("  按反馈修改中……")
            _write_structured_json(path, revise(current, feedback))
            print(f"  已按反馈覆盖：{path}")
            continue

        print("  无法识别的输入，请重试")


def _prompt_html_review(html_path: Path, script_path: Path, revise_script=None) -> bool:
    """HTML 预览暂停。True 表示继续进入视频产出，False 表示停在 HTML。"""
    while True:
        print()
        print("─" * 60)
        print(f"  HTML 预览已生成：{html_path}")
        print(f"  先打开确认页面效果：file://{html_path.resolve()}")
        print("  [Enter] 继续截图/TTS/MP4  [r] 重新渲染  [m] 用提示词修改  [s] 停在这里")
        print("  也可以直接输入一句修改意见。")
        print("─" * 60)
        try:
            raw = input("> ").strip()
        except EOFError:
            raw = ""
        ans = raw.lower()

        if ans == "" or ans == "y":
            return True
        if ans == "s":
            return False
        if ans == "r":
            script = json.loads(script_path.read_text(encoding="utf-8"))
            html_path.write_text(_slides_mod.render_slides(script), encoding="utf-8")
            print(f"  已重新渲染：{html_path}")
            continue

        if ans == "m" or (raw and ans not in {"s", "stop", "q", "quit"}):
            if not revise_script:
                print("  当前步骤没有配置提示词修改器，请手动编辑 script.json 或重新渲染")
                continue
            feedback = _read_feedback("" if ans == "m" else raw)
            if not feedback:
                print("  修改提示词为空，请重试")
                continue
            current = json.loads(script_path.read_text(encoding="utf-8"))
            print("  按反馈修改 script.json 并重新渲染 HTML……")
            _write_structured_json(script_path, revise_script(current, feedback))
            script = json.loads(script_path.read_text(encoding="utf-8"))
            html_path.write_text(_slides_mod.render_slides(script), encoding="utf-8")
            print(f"  已更新：{script_path}")
            print(f"  已重新渲染：{html_path}")
            continue

        print("  无法识别的输入，请重试")


def _prompt_quality_repair(quality_report: dict, png_dir: Path) -> str:
    print()
    print("─" * 60)
    print("  视觉预检未通过，已停在 MP4 之前。")
    print(f"  先看截图目录：{png_dir}")
    print("  [m] 输入提示词修改  [i] 忽略质量继续  [s] 停在这里")
    print("─" * 60)
    try:
        raw = input("> ").strip()
    except EOFError:
        raw = "s"
    ans = raw.lower()
    if ans in {"i", "ignore"}:
        return "__ignore__"
    if ans in {"s", "stop", "q", "quit"}:
        return "__stop__"
    if ans == "m":
        return _read_feedback()
    if raw:
        return raw
    return "__stop__"


def run(
    blog_path: Path,
    out_dir: Path,
    skip_review: bool = False,
    preview_only: bool = False,
    ignore_quality: bool = False,
    style_choices: list[str] | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    outline_path = out_dir / "outline.json"
    script_path = out_dir / "script.json"
    html_path = out_dir / "slides.html"
    quality_report_path = out_dir / "quality_report.json"
    png_dir = out_dir / "png"
    audio_dir = out_dir / "audio"
    video_path = out_dir / "video.mp4"

    t0 = time.time()

    # ⓪ 视觉大纲：先定主题、叙事弧和每页 layout
    banner("⓪ 生成视觉大纲")
    blog = blog_path.read_text(encoding="utf-8")
    if style_choices:
        print(f"  视觉风格候选：{', '.join(style_choices)}")
    outline_obj = _outline_mod.generate_outline(blog, style_choices=style_choices)
    _write_structured_json(outline_path, outline_obj)
    print(f"  {len(outline_obj.beats)} 页设计节拍，theme={outline_obj.theme} → {outline_path.name}")
    t_outline = time.time()
    print(f"  耗时 {t_outline - t0:.1f}s")

    if skip_review:
        outline = json.loads(outline_path.read_text(encoding="utf-8"))
    else:
        outline = _prompt_json_review(
            "视觉大纲",
            outline_path,
            lambda: _outline_mod.generate_outline(blog, style_choices=style_choices),
            lambda current, feedback: _outline_mod.revise_outline(
                blog,
                current,
                feedback,
                style_choices=style_choices,
            ),
        )

    # ① 脚本生成：按 outline 填字段和旁白
    banner("① 生成脚本")
    script_obj = _script_mod.generate_script(blog, outline=outline)
    _write_structured_json(script_path, script_obj)
    print(f"  {len(script_obj.slides)} 张幻灯片，theme={script_obj.theme} → {script_path.name}")
    t1 = time.time()
    print(f"  耗时 {t1 - t_outline:.1f}s")

    if skip_review:
        script = json.loads(script_path.read_text(encoding="utf-8"))
    else:
        script = _prompt_json_review(
            "脚本",
            script_path,
            lambda: _script_mod.generate_script(
                blog,
                outline=json.loads(outline_path.read_text(encoding="utf-8")),
            ),
            lambda current, feedback: _script_mod.revise_script(
                blog,
                current,
                feedback,
                outline=json.loads(outline_path.read_text(encoding="utf-8")),
            ),
        )
    t_review = time.time()

    # ② 渲染 HTML
    banner("② 渲染幻灯片 HTML")
    html = _slides_mod.render_slides(script)
    html_path.write_text(html, encoding="utf-8")
    print(f"  {len(html)} 字节 → {html_path.name}")
    t2 = time.time()
    print(f"  耗时 {t2 - t_review:.1f}s")

    if preview_only:
        print(f"  --preview-only：停在 HTML 预览，不进入 MP4：file://{html_path.resolve()}")
        return html_path

    if not skip_review and not _prompt_html_review(
        html_path,
        script_path,
        lambda current, feedback: _script_mod.revise_script(
            blog,
            current,
            feedback,
            outline=json.loads(outline_path.read_text(encoding="utf-8")),
        ),
    ):
        print(f"  已停在 HTML 预览阶段：file://{html_path.resolve()}")
        return html_path
    script = json.loads(script_path.read_text(encoding="utf-8"))

    while True:
        # ③ 截图
        banner("③ Playwright 截图")
        pngs = _render_mod.render_pngs(html_path, png_dir)
        t3 = time.time()
        print(f"  {len(pngs)} 张 PNG，耗时 {t3 - t2:.1f}s")

        # ③.5 HTML 视觉预检：失败时停在 PNG/HTML 阶段，不浪费 TTS 和 MP4 合成时间
        banner("③.5 HTML 视觉预检")
        quality_report = _quality_mod.inspect_html(
            html_path,
            report_path=quality_report_path,
        )
        _quality_mod.print_report(quality_report)
        print(f"  报告：{quality_report_path}")
        if quality_report["passed"]:
            break
        if ignore_quality:
            print("  [warn] 视觉预检未通过，但 --ignore-quality 已开启，继续生成视频")
            break
        if skip_review:
            raise RuntimeError(
                "HTML 视觉预检未通过，已在 MP4 前停止。"
                f"请先检查 {quality_report_path} 和 {png_dir}。"
            )
        feedback = _prompt_quality_repair(quality_report, png_dir)
        if feedback == "__ignore__":
            break
        if feedback == "__stop__":
            print(f"  已停在 PNG/HTML 阶段：file://{html_path.resolve()}")
            return html_path
        current = json.loads(script_path.read_text(encoding="utf-8"))
        repair_prompt = (
            f"{feedback}\n\n"
            "下面是自动视觉预检报告，请优先修复 fail 项；页面底部是字幕安全区，"
            "不要把关键文字放到底部。\n"
            f"{json.dumps(quality_report, ensure_ascii=False, indent=2)}"
        )
        print("  按反馈修复 script.json 并重新渲染 HTML……")
        _write_structured_json(
            script_path,
            _script_mod.revise_script(
                blog,
                current,
                repair_prompt,
                outline=json.loads(outline_path.read_text(encoding="utf-8")),
            ),
        )
        script = json.loads(script_path.read_text(encoding="utf-8"))
        html_path.write_text(_slides_mod.render_slides(script), encoding="utf-8")
        print(f"  已重新渲染：{html_path}")

    # ④ TTS + SRT（并发）
    banner("④ edge-tts 合成旁白 + SRT")
    narrations = [s["narration"] for s in script["slides"]]
    pairs = asyncio.run(_narrate_mod.synthesize_all(narrations, audio_dir))
    t4 = time.time()
    print(f"  {len(pairs)} 对 mp3+srt，耗时 {t4 - t3:.1f}s")

    # ⑤ 视频合成（含烧字幕）
    banner("⑤ MoviePy 合成视频（含烧字幕）")
    _compose_mod.compose_video(png_dir, audio_dir, video_path)
    t5 = time.time()
    print(f"  耗时 {t5 - t4:.1f}s")

    print()
    print("=" * 60)
    print(f"  ✓ 设计/脚本 {t1 - t0:.1f}s  +  渲染合成 {t5 - t_review:.1f}s")
    print(f"  →  {video_path}")
    print(f"  →  {video_path.with_suffix('.srt')}（软字幕）")
    print("=" * 60)
    return video_path


def _make_run_dir(base: Path, name: str | None = None) -> Path:
    """在 base/ 下建一个独立子目录给本次运行用，避免覆盖上一次产物。

    默认子目录名是 run-<时间戳>；--name 可以指定有意义的名字（例如 'harness-v2'）。
    顺便维护 base/latest -> <run_dir> 软链接，方便 `open out/latest/video.mp4`。
    """
    base.mkdir(parents=True, exist_ok=True)
    if name:
        run_dir = base / name
    else:
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        run_dir = base / f"run-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # latest 软链（best-effort：Windows 普通用户可能没权限，失败就跳过）
    latest = base / "latest"
    try:
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(run_dir.name)  # 指向相对路径，移动 base 整个目录也不会断
    except OSError:
        pass
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="博客 → 讲解视频 pipeline")
    parser.add_argument(
        "blog",
        nargs="?",
        default=str(Path(__file__).parent / "examples" / "sample_blog.md"),
        help="输入博客 markdown 路径",
    )
    parser.add_argument(
        "-o", "--out",
        default=str(Path(__file__).parent / "out"),
        help="输出根目录（默认 10_blog_to_video/out），每次跑会在它下面建一个 run-时间戳/ 子目录",
    )
    parser.add_argument(
        "-n", "--name",
        default=None,
        help="给本次运行起个有意义的子目录名（默认 run-YYYYMMDD-HHMMSS）",
    )
    parser.add_argument(
        "--style",
        default=None,
        help=(
            "视觉风格偏好：studio-clean / midnight-tech / editorial-contrast；"
            "可用逗号多选，默认交互选择或自动选择"
        ),
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="跳过大纲/脚本/HTML 预览暂停（CI 友好）",
    )
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="只生成 outline.json、script.json、slides.html，不进入截图/TTS/MP4",
    )
    parser.add_argument(
        "--ignore-quality",
        action="store_true",
        help="视觉预检失败也继续进入 TTS/MP4（默认失败即停）",
    )
    args = parser.parse_args()

    blog = Path(args.blog)
    if not blog.exists():
        sys.exit(f"博客文件不存在：{blog}")

    run_dir = _make_run_dir(Path(args.out), name=args.name)
    print(f"[pipeline] 本次输出目录：{run_dir}")
    style_choices = _prompt_style_choices(args.style, skip_review=args.yes)
    run(
        blog,
        run_dir,
        skip_review=args.yes,
        preview_only=args.preview_only,
        ignore_quality=args.ignore_quality,
        style_choices=style_choices,
    )


if __name__ == "__main__":
    main()
