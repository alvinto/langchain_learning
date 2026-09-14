from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_core.tools import tool  # 导入 @tool 装饰器
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage  # 导入消息类型 Human/AI/System
from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置
"""
05-2 bind_tools 手工 Tool Calling
学到：理解 Tool Calling 的底层原理 —— Tool execution loop 工具执行循环 
LLM 返回 tool_calls，你执行后把结果以 ToolMessage 回传，再让 LLM 总结。
（生产中用 LangGraph 的 create_react_agent 自动处理，但先看一遍手动流程很有帮助）

tool 定义格式
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "查询指定城市的当前天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "城市名称，如北京、上海"
                    }
                },
                "required": ["location"]
            }
        }
    }
]

大模型返回函数调用指令
{
  "tool_calls": [
    {
      "id": "call_001",
      "type": "function",
      "function": {
        "name": "get_current_weather",
        "arguments": "{\"location\": \"上海\"}"
      }
    },
    {
      "id": "call_002",
      "type": "function",
      "function": {
        "name": "get_current_weather",
        "arguments": "{\"location\": \"北京\"}"
      }
    }
  ]
}
"""

@tool
def get_city_weather(city:str) -> str:
    """获取城市当前摄氏温度，返回数字。拿到温度结果后，可以传给c2f工具做单位转换"""
    mock_data = {"上海":26, "北京":22, "深圳":30}
    return str(mock_data.get(city, 20))

@tool
def c2f(celcius:float) -> float:
    """摄氏度转华氏度，公式 F = C * 1.8 + 32，使用前面工具返回的温度值作为参数"""
    return celcius * 1.8 +32


TOOLS = {
    "get_city_weather": get_city_weather,
    "c2f": c2f
}


def main() -> None:  # demo 入口函数
    banner("05-2 bind_tools (manual loop)")  # 打印章节标题分隔条
    llm_with_tools = get_llm().bind_tools(list(TOOLS.values()))

    # 增加系统提示，强制多步工具推理
    messages = [  # 赋值给 messages
        SystemMessage("分步执行工具，拿到工具返回值作为下一轮工具参数，不要重复调用相同工具。"),  # 构造系统消息
        HumanMessage("上海现在多少摄氏度，转成华氏度告诉我")  # 构造用户消息
    ]  # 闭合括号/元组/字典
    ai = llm_with_tools.invoke(messages)  # 同步调用链/图

    # 改用while循环，逻辑更清晰
    max_round = 3  # 赋值给 max_round
    round_num = 1  # 赋值给 round_num
    while round_num <= max_round:  # while 循环
        print(f"\n第{round_num}轮 tool_calls: {ai.tool_calls}")  # 打印输出
        if not ai.tool_calls:  # 代码块起始
            break  # 跳出循环
        # 执行所有工具，tool的执行是在框架中，并不是大模型执行的
        # 这里是手动调用对应的tool，在Agent中原理也是这样的
        for call in ai.tool_calls:  # for 循环
            res = TOOLS[call["name"]].invoke(call["args"])  # 同步调用链/图
            print(f"  执行 {call['name']}({call['args']}) = {res}")  # 打印输出
            messages.append(ToolMessage(content=str(res), tool_call_id=call["id"]))  # 构造工具返回消息
        # 重新请求模型
        ai = llm_with_tools.invoke(messages)  # 同步调用链/图
        round_num += 1  # 执行本行逻辑

    print("\n===== 最终输出 ====")  # 打印输出
    print(ai.content)  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数