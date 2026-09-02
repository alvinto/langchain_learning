"""
01-4 输出解析器
学到：
- StrOutputParser：拿到纯字符串而不是 AIMessage
- JsonOutputParser：把 JSON 字符串解析成 dict
- PydanticOutputParser：直接得到 Pydantic 对象，附带 schema 提示
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from typing import List  # 导入 typing 类型注解
from pydantic import BaseModel, Field  # 导入 pydantic 数据校验

from langchain_core.output_parsers import StrOutputParser, JsonOutputParser  # 导入输出解析器
from langchain_core.output_parsers import PydanticOutputParser  # 导入输出解析器
from langchain_core.prompts import ChatPromptTemplate  # 导入 LangChain 提示词模板
from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置


class Recipe(BaseModel):  # 定义类
    name: str = Field(description="菜名")  # 赋值给 str
    ingredients: List[str] = Field(description="原料列表")  # 赋值给 List[str]
    steps: List[str] = Field(description="步骤")  # 赋值给 List[str]


def demo_str_parser() -> None:  # 定义函数
    banner("StrOutputParser")  # 打印章节标题分隔条
    chain = get_llm() | StrOutputParser()  # 获取 ChatOpenAI 兼容 LLM
    print(chain.invoke("写一个冷笑话"))  # 同步调用链/图


def demo_json_parser() -> None:  # 定义函数
    banner("JsonOutputParser")  # 打印章节标题分隔条
    parser = JsonOutputParser()  # 赋值给 parser
    prompt = ChatPromptTemplate.from_messages([  # 由消息列表创建 ChatPromptTemplate
        ("system", "只返回 JSON，键为 city/temperature/condition"),  # 链式/容器表达式续行
        ("human", "{q}"),  # 链式/容器表达式续行
    ])  # 执行本行逻辑
    '''
    这里的 | 不是 Python 原生位或运算符，是 LangChain 重写的魔法运算符，对应 Runnable 对象的管道，作用类似 Linux 的管道：把前一个组件的输出，作为后一个组件的输入。
    '''
    chain = prompt | get_llm() | parser  # 获取 ChatOpenAI 兼容 LLM
    print(chain.invoke({"q": "今天北京天气怎么样？给一个示例 JSON"}))  # 同步调用链/图


def demo_pydantic_parser() -> None:  # 定义函数
    banner("PydanticOutputParser")  # 打印章节标题分隔条
    parser = PydanticOutputParser(pydantic_object=Recipe)  # 赋值给 parser
    ## 把需要输出的格式通过提示词给到模型
    prompt = ChatPromptTemplate.from_messages([  # 由消息列表创建 ChatPromptTemplate
        ("system", "你是一个菜谱助手。\n{format_instructions}"),  # 链式/容器表达式续行
        ("human", "给我一个 {dish} 的菜谱"),  # 链式/容器表达式续行
    ]).partial(format_instructions=parser.get_format_instructions())  # 执行本行逻辑

    chain = prompt | get_llm() | parser  # 获取 ChatOpenAI 兼容 LLM
    recipe: Recipe = chain.invoke({"dish": "番茄炒蛋"})  # 同步调用链/图
    print(f"菜名: {recipe.name}")  # 打印输出
    print(f"原料: {recipe.ingredients}")  # 打印输出
    print("步骤:")  # 打印输出
    for i, s in enumerate(recipe.steps, 1):  # for 循环
        print(f"  {i}. {s}")  # 打印输出


def main() -> None:  # demo 入口函数
    demo_str_parser()  # 执行本行逻辑
    demo_json_parser()  # 执行本行逻辑
    demo_pydantic_parser()  # 执行本行逻辑


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
