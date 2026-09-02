"""
01-3 提示词模板
学到：
- PromptTemplate：纯文本占位符
- ChatPromptTemplate：带角色的占位符（推荐）
- MessagesPlaceholder：占位一段历史消息
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_core.prompts import (  # 导入 LangChain 提示词模板
    PromptTemplate,  # 序列/元组元素
    ChatPromptTemplate,  # 序列/元组元素
    MessagesPlaceholder,  # 序列/元组元素
)  # 闭合括号/元组/字典
from langchain_core.messages import HumanMessage  # 导入消息类型 Human/AI/System
from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置


def demo_prompt_template() -> None:  # 定义函数
    banner("PromptTemplate（纯文本）")  # 打印章节标题分隔条
    tpl = PromptTemplate.from_template("把这句话翻译成{lang}：{text}")  # 赋值给 tpl
    rendered = tpl.format(lang="英文", text="今天天气真好")  # 赋值给 rendered
    print("渲染结果:", rendered)  # 打印输出


def demo_chat_prompt() -> None:  # 定义函数
    banner("ChatPromptTemplate（带角色）")  # 打印章节标题分隔条
    tpl = ChatPromptTemplate.from_messages([  # 由消息列表创建 ChatPromptTemplate
        ("system", "你是一名 {role}，回答要简洁。"),  # 链式/容器表达式续行
        ("human", "{question}"),  # 链式/容器表达式续行
    ])  # 执行本行逻辑
    msgs = tpl.format_messages(role="Python 老师", question="装饰器是什么？")  # 赋值给 msgs
    for m in msgs:  # for 循环
        print(f"[{m.type}] {m.content}")  # 打印输出

    print("\n--- 调用 LLM ---")  # 打印输出
    llm = get_llm()  # 获取 ChatOpenAI 兼容 LLM
    print(llm.invoke(msgs).content)  # 同步调用链/图


def demo_messages_placeholder() -> None:  # 定义函数
    banner("MessagesPlaceholder（占位历史）")  # 打印章节标题分隔条
    tpl = ChatPromptTemplate.from_messages([  # 由消息列表创建 ChatPromptTemplate
        ("system", "你是一个聊天机器人。"),  # 链式/容器表达式续行
        MessagesPlaceholder("history"),  # 执行本行逻辑
        ("human", "{question}"),  # 链式/容器表达式续行
    ])  # 执行本行逻辑
    history = [HumanMessage("我叫小明")]  # 赋值给 history
    msgs = tpl.format_messages(history=history, question="我叫什么名字？")  # 赋值给 msgs
    print(get_llm().invoke(msgs).content)  # 获取 ChatOpenAI 兼容 LLM


def main() -> None:  # demo 入口函数
    demo_prompt_template()  # 执行本行逻辑
    demo_chat_prompt()  # 执行本行逻辑
    demo_messages_placeholder()  # 执行本行逻辑


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
