"""
10-4 旁白 → MP3 + SRT
学到：edge-tts 不仅能合成语音，stream() 还会同步发回 WordBoundary 事件，
     喂给 SubMaker 就能拿到精确到词的时间戳，直接生成 SRT。
     这套时间戳是后面 05 章烧硬字幕、做 word-level 高亮的基础。

edge-tts 是反向工程微软 Edge 浏览器"大声朗读"接口的 Python 包：免费、免 key、
中文音色质量很高。不开源但允许免费使用（个人项目无忧）。

中文音色推荐：
  - zh-CN-XiaoxiaoNeural  晓晓  女声，温暖自然（默认）
  - zh-CN-YunxiNeural     云希  男声，活泼
  - zh-CN-XiaoyiNeural    晓伊  女声，清亮
  - zh-CN-YunjianNeural   云健  男声，新闻播报感
完整列表：`edge-tts --list-voices`
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from _common import banner

DEFAULT_VOICE = os.getenv("TTS_VOICE", "zh-CN-XiaoxiaoNeural")


async def _synthesize_with_srt(
    text: str,
    out_audio: Path,
    out_srt: Path,
    voice: str,
    rate: str = "+10%",
) -> None:
    """合成单段音频 + 同步产出 SRT 字幕。

    edge-tts stream() 同时回吐两种 chunk：
      - {"type": "audio", "data": bytes}                       → 写进 mp3
      - {"type": "WordBoundary"/"SentenceBoundary", ...}       → 喂给 SubMaker

    **edge-tts 7.x 默认发 SentenceBoundary 不是 WordBoundary**（这是 v3 修的 bug）。
    SubMaker 锁定第一个见到的 type，之后只接受同类型。一句一 cue 对中文字幕更友好，
    不会出现逐字跳的乱花眼问题。
    """
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    submaker = edge_tts.SubMaker()

    with open(out_audio, "wb") as f:
        async for chunk in communicate.stream():
            t = chunk["type"]
            if t == "audio":
                f.write(chunk["data"])
            elif t in ("WordBoundary", "SentenceBoundary"):
                # 跨版本兼容：6.x 是 feed()，更老的版本是 create_sub()
                if hasattr(submaker, "feed"):
                    submaker.feed(chunk)
                elif hasattr(submaker, "create_sub"):
                    submaker.create_sub(
                        (chunk["offset"], chunk["duration"]), chunk["text"]
                    )

    # 多路兜底拿 SRT 文本（不同版本 API 名不同）
    srt_text = ""
    if hasattr(submaker, "get_srt"):
        srt_text = submaker.get_srt()
    elif hasattr(submaker, "generate_subs"):
        srt_text = submaker.generate_subs()
    else:
        srt_text = str(submaker)
    out_srt.write_text(srt_text or "", encoding="utf-8")


async def synthesize_all(
    narrations: list[str],
    out_dir: Path,
    voice: str = DEFAULT_VOICE,
) -> list[tuple[Path, Path]]:
    """并发合成所有页的旁白和字幕。返回 [(mp3_path, srt_path), ...]。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    pairs: list[tuple[Path, Path]] = []
    tasks = []
    for i, text in enumerate(narrations, 1):
        mp3 = out_dir / f"page_{i:03d}.mp3"
        srt = out_dir / f"page_{i:03d}.srt"
        pairs.append((mp3, srt))
        tasks.append(_synthesize_with_srt(text, mp3, srt, voice))
    await asyncio.gather(*tasks)
    return pairs


def main(script_path: str, out_dir: str, voice: str = DEFAULT_VOICE) -> None:
    banner(f"10-4 合成旁白 + 字幕（voice={voice}）")
    script = json.loads(Path(script_path).read_text(encoding="utf-8"))
    narrations = [s["narration"] for s in script["slides"]]
    print(f"共 {len(narrations)} 段旁白待合成（每段同时产 mp3 + srt）")

    pairs = asyncio.run(synthesize_all(narrations, Path(out_dir), voice))
    for mp3, srt in pairs:
        kb = mp3.stat().st_size / 1024
        cues = srt.read_text(encoding="utf-8").count("\n\n") if srt.exists() else 0
        print(f"  {mp3.name}  ({kb:.1f} KB, {cues} 条字幕)")
    print(f"\n已生成 {len(pairs)} 对文件 → {out_dir}")


if __name__ == "__main__":
    script = sys.argv[1] if len(sys.argv) > 1 else "10_blog_to_video/out/script.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "10_blog_to_video/out/audio"
    voice = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_VOICE
    main(script, out, voice)
