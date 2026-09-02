"""
01-5 流式输出
学到：用 .stream() 边生成边显示，体验更接近 ChatGPT。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_core.prompts import ChatPromptTemplate  # 导入 LangChain 提示词模板
from langchain_core.output_parsers import StrOutputParser  # 导入输出解析器
from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置


def main() -> None:  # demo 入口函数
    banner("01-5 Streaming")  # 打印章节标题分隔条
    prompt = ChatPromptTemplate.from_messages([  # 由消息列表创建 ChatPromptTemplate
        ("system", "你是一个故事大王。"),  # 链式/容器表达式续行
        ("human", "讲一个 100 字的睡前故事，主题：{topic}"),  # 链式/容器表达式续行
    ])  # 执行本行逻辑
    chain = prompt | get_llm() | StrOutputParser()  # 获取 ChatOpenAI 兼容 LLM

    # 注意：用 print(..., end="", flush=True) 才能看到流式效果
    for chunk in chain.stream({"topic": "勇敢的小兔子"}):  # 流式调用链/图
        print(chunk, end="", flush=True)  # 打印输出
    print()  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
