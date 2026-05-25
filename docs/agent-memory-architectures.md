# Agent 记忆架构设计思想

> 调研时间：2026-05-25。  
> 这份文档关注"记忆系统怎么设计"，不是简单罗列 SDK。核心问题是：Agent 在长时间、多轮、多任务运行中，如何决定**记什么、何时记、怎么取、谁能改、什么时候忘**。

---

## 1. 先建立判断标准

Agent 记忆不是一个单独的向量库功能，而是一套围绕 Agent loop 的状态管理系统。评估任何记忆方案时，先看 6 个设计问题：

| 问题 | 设计含义 |
| --- | --- |
| 记忆粒度 | 存原始对话、摘要、原子事实、任务事件，还是实体关系 |
| 生命周期 | 当前 turn、当前 session、跨 session、长期用户级、组织级 |
| 作用域 | user / project / org / agent / team / session 怎么隔离 |
| 写入权 | 系统自动写、后台 consolidator 写、Agent 自己通过工具写，还是用户确认后写 |
| 读取策略 | 全量注入、按需检索、常驻上下文、图谱查询、混合召回 |
| 治理能力 | 可编辑、可删除、可追溯、冲突处理、隐私和权限边界 |

一个成熟系统通常不是只选一种 memory，而是把短期会话、长期事实、任务经验、用户偏好、操作规程拆开管理。

---

## 2. 主流架构路线

### 2.1 Session memory：把"当前对话状态"产品化

代表：OpenAI Agents SDK Sessions、LangGraph checkpoint、各种 chat thread store。

**设计思想**：  
先不要让 Agent "学习"，先保证它能在多轮运行里延续上下文。Session memory 保存 conversation items、tool calls、approval resume state、checkpoint。它解决的是连续性和可恢复性，不解决长期个性化。

```text
new user input
      │
      ▼
retrieve session history
      │
      ▼
merge / trim / compact
      │
      ▼
model + tools
      │
      ▼
append new items to session
```

**关键抽象**：
- `session_id`：一个连续任务或聊天线程。
- `history items`：用户消息、助手消息、工具调用、工具结果。
- `compaction`：长会话时把旧历史压缩，避免无限增长。
- `resume`：审批、人类介入、中断后继续跑。

**适用场景**：
- 多轮聊天。
- 需要中断恢复的长任务。
- coding agent 的一次 issue 修复过程。

**主要风险**：
- 它只是"历史记录"，不是可靠事实库。
- 全量历史容易污染 prompt，越长越慢。
- 如果不做裁剪和压缩，成本会持续上升。

参考：[OpenAI Agents SDK Sessions](https://openai.github.io/openai-agents-python/sessions/)

---

### 2.2 Layered memory：按生命周期分层

代表：Mem0、CrewAI Memory、很多生产级个人助手。

**设计思想**：  
把记忆拆成 conversation / session / user / org 几层。越短期的记忆越接近原始上下文，越长期的记忆越应该结构化、去重、可治理。

```text
raw conversation
      │
      ├─ conversation memory  当前 turn / 最近消息
      ├─ session memory       当前任务内临时事实
      ├─ user memory          用户偏好、稳定事实
      └─ org memory           团队政策、共享知识
```

**关键抽象**：
- `user_id`：长期个性化边界。
- `run_id / session_id`：短期任务边界。
- metadata：来源、时间、重要性、类别、置信度。
- promotion：从短期对话中提炼值得长期保存的信息。

**写入链路**：
1. 原始消息进入 conversation 层。
2. 抽取候选事实。
3. 判断是否值得保存。
4. 根据生命周期写到 session / user / org。
5. 对旧记忆做更新、合并或失效。

**读取链路**：
1. 根据当前任务确定 scope。
2. 在不同层检索。
3. 按相关性、时间、重要性排序。
4. 只注入少量高价值记忆。

**适用场景**：
- 客服、教育、个人助手。
- 用户希望 Agent 跨会话记住偏好。
- 多 agent 需要共享组织知识。

**主要风险**：
- 自动写入会产生记忆污染。
- 用户偏好变化后，旧记忆需要显式失效。
- user memory 和 org memory 必须有权限隔离。

参考：[Mem0 Memory Types](https://docs.mem0.ai/core-concepts/memory-types)、[CrewAI Memory](https://docs.crewai.com/en/concepts/memory)

---

### 2.3 Structured store memory：把长期记忆当 JSON 文档

代表：LangChain / LangGraph long-term memory。

**设计思想**：  
不要把所有记忆都做成 embedding chunk。很多长期记忆天然是结构化 JSON：用户资料、项目规则、偏好、账户状态、任务决策。用 namespace + key 存储 JSON，再按需通过工具读写。

```text
namespace = ("users", user_id, "preferences")
key       = "communication_style"
value     = {
  "preference": "short and direct",
  "source": "conversation",
  "updated_at": "2026-05-25"
}
```

**关键抽象**：
- `namespace`：类似文件夹，用来表达 user / org / project / app。
- `key`：稳定对象 ID。
- `value`：结构化 JSON 文档。
- `store.search()`：在 namespace 内做语义或过滤搜索。
- tool runtime：让工具在执行时读写 memory store。

**适用场景**：
- 需要强作用域隔离的系统。
- 需要可解释、可编辑、可迁移的长期记忆。
- 已经在用 LangGraph / LangChain 的 Agent。

**主要风险**：
- 结构化 schema 要设计好，否则后期迁移成本高。
- 让 Agent 直接写结构化记忆，需要校验和审批。
- JSON store 适合事实和偏好，不适合复杂关系推理。

参考：[LangChain Long-term memory](https://docs.langchain.com/oss/python/langchain/long-term-memory)

---

### 2.4 Core memory + archival memory：常驻记忆和外部档案分离

代表：MemGPT、Letta。

**设计思想**：  
把"必须每次都看见的记忆"和"按需检索的档案"分开。Core memory 常驻 context，适合 persona、human profile、当前目标、长期规则；archival memory 放外部库，只有需要时检索。

```text
prompt context
├── system instructions
├── core memory blocks     始终可见
├── recent messages
└── retrieved snippets     按需取回

external storage
└── archival memory        大量历史、文档、事件
```

**关键抽象**：
- memory block：带 label、description、value、limit 的上下文块。
- block description：告诉 Agent 这个块该怎么用。
- read-only block：组织政策、系统规则这类不能让 Agent 改。
- archival search：在外部记忆里查找更多上下文。

**重要洞察**：  
常驻记忆不是越多越好。它适合少量高稳定、高优先级信息。大量历史应该放 archival memory，否则会挤占推理空间。

**适用场景**：
- 长期个人助手。
- coding agent 的项目规则、用户偏好、当前工作目标。
- 多 agent 通过共享 memory block 协调状态。

**主要风险**：
- Agent 自己改 core memory 可能造成自我污染。
- block description 写得差，Agent 会误用。
- 常驻块过多会让系统 prompt 变脆。

参考：[Letta Memory blocks](https://docs.letta.com/guides/core-concepts/memory/memory-blocks)

---

### 2.5 Temporal knowledge graph：把记忆建成会随时间变化的关系网络

代表：Zep / Graphiti。

**设计思想**：  
当系统需要理解"实体之间的关系如何随时间变化"时，普通向量检索不够。图谱记忆把对话、事件、业务数据抽成实体、关系和时间边，支持多跳查询、状态变化、历史追溯。

```text
episode
  "Kendra now prefers Adidas over Nike"
      │
      ▼
extract entities + edges
      │
      ▼
temporal graph
  (Kendra)-[prefers, valid_from=t2]->(Adidas)
  (Kendra)-[preferred, invalid_at=t2]->(Nike)
      │
      ▼
hybrid retrieval
  semantic + BM25 + graph traversal + temporal filters
```

**关键抽象**：
- episode：一次对话、一次事件、一个 JSON 变更。
- entity / edge：实体和关系。
- temporal metadata：关系开始、结束、更新时间。
- graph namespace：不同用户、组织、租户隔离。
- hybrid search：语义、关键词、图算法、时间过滤混合。

**适用场景**：
- CRM、客服、销售、健康、金融这类实体关系密集场景。
- 用户状态和业务状态经常变化。
- 问题需要多跳推理，比如"谁负责这个客户上次投诉后的跟进"。

**主要风险**：
- 抽取质量决定上限。
- 写入链路复杂，成本高。
- 图谱不是所有 Agent 都需要，过早引入会拖慢开发。

参考：[Graphiti Overview](https://help.getzep.com/graphiti/getting-started/overview)

---

### 2.6 File / skill memory：把经验沉淀成可版本化文件

代表：Deep Agents、Claude Code / Codex 类 coding agent、AGENTS.md、skills。

**设计思想**：  
对 coding agent 来说，最可靠的长期记忆往往不是聊天摘要，而是文件化的规则和流程：项目约定、测试命令、常见坑、工具用法、PR 规范。文件可读、可 diff、可 review、可 commit，比黑盒向量记忆更容易治理。

```text
conversation experience
      │
      ▼
distill into durable rule
      │
      ▼
AGENTS.md / SKILL.md / docs
      │
      ▼
loaded as procedural memory
```

**关键抽象**：
- procedural memory：怎么做事，而不是事实是什么。
- project-local instructions：只在对应 repo 生效。
- skill：封装一类任务的流程、脚本、参考资料。
- version control：通过 git 审查和回滚。

**适用场景**：
- coding agent。
- 长期维护的团队工程流程。
- 需要可审计、可迁移的操作经验。

**主要风险**：
- 规则太多会冲突，必须有优先级和作用域。
- 自动写文件要谨慎，最好有人 review。
- procedural memory 不能替代事实检索。

参考：[Deep Agents Memory](https://docs.langchain.com/oss/python/deepagents/memory)

---

## 3. 重要开源项目解析

这一节按"架构思想"解析几个值得重点看的开源项目。判断标准不是 star 数，而是它们分别代表了不同的记忆设计路线：通用 memory layer、stateful agent 平台、知识图谱记忆、框架内置 memory、个人/跨工具记忆。

### 3.1 Mem0：通用长期记忆层

项目：[mem0ai/mem0](https://github.com/mem0ai/mem0)  
定位：Universal memory layer for AI Agents。

**它解决的问题**：  
Mem0 想做的是"给任何 Agent 接一层长期记忆"，让应用不用自己搭 extraction、embedding、update、search、metadata、API server。它不是一个完整 Agent 框架，而是一个可插拔 memory service。

**核心设计**：

```text
messages / events
      │
      ▼
memory extraction
      │
      ▼
dedupe / update / categorization
      │
      ▼
vector / graph / metadata store
      │
      ▼
search(user_id, run_id, query)
      │
      ▼
relevant memories
```

Mem0 的关键抽象是 `user_id`、`run_id` 和 metadata。`user_id` 负责长期用户记忆，`run_id` 负责当前任务或 session 记忆。它的文档把 memory 分为 conversation、session、user、org 几层，本质是用 scope 控制生命周期。

**写入思想**：
- 用户说的话不是直接作为长期记忆保存。
- 先抽取候选事实，再判断放在哪个层。
- 对已有记忆做更新或合并，避免重复保存。
- 用 metadata 支持过滤、治理和多租户隔离。

**读取思想**：
- 查询时同时考虑 user-level 和 session-level context。
- 返回的是可注入 prompt 的记忆片段，而不是原始聊天记录。
- 更接近"personalization context API"，而不是传统 RAG。

**适合学习的点**：
- 记忆服务 API 怎么设计：`add/search/update/delete`。
- 记忆层怎么独立于 Agent 框架。
- 如何把长期用户偏好和短期任务状态拆开。
- 为什么 memory 需要 dashboard、CLI、server、自托管和 cloud 两种形态。

**局限**：
- 如果你只用开源 library，生产级治理、观测、权限、dashboard 还要自己补。
- 它默认依赖 LLM 做抽取，写入质量取决于抽取 prompt 和模型。
- 对 coding agent 的 repo 结构、git lineage、branch 冲突这类问题，不是天然建模。

**一句话评价**：  
Mem0 最值得学的是"memory as a service"这条产品路线：把记忆做成独立基础设施，而不是散落在 Agent prompt 里。

---

### 3.2 Letta / MemGPT：stateful agent 与可自我管理的记忆

项目：[letta-ai/letta](https://github.com/letta-ai/letta)  
定位：Platform for building stateful agents，前身是 MemGPT。

**它解决的问题**：  
Letta 不是只做检索，它关心的是"Agent 如何长期保持自己的状态"。它的核心思想是：Agent 不应该只是每轮 stateless 调 LLM，而应该拥有可持续的 internal state，并且能通过工具管理自己的 memory。

**核心设计**：

```text
agent context
├── system instructions
├── core memory blocks      always visible
│   ├── persona
│   ├── human
│   └── task / policy / state
├── recent conversation
└── retrieved archival memory

external storage
├── archival memory
├── files / passages
└── tools / blocks / folders
```

Letta 的 memory block 是一个很重要的抽象。每个 block 有 `label`、`description`、`value`、`limit`。其中 `description` 不只是给人看的，而是告诉 Agent 这个块该怎么读写。

**写入思想**：
- 不是所有信息都进入向量库。
- 高频、稳定、必须每次看到的信息进入 core memory。
- 大量历史、文档、事件进入 archival memory。
- Agent 可以通过内置 memory tools 主动更新 block。
- 组织政策等内容可以做 read-only block，避免 Agent 乱改。

**读取思想**：
- core memory 常驻 prompt，不需要检索。
- archival memory 按需搜索。
- 通过 context hierarchy 控制不同类型上下文优先级。

**适合学习的点**：
- 常驻记忆和检索记忆为什么要分开。
- memory block 的 `description` 是一种"给 Agent 的写入协议"。
- 让 Agent 管理自己的记忆时，必须有 size limit、read-only、工具边界。
- 多 Agent 可以通过 shared memory block 协调状态。

**局限**：
- 让 Agent 自己编辑 core memory，能力很强，但也容易自我污染。
- 如果 block 太多，prompt 会变重，行为也会变脆。
- 平台抽象较完整，想只抄一小块需要拆清楚边界。

**一句话评价**：  
Letta 最值得学的是"stateful agent"思想：长期 Agent 不是 chat history + RAG，而是 core memory、archival memory、tools、files、permissions 共同组成的状态机。

---

### 3.3 LangMem：LangGraph 生态里的热路径/后台记忆管理

项目：[langchain-ai/langmem](https://github.com/langchain-ai/langmem)  
定位：帮助 LangGraph Agent 从交互中学习和适应。

**它解决的问题**：  
LangMem 主要解决 LangGraph 用户的长期记忆问题：Agent 运行时怎么保存、搜索、更新记忆；以及如何在后台从对话中整理记忆。它不像 Mem0 那样强调独立服务，也不像 Letta 那样做完整 stateful platform，而是更贴近 LangGraph 的 store 和 tools。

**核心设计**：

```text
LangGraph agent
      │
      ├─ hot path tools
      │   ├─ manage_memory
      │   └─ search_memory
      │
      └─ background manager
          ├─ extract
          ├─ consolidate
          └─ update

LangGraph Store
└── namespace / key / JSON / vector index
```

**热路径记忆**：  
Agent 在对话过程中自己调用 `manage_memory` 或 `search_memory`。优点是实时、可控；缺点是增加 Agent 决策负担，也可能把错误信息写入长期记忆。

**后台记忆**：  
对话结束后由后台 manager 抽取、合并、更新。优点是不会打断主流程，延迟更低；缺点是写入不是即时生效。

**适合学习的点**：
- hot path 和 background memory manager 的取舍。
- 如何基于 `namespace` 做 user/project/agent scope。
- 如何把 memory tools 接进 ReAct/LangGraph agent。
- "记忆管理"可以是工具，也可以是后台管道。

**局限**：
- 强依赖 LangGraph 的 store 和运行模型。
- 生产级治理、UI、权限需要自己补。
- 如果 Agent 热路径写入太自由，仍然会有 memory poisoning 风险。

**一句话评价**：  
LangMem 最值得学的是"memory 写入时机"：有些记忆需要 Agent 当场写，有些更适合后台 consolidation。

---

### 3.4 Graphiti / Zep：时间知识图谱记忆

项目：[getzep/graphiti](https://github.com/getzep/graphiti)  
定位：Temporal context graph engine for AI agents。Zep 是其托管 context layer。

**它解决的问题**：  
当记忆不只是"用户喜欢什么"，而是"人、组织、项目、产品、事件之间的关系持续变化"时，普通向量库很难表达。Graphiti 用 temporal knowledge graph 来处理动态事实、关系更新和历史查询。

**核心设计**：

```text
episode stream
  conversations / JSON / events / documents
      │
      ▼
entity + relation extraction
      │
      ▼
temporal context graph
  nodes: entities with evolving summaries
  edges: facts with validity windows
  episodes: provenance
      │
      ▼
hybrid retrieval
  semantic + keyword + graph traversal + temporal filters
```

Graphiti 的核心不是"图谱比向量库高级"，而是"事实会变化"。比如用户以前住纽约，现在搬到旧金山；旧事实不能简单删除，因为历史问题可能仍然需要它，但当前推荐必须用新事实。

**写入思想**：
- 以 episode 为单位摄入数据。
- 从 episode 中抽取实体和关系。
- 给关系加时间有效区间。
- 保留 provenance，知道每条边来自哪个 episode。
- 新事实出现时，让旧边失效，而不是简单覆盖文本。

**读取思想**：
- 语义检索找到相关区域。
- BM25/关键词保证精确匹配。
- 图遍历支持多跳关系。
- 时间过滤支持 point-in-time query。

**适合学习的点**：
- 动态事实不要只靠"新文本覆盖旧文本"。
- 记忆需要 provenance，否则无法解释和回滚。
- 多跳问题需要图结构，不适合全部 chunk 化。
- graph memory 适合业务实体丰富的产品，不适合所有 Agent。

**局限**：
- 抽取实体和关系的成本高。
- schema/ontology 设计会影响长期质量。
- 查询链路比普通 RAG 复杂，调试难度更高。

**一句话评价**：  
Graphiti/Zep 最值得学的是"时间维度"：成熟记忆系统必须知道什么现在是真的、什么过去是真的、什么被新事实取代了。

---

### 3.5 Cognee：memory control plane + GraphRAG

项目：[topoteretes/cognee](https://github.com/topoteretes/cognee)  
定位：Memory control plane for AI Agents。

**它解决的问题**：  
Cognee 更像一个"把各种数据变成可召回上下文的控制平面"。它关注多数据源 ingestion、chunking、embedding、knowledge graph、GraphRAG、agent integration。和 Graphiti 相比，它更偏"数据管道 + 知识图谱 + agent recall"。

**核心设计**：

```text
documents / tables / transcripts / tool events
      │
      ▼
data ingestion pipeline
      │
      ├─ parsing
      ├─ chunking
      ├─ embedding
      └─ graph extraction
      │
      ▼
hybrid memory store
  vector + graph + source files
      │
      ▼
agent recall
```

Cognee 的 Claude Code 集成思路很有参考价值：通过生命周期 hook 捕获 session start、tool use、prompt submit、pre-compact、session end，把 coding agent 的工作过程变成可持久化记忆。

**写入思想**：
- 不只从聊天写记忆，也从文件、工具调用、数据源写记忆。
- session 内先捕获事件，session 结束后同步到长期图谱。
- 更强调自动管道，而不是让 Agent 自己每次决定写什么。

**读取思想**：
- 在用户提交 prompt 时注入相关上下文。
- 用 graph + vector 的组合召回。
- 对 coding agent 来说，session memory 和 permanent graph 分层。

**适合学习的点**：
- Agent memory 不一定要靠 Agent 自己写，可以靠 hooks。
- coding agent 的 tool use 是非常有价值的 episodic memory 来源。
- 记忆控制平面要处理数据接入、索引、召回、同步，而不只是 search API。

**局限**：
- 数据管道和图谱系统会带来较高复杂度。
- 需要根据自己的 Agent runtime 改 hook。
- 对简单聊天 Agent 来说可能过重。

**一句话评价**：  
Cognee 最值得学的是"从 Agent 生命周期采集记忆"：尤其适合 coding agent 和 workflow agent。

---

### 3.6 Supermemory：跨工具个人记忆和一体化 context stack

项目：[supermemoryai/supermemory](https://github.com/supermemoryai/supermemory)  
定位：Memory and context engine for AI，带 app、API、插件、MCP。

**它解决的问题**：  
Supermemory 的目标更偏用户产品：一个人可能同时用 ChatGPT、Claude Code、Cursor、OpenCode、浏览器扩展、文档连接器。它要让这些工具共享同一套个人记忆。

**核心设计**：

```text
AI tools / browser / files / connectors
      │
      ▼
single memory API
      │
      ├─ fact extraction
      ├─ user profile
      ├─ contradiction handling
      ├─ forgetting
      ├─ hybrid search
      └─ connectors / file processing
      │
      ▼
profile + relevant memories
```

它的设计把 memory、RAG、user profile、connectors 放在一个 context stack 里。这个方向适合做个人 AI 操作系统，而不是单个 Agent demo。

**写入思想**：
- 从聊天、网页、文件、连接器里保存内容。
- 抽取稳定事实和动态上下文。
- 处理时效性和矛盾，比如临时事件过期、地址变更。

**读取思想**：
- 一次请求可以拿到 profile 和 search results。
- profile 分 static 和 dynamic，更接近"当前用户画像"。
- 通过插件/MCP 给不同 Agent 使用。

**适合学习的点**：
- 个人记忆不应该锁在某一个 Agent 工具里。
- profile 和 retrieval results 应该分开。
- connectors 是长期记忆产品的重要入口。
- forgetting 和 contradiction handling 要产品化。

**局限**：
- 如果只想做本地开源实验，它的一体化产品形态可能偏重。
- 多工具共享记忆会带来更强的隐私和权限问题。
- 用户数据来源多，记忆质量治理更难。

**一句话评价**：  
Supermemory 最值得学的是"portable memory"：记忆跟着用户走，而不是跟着某个 Agent session 走。

---

### 3.7 CrewAI Memory：多 Agent 编排里的共享/私有记忆

项目：[crewAIInc/crewAI](https://github.com/crewAIInc/crewAI)  
文档：[CrewAI Memory](https://docs.crewai.com/en/concepts/memory)

**它解决的问题**：  
CrewAI 的 memory 设计服务于 multi-agent crew：多个角色执行任务时，哪些记忆共享，哪些记忆只给某个 agent，任务完成后哪些事实进入长期记忆。

**核心设计**：

```text
crew
├── shared memory
│   └── task outputs / decisions / extracted facts
└── agent scoped memory
    ├── researcher private scope
    └── writer private scope
```

新版 CrewAI Memory 倾向统一 API：`remember`、`recall`、`forget`，并用 semantic、recency、importance 混合评分。

**写入思想**：
- task output 后自动抽取离散事实。
- 允许 crew 共享 memory。
- agent 也可以有私有 scoped memory。

**读取思想**：
- task 执行前召回相关上下文注入 prompt。
- 召回时同时考虑语义相似度、时间新鲜度、重要性。

**适合学习的点**：
- multi-agent memory 一定要分 shared 和 private。
- 任务级输出是很好的 episodic memory。
- recency / importance / semantic 的组合比单纯向量相似度稳。

**局限**：
- 它是 CrewAI 框架内的能力，不是通用 memory service。
- 自动抽取 task output 可能把错误中间结论沉淀为事实。
- 多 Agent 共享记忆需要更严格的权限和来源标注。

**一句话评价**：  
CrewAI Memory 最值得学的是 multi-agent scope：共享记忆能协作，私有记忆能隔离。

---

### 3.8 LlamaIndex Memory：RAG 框架里的可插拔 memory blocks

项目：[run-llama/llama_index](https://github.com/run-llama/llama_index)  
文档：[LlamaIndex Memory](https://docs.llamaindex.ai/en/stable/module_guides/deploying/agents/memory/)

**它解决的问题**：  
LlamaIndex 原本强在 RAG 和数据索引。它的 Agent memory 更偏"在 AgentWorkflow/ReActAgent 里如何挂短期和长期记忆"。适合已经在 LlamaIndex 数据层上的应用。

**核心设计**：

```text
agent workflow
      │
      ├─ short-term message queue
      └─ memory blocks
          ├─ static block
          ├─ fact extraction block
          └─ custom block
```

**写入思想**：
- `memory.put()` 保存信息。
- memory block 可以自定义。
- 默认短期 memory 类似 FIFO chat history，长期 memory 通过 block 扩展。

**读取思想**：
- `memory.get()` 在 Agent 运行时取出上下文。
- memory 可以插入 system message 或 latest user message。
- 和 LlamaIndex 的 retrieval/index 能力结合。

**适合学习的点**：
- memory block 如何作为可插拔组件。
- RAG 框架如何从 document retrieval 扩展到 agent memory。
- 自定义 memory 对象比固定 chat buffer 更灵活。

**局限**：
- 它不是专门的 memory 产品，更多是框架组件。
- 长期个性化、冲突处理、治理能力要自己实现。
- 如果不是 LlamaIndex 技术栈，迁移价值有限。

**一句话评价**：  
LlamaIndex Memory 最值得学的是"memory as framework component"：适合把短期 history 和已有 RAG 数据层接起来。

---

### 3.9 Signet、MemLayer、Memary 等观察名单

除了上面几个，还有一些值得跟踪但不建议一开始作为主参照的项目：

| 项目 | 方向 | 为什么先放观察名单 |
| --- | --- | --- |
| [Signet](https://signetai.sh/) | 本地/自托管 coding agent memory，跨 Claude Code、OpenCode、OpenClaw 等工具 | 很贴近 coding agent，但相对新，生态和长期稳定性还需要观察 |
| [MemLayer](https://www.memlayer.dev/) | 开源知识图谱记忆，支持 MCP、REST、time-travel query | 方向清晰，但需要继续看实现成熟度和社区采用 |
| [Memary](https://github.com/kingjulio8238/Memary) | 早期 autonomous agent memory layer | 思路有启发，但活跃度和现代 Agent 栈适配不如前面几个 |

这些项目的共同趋势是：记忆开始从"某个框架的内部模块"变成"本地 daemon / MCP server / 跨工具基础设施"。这对 coding agent 很关键，因为开发者会同时使用多个 AI 工具，记忆需要在工具之间迁移。

---

### 3.10 项目选择建议

| 你要学什么 | 优先看 |
| --- | --- |
| 通用 memory service 怎么做 | Mem0 |
| 长期 stateful agent 怎么做 | Letta / MemGPT |
| LangGraph 里怎么加 memory | LangMem |
| 动态关系和时间事实怎么做 | Graphiti / Zep |
| 数据管道 + GraphRAG + agent hook | Cognee |
| 跨工具个人记忆产品怎么做 | Supermemory |
| 多 Agent 共享/私有 memory | CrewAI |
| RAG 框架内 memory block | LlamaIndex |

如果目标是给本 repo 做下一个实战项目，我建议主线参考：

1. **LangMem / LangGraph Store**：贴近你现有 LangChain 学习路线。
2. **Letta memory blocks**：学习 core memory 和 archival memory 的边界。
3. **Cognee hooks**：学习 coding agent 生命周期怎么采集 episodic memory。
4. **Graphiti**：作为高级版，后面再做时间图谱。

不要一开始照搬 Supermemory 或 Cognee 的全栈产品形态。先实现一个小而完整的 `session + profile + episodic + procedural` memory system，比堆很多后端更有学习价值。

---

## 4. 横向对比

| 路线 | 核心目标 | 存储形态 | 读取方式 | 最适合 |
| --- | --- | --- | --- | --- |
| Session memory | 多轮连续性 | 消息序列、checkpoint | 直接拼接、裁剪、压缩 | 聊天、长任务恢复 |
| Layered memory | 按生命周期管理 | 短期/长期分层记录 | 分层检索 + rerank | 个人助手、客服 |
| Structured store | 可治理事实库 | namespace + key + JSON | key lookup + search | 产品级用户记忆 |
| Core + archival | 常驻核心 + 外部档案 | memory block + retrieval store | 常驻注入 + 按需检索 | 长期 stateful agent |
| Temporal graph | 动态关系推理 | 实体、边、时间元数据 | 图谱 + 语义 + 关键词 | CRM、业务状态推理 |
| File / skill memory | 可版本化经验 | markdown、skills、代码 | 规则加载、人工 review | coding agent、团队流程 |

---

## 5. 一个推荐的工程架构

如果从零实现，不建议一开始就上图谱。更稳的路线是：

```text
                 ┌────────────────────┐
                 │      Agent Loop     │
                 └─────────┬──────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
  session store      memory service      procedural files
  SQLite/Redis       Postgres/pgvector    AGENTS.md/SKILL.md
          │                │                │
          │                ├─ profile memory
          │                ├─ semantic memory
          │                ├─ episodic memory
          │                └─ optional graph memory
          │
          ▼
  compaction / resume
```

### 写入路径

```text
raw messages + tool results
      │
      ▼
candidate extractor
      │
      ▼
memory classifier
  profile / semantic / episodic / procedural / ignore
      │
      ▼
quality gate
  relevance, stability, privacy, duplicate, conflict
      │
      ▼
write store
  with source, timestamp, confidence, scope, ttl
```

### 读取路径

```text
task intent
      │
      ▼
scope resolver
  user + project + org + session
      │
      ▼
retrieval
  exact key lookup + semantic search + recency filter
      │
      ▼
rerank and compress
      │
      ▼
prompt injection
  separate memory section, never mixed with system rules
```

### 最小可行版本

1. Session memory：先保存 thread、工具结果、checkpoint。
2. Profile memory：结构化保存用户偏好和稳定事实。
3. Episodic memory：每次任务结束保存"做了什么、结果、失败原因、可复用经验"。
4. Procedural memory：把稳定经验写进 docs / AGENTS.md / skills。
5. Semantic retrieval：给 profile/episodic 加 embedding 检索。
6. Graph memory：只有在实体关系和时间变化成为瓶颈时再加。

---

## 6. 好的实践

### 6.1 只保存稳定、高价值、可复用的信息

不要每句话都写长期记忆。适合保存：
- 用户明确偏好："以后回答要短一点"。
- 项目稳定事实："这个 repo 的测试命令是 pytest tests/unit"。
- 任务经验："Playwright 在 macOS sandbox 下需要额外权限"。
- 业务状态："客户 A 的合同负责人已经换成 B"。

不适合保存：
- 临时推测。
- 模型自己的中间想法。
- 没确认的错误结论。
- 敏感信息原文。

### 6.2 写入比读取更需要 guardrail

很多系统重视 retrieval，忽略 write path。实际生产里，记忆污染通常来自写入端：
- 候选记忆必须有 `source`。
- 自动写入要有 confidence。
- 重要偏好变更最好让用户确认。
- 新旧冲突要显式处理：覆盖、并存、失效、人工确认。

### 6.3 记忆必须有 scope

最少要区分：
- `session`：当前任务。
- `user`：某个用户长期偏好。
- `project`：当前代码库或业务项目。
- `org`：团队共享规则。
- `agent`：某个 agent 的私有经验。

没有 scope 的记忆迟早会互相污染。

### 6.4 prompt 注入要克制

检索到 20 条不代表要塞 20 条。推荐：
- 注入 3-8 条高相关记忆。
- 按类别分区：User Preferences / Project Facts / Recent Episodes。
- 每条带时间和来源。
- 和 system instructions 分开，避免把旧记忆当最高优先级规则。

### 6.5 记忆需要可见、可改、可删

成熟产品要提供：
- 用户能看到 Agent 记住了什么。
- 用户能删除或修改错误记忆。
- 系统能解释某条记忆来自哪里。
- TTL 和过期机制。
- PII 和 secret 的过滤。

---

## 7. 对本 repo 的学习建议

本 repo 已经有 `03_memory`、`04_rag`、`08_agent_harness`、`09_deep_research`。如果继续扩展，建议新增一个小项目而不是直接做大系统：

```text
11_agent_memory_system/
├── session_store.py       # SQLite 保存 thread/tool/checkpoint
├── memory_schema.py       # ProfileMemory / EpisodeMemory / ProjectMemory
├── extractor.py           # 从对话和工具结果抽取候选记忆
├── memory_store.py        # JSON + vector search
├── recall.py              # scope resolver + rerank
├── governance.py          # 去重、冲突、隐私过滤
└── demo_agent.py          # 一个会记住用户偏好和项目经验的小 agent
```

推荐实现顺序：
1. 先做 session store，复用 08 章 harness 的 state 思路。
2. 再做 profile + episodic memory，不急着做图谱。
3. 给每条记忆加 source、scope、confidence、created_at、updated_at。
4. 在 Agent 回复前只注入少量相关记忆。
5. 做一个 `memory inspect` 命令，让用户能看见和删除记忆。

---

## 8. 一句话结论

Agent 记忆的主线正在从"长上下文 + 向量库"走向"分层状态管理 + 受控写入 + 按需召回 + 可治理记忆"。  
真正难的不是存储，而是**边界、写入质量、冲突处理、可见性和遗忘机制**。
