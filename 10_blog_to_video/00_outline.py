"""
10-0 博客 -> 视觉大纲

先做 Analyze / Design，再写具体幻灯片脚本。

这个文件对应 Presenta / Slidebook / HTMLSlides 一类项目的共同做法：
- 先判断内容结构和受众
- 再选主题、叙事弧和每页 layout
- 最后才让后续步骤填短文案、旁白和 HTML

这样可以把"页面效果"的问题前移，而不是等 MP4 合成完才发现风格不对。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

sys.path.append(str(Path(__file__).resolve().parents[1]))

from pydantic import BaseModel, Field

from _common import banner, get_llm


LayoutName = Literal[
    "cover",
    "statement",
    "stat-hero",
    "bullets",
    "icon-grid",
    "timeline",
    "compare",
    "two-col",
    "quote",
    "diagram",
    "code",
    "callout",
    "roadmap",
    "architecture",
    "quadrant",
    "principles",
    "pattern-card",
]

ThemeName = Literal[
    "studio-clean",
    "midnight-tech",
    "editorial-contrast",
]

STYLE_PRESETS: dict[str, str] = {
    "studio-clean": "白底产品感，适合教程、产品解释、轻技术内容",
    "midnight-tech": "深色技术演示，适合代码、架构、Agent、系统设计",
    "editorial-contrast": "杂志/商业分析风格，适合观点文章、方法论、趋势分析",
}


class OutlineBeat(BaseModel):
    """一页幻灯片的设计意图，不写最终文案。"""

    index: int = Field(..., ge=1, le=12, description="页码，从 1 开始")
    layout: LayoutName = Field(..., description="建议使用的组件/layout")
    role: Literal[
        "hook",
        "map",
        "framework",
        "evidence",
        "example",
        "warning",
        "takeaway",
        "closing",
    ] = Field(..., description="这页在叙事里的角色")
    headline: str = Field(..., max_length=24, description="页面主张草案，不是最终标题")
    visual_brief: str = Field(
        ...,
        max_length=80,
        description="视觉设计说明：这页该让观众看到什么结构、对比或重点",
    )
    narration_brief: str = Field(
        ...,
        max_length=100,
        description="旁白目标：这页应该解释什么，不要复述页面文字",
    )


class DeckOutline(BaseModel):
    """生成脚本前的设计蓝图。"""

    title: str = Field(..., max_length=30, description="视频标题")
    audience: str = Field(..., max_length=30, description="目标观众")
    theme: ThemeName = Field(
        ...,
        description=(
            "视觉主题：studio-clean=白底产品感；midnight-tech=深色技术演示；"
            "editorial-contrast=杂志/商业分析风格"
        ),
    )
    style_rationale: str = Field(..., max_length=120, description="为什么选这个主题")
    story_arc: str = Field(..., max_length=160, description="整套 deck 的叙事线")
    beats: list[OutlineBeat] = Field(
        ...,
        min_length=5,
        max_length=12,
        description="7-10 页最佳。先地图，再框架/证据/例子，最后原则和收尾",
    )


SYSTEM_PROMPT = """你是一位技术内容的演示设计总监。你的任务不是写 PPT 文案，
而是先产出一份可编辑的「视觉大纲」。

参考这些开源/产品化路线的共同点：
1. Presenta: Analyze -> Design -> Generate，先选布局再生成页面。
2. HTMLSlides: 让模型在组件目录里选组件，而不是裸写 HTML。
3. Slidebook / Starry Slides: 把幻灯片当可编辑源文件，先固定结构再渲染。

# 输出目标
只输出 DeckOutline。不要写最终 bullets、不要写完整旁白、不要生成 HTML。

# 设计原则
1. 第 1 页必须是 cover。
2. 第 2 页必须是 roadmap / architecture / quadrant 之一，先给观众坐标系。
3. 至少 1 页 principles，用作总结和行动建议。
4. 如果原文有代码或命令，至少 1 页 code。
5. 至少一半页面要是视觉型 layout：
   roadmap, architecture, quadrant, principles, pattern-card, stat-hero,
   icon-grid, timeline, compare, diagram, code, callout。
6. timeline 只用于真实时序；分类、分层、选择题不要用 timeline。
7. 避免连续两页相同 layout。
8. 不要追求信息塞满，视频讲解靠旁白补足，画面只负责结构和记忆点。

# 主题选择
- studio-clean: 默认，适合产品、教程、轻技术解释。
- midnight-tech: 适合代码、架构、Agent、系统设计。
- editorial-contrast: 适合商业分析、观点文章、方法论。

# 每页 visual_brief 应该描述"画面结构"
好例子：
- "三层架构栈：应用层、模式层、原子能力层，从上到下递进"
- "2x2 矩阵：横轴任务复杂度，纵轴自主性，四象限给选择建议"
- "深色代码窗口，只展示最小可运行片段，突出 create_agent 一行"

坏例子：
- "介绍这个概念"
- "总结一下"
"""


def _style_instruction(style_choices: list[str] | None = None) -> str:
    if not style_choices:
        return "用户没有限定视觉主题，请根据内容自动选择最合适的 theme。"
    valid = [s for s in style_choices if s in STYLE_PRESETS]
    if not valid:
        return "用户给出的视觉主题无法识别，请根据内容自动选择最合适的 theme。"
    descriptions = "\n".join(f"- {name}: {STYLE_PRESETS[name]}" for name in valid)
    if len(valid) == 1:
        return f"用户已经指定视觉主题，DeckOutline.theme 必须是 `{valid[0]}`。\n{descriptions}"
    return (
        "用户给出了候选视觉主题，只能从这些 theme 中选择最适合本文的一种：\n"
        f"{descriptions}"
    )


def generate_outline(blog_md: str, style_choices: list[str] | None = None) -> DeckOutline:
    """调用 LLM 生成视觉大纲。"""
    llm = get_llm(temperature=0.2, role="smart").with_structured_output(
        DeckOutline, method="function_calling"
    )
    return llm.invoke(
        [
            ("system", SYSTEM_PROMPT),
            (
                "user",
                f"{_style_instruction(style_choices)}\n\n博客原文如下，请先生成视觉大纲：\n\n{blog_md}",
            ),
        ]
    )


def revise_outline(
    blog_md: str,
    current_outline: dict,
    feedback: str,
    style_choices: list[str] | None = None,
) -> DeckOutline:
    """根据用户反馈重写视觉大纲，保持 DeckOutline schema。"""
    llm = get_llm(temperature=0.2, role="smart").with_structured_output(
        DeckOutline, method="function_calling"
    )
    return llm.invoke(
        [
            ("system", SYSTEM_PROMPT),
            (
                "user",
                "下面是当前 outline.json。请按用户反馈修改它，输出新的 DeckOutline。\n"
                "要求：保留没有被反馈影响的设计；保持页码连续；不要输出解释文字。\n\n"
                f"{_style_instruction(style_choices)}\n\n"
                f"用户反馈：{feedback}\n\n"
                f"当前 outline.json:\n{json.dumps(current_outline, ensure_ascii=False, indent=2)}\n\n"
                f"博客原文:\n{blog_md}",
            ),
        ]
    )


def main(blog_path: str, out_path: str) -> None:
    banner("10-0 生成视觉大纲")
    blog = Path(blog_path).read_text(encoding="utf-8")
    print(f"输入博客：{blog_path}（{len(blog)} 字）")

    outline = generate_outline(blog)
    print(f"\n视频标题：{outline.title}")
    print(f"受众：{outline.audience}")
    print(f"主题：{outline.theme} - {outline.style_rationale}")
    print(f"叙事线：{outline.story_arc}")
    print(f"共 {len(outline.beats)} 页设计节拍：")
    for beat in outline.beats:
        print(f"  {beat.index:02d}. [{beat.layout:14s}] {beat.headline}")

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(outline.model_dump_json(indent=2), encoding="utf-8")
    print(f"\n已保存：{out_path}")


if __name__ == "__main__":
    blog = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "10_blog_to_video/examples/sample_blog.md"
    )
    out = sys.argv[2] if len(sys.argv) > 2 else "10_blog_to_video/out/outline.json"
    main(blog, out)
