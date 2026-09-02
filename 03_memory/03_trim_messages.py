"""
03-3 trim_messages 裁剪历史
学到：长对话会爆 token，用 trim_messages 按 token 数或条数滑动窗口。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_core.messages import (  # 导入消息类型 Human/AI/System
    SystemMessage, HumanMessage, AIMessage, trim_messages,  # 执行本行逻辑
)  # 闭合括号/元组/字典
from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置


def main() -> None:  # demo 入口函数
    banner("03-3 trim_messages")  # 打印章节标题分隔条

    msgs = [  # 赋值给 msgs
        SystemMessage("你是一个助手"),  # 构造系统消息
        HumanMessage("我叫小明"),  # 构造用户消息
        AIMessage("好的，小明"),  # 构造助手消息
        HumanMessage("我 25 岁"),  # 构造用户消息
        AIMessage("记下了"),  # 构造助手消息
        HumanMessage("我住在上海"),  # 构造用户消息
        AIMessage("收到"),  # 构造助手消息
        HumanMessage("我叫什么名字、住哪？"),  # 构造用户消息
    ]  # 闭合括号/元组/字典

    # 策略 1：按消息条数（保留最后 4 条 + 必带 system）
    trimmed_count = trim_messages(  # 赋值给 trimmed_count
        msgs,  # 序列/元组元素
        max_tokens=4,                      # 这里把"条数"当 token 用
        token_counter=len,                 # len 即一条算 1
        strategy="last",  # 执行本行逻辑
        include_system=True,  # 执行本行逻辑
        start_on="human",  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    print(">> 按条数裁剪后：")  # 打印输出
    for m in trimmed_count:  # for 循环
        print(f"  [{m.type}] {m.content}")  # 打印输出

    # 策略 2：按真实 token 数裁
    trimmed_tokens = trim_messages(  # 赋值给 trimmed_tokens
        msgs,  # 序列/元组元素
        max_tokens=80,  # 执行本行逻辑
        token_counter=get_llm(),           # 用 LLM 自己的 tokenizer
        strategy="last",  # 执行本行逻辑
        include_system=True,  # 执行本行逻辑
        start_on="human",  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    print("\n>> 按 token 裁剪后：")  # 打印输出
    for m in trimmed_tokens:  # for 循环
        print(f"  [{m.type}] {m.content}")  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
