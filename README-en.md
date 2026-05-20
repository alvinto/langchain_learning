# LangChain Agent from 0 to 1

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/LangChain-0.3%20%7C%201.x-green.svg)](https://python.langchain.com/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![syntax-check](https://github.com/zz-big/langchain_learning/actions/workflows/syntax-check.yml/badge.svg)](https://github.com/zz-big/langchain_learning/actions/workflows/syntax-check.yml)

> A **progressively-structured, runnable** LangChain Agent learning repo.
> Goal: take you from "calling an LLM" all the way to a **mini Claude-Code-style Agent Harness**.

> 🇨🇳 [中文版 README](README.md)

One topic per chapter, one knowledge-point per file, every demo runnable with a single `python …`. Models default to the **OpenAI-compatible protocol**, so you can switch between OpenAI / DeepSeek / Qwen (DashScope) / Zhipu / Ollama just by editing `.env`.

## Learning path

| Chapter | Topic | Key concepts |
| --- | --- | --- |
| [01_basics/](01_basics/) | LLM basics | model invocation, message types, prompt templates, output parsers, streaming |
| [02_lcel/](02_lcel/) | LCEL | the `\|` pipe, parallel, branch, lambda wrapping |
| [03_memory/](03_memory/) | Conversation memory | `ChatHistory`, `RunnableWithMessageHistory`, message trimming |
| [04_rag/](04_rag/) | Retrieval-augmented generation | loaders, splitters, embeddings, vector stores, RAG chain, multi-query |
| **[05_tools_agents/](05_tools_agents/)** | **Tools & Agent** | `@tool`, `bind_tools`, manual ReAct loop, `create_agent` |
| **[06_langgraph/](06_langgraph/)** | **LangGraph** | StateGraph, ToolNode, conditional edges, human-in-the-loop, checkpoint |
| [07_project_knowledge_bot/](07_project_knowledge_bot/) | Full project · knowledge bot | RAG + multi-turn chat + citations (synthesis of chapters 1–6) |
| **[08_agent_harness/](08_agent_harness/)** | **Mini Claude Code** | sandboxed tools, permission gate, hook bus, sub-agent, context compression, error budget |

The bolded four chapters are the **Agent main line** and the focus of this repo.

After finishing you should be able to:
- assemble a tool-using Agent in ~30 lines via `create_agent`
- hand-craft a LangGraph `StateGraph` with loops, branches, and human-in-the-loop
- understand why 90% of complexity in Claude Code / Cursor / Cline lives in the **harness layer**, not in the LLM call itself

## Quick start

```bash
# 1. clone
git clone https://github.com/zz-big/langchain_learning.git
cd langchain_learning

# 2. virtualenv (Python ≥ 3.10 recommended)
python3 -m venv .venv && source .venv/bin/activate

# 3. install
pip install -r requirements.txt

# 4. configure your model
cp .env.example .env
# edit .env: LLM_BASE_URL / LLM_API_KEY / LLM_MODEL

# 5. run the first demo
python 01_basics/01_hello_llm.py
```

## Choosing a model provider

Only three env vars matter. Common picks:

**OpenAI**
```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=gpt-4o-mini
EMBED_MODEL=text-embedding-3-small
```

**DeepSeek** (cheap, default in this repo)
```env
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=deepseek-chat
```

**Qwen / DashScope** (China region, OpenAI-compatible, **ships with embeddings**)
```env
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=qwen-plus
EMBED_MODEL=text-embedding-v3
```

**Ollama (local)** — no API key needed if you have Ollama installed
```env
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=qwen2.5:7b
```

> RAG chapters (04 / 07 / 08) need embeddings. If your primary provider does not ship embeddings (DeepSeek doesn't), set `EMBED_BASE_URL / EMBED_API_KEY / EMBED_MODEL` separately in `.env`.

## See every demo's prompt stack (LangSmith)

**Pretty much mandatory** while learning Agents: LangSmith timeline-views every LLM call, every tool call, every prompt context so you can see *what the model actually saw, said, and called*.

Two-step setup:

1. Sign up at [smith.langchain.com](https://smith.langchain.com) (free) → Settings → API Keys, create a personal key
2. Add one line to `.env`:
   ```env
   LANGCHAIN_API_KEY=lsv2_pt_xxx
   ```

Then run any demo:

```bash
$ python 05_tools_agents/03_react_agent.py
[langsmith] tracing on · project=langchain_learning · dashboard https://smith.langchain.com
…
```

Open https://smith.langchain.com and you'll see the full call stack — every prompt, every `tool_calls`, token usage, latency.

> **Filling in the key auto-enables tracing for all demos** — no code change to chapters 01–08. The logic lives in [`_common.py`](_common.py) `_setup_langsmith()` and syncs both the LangChain 0.3 (`LANGCHAIN_*`) and 1.x (`LANGSMITH_*`) env-var names.
>
> Don't want it? Leave the key blank — zero side effects.

## Repo layout

```
.
├── _common.py                 # shared config: get_llm() / get_embeddings(); single source of truth
├── .env.example               # env template
├── requirements.txt
├── 01_basics/                 # LLM basics
├── 02_lcel/                   # LCEL expressions
├── 03_memory/                 # conversation memory
├── 04_rag/                    # retrieval-augmented generation
├── 05_tools_agents/           # tools / Agent
├── 06_langgraph/              # LangGraph state machines
├── 07_project_knowledge_bot/  # full project: knowledge-base Q&A bot
└── 08_agent_harness/          # mini Claude-Code-style Agent Harness
```

Each chapter has its own README; every `.py` file has a docstring + `if __name__ == "__main__"` entrypoint — just read top-to-bottom.

## Design principles

- **One file, one concept.** Each demo stands alone. No "you must read three other files first" puzzles.
- **Code > prose.** The code plus the top-of-file docstring **is** the tutorial. READMEs are just navigation.
- **Works from anywhere.** Default is DeepSeek; `_common.py` also adds common Chinese-region API hosts to `NO_PROXY` so they survive a local Clash / V2Ray proxy.
- **Compatible with both LangChain 0.3 and 1.x.** Renamed APIs in 05/06 are wrapped in `try/except` fallbacks.

## FAQ

**Q: I get `contents is neither str nor list of str` running chapter 04.**
A: Some Chinese-region OpenAI-compatible embedding endpoints don't like tiktoken pre-chunking. `_common.get_embeddings()` already disables it via `check_embedding_ctx_length=False`. Don't construct `OpenAIEmbeddings` directly — go through the helper.

**Q: DeepSeek has no embeddings, what now?**
A: Set `EMBED_BASE_URL` separately (e.g. DashScope). The code prefers `EMBED_*` and falls back to `LLM_*`.

**Q: `FAISS.load_local` complains about `allow_dangerous_deserialization`.**
A: All sample code passes it explicitly — it's FAISS's safety prompt for pickle de-serialization. Fine for local learning.

**Q: I set my LangSmith key but don't see the `[langsmith] tracing on` line.**
A: Check whether `.env` contains `LANGCHAIN_TRACING_V2=false`. That's an explicit kill-switch which `_common.py` respects (and prints a heads-up about). Delete it or change it to `true`.

**Q: Why doesn't chapter 08 use `create_react_agent`?**
A: That prebuilt agent buries hooks / permissions / compression. Chapter 08 demonstrates exactly the layer you have to *open up* — write the `StateGraph` by hand — to insert those concerns.

## Contributing

Welcome:

- typo / bug / version-compat fixes
- new demos (please keep the "one file, one concept" rule)
- new hooks / tools / sub-agent forms under [`08_agent_harness/`](08_agent_harness/)
- translations (e.g. this English README)

Before opening a PR:

1. Confirm the demo runs standalone: `python <your-file>.py`
2. Top-of-file docstring required
3. Do not commit `.env`, `_faiss_index/`, `.DS_Store`, or other generated files

## License

[MIT](LICENSE) — free to use, modify, redistribute.

## Acknowledgements

- [LangChain](https://github.com/langchain-ai/langchain) / [LangGraph](https://github.com/langchain-ai/langgraph)
- DeepSeek / Qwen / OpenAI and other model providers
- Chapter 08 takes inspiration from open implementations of Claude Code, Cursor, and Cline
