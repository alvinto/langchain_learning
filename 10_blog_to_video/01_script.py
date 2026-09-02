"""
10-1 博客 + 视觉大纲 → 结构化幻灯片脚本（v6：outline-driven + 17 layout）

# 核心设计：把"短文案"和"视觉化"硬约束在 schema 里，而不是靠 prompt 自觉
- 17 种 layout 每个一个独立 Pydantic 模型
- 每个字段都有 max_length；轻微越界会被截断，严重结构错误仍会触发 ValidationError
- LangChain 用 function_calling 时按 layout 字段自动分支（OpenAPI discriminator）

这是 PPTAgent / Gamma / Beautiful.ai 等优秀项目殊途同归的做法：**视觉决策由 schema
决定，不由 LLM 决定**。LLM 只填短字段；layout 决定一切视觉。

为什么不让 LLM 直接生成 HTML？
  - 直接出 HTML 视觉风格不稳，每次跑结果差异大
  - 拆成 "结构化数据 + 模板渲染" 两步：LLM 只管内容选择，视觉由 02 章模板控制
  - 出错时可以单独重跑某一步，不会浪费整个 pipeline 的钱
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import json  # 导入 json 标准库
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
from typing import Annotated, Literal, Union  # 导入 typing 类型注解

sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from pydantic import BaseModel, Field, model_validator  # 导入 pydantic 数据校验

from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置


# ============================================================
# Discriminated Union：17 种 layout，每个一个独立模型
# ============================================================

# 所有 layout 共享的"听觉信息密度"：旁白
_NARRATION = Field(  # 赋值给 _NARRATION
    ...,  # 序列/元组元素
    max_length=180,  # 执行本行逻辑
    description=(  # 执行本行逻辑
        "本页旁白（讲稿），喂给 TTS 朗读。"  # 字符串/template 参数
        "60-140 字、口语化、可以是完整句、可以展开页面上没说的细节、可以举例对比。"  # 字符串/template 参数
        "**这是听觉信息密度，可以信息密集**——但不要复述页面文字。"  # 字符串/template 参数
    ),  # 闭合括号/元组/字典
)  # 闭合括号/元组/字典


def _field_max_length(field) -> int | None:  # 定义函数
    for meta in field.metadata:  # for 循环
        max_length = getattr(meta, "max_length", None)  # 赋值给 max_length
        if max_length is not None:  # 代码块起始
            return int(max_length)  # 返回结果
    return None  # 返回结果


class BoundedModel(BaseModel):  # 定义类
    """把 LLM 的轻微越界修正到 schema 边界内。

    GPT/function calling 已经能给出正确结构，但偶尔会多给一个列表项或让短标签超几
    个字符。这里按 Field(max_length=...) 做保守截断，避免整条 pipeline 因小越界
    失败；真正的视觉约束仍由 schema 和模板控制。
    """

    @model_validator(mode="before")  # 执行本行逻辑
    @classmethod  # classmethod 装饰器
    def _clip_max_lengths(cls, data):  # 定义函数
        if not isinstance(data, dict):  # 代码块起始
            return data  # 返回结果
        normalized = dict(data)  # 赋值给 normalized
        for name, field in cls.model_fields.items():  # for 循环
            if name not in normalized:  # 代码块起始
                continue  # 跳过本次循环
            max_length = _field_max_length(field)  # 赋值给 max_length
            if max_length is None:  # 代码块起始
                continue  # 跳过本次循环
            value = normalized[name]  # 赋值给 value
            if isinstance(value, str) and len(value) > max_length:  # 代码块起始
                normalized[name] = value[:max_length]  # 赋值给 normalized[name]
            elif isinstance(value, list) and len(value) > max_length:  # elif 分支
                normalized[name] = value[:max_length]  # 赋值给 normalized[name]
        return normalized  # 返回结果


class CoverSlide(BoundedModel):  # 定义类
    """封面页：一份 deck 的第 1 张。"""

    layout: Literal["cover"] = "cover"  # 赋值给 Literal["cover"]
    title: str = Field(..., max_length=20, description="主标题，6-20 字，传达本集主题")  # 赋值给 str
    subtitle: str = Field(  # 赋值给 str
        "", max_length=30, description="一句话钩子，给观众继续看的理由，10-30 字"  # 字符串/template 参数
    )  # 闭合括号/元组/字典
    narration: str = _NARRATION  # 赋值给 str


class StatementSlide(BoundedModel):  # 定义类
    """一句话核心论点页：全屏单句巨字。用于强势开场或关键转折。"""

    layout: Literal["statement"] = "statement"  # 赋值给 Literal["statement"]
    text: str = Field(  # 赋值给 str
        ...,  # 序列/元组元素
        max_length=30,  # 执行本行逻辑
        description="本页唯一的一句话，10-30 字，必须是有立场的命题（不是疑问、不是描述）",  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    highlights: list[str] = Field(  # 赋值给 list[str]
        default_factory=list,  # 执行本行逻辑
        description=(  # 执行本行逻辑
            "可选，从 text 中挑 1-3 个关键词描底色（荧光笔效果），增强视觉焦点。"  # 字符串/template 参数
            "每个必须是 text 的精确子串，1-6 个汉字。例如 text='LLM 是实习生，Harness 是公司制度'，"  # 字符串/template 参数
            "highlights 可以是 ['实习生', '公司制度']。"  # 字符串/template 参数
        ),  # 闭合括号/元组/字典
    )  # 闭合括号/元组/字典
    narration: str = _NARRATION  # 赋值给 str


class StatHeroSlide(BoundedModel):  # 定义类
    """大数字页：突出一个关键数字。"""

    layout: Literal["stat-hero"] = "stat-hero"  # 赋值给 Literal["stat-hero"]
    number: str = Field(..., max_length=8, description='巨大数字，如 "90%" / "10x" / "5 分钟"')  # 赋值给 str
    unit: str = Field("", max_length=6, description='可选单位/小注，如 "工作量" / "提升"')  # 赋值给 str
    caption: str = Field(..., max_length=28, description="一行注解，10-25 字，给数字以含义")  # 赋值给 str
    narration: str = _NARRATION  # 赋值给 str


class BulletsSlide(BoundedModel):  # 定义类
    """要点列表页：3-5 条短并列。"""

    layout: Literal["bullets"] = "bullets"  # 赋值给 Literal["bullets"]
    title: str = Field(..., max_length=18, description="本页主张，6-14 字")  # 赋值给 str
    points: list[str] = Field(  # 赋值给 list[str]
        ...,  # 序列/元组元素
        min_length=3,  # 执行本行逻辑
        max_length=5,  # 执行本行逻辑
        description=(  # 执行本行逻辑
            "3-5 条要点。**每条必须是名词短语或简短动宾，≤18 字**，不是完整长句。"  # 字符串/template 参数
            "反例 ❌：'Harness 负责约束模型能读什么、写什么，以及何时停下来'"  # 字符串/template 参数
            "正例 ✅：'读放行 / 写拦截 / 危险动作要授权'"  # 字符串/template 参数
        ),  # 闭合括号/元组/字典
    )  # 闭合括号/元组/字典
    narration: str = _NARRATION  # 赋值给 str


class IconItem(BoundedModel):  # 定义类
    icon: str = Field(  # 赋值给 str
        ...,  # 序列/元组元素
        max_length=24,  # 执行本行逻辑
        description=(  # 执行本行逻辑
            "Lucide 图标名（小写、kebab-case），从这些选："  # 字符串/template 参数
            "shield (盾/权限) / zap (闪电/速度) / users (子 Agent) / database (上下文) / "  # 字符串/template 参数
            "alert-triangle (错误/风险) / git-branch (分支决策) / settings (配置) / "  # 字符串/template 参数
            "package (模块) / target (目标) / book-open (规则) / cpu (计算) / "  # 字符串/template 参数
            "network (网络) / lock (安全) / code (代码) / play (执行) / pause (暂停) / "  # 字符串/template 参数
            "rotate-ccw (重试) / trending-up (增长) / search (搜索) / file-text (文档)"  # 字符串/template 参数
        ),  # 闭合括号/元组/字典
    )  # 闭合括号/元组/字典
    name: str = Field(..., max_length=10, description="图标下方的名字，2-8 字")  # 赋值给 str
    desc: str = Field(..., max_length=18, description="一行简短描述，8-18 字")  # 赋值给 str


class IconGridSlide(BoundedModel):  # 定义类
    """图标网格页：3-4 个并列概念，每个一个图标+短名+描述。"""

    layout: Literal["icon-grid"] = "icon-grid"  # 赋值给 Literal["icon-grid"]
    title: str = Field(..., max_length=18, description="本页主张，6-14 字")  # 赋值给 str
    items: list[IconItem] = Field(  # 赋值给 list[IconItem]
        ..., min_length=3, max_length=4, description="3-4 个图标卡片"  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    narration: str = _NARRATION  # 赋值给 str


class TimelineStep(BoundedModel):  # 定义类
    label: str = Field(..., max_length=10, description="步骤标签，2-10 字")  # 赋值给 str
    desc: str = Field(..., max_length=20, description="一行描述，6-20 字")  # 赋值给 str


class TimelineSlide(BoundedModel):  # 定义类
    """时间线页：3-5 个步骤横向串联。"""

    layout: Literal["timeline"] = "timeline"  # 赋值给 Literal["timeline"]
    title: str = Field(..., max_length=18, description="本页主张，6-14 字")  # 赋值给 str
    steps: list[TimelineStep] = Field(  # 赋值给 list[TimelineStep]
        ..., min_length=3, max_length=5, description="3-5 个步骤节点"  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    narration: str = _NARRATION  # 赋值给 str


class CompareSlide(BoundedModel):  # 定义类
    """对比表格页：2 列 × 3-5 行。"""

    layout: Literal["compare"] = "compare"  # 赋值给 Literal["compare"]
    title: str = Field(..., max_length=18, description="本页主张，6-14 字")  # 赋值给 str
    headers: list[str] = Field(  # 赋值给 list[str]
        ...,  # 序列/元组元素
        min_length=2,  # 执行本行逻辑
        max_length=3,  # 执行本行逻辑
        description="表头 2-3 列，第 1 列是维度名，后面是被对比的对象。每个 ≤10 字",  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    rows: list[list[str]] = Field(  # 赋值给 list[list[str]]
        ...,  # 序列/元组元素
        min_length=3,  # 执行本行逻辑
        max_length=5,  # 执行本行逻辑
        description="数据行 3-5 条，每行的元素数必须等于 headers 长度，**每个单元格 ≤14 字**",  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    narration: str = _NARRATION  # 赋值给 str


class TwoColSlide(BoundedModel):  # 定义类
    """左右双栏页：左短要点 + 右短解释。"""

    layout: Literal["two-col"] = "two-col"  # 赋值给 Literal["two-col"]
    title: str = Field(..., max_length=18)  # 赋值给 str
    points: list[str] = Field(  # 赋值给 list[str]
        ...,  # 序列/元组元素
        min_length=2,  # 执行本行逻辑
        max_length=4,  # 执行本行逻辑
        description="左栏 2-4 条要点，每条 ≤18 字、名词短语",  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    body: str = Field(..., max_length=80, description="右栏一段解释，30-80 字")  # 赋值给 str
    highlights: list[str] = Field(  # 赋值给 list[str]
        default_factory=list,  # 执行本行逻辑
        description="可选，从 body 中挑 1-3 个关键词描底色突出。每个必须是 body 的精确子串，1-6 字",  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    narration: str = _NARRATION  # 赋值给 str


class QuoteSlide(BoundedModel):  # 定义类
    """金句页：通常用作收尾。"""

    layout: Literal["quote"] = "quote"  # 赋值给 Literal["quote"]
    text: str = Field(..., max_length=50, description="引言/金句，15-50 字")  # 赋值给 str
    cite: str = Field("", max_length=20, description="出处或作者，可空")  # 赋值给 str
    narration: str = _NARRATION  # 赋值给 str


class RoadmapStep(BoundedModel):  # 定义类
    label: str = Field(..., max_length=14, description="章节短名，2-14 字")  # 赋值给 str


class RoadmapSlide(BoundedModel):  # 定义类
    """演讲大纲页：横向 4-7 节点串成 chevron，给观众"地图"。

    用法：建议放在第 2 张，告诉观众"接下来要走的几站"。"""

    layout: Literal["roadmap"] = "roadmap"  # 赋值给 Literal["roadmap"]
    title: str = Field(..., max_length=18, description="如「今天要讲的 5 件事」")  # 赋值给 str
    steps: list[RoadmapStep] = Field(  # 赋值给 list[RoadmapStep]
        ..., min_length=4, max_length=7, description="演讲将经过的 4-7 个章节"  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    narration: str = _NARRATION  # 赋值给 str


class ArchLayer(BoundedModel):  # 定义类
    label: str = Field(..., max_length=16, description="层名，2-12 字，如「应用层」")  # 赋值给 str
    items: list[str] = Field(  # 赋值给 list[str]
        ...,  # 序列/元组元素
        min_length=1,  # 执行本行逻辑
        max_length=4,  # 执行本行逻辑
        description="该层 1-4 个组件名/概念名，每个 ≤10 字",  # 执行本行逻辑
    )  # 闭合括号/元组/字典


class ArchitectureSlide(BoundedModel):  # 定义类
    """技术架构/层级栈页：3-5 层水平堆叠，每层有 1-4 个组件标签。

    用于呈现技术体系的"垂直分层"（如：基础层 → 模式层 → 应用层）。
    比 Mermaid 流程图更适合表达层级结构。"""

    layout: Literal["architecture"] = "architecture"  # 赋值给 Literal["architecture"]
    title: str = Field(..., max_length=18)  # 赋值给 str
    layers: list[ArchLayer] = Field(  # 赋值给 list[ArchLayer]
        ...,  # 序列/元组元素
        min_length=3,  # 执行本行逻辑
        max_length=5,  # 执行本行逻辑
        description="3-5 层。**从上到下：抽象层 → 基础层**（应用层在最上）",  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    narration: str = _NARRATION  # 赋值给 str


class QuadrantSlide(BoundedModel):  # 定义类
    """2×2 决策矩阵页：两条轴 + 四象限推荐方案。

    经典套路："何时用 A、何时用 B" 的可视化决策树替代品。
    """

    layout: Literal["quadrant"] = "quadrant"  # 赋值给 Literal["quadrant"]
    title: str = Field(..., max_length=18)  # 赋值给 str
    x_axis: str = Field(..., max_length=14, description="x 轴标签，如「任务复杂度」")  # 赋值给 str
    y_axis: str = Field(..., max_length=14, description="y 轴标签，如「需要灵活度」")  # 赋值给 str
    q_tl: str = Field(..., max_length=22, description="左上象限：x 低 y 高，一句方案")  # 赋值给 str
    q_tr: str = Field(..., max_length=22, description="右上象限：x 高 y 高")  # 赋值给 str
    q_bl: str = Field(..., max_length=22, description="左下象限：x 低 y 低")  # 赋值给 str
    q_br: str = Field(..., max_length=22, description="右下象限：x 高 y 低")  # 赋值给 str
    narration: str = _NARRATION  # 赋值给 str


class Principle(BoundedModel):  # 定义类
    title: str = Field(..., max_length=14, description="原则名，4-12 字")  # 赋值给 str
    desc: str = Field(..., max_length=36, description="一句话注解，10-36 字")  # 赋值给 str
    icon: str = Field(  # 赋值给 str
        "",  # 字符串/template 参数
        max_length=24,  # 执行本行逻辑
        description="可选 Lucide 图标名，如 target / zap / shield / book-open",  # 执行本行逻辑
    )  # 闭合括号/元组/字典


class PrinciplesSlide(BoundedModel):  # 定义类
    """设计原则页：3-4 张并列大卡片，每张：大编号 + 标题 + 注解。

    比 bullets 重 3 倍——把行动建议提炼成可记忆的几条 maxim。
    """

    layout: Literal["principles"] = "principles"  # 赋值给 Literal["principles"]
    title: str = Field(..., max_length=18, description="如「设计三原则」")  # 赋值给 str
    items: list[Principle] = Field(..., min_length=2, max_length=4)  # 赋值给 list[Principle]
    narration: str = _NARRATION  # 赋值给 str


class PatternCardSlide(BoundedModel):  # 定义类
    """模式描述卡：Martin Fowler 式 Context / Problem / Solution 三段结构。

    适合"我要介绍 X 模式"这类内容，比 bullets 更有"教科书"权威感。
    """

    layout: Literal["pattern-card"] = "pattern-card"  # 赋值给 Literal["pattern-card"]
    name: str = Field(..., max_length=16, description="模式名，2-16 字")  # 赋值给 str
    context: str = Field(..., max_length=50, description="什么场景下会遇到")  # 赋值给 str
    problem: str = Field(..., max_length=50, description="具体面对什么问题")  # 赋值给 str
    solution: str = Field(..., max_length=50, description="模式给出的解法")  # 赋值给 str
    narration: str = _NARRATION  # 赋值给 str


class CodeSlide(BoundedModel):  # 定义类
    """代码展示页：深色卡片 + 语法高亮 + 文件名 tab。技术博客必备。"""

    layout: Literal["code"] = "code"  # 赋值给 Literal["code"]
    title: str = Field("", max_length=18, description="可选小标题，不写也行")  # 赋值给 str
    filename: str = Field(  # 赋值给 str
        "",  # 字符串/template 参数
        max_length=40,  # 执行本行逻辑
        description='可选文件名（如 "agent.py" / "main.go"），显示在代码窗口顶部 tab',  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    language: Literal[  # 执行本行逻辑
        "python",  # 字符串/template 参数
        "javascript",  # 字符串/template 参数
        "typescript",  # 字符串/template 参数
        "bash",  # 字符串/template 参数
        "shell",  # 字符串/template 参数
        "sql",  # 字符串/template 参数
        "yaml",  # 字符串/template 参数
        "json",  # 字符串/template 参数
        "go",  # 字符串/template 参数
        "rust",  # 字符串/template 参数
        "java",  # 字符串/template 参数
        "html",  # 字符串/template 参数
        "css",  # 字符串/template 参数
        "markdown",  # 字符串/template 参数
        "plaintext",  # 字符串/template 参数
    ] = Field("python", description="语言名（小写），用于 highlight.js 上色")  # 赋值给 ]
    code: str = Field(  # 赋值给 str
        ...,  # 序列/元组元素
        max_length=700,  # 执行本行逻辑
        description=(  # 执行本行逻辑
            "代码本体，**建议 ≤15 行，每行 ≤45 字符**，超出会被裁剪看不见。"  # 字符串/template 参数
            "用真实换行不是 \\n。保留缩进。"  # 字符串/template 参数
        ),  # 闭合括号/元组/字典
    )  # 闭合括号/元组/字典
    narration: str = _NARRATION  # 赋值给 str


class CalloutSlide(BoundedModel):  # 定义类
    """提示框页：info/tip/warn/danger 四种语义色，强调踩坑或重要建议。"""

    layout: Literal["callout"] = "callout"  # 赋值给 Literal["callout"]
    tone: Literal["info", "tip", "warn", "danger"] = Field(  # 赋值给 "danger"]
        ...,  # 序列/元组元素
        description=(  # 执行本行逻辑
            "语气："  # 字符串/template 参数
            "info=信息（蓝）；tip=建议/技巧（绿）；warn=警告/注意（黄）；danger=危险/陷阱（红）"  # 字符串/template 参数
        ),  # 闭合括号/元组/字典
    )  # 闭合括号/元组/字典
    title: str = Field(..., max_length=16, description="标题，2-16 字")  # 赋值给 str
    body: str = Field(..., max_length=80, description="一段说明，20-80 字")  # 赋值给 str
    icon: str = Field(  # 赋值给 str
        "",  # 字符串/template 参数
        max_length=24,  # 执行本行逻辑
        description=(  # 执行本行逻辑
            "可选 Lucide 图标名覆盖默认（默认按 tone 自动选）。"  # 字符串/template 参数
            "建议候选：info / lightbulb / alert-triangle / shield-alert / "  # 字符串/template 参数
            "alert-octagon / book-open / target / zap"  # 字符串/template 参数
        ),  # 闭合括号/元组/字典
    )  # 闭合括号/元组/字典
    narration: str = _NARRATION  # 赋值给 str


class DiagramSlide(BoundedModel):  # 定义类
    """流程图/架构图页：Mermaid 渲染。"""

    layout: Literal["diagram"] = "diagram"  # 赋值给 Literal["diagram"]
    title: str = Field(..., max_length=18)  # 赋值给 str
    mermaid: str = Field(  # 赋值给 str
        ...,  # 序列/元组元素
        max_length=500,  # 执行本行逻辑
        description=(  # 执行本行逻辑
            "合法的 Mermaid 代码。优先 `graph LR` 横向流程图，节点标签用中文短词。"  # 字符串/template 参数
            "示例：\n"  # 字符串/template 参数
            "graph LR\n  A[用户请求] --> B[权限网关]\n  B --> C{是否高危}\n"  # 字符串/template 参数
            "  C -->|是| D[用户授权]\n  C -->|否| E[执行]"  # 字符串/template 参数
        ),  # 闭合括号/元组/字典
    )  # 闭合括号/元组/字典
    caption: str = Field("", max_length=30, description="图下方一行注解，可空")  # 赋值给 str
    narration: str = _NARRATION  # 赋值给 str


# 把所有 layout 通过 layout 字段做 discriminated union
# LangChain `with_structured_output(method="function_calling")` 会自动按
# discriminator 生成 anyOf JSON Schema，LLM 按 layout 字段决定填哪些其它字段
Slide = Annotated[  # 赋值给 Slide
    Union[  # 序列/元组元素
        CoverSlide,  # 序列/元组元素
        StatementSlide,  # 序列/元组元素
        StatHeroSlide,  # 序列/元组元素
        BulletsSlide,  # 序列/元组元素
        IconGridSlide,  # 序列/元组元素
        TimelineSlide,  # 序列/元组元素
        CompareSlide,  # 序列/元组元素
        TwoColSlide,  # 序列/元组元素
        QuoteSlide,  # 序列/元组元素
        DiagramSlide,  # 序列/元组元素
        CodeSlide,  # 序列/元组元素
        CalloutSlide,  # 序列/元组元素
        # v5: 概念骨架类
        RoadmapSlide,  # 序列/元组元素
        ArchitectureSlide,  # 序列/元组元素
        QuadrantSlide,  # 序列/元组元素
        PrinciplesSlide,  # 序列/元组元素
        PatternCardSlide,  # 序列/元组元素
    ],  # 闭合括号/元组/字典
    Field(discriminator="layout"),  # 执行本行逻辑
]  # 闭合括号/元组/字典


class Script(BoundedModel):  # 定义类
    """整个视频的脚本。"""

    title: str = Field(..., max_length=30, description="视频标题，封面页可能复用")  # 赋值给 str
    theme: Literal[  # 执行本行逻辑
        "studio-clean",  # 字符串/template 参数
        "midnight-tech",  # 字符串/template 参数
        "editorial-contrast",  # 字符串/template 参数
    ] = Field(  # 赋值给 ]
        "studio-clean",  # 字符串/template 参数
        description="视觉主题，必须优先沿用 outline.json 里的 theme",  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    slides: list[Slide] = Field(  # type: ignore[valid-type]
        ...,  # 序列/元组元素
        min_length=5,  # 执行本行逻辑
        max_length=12,  # 执行本行逻辑
        description="幻灯片列表，7-12 张，结构通常是 1 cover + roadmap + 5-9 内容 + principles + 1 收尾",  # 执行本行逻辑
    )  # 闭合括号/元组/字典


# ============================================================
# Prompt：教 LLM 先选 layout 再填内容
# ============================================================

SYSTEM_PROMPT = """你是一位资深技术演讲设计师（不是写手），把博客拆成 7-10 张幻灯片做讲解视频。
你的标杆是 Lilian Weng 的博客、Anthropic Eng Blog、Martin Fowler 的模式文档——
**先给观众一张概念地图，再讲细节**。

# 工作原则 #1: 骨架优先 FRAMEWORK-FIRST
拿到博客先**别急着写幻灯片**，先在心里回答：
1. 这篇博客的「全景图」是什么？整个领域长什么形状？
2. 有哪些「命名实体」（专有名词）？例如 "Augmented LLM" / "Hook Bus" / "ReAct"
3. 有没有「分层关系」（A 在 B 之下）或「分类法」（A、B、C 是 X 的三种）？
4. 有没有「决策矩阵」（什么时候用 A、什么时候用 B）？
5. 最终的「行动建议」能否浓缩为几条命名的原则？

回答完这些再开始排版。**幻灯片是骨架的"投影"，不是博客的"摘要"**。

# 17 种 layout

## 概念骨架类（v5 新加，优先用）
1. **roadmap** —— 演讲大纲，4-7 节点横排。**强烈建议放第 2 张**，开篇就给观众"今天要走的路线"。
2. **architecture** —— 技术分层栈，3-5 层从上（应用）到下（基础），每层 1-4 个命名组件。**有明显分层关系时必用**。
3. **quadrant** —— 2x2 决策矩阵，两条轴 + 四象限的方案。"何时用 A vs B" 必备。
4. **principles** —— 3-4 张大原则卡，每张：大编号 + 名字 + 注解。**总结 / 行动建议必用，不是 bullets**。
5. **pattern-card** —— Martin Fowler 式 Context / Problem / Solution 三段，介绍单个模式时用。

## 重型视觉类
6. **statement** —— 一句话论点，**支持 highlights** 描底色。
7. **stat-hero** —— 巨大数字 + 注解。
8. **icon-grid** —— 3-4 个 Lucide 图标卡片。
9. **timeline** —— 横向 3-5 步流程（**仅用于真正的时序**，不是并列分类！）。
10. **compare** —— 表格对比 2-3 列 x 3-5 行。
11. **diagram** —— Mermaid 流程图。
12. **code** —— 深色代码窗口，技术博客的灵魂。
13. **callout** —— 4 色提示框 info / tip / warn / danger。

## 基础类
14. **cover**, 15. **bullets**, 16. **two-col** (支持 highlights), 17. **quote**

# 必须遵守的硬约束
1. **每页字段都有严格 max_length**，**不要踩线**。
2. **骨架先行的强制配比**（v5 重点）：
   - **第 2 张必须**是 `roadmap` 或 `architecture` 或 `quadrant`，给观众坐标系
   - **至少 1 张** `principles`（最后总结，不要用 bullets 替代）
   - **至少 1 张** `code`（如果原文涉及代码）
   - **至少 1 张** `callout`（强调踩坑/重点）
3. **timeline 严格用于时序**——"5 种 workflow 并列" 不是 timeline，是 architecture 或 icon-grid！
4. **bullets / icon-grid / timeline 里禁止长句**：每条 ≤18 字、名词短语。
   - X 'Harness 负责约束模型能读什么、写什么'
   - V '读放行 / 写拦截 / 危险动作要授权'
5. 不要 emoji、不要 markdown 加粗符号 (**xxx**)
6. **避免连续两张相同 layout**

# highlights 字段（statement / two-col）
挑 1-3 个关键词描底色：必须是 text/body 的**精确子串**，1-6 个汉字，挑实词。
- text='LLM 是实习生，Harness 是公司制度' → highlights=['实习生', '公司制度']

# 旁白 narration 的专业度要求（v5 升级）
**目标音色**：像 Andrej Karpathy / Lilian Weng 做 TED talk 时的口吻，**不是博客复述**。

必备元素：
1. **命名实体优先**：发明或借用专有名词并定义。
   - X "这一层负责管模型能调用什么工具"
   - V "我们把这一层叫做权限网关 (permission gateway)。它的职责是……"
2. **路标语 signposts**：每页旁白用 1 句话承上启下。
   - "刚才我们看了 X 的全景，现在 zoom in 到具体一层。"
   - "暂停一下——这里是整个系统最容易出问题的地方。"
   - "记住这三个名字，我们后面还会用到。"
3. **节奏**：先抛钩子（"有意思的是……"、"这里有个反直觉的地方"）再展开。
4. **不复述页面文字**：narration 讲页面文字背后的"为什么"，不是"是什么"。

# 视觉节奏建议
1. cover                  钩子
2. roadmap/architecture   给地图
3-N 中间穿插:
     architecture / quadrant / pattern-card  概念框架
     icon-grid / compare / diagram          分类/对比
     code / stat-hero                       具体证据
     callout                                关键提示
N-1. principles            3 条 takeaway
N.   quote                 金句收尾

# Mermaid（diagram layout）规则
- 优先 `graph LR`（横向），节点中文短标签，≤8 个节点
- 示例：graph LR\n  A[博客] --> B[脚本] --> C[幻灯片] --> D[视频]

# 如果用户消息里提供了 outline.json
outline 是设计合同，不是灵感参考。你必须：
1. 沿用 outline.theme。
2. 尽量保持页数、顺序、layout 和每页 headline/visual_brief 的设计意图。
3. 只在 schema 不支持或原文事实冲突时做最小调整。
4. 把 visual_brief 转换成具体字段，而不是在页面里复述 visual_brief。
5. narration_brief 决定旁白重点，但 narration 必须是自然口语，不能像提纲。

# v5 新 layout 范例

## roadmap
title: "今天要讲的 5 件事"
steps: ['基础积木', '工作流', 'Agent', '何时用', '生产建议']

## architecture
title: "Agent 系统的分层"
layers:
  - label: "应用层",  items: ["Coding Agent", "客服 Agent"]
  - label: "模式层",  items: ["Chain", "Route", "Parallel", "Orchestrator"]
  - label: "原子层",  items: ["Augmented LLM"]
  - label: "基础层",  items: ["Tools", "Memory", "Retrieval"]

## quadrant
title: "工作流 vs Agent 怎么选"
x_axis: "任务复杂度"  y_axis: "需要灵活度"
q_tl: "工作流足够"    q_tr: "上 Agent"
q_bl: "单次调用"      q_br: "工作流加重试"

## principles
title: "Agent 设计三原则"
items:
  - title: "简单优先", desc: "用最少的部件解决问题", icon: "minimize-2"
  - title: "透明",     desc: "把规划步骤显式展示给用户", icon: "eye"
  - title: "工具接口", desc: "ACI 和 HCI 一样要精心设计", icon: "code"

## pattern-card
name: "Orchestrator-Workers"
context: "子任务无法预先列出的复杂场景"
problem: "并行模式要事先定好分支，灵活性不够"
solution: "主 LLM 动态拆任务给 worker，再合并结果"

## code 例子
title: "ReAct Agent 一行起步"
filename: "agent.py"
language: "python"
code:
  from langchain.agents import create_agent
  agent = create_agent(model="gpt-5", tools=[search, calc])
  print(agent.invoke({"messages": [("user", "帮我查天气")]}))

## callout 例子
- tone='warn', title='别一上来就 Agent', body='单轮调用 + RAG 已经能解 80% 问题。'
- tone='tip',  title='调试神器', body='把 LANGCHAIN_API_KEY 填到 .env 自动追踪。'
- tone='danger', title='Bash 工具别裸给 LLM', body='危险动作必须经权限网关，写操作默认拦截。'
"""


def generate_script(blog_md: str, outline: dict | None = None) -> Script:  # 定义函数
    """调用 LLM 生成结构化脚本。

    outline 来自 00_outline.py，是前置的视觉设计蓝图。传入后，LLM 的职责从
    "自由设计整套 deck" 收窄为 "按设计合同填充页面字段和旁白"。
    """
    # method="function_calling" 兼容性最广（DeepSeek/Qwen 等国产兼容协议 + OpenAI 官方都 OK）
    llm = get_llm(temperature=0.3).with_structured_output(  # 获取 ChatOpenAI 兼容 LLM
        Script, method="function_calling"  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    user_text = f"博客原文如下，请生成幻灯片脚本：\n\n{blog_md}"  # 赋值给 user_text
    if outline:  # 代码块起始
        user_text = (  # 赋值给 user_text
            "下面先给出已经审核过的视觉大纲 outline.json。"  # 字符串/template 参数
            "请严格按照这个大纲生成最终幻灯片脚本。\n\n"  # 字符串/template 参数
            f"outline.json:\n{json.dumps(outline, ensure_ascii=False, indent=2)}\n\n"  # 字符串/template 参数
            f"博客原文:\n{blog_md}"  # 字符串/template 参数
        )  # 闭合括号/元组/字典
    script = llm.invoke(  # 同步调用链/图
        [  # 链式/容器表达式续行
            ("system", SYSTEM_PROMPT),  # 链式/容器表达式续行
            ("user", user_text),  # 链式/容器表达式续行
        ]  # 闭合括号/元组/字典
    )  # 闭合括号/元组/字典
    if outline and outline.get("theme"):  # 代码块起始
        script.theme = outline["theme"]  # 赋值给 script.theme
    return script  # 返回结果


def revise_script(  # 定义函数
    blog_md: str,  # 执行本行逻辑
    current_script: dict,  # 执行本行逻辑
    feedback: str,  # 执行本行逻辑
    outline: dict | None = None,  # 赋值给 None
) -> Script:  # 代码块起始
    """根据用户反馈重写 script.json，保持 Script schema。"""
    llm = get_llm(temperature=0.25).with_structured_output(  # 获取 ChatOpenAI 兼容 LLM
        Script, method="function_calling"  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    context = ""  # 赋值给 context
    if outline:  # 代码块起始
        context = (  # 赋值给 context
            "下面还有当前 outline.json。outline 仍然是设计合同；"  # 字符串/template 参数
            "除非用户反馈明确要求改变结构，否则尽量保持它的设计意图。\n\n"  # 字符串/template 参数
            f"outline.json:\n{json.dumps(outline, ensure_ascii=False, indent=2)}\n\n"  # 字符串/template 参数
        )  # 闭合括号/元组/字典
    script = llm.invoke(  # 同步调用链/图
        [  # 链式/容器表达式续行
            ("system", SYSTEM_PROMPT),  # 链式/容器表达式续行
            (  # 链式/容器表达式续行
                "user",  # 字符串/template 参数
                "下面是当前 script.json。请按用户反馈修改它，输出新的 Script。\n"  # 字符串/template 参数
                "要求：只改受反馈影响的页面；保持字段短小；字幕安全，页面底部不要放关键文字；"  # 字符串/template 参数
                "不要输出解释文字。\n\n"  # 字符串/template 参数
                f"用户反馈：{feedback}\n\n"  # 字符串/template 参数
                f"{context}"  # 字符串/template 参数
                f"当前 script.json:\n{json.dumps(current_script, ensure_ascii=False, indent=2)}\n\n"  # 字符串/template 参数
                f"博客原文:\n{blog_md}",  # 字符串/template 参数
            ),  # 闭合括号/元组/字典
        ]  # 闭合括号/元组/字典
    )  # 闭合括号/元组/字典
    if outline and outline.get("theme"):  # 代码块起始
        script.theme = outline["theme"]  # 赋值给 script.theme
    elif current_script.get("theme"):  # elif 分支
        script.theme = current_script["theme"]  # 赋值给 script.theme
    return script  # 返回结果


def main(blog_path: str, out_path: str, outline_path: str | None = None) -> None:  # 定义函数
    banner("10-1 生成幻灯片脚本")  # 打印章节标题分隔条
    blog = Path(blog_path).read_text(encoding="utf-8")  # 赋值给 blog
    print(f"输入博客：{blog_path}（{len(blog)} 字）")  # 打印输出

    outline = None  # 赋值给 outline
    if outline_path:  # 代码块起始
        outline = json.loads(Path(outline_path).read_text(encoding="utf-8"))  # 赋值给 outline
        print(f"视觉大纲：{outline_path}（{len(outline.get('beats', []))} 页节拍）")  # 打印输出

    script = generate_script(blog, outline=outline)  # 赋值给 script
    print(f"\n视频标题：{script.title}")  # 打印输出
    print(f"视觉主题：{script.theme}")  # 打印输出
    print(f"共 {len(script.slides)} 张幻灯片：")  # 打印输出
    visual_layouts = {  # 赋值给 visual_layouts
        "stat-hero", "icon-grid", "timeline", "compare", "diagram",  # 字符串/template 参数
        "code", "callout",  # 字符串/template 参数
        # v5 概念骨架也算视觉化
        "roadmap", "architecture", "quadrant", "principles", "pattern-card",  # 字符串/template 参数
    }  # 闭合括号/元组/字典
    visual_count = sum(1 for s in script.slides if s.layout in visual_layouts)  # for 循环
    for i, s in enumerate(script.slides, 1):  # for 循环
        marker = "🎨" if s.layout in visual_layouts else "  "  # 赋值给 marker
        # 取标题字段做预览（不同 layout 标题在不同字段）
        preview = getattr(s, "title", None) or getattr(s, "text", "") or getattr(s, "caption", "")  # 赋值给 preview
        print(f"  {marker} {i}. [{s.layout:10s}] {preview}")  # 打印输出
    print(f"\n视觉化页占比: {visual_count}/{len(script.slides)} "  # 打印输出
          f"({'✓ 达标' if visual_count >= 2 else '⚠ 太少，可让 LLM 重新生成'})")  # 字符串/template 参数

    out = Path(out_path)  # 赋值给 out
    out.parent.mkdir(parents=True, exist_ok=True)  # 执行本行逻辑
    out.write_text(script.model_dump_json(indent=2), encoding="utf-8")  # 执行本行逻辑
    print(f"\n已保存：{out_path}")  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    blog = sys.argv[1] if len(sys.argv) > 1 else "10_blog_to_video/examples/sample_blog.md"  # 赋值给 blog
    out = sys.argv[2] if len(sys.argv) > 2 else "10_blog_to_video/out/script.json"  # 赋值给 out
    outline = sys.argv[3] if len(sys.argv) > 3 else None  # 赋值给 outline
    main(blog, out, outline)  # 执行本行逻辑
