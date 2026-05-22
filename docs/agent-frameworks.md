# Agent 能力维度框架对照

每个搞 agent 的人都会被问到："Agent 到底有几个能力维度？"  
不同来源给的答案不一样，但其实**互相对应**。这份文档把主流 3 套对齐，再映射回本 repo 的章节，让你写代码时心里有数。

---

## 1. Lilian Weng 三支柱（2023.06，最经典）

📅 来源：[LLM Powered Autonomous Agents](https://lilianweng.github.io/posts/2023-06-23-agent/)（OpenAI 前研究员）

整个 agent 圈的**事实标准词汇**：

```
              ┌──────────────────┐
              │       Agent      │
              └────────┬─────────┘
            ┌──────────┼──────────┐
            │          │          │
       ┌────▼───┐ ┌────▼───┐ ┌────▼─────┐
       │Planning│ │ Memory │ │ Tool Use │
       └────────┘ └────────┘ └──────────┘
```

| 维度 | 含义 | 本 repo 章节 |
| --- | --- | --- |
| **Planning（规划）** | 子目标拆解、自我反思、批评 | 09 章 planner + supervisor 决策循环 |
| **Memory（记忆）** | 短期（context window）+ 长期（向量库 / 外部存储） | 03_memory + 04_rag |
| **Tool Use（工具）** | 调外部 API、查数据库、执行代码 | 05_tools_agents + 08_agent_harness 工具沙箱 |

---

## 2. Lilian 三支柱 + Reflection（4 维扩展，最常见的中文圈说法）

后来大家发现"反思"虽然属于 Planning 但单拎出来更好讲，于是变成 4 维：

```
   Planning + Memory + Tool + Reflection
```

| 维度 | 本 repo 体现 |
| --- | --- |
| Planning | 09 章 planner |
| Memory | 03/04 章 |
| Tool | 05/08 章 |
| **Reflection** | 09 supervisor 看回来的 findings 后决定"够不够、要不要补研究"——典型的 reflection |

> **如果你之前记的就是这个 4 维，那它的源头就是 Lilian Weng 三支柱 + 业界扩展。**

---

## 3. Anthropic Augmented LLM（2024.12）

📅 来源：[Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)

跟 Lilian 三支柱**重叠很大**，但把 Planning 隐到 LLM 自己干、把 Retrieval 单独拎出来：

```
                  ┌──────────┐
                  │  Memory  │
                  └────┬─────┘
                       │
               ┌───────▼───────┐
               │      LLM      │
               └───┬───────┬───┘
                   │       │
             ┌─────▼──┐  ┌─▼─────────┐
             │ Tools  │  │ Retrieval │
             └────────┘  └───────────┘
```

| 维度 | 跟 Lilian 对应 | 本 repo |
| --- | --- | --- |
| Tools | Tool Use | 05/08 章 |
| Memory | 短期 Memory | 03 章 + 09 章 state |
| **Retrieval** | 长期 Memory 的特化 | 04/07 章 RAG |

Planning 哪去了？Anthropic 认为对现代模型（Claude 3.5+）来说，Planning 是 LLM 自带能力，外部 scaffold 越少越好。

---

## 4. Manus 5 维上下文工程（2025.07，最新最实用）

📅 来源：[Context Engineering in Manus — Lance Martin](https://rlancemartin.github.io/2025/10/15/manus/)

把 Memory 那一维**彻底拆开**，专门讲"上下文怎么管理"——这是 long-running agent 真正的难点：

| 维度 | 含义 | 本 repo 实现 |
| --- | --- | --- |
| **Offloading（外置）** | 把状态从 prompt 挪到外部（文件/state/数据库） | 08 章 todos 写到 state、Agent 写文件不塞 prompt |
| **Reduction（压缩）** | 把老消息总结掉省 token | 08 章 [compression.py](../08_agent_harness/compression.py) |
| **Retrieval（检索）** | 按需从大库里捞相关片段进 prompt | 04/07 章 RAG |
| **Isolation（隔离）** | 多 Agent 各自的上下文边界 | 09 章 supervisor 子图 + ResearcherState 独立 |
| **Caching（缓存）** | KV-cache 友好的 prompt 设计 | ⚠️ **你还没做**——这是 v3 可以加的 |

> Manus 团队的核心洞察：**input/output token 比 100:1，成败全在 context 怎么管**。

---

## 5. 三套框架对齐表

| 能力 | Lilian 三支柱 | Anthropic Augmented LLM | Manus 5 维 | 本 repo 章节 |
| --- | --- | --- | --- | --- |
| 规划/决策 | Planning | （LLM 内化） | —— | 09 planner/supervisor |
| 短期上下文 | Memory | Memory | Reduction + Caching | 03 + 08 compression |
| 长期知识 | Memory | Retrieval | Retrieval | 04/07 RAG |
| 外部工具 | Tool Use | Tools | —— | 05/08 |
| 反思/批评 | Planning 子项 | （LLM 内化） | —— | 09 supervisor 循环 |
| 状态外置 | —— | —— | **Offloading** | 08 todos + 文件 |
| 多 Agent 隔离 | —— | —— | **Isolation** | 09 子图 + state 分层 |

**怎么看这张表**：
- Lilian 三支柱 = 入门词汇
- Anthropic 4 模式 = 工程模式语言（Prompt Chaining / Routing / Parallelization / Orchestrator-Worker / Evaluator-Optimizer）
- Manus 5 维 = **真正 production 时的施工图**

---

## 用这些框架做什么

### 设计新 Agent 时

用 Lilian 三支柱**自问**：
- 它需要规划吗？复杂任务才需要，简单 ReAct 一把搞定
- 它需要长期记忆吗？跨会话才需要，单次任务不必
- 它需要哪些工具？最少最少最少

### 排查 Agent 卡壳时

用 Manus 5 维**自检**：
- 上下文太长？→ Reduction（压缩）+ Offloading（外置）
- 反复忘记重要事？→ Retrieval（按需召回）
- 子 Agent 互相污染？→ Isolation（独立 state）
- 跑得慢？→ Caching（KV-cache 优化 prompt）

### 跟别人聊 Agent 时

用 Anthropic 5 pattern：Prompt Chaining / Routing / Parallelization / Orchestrator-Worker / Evaluator-Optimizer。**这是事实通用语**。

---

## 还有哪些框架（不推荐但你可能听到）

- **古典 AI agent**：Perception / Planning / Memory / Action（4 模块）—— 来自 1990s 经典 AI 教材，跟 LLM 时代不大匹配
- **AutoGPT / BabyAGI 风格**：Goal / Task Queue / Agent Loop —— 已经过时，更多是早期实验
- **CrewAI / AutoGen 的 role-based**：Manager / Researcher / Critic 角色分工 —— 太具体的实现，不是通用维度

如果你听到别的 4/5/6/N 维框架觉得耳熟，多半都是上面这几套的**包装**或**子集**，看清本质再判断。
