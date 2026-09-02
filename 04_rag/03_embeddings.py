"""
04-3 Embedding 向量化
学到：把文本变成定长向量，向量越接近 → 语义越相似（余弦相似度）。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
import math  # 执行本行逻辑
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from _common import get_embeddings, banner  # 导入项目共享 LLM/Embedding 配置


def cosine(a, b) -> float:  # 定义函数
    dot = sum(x * y for x, y in zip(a, b))  # for 循环
    na = math.sqrt(sum(x * x for x in a))  # for 循环
    nb = math.sqrt(sum(y * y for y in b))  # for 循环
    return dot / (na * nb)  # 返回结果


def main() -> None:  # demo 入口函数
    banner("04-3 Embeddings")  # 打印章节标题分隔条
    emb = get_embeddings()  # 获取 Embedding 模型

    sentences = [  # 赋值给 sentences
        "我今天吃了拉面",  # 字符串/template 参数
        "今天的午饭是面条",  # 字符串/template 参数
        "今天天气真不错",  # 字符串/template 参数
    ]  # 闭合括号/元组/字典
    vectors = emb.embed_documents(sentences)  # 赋值给 vectors
    print(f"向量维度: {len(vectors[0])}\n")  # 打印输出

    # 两两计算余弦相似度
    for i in range(len(sentences)):  # for 循环
        for j in range(i + 1, len(sentences)):  # for 循环
            sim = cosine(vectors[i], vectors[j])  # 赋值给 sim
            print(f"{sentences[i]:20s} vs {sentences[j]:20s} -> {sim:.4f}")  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
