"""
01-4 输出解析器
学到：
- StrOutputParser：拿到纯字符串而不是 AIMessage
- JsonOutputParser：把 JSON 字符串解析成 dict
- PydanticOutputParser：直接得到 Pydantic 对象，附带 schema 提示
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from typing import List
from pydantic import BaseModel, Field

from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from _common import get_llm, banner


class Recipe(BaseModel):
    name: str = Field(description="菜名")
    ingredients: List[str] = Field(description="原料列表")
    steps: List[str] = Field(description="步骤")


def demo_str_parser() -> None:
    banner("StrOutputParser")
    chain = get_llm() | StrOutputParser()
    print(chain.invoke("写一个冷笑话"))


def demo_json_parser() -> None:
    banner("JsonOutputParser")
    parser = JsonOutputParser()
    prompt = ChatPromptTemplate.from_messages([
        ("system", "只返回 JSON，键为 city/temperature/condition"),
        ("human", "{q}"),
    ])
    '''
    这里的 | 不是 Python 原生位或运算符，是 LangChain 重写的魔法运算符，对应 Runnable 对象的管道，作用类似 Linux 的管道：把前一个组件的输出，作为后一个组件的输入。
    '''
    chain = prompt | get_llm() | parser
    print(chain.invoke({"q": "今天北京天气怎么样？给一个示例 JSON"}))


def demo_pydantic_parser() -> None:
    banner("PydanticOutputParser")
    parser = PydanticOutputParser(pydantic_object=Recipe)
    ## 把需要输出的格式通过提示词给到模型
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个菜谱助手。\n{format_instructions}"),
        ("human", "给我一个 {dish} 的菜谱"),
    ]).partial(format_instructions=parser.get_format_instructions())

    chain = prompt | get_llm() | parser
    recipe: Recipe = chain.invoke({"dish": "番茄炒蛋"})
    print(f"菜名: {recipe.name}")
    print(f"原料: {recipe.ingredients}")
    print("步骤:")
    for i, s in enumerate(recipe.steps, 1):
        print(f"  {i}. {s}")


def main() -> None:
    demo_str_parser()
    demo_json_parser()
    demo_pydantic_parser()


if __name__ == "__main__":
    main()
