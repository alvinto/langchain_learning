"""
02-1 LCEL 管道
学到：用 `|` 把 prompt → llm → parser 串成一条 Runnable，统一接口（invoke/stream/batch/ainvoke）。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_core.prompts import ChatPromptTemplate  # 导入 LangChain 提示词模板
from langchain_core.output_parsers import StrOutputParser  # 导入输出解析器
from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置


def main() -> None:  # demo 入口函数
    banner("02-1 LCEL Pipe Chain")  # 打印章节标题分隔条
    prompt = ChatPromptTemplate.from_template("用一个比喻解释 {concept}")  # 由模板创建 ChatPromptTemplate
    chain = prompt | get_llm() | StrOutputParser()  # 获取 ChatOpenAI 兼容 LLM

    print(">> invoke:")  # 打印输出
    print(chain.invoke({"concept": "递归"}))  # 同步调用链/图

    print("\n>> batch:")  # 批量并发
    for r in chain.batch([{"concept": "闭包"}, {"concept": "并发"}]):  # for 循环
        print("-", r[:60], "...")  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
