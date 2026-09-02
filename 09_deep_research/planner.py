"""Planner：把研究问题拆成 3~6 个互不重叠的子问题。

这是 multi-agent 系统里最关键的一步——拆得好，后面 fan-out 出去的 researcher
能各管各的；拆得差，几个 researcher 会重复劳动甚至互相矛盾。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解

import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径

from langchain_core.prompts import ChatPromptTemplate  # 导入 LangChain 提示词模板
from pydantic import BaseModel, Field  # 导入 pydantic 数据校验

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 执行本行逻辑
from _common import get_llm  # noqa: E402


class Plan(BaseModel):  # 定义类
    sub_questions: list[str] = Field(  # 赋值给 list[str]
        description="3~6 个互不重叠、可独立搜索的子问题，中文"  # 执行本行逻辑
    )  # 闭合括号/元组/字典


_PROMPT = ChatPromptTemplate.from_messages(  # 由消息列表创建 ChatPromptTemplate
    [  # 链式/容器表达式续行
        (  # 链式/容器表达式续行
            "system",  # 字符串/template 参数
            "你是研究规划专家。把用户的研究问题拆成 3~6 个子问题，要求：\n"  # 字符串/template 参数
            "1. 子问题加起来能完整覆盖原问题，不重不漏\n"  # 字符串/template 参数
            "2. 每条独立可搜索（不要互相依赖、不要套娃）\n"  # 字符串/template 参数
            "3. 粒度适中：不要太宽泛（一个子问题等于原问题），也不要太细（10 个琐碎条目）\n"  # 字符串/template 参数
            "4. 用中文输出\n"  # 字符串/template 参数
            "5. 如果原问题已经足够具体（比如「Python 3.13 的 GIL 移除提案是什么」），"  # 字符串/template 参数
            "可以只拆 2~3 个子问题，不必凑数",  # 字符串/template 参数
        ),  # 闭合括号/元组/字典
        ("user", "研究问题：{question}"),  # 链式/容器表达式续行
    ]  # 闭合括号/元组/字典
)  # 闭合括号/元组/字典


def plan(question: str) -> list[str]:  # 定义函数
    """把 question 拆成子问题列表。

    注意 method="function_calling"：langchain-openai 新版默认用 json_schema 模式，
    但 OpenAI 兼容协议提供方（DeepSeek / Qwen / 智谱…）大多只支持老的 function_calling，
    不显式指定会让 LLM 直接返回 Markdown 文本，导致 OpenAI SDK 解析 JSON 失败。
    """
    llm = get_llm(temperature=0)  # 获取 ChatOpenAI 兼容 LLM
    chain = _PROMPT | llm.with_structured_output(Plan, method="function_calling")  # 赋值给 chain
    result: Plan = chain.invoke({"question": question})  # 同步调用链/图
    return result.sub_questions  # 返回结果


if __name__ == "__main__":  # 脚本直接运行时执行 main
    import sys  # 导入 sys 标准库

    q = " ".join(sys.argv[1:]) or "对比 LangGraph 和 OpenAI Agents SDK 的差异和适用场景"  # 赋值给 q
    for i, sq in enumerate(plan(q), 1):  # for 循环
        print(f"{i}. {sq}")  # 打印输出
