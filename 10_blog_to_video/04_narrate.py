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
from __future__ import annotations  # 启用 PEP 563 延迟注解
import asyncio  # 导入 asyncio 异步库
import json  # 导入 json 标准库
import os  # 导入 os 标准库
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径

sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from _common import banner  # 导入项目共享 LLM/Embedding 配置

DEFAULT_VOICE = os.getenv("TTS_VOICE", "zh-CN-XiaoxiaoNeural")  # 赋值给 DEFAULT_VOICE


async def _synthesize_with_srt(  # 定义异步函数
    text: str,  # 执行本行逻辑
    out_audio: Path,  # 执行本行逻辑
    out_srt: Path,  # 执行本行逻辑
    voice: str,  # 执行本行逻辑
    rate: str = "+10%",  # 赋值给 str
) -> None:  # 代码块起始
    """合成单段音频 + 同步产出 SRT 字幕。

    edge-tts stream() 同时回吐两种 chunk：
      - {"type": "audio", "data": bytes}                       → 写进 mp3
      - {"type": "WordBoundary"/"SentenceBoundary", ...}       → 喂给 SubMaker

    **edge-tts 7.x 默认发 SentenceBoundary 不是 WordBoundary**（这是 v3 修的 bug）。
    SubMaker 锁定第一个见到的 type，之后只接受同类型。一句一 cue 对中文字幕更友好，
    不会出现逐字跳的乱花眼问题。
    """
    import edge_tts  # 执行本行逻辑

    communicate = edge_tts.Communicate(text, voice, rate=rate)  # 赋值给 communicate
    submaker = edge_tts.SubMaker()  # 赋值给 submaker

    with open(out_audio, "wb") as f:  # with 上下文管理
        async for chunk in communicate.stream():  # 流式调用链/图
            t = chunk["type"]  # 赋值给 t
            if t == "audio":  # 代码块起始
                f.write(chunk["data"])  # 执行本行逻辑
            elif t in ("WordBoundary", "SentenceBoundary"):  # elif 分支
                # 跨版本兼容：6.x 是 feed()，更老的版本是 create_sub()
                if hasattr(submaker, "feed"):  # 代码块起始
                    submaker.feed(chunk)  # 执行本行逻辑
                elif hasattr(submaker, "create_sub"):  # elif 分支
                    submaker.create_sub(  # 执行本行逻辑
                        (chunk["offset"], chunk["duration"]), chunk["text"]  # 链式/容器表达式续行
                    )  # 闭合括号/元组/字典

    # 多路兜底拿 SRT 文本（不同版本 API 名不同）
    srt_text = ""  # 赋值给 srt_text
    if hasattr(submaker, "get_srt"):  # 代码块起始
        srt_text = submaker.get_srt()  # 赋值给 srt_text
    elif hasattr(submaker, "generate_subs"):  # elif 分支
        srt_text = submaker.generate_subs()  # 赋值给 srt_text
    else:  # else 分支
        srt_text = str(submaker)  # 赋值给 srt_text
    out_srt.write_text(srt_text or "", encoding="utf-8")  # 执行本行逻辑


async def synthesize_all(  # 定义异步函数
    narrations: list[str],  # 执行本行逻辑
    out_dir: Path,  # 执行本行逻辑
    voice: str = DEFAULT_VOICE,  # 赋值给 str
) -> list[tuple[Path, Path]]:  # 代码块起始
    """并发合成所有页的旁白和字幕。返回 [(mp3_path, srt_path), ...]。"""
    out_dir.mkdir(parents=True, exist_ok=True)  # 执行本行逻辑
    pairs: list[tuple[Path, Path]] = []  # 赋值给 Path]]
    tasks = []  # 赋值给 tasks
    for i, text in enumerate(narrations, 1):  # for 循环
        mp3 = out_dir / f"page_{i:03d}.mp3"  # 赋值给 mp3
        srt = out_dir / f"page_{i:03d}.srt"  # 赋值给 srt
        pairs.append((mp3, srt))  # 执行本行逻辑
        tasks.append(_synthesize_with_srt(text, mp3, srt, voice))  # 执行本行逻辑
    await asyncio.gather(*tasks)  # 等待异步结果
    return pairs  # 返回结果


def main(script_path: str, out_dir: str, voice: str = DEFAULT_VOICE) -> None:  # 定义函数
    banner(f"10-4 合成旁白 + 字幕（voice={voice}）")  # 打印章节标题分隔条
    script = json.loads(Path(script_path).read_text(encoding="utf-8"))  # 赋值给 script
    narrations = [s["narration"] for s in script["slides"]]  # for 循环
    print(f"共 {len(narrations)} 段旁白待合成（每段同时产 mp3 + srt）")  # 打印输出

    pairs = asyncio.run(synthesize_all(narrations, Path(out_dir), voice))  # 赋值给 pairs
    for mp3, srt in pairs:  # for 循环
        kb = mp3.stat().st_size / 1024  # 赋值给 kb
        cues = srt.read_text(encoding="utf-8").count("\n\n") if srt.exists() else 0  # 赋值给 cues
        print(f"  {mp3.name}  ({kb:.1f} KB, {cues} 条字幕)")  # 打印输出
    print(f"\n已生成 {len(pairs)} 对文件 → {out_dir}")  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    script = sys.argv[1] if len(sys.argv) > 1 else "10_blog_to_video/out/script.json"  # 赋值给 script
    out = sys.argv[2] if len(sys.argv) > 2 else "10_blog_to_video/out/audio"  # 赋值给 out
    voice = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_VOICE  # 赋值给 voice
    main(script, out, voice)  # 执行本行逻辑
