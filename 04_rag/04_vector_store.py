"""
04-4 向量库（FAISS）
学到：把 chunk + 向量存进 FAISS，再做相似度检索。
FAISS 不需要外部服务，本地一个文件夹就能跑。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_community.document_loaders import TextLoader  # 导入 LangChain 社区集成组件
from langchain_community.vectorstores import FAISS  # 导入 LangChain 社区集成组件
from langchain_text_splitters import RecursiveCharacterTextSplitter  # 导入文本切分器
from _common import get_embeddings, banner  # 导入项目共享 LLM/Embedding 配置


INDEX_DIR = Path(__file__).parent / "_faiss_index"  # 赋值给 INDEX_DIR


def build_index() -> FAISS:  # 定义函数
    docs = TextLoader(  # 赋值给 docs
        str(Path(__file__).parent / "data" / "sample.md"),  # 执行本行逻辑
        encoding="utf-8",  # 执行本行逻辑
    ).load()  # 执行本行逻辑
    chunks = RecursiveCharacterTextSplitter(chunk_size=150, chunk_overlap=20).split_documents(docs)  # 赋值给 chunks
    vs = FAISS.from_documents(chunks, get_embeddings())  # 获取 Embedding 模型
    vs.save_local(str(INDEX_DIR))  # 执行本行逻辑
    return vs  # 返回结果


def main() -> None:  # demo 入口函数
    banner("04-4 FAISS Vector Store")  # 打印章节标题分隔条

    if INDEX_DIR.exists():  # 代码块起始
        print("[载入已有索引]")  # 打印输出
        vs = FAISS.load_local(str(INDEX_DIR), get_embeddings(), allow_dangerous_deserialization=True)  # 获取 Embedding 模型
    else:  # else 分支
        print("[首次构建索引]")  # 打印输出
        vs = build_index()  # 赋值给 vs

    query = "LangChain 的核心组件有哪些？"  # 赋值给 query
    print(f"\n查询: {query}\n")  # 打印输出
    for i, doc in enumerate(vs.similarity_search(query, k=3), 1):  # for 循环
        print(f"--- 命中 {i} ---")  # 打印输出
        print(doc.page_content)  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
