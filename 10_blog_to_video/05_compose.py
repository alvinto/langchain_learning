"""
10-5 PNG + MP3 + SRT → MP4 (含烧入字幕)
学到：
  1. MoviePy CompositeVideoClip 把字幕 TextClip 叠在 ImageClip 上 → 硬字幕
  2. 每页 srt 时间是页内相对的，全片合并要按累计页长偏移
  3. MoviePy 2.x (Pillow 后端) 和 1.x (ImageMagick 后端) 的 TextClip 签名不同，
     这里用 try/except 自动适配

兼容 MoviePy 1.x（from moviepy.editor）和 2.x（from moviepy）：
  - 2.x 的方法改名了 set_duration → with_duration、set_audio → with_audio
  - 用 hasattr 自动适配，不强求用户装某个特定版本
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import os  # 导入 os 标准库
import re  # 导入 re 正则模块
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径

sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from _common import banner  # 导入项目共享 LLM/Embedding 配置

# MoviePy 2.x 在 2024-11 发布，import 路径和方法名都变了 —— 同时支持
try:  # 代码块起始
    from moviepy import (  # 执行本行逻辑
        ImageClip,  # 序列/元组元素
        AudioFileClip,  # 序列/元组元素
        TextClip,  # 序列/元组元素
        ColorClip,  # 序列/元组元素
        CompositeVideoClip,  # 序列/元组元素
        concatenate_videoclips,  # 序列/元组元素
    )  # 2.x
except ImportError:  # 捕获异常
    from moviepy.editor import (  # type: ignore
        ImageClip,  # 序列/元组元素
        AudioFileClip,  # 序列/元组元素
        TextClip,  # 序列/元组元素
        ColorClip,  # 序列/元组元素
        CompositeVideoClip,  # 序列/元组元素
        concatenate_videoclips,  # 序列/元组元素
    )  # 闭合括号/元组/字典

VIDEO_W, VIDEO_H = 1920, 1080  # 赋值给 VIDEO_H
# 成片把幻灯片放在上方 16:9 安全画布，底部独立留给硬字幕，避免遮挡页面文字。
SLIDE_AREA_H = 900  # 赋值给 SLIDE_AREA_H
SLIDE_AREA_W = 1600  # 赋值给 SLIDE_AREA_W
SUB_BAND_TOP = SLIDE_AREA_H  # 赋值给 SUB_BAND_TOP
SUB_TOP = SUB_BAND_TOP + 34  # 赋值给 SUB_TOP
SUB_FONT_SIZE = 42  # 赋值给 SUB_FONT_SIZE
# 字幕条宽度（占视频宽度 85%，留两侧边距）
SUB_BOX_WIDTH = int(VIDEO_W * 0.85)  # 赋值给 SUB_BOX_WIDTH


# ---------------- 跨版本兼容 helpers ----------------
def _with_duration(clip, d):  # 定义函数
    return clip.with_duration(d) if hasattr(clip, "with_duration") else clip.set_duration(d)  # 返回结果


def _with_audio(clip, a):  # 定义函数
    return clip.with_audio(a) if hasattr(clip, "with_audio") else clip.set_audio(a)  # 返回结果


def _with_start(clip, s):  # 定义函数
    return clip.with_start(s) if hasattr(clip, "with_start") else clip.set_start(s)  # 返回结果


def _with_position(clip, p):  # 定义函数
    return clip.with_position(p) if hasattr(clip, "with_position") else clip.set_position(p)  # 返回结果


def _resized(clip, *, height: int | None = None, width: int | None = None):  # 定义函数
    if hasattr(clip, "resized"):  # 代码块起始
        return clip.resized(height=height, width=width)  # 返回结果
    return clip.resize(height=height, width=width)  # 返回结果


# ---------------- 中文字体检测 ----------------
def detect_chinese_font() -> str:  # 定义函数
    """返回系统中文字体路径；找不到就返回空字符串（MoviePy 会用默认字体，中文会变方框）。

    通过 CN_FONT 环境变量可强制指定。
    """
    env = os.getenv("CN_FONT")  # 赋值给 env
    if env and Path(env).exists():  # 代码块起始
        return env  # 返回结果
    candidates = [  # 赋值给 candidates
        # macOS
        "/System/Library/Fonts/PingFang.ttc",  # 字符串/template 参数
        "/System/Library/Fonts/STHeiti Medium.ttc",  # 字符串/template 参数
        "/System/Library/Fonts/Hiragino Sans GB.ttc",  # 字符串/template 参数
        # Linux
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # 字符串/template 参数
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",  # 字符串/template 参数
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",  # 字符串/template 参数
        # Windows
        "C:\\Windows\\Fonts\\msyh.ttc",  # 字符串/template 参数
        "C:\\Windows\\Fonts\\msyhbd.ttc",  # 字符串/template 参数
    ]  # 闭合括号/元组/字典
    for p in candidates:  # for 循环
        if Path(p).exists():  # 代码块起始
            return p  # 返回结果
    return ""  # 返回结果


# ---------------- SRT 解析 / 拼接 ----------------
_SRT_TIME = re.compile(  # 编译图为可执行应用
    r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)"  # 执行本行逻辑
)  # 闭合括号/元组/字典


def _t2s(h: int, m: int, s: int, ms: int) -> float:  # 定义函数
    return h * 3600 + m * 60 + s + ms / 1000.0  # 返回结果


def _s2t(sec: float) -> str:  # 定义函数
    h = int(sec // 3600)  # 赋值给 h
    m = int((sec % 3600) // 60)  # 赋值给 m
    s = int(sec % 60)  # 赋值给 s
    ms = int(round((sec - int(sec)) * 1000))  # 赋值给 ms
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"  # 返回结果


def parse_srt(text: str) -> list[tuple[float, float, str]]:  # 定义函数
    """SRT → [(start, end, text), ...]，时间单位为秒。"""
    out: list[tuple[float, float, str]] = []  # 赋值给 str]]
    for block in re.split(r"\n\s*\n", text.strip()):  # for 循环
        lines = block.strip().splitlines()  # 赋值给 lines
        if len(lines) < 2:  # 代码块起始
            continue  # 跳过本次循环
        # 找第一行包含 --> 的，前面那行（如果是数字）当 cue 索引忽略
        time_line_idx = next((i for i, l in enumerate(lines) if "-->" in l), -1)  # for 循环
        if time_line_idx < 0:  # 代码块起始
            continue  # 跳过本次循环
        m = _SRT_TIME.search(lines[time_line_idx])  # 赋值给 m
        if not m:  # 代码块起始
            continue  # 跳过本次循环
        h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, m.groups())  # 赋值给 ms2
        body = "\n".join(lines[time_line_idx + 1 :]).strip()  # 赋值给 body
        if body:  # 代码块起始
            out.append((_t2s(h1, m1, s1, ms1), _t2s(h2, m2, s2, ms2), body))  # 执行本行逻辑
    return out  # 返回结果


def build_global_srt(srt_paths: list[Path], page_durations: list[float], out: Path) -> None:  # 定义函数
    """把每页相对时间的 srt 合并成全片绝对时间的 srt（用于软字幕分发）。"""
    parts: list[str] = []  # 赋值给 list[str]
    idx = 1  # 赋值给 idx
    offset = 0.0  # 赋值给 offset
    for srt_path, dur in zip(srt_paths, page_durations):  # for 循环
        if srt_path.exists():  # 代码块起始
            for start, end, body in parse_srt(srt_path.read_text(encoding="utf-8")):  # for 循环
                parts.append(str(idx))  # 执行本行逻辑
                parts.append(f"{_s2t(start + offset)} --> {_s2t(end + offset)}")  # 执行本行逻辑
                parts.append(body)  # 执行本行逻辑
                parts.append("")  # 执行本行逻辑
                idx += 1  # 执行本行逻辑
        offset += dur  # 执行本行逻辑
    out.write_text("\n".join(parts), encoding="utf-8")  # 执行本行逻辑


# ---------------- 字幕 TextClip 工厂 ----------------
def _make_subtitle_clip(text: str, duration: float, font_path: str):  # 定义函数
    """构造一个底部字幕带里的 TextClip，跨 MoviePy 1.x/2.x 兼容。"""
    common = dict(  # 赋值给 common
        color="white",  # 执行本行逻辑
        stroke_color="black",  # 执行本行逻辑
        stroke_width=3,  # 执行本行逻辑
        method="caption",  # 执行本行逻辑
        size=(SUB_BOX_WIDTH, None),  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    try:  # 代码块起始
        # MoviePy 2.x：font_size / text=
        clip = TextClip(  # 赋值给 clip
            text=text,  # 执行本行逻辑
            font=font_path or None,  # 执行本行逻辑
            font_size=SUB_FONT_SIZE,  # 执行本行逻辑
            text_align="center",  # 执行本行逻辑
            **common,  # 执行本行逻辑
        )  # 闭合括号/元组/字典
    except TypeError:  # 捕获异常
        # MoviePy 1.x：fontsize / 第一个位置参数是文本
        clip = TextClip(  # 赋值给 clip
            text,  # 序列/元组元素
            font=font_path or None,  # 执行本行逻辑
            fontsize=SUB_FONT_SIZE,  # 执行本行逻辑
            align="center",  # 执行本行逻辑
            **common,  # 执行本行逻辑
        )  # 闭合括号/元组/字典
    clip = _with_duration(clip, duration)  # 赋值给 clip
    clip = _with_position(clip, ("center", SUB_TOP))  # 赋值给 clip
    return clip  # 返回结果


def _build_subtitle_clips_for_slide(  # 定义函数
    srt_path: Path, slide_duration: float, font_path: str  # 执行本行逻辑
):  # 代码块起始
    """读单页 srt，构造一组带 start/end 的 TextClip 叠在画面上。"""
    if not srt_path.exists() or not font_path:  # 代码块起始
        return []  # 返回结果
    cues = parse_srt(srt_path.read_text(encoding="utf-8"))  # 赋值给 cues
    clips = []  # 赋值给 clips
    for start, end, text in cues:  # for 循环
        # 裁剪到不超过 slide 总长（防止 srt 比音频还长一点点造成报错）
        end = min(end, slide_duration)  # 赋值给 end
        dur = max(0.05, end - start)  # 赋值给 dur
        try:  # 代码块起始
            sub = _make_subtitle_clip(text, dur, font_path)  # 赋值给 sub
        except Exception as e:  # 捕获异常
            print(f"  [warn] 字幕 '{text}' 渲染失败：{e}，跳过")  # 打印输出
            continue  # 跳过本次循环
        sub = _with_start(sub, start)  # 赋值给 sub
        clips.append(sub)  # 执行本行逻辑
    return clips  # 返回结果


# ---------------- 主流程 ----------------
def compose_video(  # 定义函数
    png_dir: Path,  # 执行本行逻辑
    audio_dir: Path,  # 执行本行逻辑
    out_path: Path,  # 执行本行逻辑
    buffer: float = 0.3,  # 赋值给 float
    fps: int = 30,  # 赋值给 int
    burn_subtitles: bool = True,  # 赋值给 bool
) -> Path:  # 代码块起始
    pngs = sorted(png_dir.glob("page_*.png"))  # 赋值给 pngs
    mp3s = sorted(audio_dir.glob("page_*.mp3"))  # 赋值给 mp3s
    srts = sorted(audio_dir.glob("page_*.srt"))  # 赋值给 srts
    n = min(len(pngs), len(mp3s))  # 赋值给 n
    if n == 0:  # 代码块起始
        raise RuntimeError("没找到 PNG/MP3 配对，先跑 03/04 步")  # 抛出异常
    if len(pngs) != len(mp3s):  # 代码块起始
        print(f"[警告] PNG 数 ({len(pngs)}) 和 MP3 数 ({len(mp3s)}) 不一致，按少的算 ({n})")  # 打印输出

    font_path = detect_chinese_font() if burn_subtitles else ""  # 赋值给 font_path
    if burn_subtitles:  # 代码块起始
        if font_path:  # 代码块起始
            print(f"  字幕字体：{font_path}")  # 打印输出
        else:  # else 分支
            print("  [warn] 未找到中文字体（设 CN_FONT=/path/to/font.ttf 强制指定）。"  # 打印输出
                  "本次不烧硬字幕，但仍会输出软字幕 .srt")  # 字符串/template 参数

    clips = []  # 赋值给 clips
    page_durations: list[float] = []  # 赋值给 list[float]
    for i in range(n):  # for 循环
        png, mp3 = pngs[i], mp3s[i]  # 赋值给 mp3
        srt = audio_dir / f"page_{i+1:03d}.srt"  # 赋值给 srt
        audio = AudioFileClip(str(mp3))  # 赋值给 audio
        duration = audio.duration + buffer  # 赋值给 duration

        img = ImageClip(str(png))  # 赋值给 img
        img = _resized(img, height=SLIDE_AREA_H)  # 赋值给 img
        img = _with_duration(img, duration)  # 赋值给 img
        img = _with_position(img, ("center", 0))  # 赋值给 img

        bg = ColorClip(size=(VIDEO_W, VIDEO_H), color=(6, 8, 14))  # 赋值给 bg
        bg = _with_duration(bg, duration)  # 赋值给 bg
        layers = [bg, img]  # 赋值给 layers
        if burn_subtitles and font_path:  # 代码块起始
            layers.extend(_build_subtitle_clips_for_slide(srt, duration, font_path))  # 执行本行逻辑

        composed = CompositeVideoClip(layers, size=(VIDEO_W, VIDEO_H))  # 赋值给 composed
        composed = _with_duration(composed, duration)  # 赋值给 composed
        composed = _with_audio(composed, audio)  # 赋值给 composed
        clips.append(composed)  # 执行本行逻辑
        page_durations.append(duration)  # 执行本行逻辑
        print(f"  page {i+1}: {audio.duration:.2f}s + {buffer}s buffer = {duration:.2f}s")  # 打印输出

    final = concatenate_videoclips(clips, method="compose")  # 赋值给 final
    out_path.parent.mkdir(parents=True, exist_ok=True)  # 执行本行逻辑

    # 显式指定临时音频文件路径，避免 MoviePy 默认行为：
    #   - 默认会在「output 文件同目录」生成形如 videoTEMP_MPY_wvf_snd.mp4 的临时文件
    #   - 正常收尾时它自己会删；但如果中途崩了/被 Ctrl-C，这只孤儿就会留在那
    #   - 把它丢进 out_path.parent（run-时间戳子目录）下，万一漏了也跟着 run 目录走，
    #     不会污染代码目录
    temp_audio = out_path.parent / f".{out_path.stem}.tempaudio.m4a"  # 赋值给 temp_audio
    final.write_videofile(  # 执行本行逻辑
        str(out_path),  # 执行本行逻辑
        fps=fps,  # 执行本行逻辑
        codec="libx264",  # 执行本行逻辑
        audio_codec="aac",  # 执行本行逻辑
        temp_audiofile=str(temp_audio),  # 执行本行逻辑
        remove_temp=True,  # 执行本行逻辑
        logger=None,  # 执行本行逻辑
    )  # 闭合括号/元组/字典

    # 软字幕：把每页 srt 合并成全片 srt（同名同目录的 .srt 大多数播放器自动加载）
    if srts:  # 代码块起始
        global_srt = out_path.with_suffix(".srt")  # 赋值给 global_srt
        build_global_srt(  # 执行本行逻辑
            [audio_dir / f"page_{i+1:03d}.srt" for i in range(n)],  # for 循环
            page_durations,  # 序列/元组元素
            global_srt,  # 序列/元组元素
        )  # 闭合括号/元组/字典
        print(f"  软字幕：{global_srt}")  # 打印输出

    return out_path  # 返回结果


def main(png_dir: str, audio_dir: str, out_path: str) -> None:  # 定义函数
    banner("10-5 合成视频（含烧入字幕 + 软字幕 .srt）")  # 打印章节标题分隔条
    out = compose_video(Path(png_dir), Path(audio_dir), Path(out_path))  # 赋值给 out
    size_mb = out.stat().st_size / (1024 * 1024)  # 赋值给 size_mb
    print(f"\n已生成视频：{out}（{size_mb:.1f} MB）")  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    png_dir = sys.argv[1] if len(sys.argv) > 1 else "10_blog_to_video/out/png"  # 赋值给 png_dir
    audio_dir = sys.argv[2] if len(sys.argv) > 2 else "10_blog_to_video/out/audio"  # 赋值给 audio_dir
    out = sys.argv[3] if len(sys.argv) > 3 else "10_blog_to_video/out/video.mp4"  # 赋值给 out
    main(png_dir, audio_dir, out)  # 执行本行逻辑
