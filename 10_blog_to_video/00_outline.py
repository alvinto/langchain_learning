"""
10-0 博客 -> 视觉大纲

先做 Analyze / Design，再写具体幻灯片脚本。

这个文件对应 Presenta / Slidebook / HTMLSlides 一类项目的共同做法：
- 先判断内容结构和受众
- 再选主题、叙事弧和每页 layout
- 最后才让后续步骤填短文案、旁白和 HTML

这样可以把"页面效果"的问题前移，而不是等 MP4 合成完才发现风格不对。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解

import json  # 导入 json 标准库
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
from typing import Literal  # 导入 typing 类型注解

sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from pydantic import BaseModel, Field  # 导入 pydantic 数据校验

from _common import banner, get_llm  # 导入项目共享 LLM/Embedding 配置


LayoutName = Literal[  # 赋值给 LayoutName
    "cover",  # 字符串/template 参数
    "statement",  # 字符串/template 参数
    "stat-hero",  # 字符串/template 参数
    "bullets",  # 字符串/template 参数
    "icon-grid",  # 字符串/template 参数
    "timeline",  # 字符串/template 参数
    "compare",  # 字符串/template 参数
    "two-col",  # 字符串/template 参数
    "quote",  # 字符串/template 参数
    "diagram",  # 字符串/template 参数
    "code",  # 字符串/template 参数
    "callout",  # 字符串/template 参数
    "roadmap",  # 字符串/template 参数
    "architecture",  # 字符串/template 参数
    "quadrant",  # 字符串/template 参数
    "principles",  # 字符串/template 参数
    "pattern-card",  # 字符串/template 参数
]  # 闭合括号/元组/字典

ThemeName = Literal[  # 赋值给 ThemeName
    "studio-clean",  # 字符串/template 参数
    "midnight-tech",  # 字符串/template 参数
    "editorial-contrast",  # 字符串/template 参数
]  # 闭合括号/元组/字典

STYLE_PRESETS: dict[str, str] = {  # 赋值给 str]
    "studio-clean": "白底产品感，适合教程、产品解释、轻技术内容",  # 字符串/template 参数
    "midnight-tech": "深色技术演示，适合代码、架构、Agent、系统设计",  # 字符串/template 参数
    "editorial-contrast": "杂志/商业分析风格，适合观点文章、方法论、趋势分析",  # 字符串/template 参数
}  # 闭合括号/元组/字典


class OutlineBeat(BaseModel):  # 定义类
    """一页幻灯片的设计意图，不写最终文案。"""

    index: int = Field(..., ge=1, le=12, description="页码，从 1 开始")  # 赋值给 int
    layout: LayoutName = Field(..., description="建议使用的组件/layout")  # 赋值给 LayoutName
    role: Literal[  # 执行本行逻辑
        "hook",  # 字符串/template 参数
        "map",  # 字符串/template 参数
        "framework",  # 字符串/template 参数
        "evidence",  # 字符串/template 参数
        "example",  # 字符串/template 参数
        "warning",  # 字符串/template 参数
        "takeaway",  # 字符串/template 参数
        "closing",  # 字符串/template 参数
    ] = Field(..., description="这页在叙事里的角色")  # 赋值给 ]
    headline: str = Field(..., max_length=24, description="页面主张草案，不是最终标题")  # 赋值给 str
    visual_brief: str = Field(  # 赋值给 str
        ...,  # 序列/元组元素
        max_length=80,  # 执行本行逻辑
        description="视觉设计说明：这页该让观众看到什么结构、对比或重点",  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    narration_brief: str = Field(  # 赋值给 str
        ...,  # 序列/元组元素
        max_length=100,  # 执行本行逻辑
        description="旁白目标：这页应该解释什么，不要复述页面文字",  # 执行本行逻辑
    )  # 闭合括号/元组/字典


class DeckOutline(BaseModel):  # 定义类
    """生成脚本前的设计蓝图。"""

    title: str = Field(..., max_length=30, description="视频标题")  # 赋值给 str
    audience: str = Field(..., max_length=30, description="目标观众")  # 赋值给 str
    theme: ThemeName = Field(  # 赋值给 ThemeName
        ...,  # 序列/元组元素
        description=(  # 执行本行逻辑
            "视觉主题：studio-clean=白底产品感；midnight-tech=深色技术演示；"  # 字符串/template 参数
            "editorial-contrast=杂志/商业分析风格"  # 字符串/template 参数
        ),  # 闭合括号/元组/字典
    )  # 闭合括号/元组/字典
    style_rationale: str = Field(..., max_length=120, description="为什么选这个主题")  # 赋值给 str
    story_arc: str = Field(..., max_length=160, description="整套 deck 的叙事线")  # 赋值给 str
    beats: list[OutlineBeat] = Field(  # 赋值给 list[OutlineBeat]
        ...,  # 序列/元组元素
        min_length=5,  # 执行本行逻辑
        max_length=12,  # 执行本行逻辑
        description="7-10 页最佳。先地图，再框架/证据/例子，最后原则和收尾",  # 执行本行逻辑
    )  # 闭合括号/元组/字典


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


def _style_instruction(style_choices: list[str] | None = None) -> str:  # 定义函数
    if not style_choices:  # 代码块起始
        return "用户没有限定视觉主题，请根据内容自动选择最合适的 theme。"  # 返回结果
    valid = [s for s in style_choices if s in STYLE_PRESETS]  # for 循环
    if not valid:  # 代码块起始
        return "用户给出的视觉主题无法识别，请根据内容自动选择最合适的 theme。"  # 返回结果
    descriptions = "\n".join(f"- {name}: {STYLE_PRESETS[name]}" for name in valid)  # for 循环
    if len(valid) == 1:  # 代码块起始
        return f"用户已经指定视觉主题，DeckOutline.theme 必须是 `{valid[0]}`。\n{descriptions}"  # 返回结果
    return (  # 返回结果
        "用户给出了候选视觉主题，只能从这些 theme 中选择最适合本文的一种：\n"  # 字符串/template 参数
        f"{descriptions}"  # 字符串/template 参数
    )  # 闭合括号/元组/字典


def generate_outline(blog_md: str, style_choices: list[str] | None = None) -> DeckOutline:  # 定义函数
    """调用 LLM 生成视觉大纲。"""
    llm = get_llm(temperature=0.2, role="smart").with_structured_output(  # 获取 ChatOpenAI 兼容 LLM
        DeckOutline, method="function_calling"  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    return llm.invoke(  # 同步调用链/图
        [  # 链式/容器表达式续行
            ("system", SYSTEM_PROMPT),  # 链式/容器表达式续行
            (  # 链式/容器表达式续行
                "user",  # 字符串/template 参数
                f"{_style_instruction(style_choices)}\n\n博客原文如下，请先生成视觉大纲：\n\n{blog_md}",  # 字符串/template 参数
            ),  # 闭合括号/元组/字典
        ]  # 闭合括号/元组/字典
    )  # 闭合括号/元组/字典


def revise_outline(  # 定义函数
    blog_md: str,  # 执行本行逻辑
    current_outline: dict,  # 执行本行逻辑
    feedback: str,  # 执行本行逻辑
    style_choices: list[str] | None = None,  # 赋值给 None
) -> DeckOutline:  # 代码块起始
    """根据用户反馈重写视觉大纲，保持 DeckOutline schema。"""
    llm = get_llm(temperature=0.2, role="smart").with_structured_output(  # 获取 ChatOpenAI 兼容 LLM
        DeckOutline, method="function_calling"  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    return llm.invoke(  # 同步调用链/图
        [  # 链式/容器表达式续行
            ("system", SYSTEM_PROMPT),  # 链式/容器表达式续行
            (  # 链式/容器表达式续行
                "user",  # 字符串/template 参数
                "下面是当前 outline.json。请按用户反馈修改它，输出新的 DeckOutline。\n"  # 字符串/template 参数
                "要求：保留没有被反馈影响的设计；保持页码连续；不要输出解释文字。\n\n"  # 字符串/template 参数
                f"{_style_instruction(style_choices)}\n\n"  # 字符串/template 参数
                f"用户反馈：{feedback}\n\n"  # 字符串/template 参数
                f"当前 outline.json:\n{json.dumps(current_outline, ensure_ascii=False, indent=2)}\n\n"  # 字符串/template 参数
                f"博客原文:\n{blog_md}",  # 字符串/template 参数
            ),  # 闭合括号/元组/字典
        ]  # 闭合括号/元组/字典
    )  # 闭合括号/元组/字典


def main(blog_path: str, out_path: str) -> None:  # 定义函数
    banner("10-0 生成视觉大纲")  # 打印章节标题分隔条
    blog = Path(blog_path).read_text(encoding="utf-8")  # 赋值给 blog
    print(f"输入博客：{blog_path}（{len(blog)} 字）")  # 打印输出

    outline = generate_outline(blog)  # 赋值给 outline
    print(f"\n视频标题：{outline.title}")  # 打印输出
    print(f"受众：{outline.audience}")  # 打印输出
    print(f"主题：{outline.theme} - {outline.style_rationale}")  # 打印输出
    print(f"叙事线：{outline.story_arc}")  # 打印输出
    print(f"共 {len(outline.beats)} 页设计节拍：")  # 打印输出
    for beat in outline.beats:  # for 循环
        print(f"  {beat.index:02d}. [{beat.layout:14s}] {beat.headline}")  # 打印输出

    out = Path(out_path)  # 赋值给 out
    out.parent.mkdir(parents=True, exist_ok=True)  # 执行本行逻辑
    out.write_text(outline.model_dump_json(indent=2), encoding="utf-8")  # 执行本行逻辑
    print(f"\n已保存：{out_path}")  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    blog = (  # 赋值给 blog
        sys.argv[1]  # 序列/元组元素
        if len(sys.argv) > 1  # 执行本行逻辑
        else "10_blog_to_video/examples/sample_blog.md"  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    out = sys.argv[2] if len(sys.argv) > 2 else "10_blog_to_video/out/outline.json"  # 赋值给 out
    main(blog, out)  # 执行本行逻辑
