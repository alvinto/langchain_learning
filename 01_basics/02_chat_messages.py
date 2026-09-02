"""
01-2 消息类型
学到：SystemMessage / HumanMessage / AIMessage 三种角色，多轮对话靠传消息列表实现。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage  # 导入消息类型 Human/AI/System
from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置


def main() -> None:  # demo 入口函数
    banner("01-2 Chat Messages")  # 打印章节标题分隔条
    llm = get_llm()  # 获取 ChatOpenAI 兼容 LLM

    # 第一轮：给系统设定 + 用户提问
    messages = [  # 赋值给 messages
        SystemMessage("你是一个用河南话回答问题的助手。"),  # 构造系统消息
        HumanMessage("讲讲冬天怎么穿衣服？"),  # 构造用户消息
    ]  # 闭合括号/元组/字典
    reply1 = llm.invoke(messages)  # 同步调用链/图
    print("助手:", reply1.content, "\n")  # 打印输出

    # 第二轮：把助手的回答作为 AIMessage 拼回去，继续问
    messages.extend([  # 执行本行逻辑
        AIMessage(reply1.content),  # 构造助手消息
        HumanMessage("那夏天呢？"),  # 构造用户消息
    ])  # 执行本行逻辑
    reply2 = llm.invoke(messages)  # 同步调用链/图
    print("助手:", reply2.content)  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
