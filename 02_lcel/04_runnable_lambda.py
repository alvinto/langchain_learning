"""
02-4 RunnableLambda
学到：把任意 Python 函数包成 Runnable，插进 LCEL 链路里做前/后处理。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_core.prompts import ChatPromptTemplate  # 导入 LangChain 提示词模板
from langchain_core.output_parsers import StrOutputParser  # 导入输出解析器
from langchain_core.runnables import RunnableLambda  # 导入 LCEL Runnable 组件
from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置


def normalize(payload: dict) -> dict:  # 定义函数
    """前处理：把输入文本去空白 + 截断。"""
    payload["text"] = payload["text"].strip()[:200]  # 赋值给 payload["text"]
    return payload  # 返回结果


def add_meta(answer: str) -> dict:  # 定义函数
    """后处理：在 LLM 回答上附加元数据。"""
    return {"answer": answer, "length": len(answer)}  # 返回结果


def main() -> None:  # demo 入口函数
    banner("02-4 RunnableLambda")  # 打印章节标题分隔条

    prompt = ChatPromptTemplate.from_template("用一句话总结：{text}")  # 由模板创建 ChatPromptTemplate
    chain = (  # 赋值给 chain
        RunnableLambda(normalize)  # 创建 Lambda Runnable
        | prompt  # 执行本行逻辑
        | get_llm()  # 获取 ChatOpenAI 兼容 LLM
        | StrOutputParser()  # 创建字符串输出解析器
        | RunnableLambda(add_meta)  # 创建 Lambda Runnable
    )  # 闭合括号/元组/字典

    result = chain.invoke({"text": "   LangChain 是一个用于构建 LLM 应用的框架，它把 prompt、模型、工具、记忆、检索等抽象成统一接口。   "})  # 同步调用链/图
    print(result)  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
