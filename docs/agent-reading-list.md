# Agent 学习精选文章

> 给已经写完本 repo 8/9 章（迷你 Claude Code + Deep Research）后的进阶读者。  
> 跳过"agents 101"和营销稿，只留**第一手洞察**和**生产级反思**。

**标签说明**
- 【必读】 = 整个 agent 圈共同词汇基线，不读后面看别人聊天都跟不上
- 【推荐】 = 读完会让你写代码方式发生改变
- 【参考】 = 不必通读，遇到具体问题时回查

---

## 🥇 如果只读 3 篇

### 1. Anthropic: Building Effective Agents 【必读】

- 📅 2024.12 · 🔗 <https://www.anthropic.com/research/building-effective-agents>
- 整个领域的**词汇基线**。提出了 Prompt Chaining / Routing / Parallelization / Orchestrator-Worker / Evaluator-Optimizer 这 5 个 pattern——你之后读所有 agent 文章用的都是这套黑话
- 配套：[Simon Willison 的笔记版](https://simonwillison.net/2024/Dec/20/building-effective-agents/)（更短，能快速复习）

### 2. Anthropic: How we built our multi-agent research system 【必读】

- 📅 2025.06 · 🔗 <https://www.anthropic.com/engineering/built-multi-agent-research-system>
- 本 repo 09 章直接对标的系统。讲了为什么 multi-agent 在 research 任务上能比 single agent 提升 90.2%，但用 15× token
- **读这篇前先把 09 章跑一遍**，会发现你写的 supervisor 决策 prompt 还能怎么调

### 3. Cognition: Don't Build Multi-Agents 【必读·唱反调】

- 📅 2025 · 🔗 <https://cognition.ai/blog/dont-build-multi-agents>
- Devin 团队的反方立场：multi-agent 是 footgun，应该单 Agent + 强上下文一致性
- 和上面 Anthropic 那篇**直接冲突**。**两边都对**，区别在任务形态（research vs coding）
- 后续：Cognition 在 2026.03 反悔了，发了"Devin can manage Devins"（参见 [架构辩论综述](https://patmcguinness.substack.com/p/the-ai-agent-architecture-debate)）

---

## 🧠 上下文工程（最该花时间）

context engineering 是 2025 年下半年起整个圈子的共识——比"调 prompt"高一个层次。

### Context Engineering in Manus — Lance Martin 【必读】

- 📅 2025.10 · 🔗 <https://rlancemartin.github.io/2025/10/15/manus/>
- Lance Martin（LangChain 核心）拆解 Manus 的 5 维上下文工程：offloading / reduction / retrieval / isolation / caching
- Manus 团队重写了 4 次 agent framework 才稳，痛苦换来的方法论
- 详见 [agent-frameworks.md](agent-frameworks.md) 的对应章节

### Anthropic: Effective Context Engineering 【推荐】

- 📅 2025.12 · 🔗 <https://01.me/en/2025/12/context-engineering-from-claude/>（李博杰译/转写的英文版，质量很好）
- Claude 团队的"goldilocks zone"理论：system prompt 太死会脆、太松会乱
- 涵盖三个层面：prompt 写法、tool 设计、长会话状态管理

### Learning the Bitter Lesson — Lance Martin 【推荐】

- 📅 2025.07 · 🔗 <https://rlancemartin.github.io/2025/07/30/bitter_lesson/>
- 用 LangGraph 时**只用底层 node/edge，避免 prebuilt**——直接对应本 repo 08 章为什么手写 StateGraph 而不是 create_agent
- 提出了"agent harness"这个词在 LangChain 圈的标准用法

### Latent Space podcast: Context Engineering for Agents — Lance Martin 【参考】

- 🔗 <https://www.latent.space/p/context-engineering-for-agents-lance>
- 上面那篇 Bitter Lesson 的播客版，开车/通勤时听
- 配套：[High Signal 播客的另一期](https://high-signal.delphina.ai/episode/context-engineering-to-ai-agent-harnesses-the-new-software-discipline) 也在讨论 agent harness 这个新学科

---

## 🔬 Claude Code 架构深度拆解

你已经写了迷你版，看真版能补很多细节。

### Inside Claude Code: An Architecture Deep Dive — Zain Hasan 【推荐】

- 📅 2026 · 🔗 <https://zainhas.github.io/blog/2026/inside-claude-code-architecture/>
- QueryEngine、Tool 接口契约、三层 compaction（Micro/Auto/Full）、7 层 safety——全画出来了
- **共同结论**：只有 1.6% 是 AI 决策代码，98.4% 是 harness（跟本 repo 08 章 README 完全印证）

### Dive into Claude Code（arxiv 2604.14228）【参考】

- 🔗 <https://arxiv.org/abs/2604.14228> · 配套 repo：<https://github.com/VILA-Lab/Dive-into-Claude-Code>
- 学术级源码分析，v2.1.88 的 1900 文件 / 512K LoC 系统拆解
- 又厚又干，作为查考手册用

### Claude Code architecture: Leaked source deep dive (WaveSpeed) 【参考·谨慎】

- 🔗 <https://wavespeed.ai/blog/posts/claude-code-architecture-leaked-source-deep-dive/>
- 基于"泄漏"源码的逆向分析，读的时候带怀疑——某些细节可能跟最新版不一致

---

## 🧰 厂商官方指南

### OpenAI: A Practical Guide to Building Agents 【必读】

- 📅 2025.04 · 🔗 <https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf>（PDF）
- 何时该建 Agent、orchestration pattern、guardrails、tool 设计
- 比 Anthropic Building Effective Agents 更工程化，**互补着读**

### LangChain: Open Deep Research blog 【推荐】

- 📅 2025.07 · 🔗 <https://blog.langchain.com/open-deep-research/>
- 官方 Deep Research 项目的设计博客，对应本 repo 09 章
- 看完再去读 [配套 GitHub](https://github.com/langchain-ai/open_deep_research) 源码

---

## 📊 评测（你下一个该学的方向）

做完 Deep Research 后，**没有 eval 就是没有 ground truth**——从"会做"到"会调"的分水岭。

### Establishing Best Practices for Building Rigorous Agentic Benchmarks 【必读·写 eval 前】

- 📅 2025.07 · 🔗 <https://arxiv.org/pdf/2507.02825>
- 给 17 个常见 agent benchmark 找出系统性问题
- 写自己 eval 前必读，避免重复别人踩过的坑

### AI Agent Benchmarks 2026 全景 【参考】

- 🔗 <https://benchmarkingagents.com/agent-benchmarks/>
- SWE-bench / WebArena / AgentBench / Terminal-Bench / OSWorld / Tau-Bench 全列出来对比
- 挑一个跟你方向匹配的入手

### Top 7 Benchmarks That Actually Matter — MarkTechPost 【参考】

- 📅 2026.04 · 🔗 <https://www.marktechpost.com/2026/04/26/top-7-benchmarks-that-actually-matter-for-agentic-reasoning-in-large-language-models/>
- 2026 年的更新版：哪些 benchmark 还有信号、哪些已经饱和

---

## 🎓 配套代码 / 课程

### LangChain Academy: Deep Research with LangGraph 【推荐】

- 🔗 <https://academy.langchain.com/courses/deep-research-with-langgraph>（免费课）
- 配套 repo：<https://github.com/langchain-ai/deep_research_from_scratch>
- **跟本 repo 09 章同一个教学路径**，对照看你写的代码和官方怎么做相同决策的

### langchain-ai/open_deep_research 【参考】

- 🔗 <https://github.com/langchain-ai/open_deep_research>
- 生产版（Deep Research Bench 第 6），本 repo 09 章的对照标杆
- 想做 v3 升级时来这里抄思路

### All-Hands-AI/OpenHands 【参考】

- 🔗 <https://github.com/All-Hands-AI/OpenHands>
- 开源 coding agent（前身叫 OpenDevin），全栈：file edit / bash / browser
- 看 harness 怎么处理多模态工具时的最完整开源参照

---

## 📬 持续关注（订阅源）

| 源 | 何许人 | 频率 | 含金量 |
| --- | --- | --- | --- |
| [rlancemartin.github.io](https://rlancemartin.github.io) | Lance Martin（LangChain 核心） | 月更 | 每篇都干 |
| [Anthropic Engineering Blog](https://www.anthropic.com/engineering) | Anthropic 团队 | 月 1-2 篇 | 稳定高质量 |
| [Latent Space](https://www.latent.space/) | swyx & Alessio | 周更 | AI Engineer 圈事实标准播客 |
| [Simon Willison's Weblog](https://simonwillison.net/) | Simon Willison | 几乎日更 | 实践细节最勤的个人博主 |

---

## ⚠️ 一些坦白话

- **跳过的**：medium.com 上各种"我读完 Anthropic blog 总结了 5 点"类文章——读原文就行
- **小心的**：标题党 "Manus 让 Devin 失业" / "AI Agent 终极架构" 这种，多半是营销
- **中文资源**：李博杰那篇 [Claude's Context Engineering Secrets](https://01.me/en/2025/12/context-engineering-from-claude/) 是原创高质量。其它中文 agent 文章九成是英文文章转译，没必要绕

---

## 给你的一周阅读路径

1. **Day 1-2**：🥇 三篇（Anthropic Effective Agents + Multi-Agent Research + Cognition Don't Build）
2. **Day 3**：Lance Martin 两篇（Bitter Lesson + Manus Context Engineering）
3. **Day 4-5**：过 [LangChain Deep Research 课](https://academy.langchain.com/courses/deep-research-with-langgraph)，对照本 repo 09 章看官方怎么写相同决策
4. **Day 6-7**：挑一个 agent benchmark（建议 Tau-Bench 或 Terminal-Bench，比 SWE-bench 轻量），给本 repo 08 章 harness 跑 5-10 个 sample，**自己看分数**

读完再回来讨论：v3 升级 / 新开 `10_eval_harness` / 做 MCP server / 做 Browser-Use 风格 Agent —— 这时候你会知道自己想做哪个。
