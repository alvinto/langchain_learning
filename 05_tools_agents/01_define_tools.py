"""
05-1 定义工具
学到：用 @tool 装饰器把 Python 函数变成 LLM 能调用的 Tool。
docstring 和参数 type hint 会被 LLM 当成"使用说明"，所以要写清楚。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_core.tools import tool
from _common import banner


@tool
def add(a: int, b: int) -> int:
    """计算两个整数相加。"""
    return a + b


@tool
def get_weather(city: str) -> str:
    """查询指定城市的天气（示例返回固定值）。"""
    return f"{city} 今天 25 度，多云。"


def main() -> None:
    banner("05-1 Define Tools")
    for t in [add, get_weather]:
        print(f"name: {t.name}")
        print(f"description: {t.description}")
        print(f"args_schema: {t.args}")
        print()

    # 直接像普通函数一样调用
    print("add.invoke({'a': 2, 'b': 3}) =", add.invoke({"a": 2, "b": 3}))
    print("get_weather.invoke({'city': '北京'}) =", get_weather.invoke({"city": "北京"}))


if __name__ == "__main__":
    main()
