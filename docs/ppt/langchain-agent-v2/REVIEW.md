# LangChain PPT v1 → v2 专家审阅说明

审阅视角：LangChain v1 生态（`langchain-core` LCEL、`create_agent`、LangGraph、LangSmith）与本仓库 `langchain_learning` 学习路径。

## v1 主要问题（不完整 / 不准确 / 重复）

### 缺失的基础层

| 主题 | v1 状态 | 影响 |
|------|---------|------|
| **LCEL / Runnable** | 仅在 §3.2 卡片中零散提到 `\|`、`RunnableBranch` | 听众不理解「所有组件为何能 pipe」；缺少 `invoke` / `stream`、`RunnableParallel` |
| **Message 类型** | 几乎未单独说明 | Tool 循环、Chat 历史、RAG 上下文难以建立心智模型 |
| **Agent API 演进** | 正文使用 `create_react_agent` 表述 ReAct | LangChain **v1** 推荐 `create_agent`；`AgentExecutor` 旧路径未对比说明 |
| **LangSmith** | 仅在矩阵卡片、结尾一句带过 | 缺少 Trace / Debug / Eval 的**专页**，生产价值不清晰 |
| **仓库学习路径** | 零散目录注释（如 `02_lcel/`） | 无 **01–09 章**总览，难与分享结构对照自学 |

### 结构重复

- **§3.2**：`sec3-2-overview` + `sec3-2-chain-route` + `sec3-2-tool-reflect` 三页讲同一「四大模式」，信息重叠。
- **§4**：`sec4-stategraph` 与 `sec4-react` 可合并为「核心建模 + ReAct 循环」；`sec4-checkpoint` 与 `sec4-hitl` 同属生产特性。
- **§4 章节页**：四张 mini card 与后续正文重复。

### 概念层次不清

- **§3.1 Common Patterns**（RAG / Agent / Multi-Agent）与 **§3.2 四大编排模式**（Chaining / Routing / Tool / Reflection）未区分「**应用怎么拼**」vs「**编排怎么实现**」。

## v2 变更摘要

**文件**：[`index.html`](./index.html)（由 [`../langchain-agent/index.html`](../langchain-agent/index.html) 复制，**未修改 v1 源文件**）

**标题**：`LangChain 生态与底层原理 · v2`（`<title>`、封面副标题、目录 Vol）

**页数**：19 → **17** 页（`data-slide-id` 计数）

### 新增

| Slide ID | 位置 | 内容 |
|----------|------|------|
| `sec3-lcel` | `sec3-divider` 之后 | LCEL & Runnable：`invoke`、`\|`、`RunnableParallel`；Human/AI/Tool/System；`create_agent` vs `AgentExecutor` |
| `sec5-observability` | `closing` 之前 | LangSmith Trace 价值；本仓库 **01–09** 章学习路径 |

### 合并 / 删减

| 操作 | 结果 Slide ID |
|------|----------------|
| 删除 `sec3-2-chain-route`、`sec3-2-tool-reflect` | 并入 `sec3-2-overview`（一页四大编排模式 + 简图） |
| 删除 `sec4-stategraph`、`sec4-react` | 合并为 `sec4-core`（LangGraph 核心） |
| 删除 `sec4-checkpoint`、`sec4-hitl` | 合并为 `sec4-prod`（LangGraph 生产特性） |
| 简化 `sec4-divider` | 去掉 4 张重复 mini card |

### 文案与 API

- §3.1 标注为 **应用组合模式**；§3.2 标注为 **编排实现模式**。
- ReAct 图说明改为以 **`create_agent`** 为主、手写 `StateGraph` 对照 `06_langgraph/`；`create_react_agent` 仅在历史对照处出现。
- `sec2-modules` 的 core 卡片补充 Message 类型。
- 封面目录、`SPEAKER_NOTES`（17 条，与 slide id 一致）、页码 **01 / 17 – 16 / 17**（章节 divider 页脚仍保留 v1 的 `— · —` 样式）。

## v2 Slide ID 列表（17）

1. `cover`
2. `sec1-divider`
3. `sec1-problems`
4. `sec2-divider`
5. `sec2-modules`
6. `sec3-divider`
7. `sec3-lcel` **（新）**
8. `sec3-1-categories`
9. `sec3-1-architecture`
10. `sec3-1-patterns`
11. `sec3-2-overview` **（扩展）**
12. `sec4-divider` **（简化）**
13. `sec4-core` **（新，合并）**
14. `sec4-prod` **（新，合并）**
15. `sec4-compare`
16. `sec5-observability` **（新）**
17. `closing`

## v2.1 变更（对照《AI Agent + LangChain 底层实现完整学习指南》）

**标题**：`Agent 第一性原理 × 实现 · v2.1`

**页数**：17 → **19** 页（含封面共 19 section，`01/18`–`18/18` 编号）

### 新增

| Slide ID | 内容 |
|----------|------|
| `sec1-first-principles` | Agent 五步闭环 + 四大组件 + 边界公理（指南 §1） |
| `sec3-memory` | Memory 二分法（短时/长时 RAG）+ Agent 两种接入方式（指南 §3） |

### 增强

| Slide ID | 变更 |
|----------|------|
| `sec3-1-patterns` | Multi-Agent 三种拓扑（层级/并行/网络） |
| `sec3-2-overview` | 四大模式各补「第一性原理」+ LCEL vs LangGraph 边界 |
| `sec4-divider` | 强调全链路 8 步 |
| `sec4-compare` | LangChain vs LangGraph 第一性边界 + 全链路 8 步 |
| `closing` | 收束改为五步闭环金句 |

### v2.1 Slide ID 列表（19）

1. `cover`
2. `sec1-divider`
3. `sec1-first-principles` **（新）**
4. `sec1-problems`
5. `sec2-divider`
6. `sec2-modules`
7. `sec3-divider`
8. `sec3-lcel`
9. `sec3-memory` **（新）**
10. `sec3-1-categories`
11. `sec3-1-architecture`
12. `sec3-1-patterns`
13. `sec3-2-overview`
14. `sec4-divider`
15. `sec4-core`
16. `sec4-prod`
17. `sec4-compare`
18. `sec5-observability`
19. `closing`

`SPEAKER_NOTES` 已同步为 19 条。

## 建议后续（可选）

- 在 `sec3-lcel` 增加 `RunnableParallel` 极简代码截图（与 `02_lcel/03_parallel.py` 一致）。
- LangSmith 页可补一张 Trace 截图占位（`img-slot`）。
