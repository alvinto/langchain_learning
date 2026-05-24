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
from __future__ import annotations
import os
import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from _common import banner

# MoviePy 2.x 在 2024-11 发布，import 路径和方法名都变了 —— 同时支持
try:
    from moviepy import (
        ImageClip,
        AudioFileClip,
        TextClip,
        ColorClip,
        CompositeVideoClip,
        concatenate_videoclips,
    )  # 2.x
except ImportError:
    from moviepy.editor import (  # type: ignore
        ImageClip,
        AudioFileClip,
        TextClip,
        ColorClip,
        CompositeVideoClip,
        concatenate_videoclips,
    )

VIDEO_W, VIDEO_H = 1920, 1080
# 成片把幻灯片放在上方 16:9 安全画布，底部独立留给硬字幕，避免遮挡页面文字。
SLIDE_AREA_H = 900
SLIDE_AREA_W = 1600
SUB_BAND_TOP = SLIDE_AREA_H
SUB_TOP = SUB_BAND_TOP + 34
SUB_FONT_SIZE = 42
# 字幕条宽度（占视频宽度 85%，留两侧边距）
SUB_BOX_WIDTH = int(VIDEO_W * 0.85)


# ---------------- 跨版本兼容 helpers ----------------
def _with_duration(clip, d):
    return clip.with_duration(d) if hasattr(clip, "with_duration") else clip.set_duration(d)


def _with_audio(clip, a):
    return clip.with_audio(a) if hasattr(clip, "with_audio") else clip.set_audio(a)


def _with_start(clip, s):
    return clip.with_start(s) if hasattr(clip, "with_start") else clip.set_start(s)


def _with_position(clip, p):
    return clip.with_position(p) if hasattr(clip, "with_position") else clip.set_position(p)


def _resized(clip, *, height: int | None = None, width: int | None = None):
    if hasattr(clip, "resized"):
        return clip.resized(height=height, width=width)
    return clip.resize(height=height, width=width)


# ---------------- 中文字体检测 ----------------
def detect_chinese_font() -> str:
    """返回系统中文字体路径；找不到就返回空字符串（MoviePy 会用默认字体，中文会变方框）。

    通过 CN_FONT 环境变量可强制指定。
    """
    env = os.getenv("CN_FONT")
    if env and Path(env).exists():
        return env
    candidates = [
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        # Linux
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        # Windows
        "C:\\Windows\\Fonts\\msyh.ttc",
        "C:\\Windows\\Fonts\\msyhbd.ttc",
    ]
    for p in candidates:
        if Path(p).exists():
            return p
    return ""


# ---------------- SRT 解析 / 拼接 ----------------
_SRT_TIME = re.compile(
    r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)"
)


def _t2s(h: int, m: int, s: int, ms: int) -> float:
    return h * 3600 + m * 60 + s + ms / 1000.0


def _s2t(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(text: str) -> list[tuple[float, float, str]]:
    """SRT → [(start, end, text), ...]，时间单位为秒。"""
    out: list[tuple[float, float, str]] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.strip().splitlines()
        if len(lines) < 2:
            continue
        # 找第一行包含 --> 的，前面那行（如果是数字）当 cue 索引忽略
        time_line_idx = next((i for i, l in enumerate(lines) if "-->" in l), -1)
        if time_line_idx < 0:
            continue
        m = _SRT_TIME.search(lines[time_line_idx])
        if not m:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, m.groups())
        body = "\n".join(lines[time_line_idx + 1 :]).strip()
        if body:
            out.append((_t2s(h1, m1, s1, ms1), _t2s(h2, m2, s2, ms2), body))
    return out


def build_global_srt(srt_paths: list[Path], page_durations: list[float], out: Path) -> None:
    """把每页相对时间的 srt 合并成全片绝对时间的 srt（用于软字幕分发）。"""
    parts: list[str] = []
    idx = 1
    offset = 0.0
    for srt_path, dur in zip(srt_paths, page_durations):
        if srt_path.exists():
            for start, end, body in parse_srt(srt_path.read_text(encoding="utf-8")):
                parts.append(str(idx))
                parts.append(f"{_s2t(start + offset)} --> {_s2t(end + offset)}")
                parts.append(body)
                parts.append("")
                idx += 1
        offset += dur
    out.write_text("\n".join(parts), encoding="utf-8")


# ---------------- 字幕 TextClip 工厂 ----------------
def _make_subtitle_clip(text: str, duration: float, font_path: str):
    """构造一个底部字幕带里的 TextClip，跨 MoviePy 1.x/2.x 兼容。"""
    common = dict(
        color="white",
        stroke_color="black",
        stroke_width=3,
        method="caption",
        size=(SUB_BOX_WIDTH, None),
    )
    try:
        # MoviePy 2.x：font_size / text=
        clip = TextClip(
            text=text,
            font=font_path or None,
            font_size=SUB_FONT_SIZE,
            text_align="center",
            **common,
        )
    except TypeError:
        # MoviePy 1.x：fontsize / 第一个位置参数是文本
        clip = TextClip(
            text,
            font=font_path or None,
            fontsize=SUB_FONT_SIZE,
            align="center",
            **common,
        )
    clip = _with_duration(clip, duration)
    clip = _with_position(clip, ("center", SUB_TOP))
    return clip


def _build_subtitle_clips_for_slide(
    srt_path: Path, slide_duration: float, font_path: str
):
    """读单页 srt，构造一组带 start/end 的 TextClip 叠在画面上。"""
    if not srt_path.exists() or not font_path:
        return []
    cues = parse_srt(srt_path.read_text(encoding="utf-8"))
    clips = []
    for start, end, text in cues:
        # 裁剪到不超过 slide 总长（防止 srt 比音频还长一点点造成报错）
        end = min(end, slide_duration)
        dur = max(0.05, end - start)
        try:
            sub = _make_subtitle_clip(text, dur, font_path)
        except Exception as e:
            print(f"  [warn] 字幕 '{text}' 渲染失败：{e}，跳过")
            continue
        sub = _with_start(sub, start)
        clips.append(sub)
    return clips


# ---------------- 主流程 ----------------
def compose_video(
    png_dir: Path,
    audio_dir: Path,
    out_path: Path,
    buffer: float = 0.3,
    fps: int = 30,
    burn_subtitles: bool = True,
) -> Path:
    pngs = sorted(png_dir.glob("page_*.png"))
    mp3s = sorted(audio_dir.glob("page_*.mp3"))
    srts = sorted(audio_dir.glob("page_*.srt"))
    n = min(len(pngs), len(mp3s))
    if n == 0:
        raise RuntimeError("没找到 PNG/MP3 配对，先跑 03/04 步")
    if len(pngs) != len(mp3s):
        print(f"[警告] PNG 数 ({len(pngs)}) 和 MP3 数 ({len(mp3s)}) 不一致，按少的算 ({n})")

    font_path = detect_chinese_font() if burn_subtitles else ""
    if burn_subtitles:
        if font_path:
            print(f"  字幕字体：{font_path}")
        else:
            print("  [warn] 未找到中文字体（设 CN_FONT=/path/to/font.ttf 强制指定）。"
                  "本次不烧硬字幕，但仍会输出软字幕 .srt")

    clips = []
    page_durations: list[float] = []
    for i in range(n):
        png, mp3 = pngs[i], mp3s[i]
        srt = audio_dir / f"page_{i+1:03d}.srt"
        audio = AudioFileClip(str(mp3))
        duration = audio.duration + buffer

        img = ImageClip(str(png))
        img = _resized(img, height=SLIDE_AREA_H)
        img = _with_duration(img, duration)
        img = _with_position(img, ("center", 0))

        bg = ColorClip(size=(VIDEO_W, VIDEO_H), color=(6, 8, 14))
        bg = _with_duration(bg, duration)
        layers = [bg, img]
        if burn_subtitles and font_path:
            layers.extend(_build_subtitle_clips_for_slide(srt, duration, font_path))

        composed = CompositeVideoClip(layers, size=(VIDEO_W, VIDEO_H))
        composed = _with_duration(composed, duration)
        composed = _with_audio(composed, audio)
        clips.append(composed)
        page_durations.append(duration)
        print(f"  page {i+1}: {audio.duration:.2f}s + {buffer}s buffer = {duration:.2f}s")

    final = concatenate_videoclips(clips, method="compose")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 显式指定临时音频文件路径，避免 MoviePy 默认行为：
    #   - 默认会在「output 文件同目录」生成形如 videoTEMP_MPY_wvf_snd.mp4 的临时文件
    #   - 正常收尾时它自己会删；但如果中途崩了/被 Ctrl-C，这只孤儿就会留在那
    #   - 把它丢进 out_path.parent（run-时间戳子目录）下，万一漏了也跟着 run 目录走，
    #     不会污染代码目录
    temp_audio = out_path.parent / f".{out_path.stem}.tempaudio.m4a"
    final.write_videofile(
        str(out_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=str(temp_audio),
        remove_temp=True,
        logger=None,
    )

    # 软字幕：把每页 srt 合并成全片 srt（同名同目录的 .srt 大多数播放器自动加载）
    if srts:
        global_srt = out_path.with_suffix(".srt")
        build_global_srt(
            [audio_dir / f"page_{i+1:03d}.srt" for i in range(n)],
            page_durations,
            global_srt,
        )
        print(f"  软字幕：{global_srt}")

    return out_path


def main(png_dir: str, audio_dir: str, out_path: str) -> None:
    banner("10-5 合成视频（含烧入字幕 + 软字幕 .srt）")
    out = compose_video(Path(png_dir), Path(audio_dir), Path(out_path))
    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"\n已生成视频：{out}（{size_mb:.1f} MB）")


if __name__ == "__main__":
    png_dir = sys.argv[1] if len(sys.argv) > 1 else "10_blog_to_video/out/png"
    audio_dir = sys.argv[2] if len(sys.argv) > 2 else "10_blog_to_video/out/audio"
    out = sys.argv[3] if len(sys.argv) > 3 else "10_blog_to_video/out/video.mp4"
    main(png_dir, audio_dir, out)
