"""
03-1 ChatMessageHistory（最底层）
学到：手工维护一份消息列表，每轮对话往里 append。
适合理解原理，实际项目用 03-2 的 RunnableWithMessageHistory 更省事。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_core.chat_history import InMemoryChatMessageHistory  # 执行本行逻辑
from langchain_core.messages import HumanMessage  # 导入消息类型 Human/AI/System
from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置


def main() -> None:  # demo 入口函数
    banner("03-1 ChatMessageHistory")  # 打印章节标题分隔条
    llm = get_llm()  # 获取 ChatOpenAI 兼容 LLM
    history = InMemoryChatMessageHistory()  # 赋值给 history

    def chat(user_input: str) -> str:  # 定义函数
        history.add_user_message(user_input)  # 执行本行逻辑
        ai = llm.invoke(history.messages)  # 把整段历史交给模型
        history.add_ai_message(ai.content)  # 执行本行逻辑
        return ai.content  # 返回结果

    print("用户: 我叫小明")  # 打印输出
    print("助手:", chat("我叫小明"))  # 打印输出
    print("\n用户: 你还记得我叫什么吗？")  # 打印输出
    print("助手:", chat("你还记得我叫什么吗？"))  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
