"""
02-5 RunnableBranch（条件路由）
学到：根据输入特征走不同的子链，类似 if/elif/else。
场景：意图识别后分发到"翻译/编程/闲聊"不同处理链。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_core.prompts import ChatPromptTemplate  # 导入 LangChain 提示词模板
from langchain_core.output_parsers import StrOutputParser  # 导入输出解析器
from langchain_core.runnables import RunnableBranch  # 导入 LCEL Runnable 组件
from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置


def main() -> None:  # demo 入口函数
    banner("02-5 RunnableBranch")  # 打印章节标题分隔条
    llm = get_llm()  # 获取 ChatOpenAI 兼容 LLM
    parser = StrOutputParser()  # 创建字符串输出解析器

    # 1) 先用一个分类链识别意图
    classify = (  # 赋值给 classify
        ChatPromptTemplate.from_template(  # 由模板创建 ChatPromptTemplate
            "判断下列问题属于哪一类，只回答一个词：translate / code / chitchat\n问题: {q}"  # 字符串/template 参数
        )  # 闭合括号/元组/字典
        | llm | parser  # 执行本行逻辑
    )  # 闭合括号/元组/字典

    # 2) 各自的处理链
    # 注意：用户输入本身可能已经是"指令式"的（"把X翻成英文"），所以下面的 prompt
    # 不能再写"把这句话翻成英语：{q}"——那样会变成"翻译一句翻译指令"，LLM 通常会
    # 把指令本身当作待翻译文本返回。正确做法是让模型"理解意图后只产出结果"。
    translate_chain = ChatPromptTemplate.from_template(  # 由模板创建 ChatPromptTemplate
        "用户消息: {q}\n请理解用户想把什么内容翻译成英文，只输出英文翻译结果，"  # 字符串/template 参数
        "不要重复用户消息、不要加引号或前缀。"  # 字符串/template 参数
    ) | llm | parser  # 执行本行逻辑
    code_chain = ChatPromptTemplate.from_template(  # 由模板创建 ChatPromptTemplate
        "用户消息: {q}\n请写一段 Python 代码完成用户的需求，只输出代码（含必要注释），不要解释。"  # 字符串/template 参数
    ) | llm | parser  # 执行本行逻辑
    chat_chain = ChatPromptTemplate.from_template(  # 由模板创建 ChatPromptTemplate
        "用户消息: {q}\n用轻松自然的语气回答，不要前缀。"  # 字符串/template 参数
    ) | llm | parser  # 执行本行逻辑

    # 3) 分支：每个 (条件函数, 分支链)，最后一个是默认
    branch = RunnableBranch(  # 创建条件分支 Runnable
        (lambda x: "translate" in x["intent"].lower(), translate_chain),  # 链式/容器表达式续行
        (lambda x: "code" in x["intent"].lower(),      code_chain),  # 链式/容器表达式续行
        chat_chain,  # default
    )  # 闭合括号/元组/字典

    # 4) 总链：先识别 → 再路由
    full = (  # 赋值给 full
        {"q": lambda x: x["q"], "intent": classify}  # 字典键值对
        | branch  # 执行本行逻辑
    )  # 闭合括号/元组/字典

    for q in ["把'我爱你'翻译成英文", "写一个二分查找", "你今天怎么样？"]:  # for 循环
        print(f"\n问: {q}")  # 打印输出
        print("答:", full.invoke({"q": q}))  # 同步调用链/图


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
