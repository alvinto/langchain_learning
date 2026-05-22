# 09_deep_research — Deep Research Agent（v2）

**并行多 Agent 研究助手**：给一个研究问题，它会自己规划、派多个子 Agent 并行检索、必要时反思补研究、最后合成一篇带引用的 Markdown 报告。

类比：OpenAI Deep Research / Perplexity Pro / Anthropic Research 的开源最小可跑实现。

> **v2 升级**：从 simple planner 升级为可选 supervisor 动态调度，全程 async 真并行，加入模型分层和实时进度。仍保留 simple 模式做教学对照。

## 两种运行模式

```bash
# supervisor 模式（默认）：动态决策、自带反思补研究
python 09_deep_research/app.py "你的研究问题"

# simple 模式：一次性 planner → 并行 researcher → writer（v1 教学版）
python 09_deep_research/app.py -m simple "你的研究问题"

# supervisor 最多 4 轮决策
python 09_deep_research/app.py -i 4 "你的研究问题"
```

### 主图拓扑对照

**simple 模式**（教学清晰，固定拆解）：

```
START → planner → [Send] → researcher×N (asyncio.gather 真并行) → writer → END
```

**supervisor 模式**（生产可用，动态调度）：

```
START → supervisor 子图 ──→ writer → END
        │
        └─ 内部循环：supervisor (ReAct) ─→ tools_node
                       ↑                      │ 并发跑所有 ConductResearch
                       └──────── 返回 ────────┘
           supervisor 看回来的 findings 后决定：
             a) 再调多个 ConductResearch 补研究
             b) 调 ResearchComplete 收工
```

## 跟前面章节的关系

| 章节 | 你已经学到的 | 在本章用到 |
| --- | --- | --- |
| 06 LangGraph | StateGraph、reducer、checkpointer | 主图就是 StateGraph，simple 模式用 **`Send` API** 做静态 fan-out |
| 08 Agent Harness | 手写 ReAct 循环 + 子 Agent | supervisor 子图本质就是 ReAct，只是工具变成 `ConductResearch/ResearchComplete` |
| —— 新概念 | —— | **multi-state 分层**（主图/supervisor/researcher 独立 state）、**custom reducer** override_or_extend、**async + asyncio.gather** 真并行 |

## 文件结构

```
09_deep_research/
├── app.py          ← CLI 入口（async, -m / -i 开关）
├── graph.py        ← 主图工厂 build_graph(mode=...)，两种模式都走这里
├── supervisor.py   ← 【v2 新增】supervisor 子图：ReAct 循环 + 并发派 researcher
├── planner.py      ← simple 模式用：一次性把 question 拆成 sub_questions
├── researcher.py   ← 子 Agent（async + progress_cb），simple/supervisor 都复用
├── writer.py       ← findings → 带 [^N] 引用的 Markdown 报告（async）
├── search.py       ← Tavily 优先 / DDG 兜底，async + 同步双入口
├── fetch.py        ← URL → 正文，httpx.AsyncClient + 重试，async + 同步双入口
├── state.py        ← 【v2 新增分层】ResearchState / SupervisorState / ResearcherState + override_or_extend
└── reports/        ← 生成的报告
```

## v2 核心设计点

| 设计点 | 在哪 | 为啥 |
| --- | --- | --- |
| **Supervisor 动态调度** | `supervisor.py` | 替代静态 planner。supervisor 用 `ConductResearch(topic)` 和 `ResearchComplete()` 两个工具自决，第一轮就并发派几个，看结果不够再派——**自带反思** |
| **真并行 async** | `search.py` / `fetch.py` / `researcher.py` 全部 async | 3 个子问题串行 ≈ 3×单个时间；用 `asyncio.gather` 并行后 ≈ max(单个) |
| **多 state 分层** | `state.py` | 主图/supervisor/researcher 各自 state 类，从**类型层面**禁止上下文越界。supervisor 内部 100 条 messages 不会污染主图 |
| **`override_or_extend` reducer** | `state.py` | 默认 append，传 `{"__override__": True, "value": [...]}` 时整体覆盖。supervisor 想"清空 findings 重研究"时用得到 |
| **模型分层** | `_common.py:get_llm(role=...)` + 各节点 | smart=决策、writer=写报告、cheap=压缩。设 `LLM_MODEL_SMART/WRITER/CHEAP` env var 切换；不设则全部回退到 `LLM_MODEL` |
| **实时流式进度** | `researcher.py:progress_cb` → `state.progress_events` → `app.py` stream | 每个 researcher 搜什么、读什么 URL 实时打到 CLI，告别"等 30 秒只看到一行" |
| **错误容忍** | `fetch.py` 重试 / `researcher.py` 异常兜底 / `supervisor.py` `asyncio.gather(return_exceptions=True)` | 单个 researcher 挂不影响整体；网络全挂时 writer 也能出"基于已有信息"的报告 |
| **引用编号在 Python 算** | `writer.py:_build_source_table` | LLM 自己编号经常错位，先把 url 去重编号再喂 `(id, url)` 表给 prompt |
| **planner / 简单模式保留** | `planner.py` + `graph.py:mode="simple"` | 静态 plan 比 supervisor 简单一个数量级，教学时还是好工具 |

## 怎么跑

### 1. 装依赖

```bash
pip install -r requirements.txt
```

v2 比 v1 新增 `httpx`。

### 2. （强烈推荐）申请 Tavily key

DDG 免 key 但结果一般且偶尔限流。Tavily 注册 [tavily.com](https://tavily.com) 免费 1000 次/月：

```env
TAVILY_API_KEY=tvly-xxxxxxxxxx
```

### 3. （可选）配模型分层

不配的话全程用 `LLM_MODEL`，能跑但不省钱。开 OpenAI 账号的可以这样：

```env
LLM_MODEL_SMART=gpt-4.1            # supervisor 决策 / researcher 探索
LLM_MODEL_WRITER=gpt-4.1           # 最终报告
LLM_MODEL_CHEAP=gpt-4.1-mini       # finalize 压缩
```

DeepSeek 用户单档就够便宜，全部留空即可。

### 4. 跑

```bash
python 09_deep_research/app.py "对比 LangGraph 和 OpenAI Agents SDK 的差异和适用场景"
```

报告会保存到 `09_deep_research/reports/<时间戳>_<mode>_<问题>.md`，全文也打到终端。

开着 LangSmith 看（`LANGCHAIN_API_KEY` 已配的话自动）特别爽——能直观看到 supervisor 怎么决策、每个 researcher 内部怎么循环。

## 试试这些 prompt

由浅到深，能体现 supervisor 价值的从第 3 题开始：

1. **简单事实查询**：「LangGraph 的 Send API 是用来做什么的」  
   → simple 模式 1~2 个子问题就解决；supervisor 也会很快收工
2. **对比类**：「对比 LangGraph 和 OpenAI Agents SDK 的差异和适用场景」  
   → simple 拆 4 个并行；supervisor 第一轮可能派 3 个，结果回来看有缺再派 1 个
3. **时效类**：「2025 年开源 Deep Research 项目有哪些值得关注」  
   → 测搜索时效；supervisor 模式更可能在第二轮补查"还有哪些没提到"
4. **多领域综合**：「为什么 MCP 协议在 2025 年突然火起来，它解决了什么」  
   → 横跨技术/生态/历史；supervisor 拆分能体现优势
5. **故意刁难**：「2026 年图灵奖会颁给谁」  
   → 好的 prompt 让它说"无法预测"而不是乱编

## 跟官方 open_deep_research 的对照

| 维度 | 我们的 09 章 v2 | 官方 langchain-ai/open_deep_research |
| --- | --- | --- |
| **核心架构** | supervisor + researcher，两层 | 几乎一致（clarify + brief + supervisor + researcher + compress + final_report） |
| **HITL clarification** | 跳过（v3 加） | 有：研究开始前 LLM 判断要不要先问用户 |
| **每个 researcher 独立 compress 节点** | 没有（在 `_finalize` 一步搞定） | 有，单独节点单独 prompt |
| **搜索后端** | Tavily + DDG | Tavily + Anthropic/OpenAI native search + **MCP 工具**（用户挂自己的） |
| **执行模式** | 全 async | 全 async（一致） |
| **模型分层** | smart/writer/cheap 三档 | summarize/research/compress/final 四档 |
| **评测** | 无 | 接入 Deep Research Bench，RACE 0.43，榜单第 6 |
| **部署** | CLI | LangGraph Studio + LangGraph Platform + Open Agent Platform |
| **代码量** | ~1000 行 | ~3000+ 行（单 `deep_researcher.py` 就 30KB） |
| **学习曲线** | 一个下午 | 一周 |

**何时该看官方版**：要打 benchmark、要在 LangGraph Studio 里调试、要上 Open Agent Platform、要接 MCP 工具生态。

**何时本章足够**：自己日常用、想读全代码、想理解每个设计为什么这样做、想在它基础上加自己的工具。

## 还能继续怎么优化（v3 待办）

- **HITL clarification 节点**：研究启动前 LLM 判断 question 是否清晰，不清晰先问用户
- **独立 compress 节点**：把 researcher 的 `_finalize` 拆成独立节点，prompt 单独调优
- **多档模型再细化**：summarize/research/compress/final 四档（对齐官方）
- **MCP 工具支持**：让 researcher 能调用用户自己挂的 MCP server
- **SQLite 缓存**：相同 query+date 缓存 finding，重复跑近瞬时
- **Streamlit / Gradio Web UI**：实时流式日志面板 + 历史报告列表 + 报告导出 PDF
- **LangGraph Studio 适配**：能在浏览器里调试 supervisor 决策路径
- **eval harness**：从 [Deep Research Bench](https://huggingface.co/spaces/Ayanami0730/DeepResearch-Leaderboard) 选 5~10 个 sample 自评

## 跟 08_agent_harness 的对照

| 维度 | 08 Agent Harness | 09 Deep Research v2 |
| --- | --- | --- |
| Agent 数量 | 1 主 + 0~N 临时子 | 1 主图 + 1 supervisor + N 并行 researcher |
| Agent 通信 | spawn_subagent 工具（同步） | LangGraph 子图 + ConductResearch 工具（async） |
| 上下文管理 | 主图压缩老消息 | 主图根本不持有子 messages，state 分层 |
| 工具 | 文件/Bash/Grep（本地） | Search/Fetch（互联网） |
| 产出 | 修改 workspace 里的文件 | 生成 Markdown 报告 |
| 适合学的 | 写工具、做 harness | 多 Agent 编排、动态决策、async 并行 |

读完这套你应该理解：**multi-agent 系统的关键不是"几个 LLM"，而是"上下文怎么切割、决策权怎么交付、结论怎么合并"**——拆好了，三流模型也能写出像样的研究报告；拆不好，GPT-5 也会自己跟自己打架。
