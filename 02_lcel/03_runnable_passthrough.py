"""
02-3 RunnablePassthrough
学到：
- RunnablePassthrough() 把输入原样传下去
- .assign(...) 在原 dict 上加新字段
典型用法：RAG 里把 question 透传，同时新增 context 字段。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_core.prompts import ChatPromptTemplate  # 导入 LangChain 提示词模板
from langchain_core.output_parsers import StrOutputParser  # 导入输出解析器
from langchain_core.runnables import RunnablePassthrough  # 导入 LCEL Runnable 组件
from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置


def fake_retrieve(question: str) -> str:  # 定义函数
    """模拟一个检索器，返回相关文档。"""
    return f"[模拟检索结果] 关于'{question}'的资料：太阳系有八大行星。"  # 返回结果


def main() -> None:  # demo 入口函数
    banner("02-3 RunnablePassthrough.assign")  # 打印章节标题分隔条

    prompt = ChatPromptTemplate.from_template(  # 由模板创建 ChatPromptTemplate
        "根据下面的资料回答问题。\n资料: {context}\n问题: {question}"  # 字符串/template 参数
    )  # 闭合括号/元组/字典

    # assign 在输入 dict 上"追加" context 字段，保留原有的 question
    chain = (  # 赋值给 chain
        RunnablePassthrough.assign(context=lambda x: fake_retrieve(x["question"]))  # 执行本行逻辑
        | prompt  # 执行本行逻辑
        | get_llm()  # 获取 ChatOpenAI 兼容 LLM
        | StrOutputParser()  # 创建字符串输出解析器
    )  # 闭合括号/元组/字典
    print(chain.invoke({"question": "太阳系有几颗行星？"}))  # 同步调用链/图


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
