"""
02-2 RunnableParallel
学到：把多个分支并行跑，结果合并成一个 dict，常用于"同时算多个东西"的场景。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_core.prompts import ChatPromptTemplate  # 导入 LangChain 提示词模板
from langchain_core.output_parsers import StrOutputParser  # 导入输出解析器
from langchain_core.runnables import RunnableParallel  # 导入 LCEL Runnable 组件
from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置


def main() -> None:  # demo 入口函数
    banner("02-2 RunnableParallel")  # 打印章节标题分隔条
    llm = get_llm()  # 获取 ChatOpenAI 兼容 LLM
    parser = StrOutputParser()  # 创建字符串输出解析器

    joke_chain = ChatPromptTemplate.from_template("讲一个关于 {topic} 的笑话") | llm | parser  # 由模板创建 ChatPromptTemplate
    poem_chain = ChatPromptTemplate.from_template("写一首关于 {topic} 的两句小诗") | llm | parser  # 由模板创建 ChatPromptTemplate

    # 字典写法等价于 RunnableParallel(joke=..., poem=...)
    parallel = RunnableParallel(joke=joke_chain, poem=poem_chain)  # 创建并行 Runnable
    result = parallel.invoke({"topic": "程序员"})  # 同步调用链/图
    print("== 笑话 ==\n", result["joke"])  # 打印输出
    print("\n== 小诗 ==\n", result["poem"])  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
