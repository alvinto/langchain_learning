"""
01-1 第一次调用 LLM
学到：怎么用 _common.get_llm() 拿模型，调用 .invoke() 单轮问答。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from _common import get_llm, banner  # 导入项目共享 LLM/Embedding 配置


def main() -> None:  # demo 入口函数
    banner("01-1 Hello LLM")  # 打印章节标题分隔条
    llm = get_llm()  # 获取 ChatOpenAI 兼容 LLM
    # invoke 是最基础的同步调用，返回 AIMessage
    answer = llm.invoke("用一句话解释什么是 LangChain")  # 同步调用链/图
    print("内容字段:", answer.content)  # 打印输出
    print("元信息:", answer.response_metadata)  # 打印输出

if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
