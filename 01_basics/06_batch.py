"""
01-6 batch批量处理
学到：用 .batch() 将多个消息批量发送给模型，batch_as_completed生成过程中收到单个输入的处理结果，max_concurrency控制并发数量
config={
        'max_concurrency': 5,  # Limit to 5 parallel calls
    }
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_core.prompts import ChatPromptTemplate  # 导入 LangChain 提示词模板
from langchain_core.output_parsers import StrOutputParser  # 导入输出解析器
from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置


def main() -> None:  # demo 入口函数
    banner("01-6 batch")  # 打印章节标题分隔条

    model = get_llm()
    responses = model.batch([
        "为什么鹦鹉有五颜六色的羽毛？",
        "飞机是如何飞行的？",
        "什么是量子计算？"
    ])
    #需要所有结果都返回后一起返回
    for response in responses:
        print(response)

    # 一个个返回,使用max_concurrency控制并发
    for response in model.batch_as_completed([
        "为什么鹦鹉有五颜六色的羽毛？",
        "飞机是如何飞行的？",
        "什么是量子计算？"
    ],
            config={
                'max_concurrency': 2,  # Limit to 5 parallel calls
            }
    ):
        print(response)

if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
