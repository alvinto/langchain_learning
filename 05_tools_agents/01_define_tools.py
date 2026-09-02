"""
05-1 定义工具
学到：用 @tool 装饰器把 Python 函数变成 LLM 能调用的 Tool。
docstring 和参数 type hint 会被 LLM 当成"使用说明"，所以要写清楚。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_core.tools import tool  # 导入 @tool 装饰器
from _common import banner  # 导入项目共享 LLM/Embedding 配置


@tool  # 声明 LangChain 工具
def add(a: int, b: int) -> int:  # 定义函数
    """计算两个整数相加。"""
    return a + b  # 返回结果


@tool  # 声明 LangChain 工具
def get_weather(city: str) -> str:  # 定义函数
    """查询指定城市的天气（示例返回固定值）。"""
    return f"{city} 今天 25 度，多云。"  # 返回结果


def main() -> None:  # demo 入口函数
    banner("05-1 Define Tools")  # 打印章节标题分隔条
    for t in [add, get_weather]:  # for 循环
        print(f"name: {t.name}")  # 打印输出
        print(f"description: {t.description}")  # 打印输出
        print(f"args_schema: {t.args}")  # 打印输出
        print()  # 打印输出

    # 直接像普通函数一样调用
    print("add.invoke({'a': 2, 'b': 3}) =", add.invoke({"a": 2, "b": 3}))  # 同步调用链/图
    print("get_weather.invoke({'city': '北京'}) =", get_weather.invoke({"city": "北京"}))  # 同步调用链/图


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
