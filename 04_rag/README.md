# 04 · RAG（检索增强生成）

让 LLM 回答它本来不知道的私有/外部知识：把文档切块、向量化、存到向量库，问的时候先检索 top-k 再喂给模型。

| 文件 | 学到什么 |
| --- | --- |
| [01_document_loader.py](01_document_loader.py) | `TextLoader / DirectoryLoader` 把文件变成 `Document` |
| [02_text_splitter.py](02_text_splitter.py) | `RecursiveCharacterTextSplitter` 切长文 |
| [03_embeddings.py](03_embeddings.py) | Embedding 模型 + 余弦相似度 |
| [04_vector_store.py](04_vector_store.py) | FAISS 本地向量库，索引可保存到磁盘 |
| [05_basic_rag.py](05_basic_rag.py) | 一条完整 RAG 链：`retriever → context → prompt → llm` |
| [06_multi_query_rag.py](06_multi_query_rag.py) | `MultiQueryRetriever`：让 LLM 改写多个 query 提高召回 |

```bash
python 04_rag/05_basic_rag.py   # 首次跑会自动建索引
```

> 索引存在 `_faiss_index/` 下（已在 `.gitignore` 中），删掉重跑即可重建。
> 示例文档在 [`data/sample.md`](data/sample.md)，换成你自己的 `.md` 试试。
