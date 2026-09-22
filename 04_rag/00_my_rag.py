"""
04-7 手写简易 RAG（从零实现）
学到：不依赖 LangChain 高层组件，手动实现文档切分、向量化、余弦相似度检索、LLM 调用，理解 RAG 核心原理。
"""
import numpy as np

from _common import get_embeddings, get_llm

# 1. 原始文档
raw_text = """
RAG全称检索增强生成。
RAG分为离线索引和在线查询两个阶段。
索引阶段：文档加载、切分、向量化入库。
查询阶段：问题向量化，检索相关文档，拼接上下文交给大模型。
"""

# 2. 简单切分（替代RecursiveCharacterTextSplitter）
def simple_split(text, chunk_size=50):
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunks.append(text[i:i+chunk_size])
    return chunks
chunks = simple_split(raw_text)

# 3. Embedding 调用
client = get_embeddings()

# 4. 构建向量库（内存字典，替代FAISS/Chroma）
vector_db = []
for chunk in chunks:
    vec = client.embed_documents(chunk)[0]
    vector_db.append({"text": chunk, "vec": vec})

# 余弦相似度
def cos_sim(a,b):
    return np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b))

# 5. 检索函数（替代Retriever）
def retrieve(query, top_k=2):
    q_vec = client.embed_documents(query)[0]
    scored = []
    for item in vector_db:
        score = cos_sim(q_vec, item["vec"])
        scored.append((score, item["text"]))
    scored.sort(reverse=True)
    return [s[1] for s in scored[:top_k]]

# 6. 组装prompt调用LLM
question = "RAG包含哪两个阶段？"
docs = retrieve(question)
context = "\n".join(docs)
prompt = f"""基于上下文回答，不要编造。
上下文：{context}
问题：{question}
"""
resp = get_llm().invoke([{"role":"user","content":prompt}])
print(resp.content)