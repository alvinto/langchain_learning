"""
02-5 RunnableBranch（条件路由）
学到：根据输入特征走不同的子链，类似 if/elif/else。
场景：意图识别后分发到"翻译/编程/闲聊"不同处理链。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableBranch
from _common import get_llm, banner


def main() -> None:
    banner("02-5 RunnableBranch")
    llm = get_llm()
    parser = StrOutputParser()

    # 1) 先用一个分类链识别意图
    classify = (
        ChatPromptTemplate.from_template(
            "判断下列问题属于哪一类，只回答一个词：translate / code / chitchat\n问题: {q}"
        )
        | llm | parser
    )

    # 2) 各自的处理链
    # 注意：用户输入本身可能已经是"指令式"的（"把X翻成英文"），所以下面的 prompt
    # 不能再写"把这句话翻成英语：{q}"——那样会变成"翻译一句翻译指令"，LLM 通常会
    # 把指令本身当作待翻译文本返回。正确做法是让模型"理解意图后只产出结果"。
    translate_chain = ChatPromptTemplate.from_template(
        "用户消息: {q}\n请理解用户想把什么内容翻译成英文，只输出英文翻译结果，"
        "不要重复用户消息、不要加引号或前缀。"
    ) | llm | parser
    code_chain = ChatPromptTemplate.from_template(
        "用户消息: {q}\n请写一段 Python 代码完成用户的需求，只输出代码（含必要注释），不要解释。"
    ) | llm | parser
    chat_chain = ChatPromptTemplate.from_template(
        "用户消息: {q}\n用轻松自然的语气回答，不要前缀。"
    ) | llm | parser

    # 3) 分支：每个 (条件函数, 分支链)，最后一个是默认
    branch = RunnableBranch(
        (lambda x: "translate" in x["intent"].lower(), translate_chain),
        (lambda x: "code" in x["intent"].lower(),      code_chain),
        chat_chain,  # default
    )

    # 4) 总链：先识别 → 再路由
    full = (
        {"q": lambda x: x["q"], "intent": classify}
        | branch
    )

    for q in ["把'我爱你'翻译成英文", "写一个二分查找", "你今天怎么样？"]:
        print(f"\n问: {q}")
        print("答:", full.invoke({"q": q}))


if __name__ == "__main__":
    main()
