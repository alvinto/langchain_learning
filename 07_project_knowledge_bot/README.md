# 个人知识库问答机器人（完整项目）

把前 6 章的能力组合起来：**RAG 检索 + 多轮对话 + 引用来源**。

## 功能

- 把 `data/` 下的所有 `.md` / `.txt` 文件（你自己的笔记/文档）建索引
- 命令行交互问答，回答时给出引用片段
- 多轮对话记忆（按 thread_id 隔离）
- 一键改写问题（用历史上下文消歧后再去检索）

## 目录结构

```
07_project_knowledge_bot/
├── config.py        # 路径与常量
├── ingest.py        # 数据导入：load → split → embed → save FAISS
├── chains.py        # 三个核心链：condense / retrieve / answer
├── app.py           # CLI 入口（LangGraph 编排）
└── data/            # 你的私有文档放这里
    ├── intro.md
    └── faq.md
```

## 怎么跑

```bash
# 1. 把要问的文档放进 data/（已附两份示例）
ls 07_project_knowledge_bot/data/

# 2. 建索引（首次或文档有更新时跑）
python 07_project_knowledge_bot/ingest.py

# 3. 启动问答
python 07_project_knowledge_bot/app.py
```

## 关键设计

| 步骤 | 做了什么 | 对应章节 |
| --- | --- | --- |
| 加载文档 | DirectoryLoader 读 `data/**` | 04-1 |
| 切分 | RecursiveCharacterTextSplitter | 04-2 |
| 向量化 + 持久化 | Embeddings + FAISS.save_local | 04-3/4 |
| 改写问题 | 用历史消息把"它/那个"消歧 | 02-5 |
| 检索 | 向量相似度 top-k | 04-5 |
| 回答 | 拼 prompt → LLM → 流式输出 | 04-5 / 01-5 |
| 多轮记忆 | LangGraph MessagesState + checkpoint | 06-2 |

## 进阶练习

- 把 FAISS 换成 Chroma 或 Milvus
- 加个 `@tool` 让 Agent 可以"按需检索"而不是每次都查（参考 05-3）
- 接 Streamlit / Gradio 给它加个 Web UI
- 把 MemorySaver 换成 SqliteSaver 实现持久化
