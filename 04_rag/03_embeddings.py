"""
04-3 Embedding 向量化
学到：把文本变成定长向量，向量越接近 → 语义越相似（余弦相似度）。
"""
from __future__ import annotations
import sys
import math
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from _common import get_embeddings, banner


def cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb)


def main() -> None:
    banner("04-3 Embeddings")
    emb = get_embeddings()

    sentences = [
        "我今天吃了拉面",
        "今天的午饭是面条",
        "今天天气真不错",
    ]
    vectors = emb.embed_documents(sentences)
    print(f"向量维度: {len(vectors[0])}\n")

    # 两两计算余弦相似度
    for i in range(len(sentences)):
        for j in range(i + 1, len(sentences)):
            sim = cosine(vectors[i], vectors[j])
            print(f"{sentences[i]:20s} vs {sentences[j]:20s} -> {sim:.4f}")


if __name__ == "__main__":
    main()
