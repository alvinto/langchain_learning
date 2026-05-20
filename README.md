# LangChain Agent 从 0 到 1

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/LangChain-0.3%20%7C%201.x-green.svg)](https://python.langchain.com/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

> 一份循序渐进、可独立运行的 **LangChain Agent 学习仓库**，目标是把 Agent 从"调用 LLM"一路带到"迷你版 Claude Code 风格的 Agent Harness"。

每一章一个目录、一个文件一个知识点、所有 demo 直接 `python ...` 就能跑。模型默认走 **OpenAI 兼容协议**，方便切换 DeepSeek / 通义千问 / 智谱 / Ollama / OpenAI 等任一提供方。

## 学习路径

| 章节 | 主题 | 关键知识点 |
| --- | --- | --- |
| [01_basics/](01_basics/) | LLM 基础 | 调用模型、消息类型、提示词模板、输出解析、流式输出 |
| [02_lcel/](02_lcel/) | LCEL 表达式 | `\|` 管道、并行、分支、Lambda 包装 |
| [03_memory/](03_memory/) | 会话记忆 | ChatHistory、`RunnableWithMessageHistory`、消息裁剪 |
| [04_rag/](04_rag/) | 检索增强生成 | 文档加载、切分、Embedding、向量库、RAG 链路、多查询召回 |
| **[05_tools_agents/](05_tools_agents/)** | **工具与 Agent** | `@tool`、`bind_tools`、手写 ReAct、`create_agent` |
| **[06_langgraph/](06_langgraph/)** | **LangGraph** | 状态图、ToolNode、条件边、人在回路、checkpoint |
| [07_project_knowledge_bot/](07_project_knowledge_bot/) | 完整项目 · 知识库问答 | RAG + 多轮对话 + 引用来源（前 6 章的综合） |
| **[08_agent_harness/](08_agent_harness/)** | **迷你 Claude Code** | 工具沙箱、权限网关、Hook 总线、子 Agent、上下文压缩、错误预算 |

加粗的四章是 **Agent 主线**，也是这份仓库的重点。

读完之后你应该能：
- 用 `create_agent` 在 30 行内拼一个会调工具的 Agent
- 用 LangGraph `StateGraph` 手写循环、分支、人在回路的复杂 Agent
- 理解 Claude Code / Cursor / Cline 这类产品 90% 的复杂度 ——在 **Harness 层**，不在 LLM 调用本身

## 快速开始

```bash
# 1. 克隆 + 进目录
git clone https://github.com/zz-big/langchain_learning.git
cd langchain_learning

# 2. 创建虚拟环境（建议 Python ≥ 3.10）
python3 -m venv .venv && source .venv/bin/activate

# 3. 装依赖
pip install -r requirements.txt

# 4. 配置模型
cp .env.example .env
# 编辑 .env，填入你的 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL

# 5. 跑第一个 demo
python 01_basics/01_hello_llm.py
```

## 选择模型提供方

`.env` 里只需要改三个变量。下面是常见选择：

**DeepSeek**（国内可直连、便宜，**默认推荐**）
```env
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=deepseek-chat
```

**通义千问 DashScope**（国内，OpenAI 兼容模式，**带原生 Embedding**）
```env
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=qwen-plus
EMBED_MODEL=text-embedding-v3
```

**OpenAI 官方**
```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=gpt-4o-mini
EMBED_MODEL=text-embedding-3-small
```

**Ollama 本地**（无需 API key，但要本地装好 Ollama）
```env
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=qwen2.5:7b
```

> RAG 章节（04/07/08）需要 Embedding。如果主模型方没有 Embedding（如 DeepSeek），就在 `.env` 里单独配 `EMBED_BASE_URL / EMBED_API_KEY / EMBED_MODEL`。

## 看每个 demo 的提示词堆栈（LangSmith）

**学 Agent 时几乎必备的调试工具**：把每一次模型调用、每一个工具调用、每一段 prompt 上下文都画成时间线，让你看到"LLM 到底看到了什么、说了什么、调用了什么工具"。

接入方法只有两步：

1. 去 [smith.langchain.com](https://smith.langchain.com) 注册（免费）→ Settings → API Keys 申请一个个人 key
2. 在 `.env` 里加一行（其它什么都不用改）：
   ```env
   LANGCHAIN_API_KEY=lsv2_pt_xxx
   ```

然后跑任意一个 demo：

```bash
$ python 05_tools_agents/03_react_agent.py
[langsmith] tracing on · project=langchain_learning · dashboard https://smith.langchain.com
...
```

打开 https://smith.langchain.com 就能看到这次跑出来的完整调用栈：每条提示词、每个 `tool_calls`、token 用量、耗时全都在。

> **填了 key 就自动接入所有 demo**——01 到 08 章不用改一行代码。背后逻辑写在 [`_common.py`](_common.py) 的 `_setup_langsmith()` 函数里，按需自动同步 LangChain 0.3 (`LANGCHAIN_*`) 和 1.x (`LANGSMITH_*`) 两套环境变量名。
>
> 不想用？不填 key 就完全跳过，零副作用。

## 仓库结构

```
.
├── _common.py                 # 共享配置：get_llm() / get_embeddings()，所有 demo 通过它建模型
├── .env.example               # 环境变量模板
├── requirements.txt
├── 01_basics/                 # LLM 基础
├── 02_lcel/                   # LCEL 表达式
├── 03_memory/                 # 会话记忆
├── 04_rag/                    # 检索增强生成
├── 05_tools_agents/           # 工具 / Agent
├── 06_langgraph/              # LangGraph 状态图
├── 07_project_knowledge_bot/  # 完整项目：知识库问答机器人
└── 08_agent_harness/          # 迷你版 Claude Code 风格 Agent Harness
```

每章一份 README，每个 `.py` 文件顶部都有中文说明 + `if __name__ == "__main__"` 入口，按顺序读就行。

## 设计原则

- **每个文件一个知识点**：单独跑、单独懂，不强行串成大项目。
- **代码 > 文字**：示例代码 + 顶部 docstring 就是教程本身，README 只是导览。
- **国内可用**：默认 DeepSeek，`_common.py` 还自动把国内 API 域名加进 `NO_PROXY`，避免 Clash/V2Ray 影响 SSL 握手。
- **同时兼容 LangChain 0.3 与 1.x**：05/06 章涉及到改名的 API 都做了 `try/except` fallback。

## 常见问题

**Q：跑到 04 章报 "contents is neither str nor list of str"？**
A：国产 Embedding 兼容接口对 tiktoken 预切分不友好。`_common.get_embeddings()` 已经把 `check_embedding_ctx_length=False` 默认关掉了，不要自己再手工建 `OpenAIEmbeddings`。

**Q：DeepSeek 没有 Embedding 怎么办？**
A：在 `.env` 里单独配 `EMBED_BASE_URL`（如 DashScope）。代码会优先用 `EMBED_*`，回退到 `LLM_*`。

**Q：FAISS 报 "allow_dangerous_deserialization"？**
A：示例代码都已经显式打开。这是 FAISS 自己反序列化 pickle 的安全提示，仅供本地学习用。

**Q：我填了 LangSmith key 但跑 demo 时没看到 `[langsmith] tracing on` 那行？**
A：检查 `.env` 里有没有 `LANGCHAIN_TRACING_V2=false`。这一项是显式开关，设了 false 会被 `_common.py` 尊重并打印一条提示。删掉那行或改成 `true` 即可。

**Q：为什么 08 章不用 `create_react_agent`？**
A：prebuilt agent 把 hook / 权限 / 压缩这些都封死了。08 章演示的就是"打开盒子，自己手写 StateGraph 才能插入这些层"。

## 贡献

欢迎以下形式的 PR：

- 修 typo / bug / 老版本 API 兼容
- 加新的 demo（请保持"一文件一知识点"）
- 在 `08_agent_harness/` 加新的 hook / 工具示例
- 翻译（如英文版 README）

提 PR 前请：
1. 确认 demo 可独立运行（`python <你的文件>.py`）
2. 文件顶部加中文说明
3. 不要把 `.env` / 索引文件 / `.DS_Store` 提交进来

## License

[MIT](LICENSE) — 自由使用、修改、再分发。

## 致谢

- [LangChain](https://github.com/langchain-ai/langchain) / [LangGraph](https://github.com/langchain-ai/langgraph)
- DeepSeek / 通义千问 / OpenAI 等模型提供方
- 08 章的设计灵感来自 Claude Code、Cursor、Cline 等开源 Agent 实现
