"""
数据导入：把 data/ 下的所有 .md/.txt 切片、向量化、存进 FAISS。
重新跑一次会重建索引（覆盖）。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
import sys  # 导入 sys 标准库
import shutil  # 导入 shutil 文件操作
from pathlib import Path  # 导入 Path 处理路径
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将项目根目录加入模块搜索路径

from langchain_community.document_loaders import DirectoryLoader, TextLoader  # 导入 LangChain 社区集成组件
from langchain_community.vectorstores import FAISS  # 导入 LangChain 社区集成组件
from langchain_text_splitters import RecursiveCharacterTextSplitter  # 导入文本切分器

from _common import get_embeddings, banner  # 导入项目共享 LLM/Embedding 配置
from config import DATA_DIR, INDEX_DIR, CHUNK_SIZE, CHUNK_OVERLAP  # 执行本行逻辑


def load_documents():  # 定义函数
    loaders = []  # 赋值给 loaders
    for pattern in ("**/*.md", "**/*.txt"):  # for 循环
        loaders.append(DirectoryLoader(  # 执行本行逻辑
            str(DATA_DIR),  # 执行本行逻辑
            glob=pattern,  # 执行本行逻辑
            loader_cls=TextLoader,  # 执行本行逻辑
            loader_kwargs={"encoding": "utf-8"},  # 执行本行逻辑
            show_progress=False,  # 执行本行逻辑
        ))  # 执行本行逻辑
    docs = []  # 赋值给 docs
    for loader in loaders:  # for 循环
        docs.extend(loader.load())  # 执行本行逻辑
    return docs  # 返回结果


def main() -> None:  # demo 入口函数
    banner("Knowledge Bot · Ingest")  # 打印章节标题分隔条

    if not DATA_DIR.exists() or not any(DATA_DIR.iterdir()):  # 代码块起始
        print(f"[!] {DATA_DIR} 是空的，请先放入 .md / .txt 文件。")  # 打印输出
        return  # 提前返回

    docs = load_documents()  # 赋值给 docs
    print(f"加载 {len(docs)} 个文档")  # 打印输出

    splitter = RecursiveCharacterTextSplitter(  # 赋值给 splitter
        chunk_size=CHUNK_SIZE,  # 执行本行逻辑
        chunk_overlap=CHUNK_OVERLAP,  # 执行本行逻辑
        separators=["\n\n", "\n", "。", "！", "？", "，", " ", ""],  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    chunks = splitter.split_documents(docs)  # 赋值给 chunks
    print(f"切分出 {len(chunks)} 个 chunk")  # 打印输出

    if INDEX_DIR.exists():  # 代码块起始
        shutil.rmtree(INDEX_DIR)  # 执行本行逻辑

    print("正在向量化并写入 FAISS …")  # 打印输出
    vs = FAISS.from_documents(chunks, get_embeddings())  # 获取 Embedding 模型
    vs.save_local(str(INDEX_DIR))  # 执行本行逻辑
    print(f"[√] 索引已保存到 {INDEX_DIR}")  # 打印输出


if __name__ == "__main__":  # 脚本直接运行时执行 main
    main()  # 调用 demo 主函数
