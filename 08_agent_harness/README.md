# 08_agent_harness — 迷你版 Claude Code 风格 Agent Harness

把"Agent"和"harness"分开来理解：
- **Agent** = LLM + 工具，本质就是一个会调用工具的模型
- **Harness** = 让 Agent 能在真实世界跑起来的那一层运行时：工具注册、权限网关、Hook、上下文管理、Checkpointing、错误预算、子 Agent 派发……

`create_react_agent` 给你的是 Agent，但生产里你需要的是 Harness。这个示例就是把这层东西完整地实现出来。

## 文件结构

```
08_agent_harness/
├── app.py            ← REPL 入口，斜杠命令在这里
├── harness.py        ← LangGraph 状态机：agent ⇄ tools ⇄ compress
├── tools.py          ← 沙箱化工具：read/write/list/grep/bash/todo
├── subagent.py       ← spawn_subagent 工具 + 只读子 Agent 实现
├── permissions.py    ← auto / ask / deny 三档权限策略
├── hooks.py          ← pre_tool / post_tool / on_stop hook 总线 + 内置审计
├── compression.py    ← 历史消息超阈值时的安全压缩
├── state.py          ← AgentState TypedDict
└── workspace/        ← Agent 的沙箱根目录（所有路径工具被锁在这里）
```

## 高级特性逐项

| 特性 | 实现位置 | 说明 |
| --- | --- | --- |
| 工具注册表 + Pydantic schema | `tools.py` | 所有工具都用 `@tool + args_schema` 暴露给 LLM，参数自动校验 |
| Workspace 沙箱 | `tools.py:_safe_path` | 任何路径越界（`../etc/passwd`）直接拒绝 |
| 权限网关 (auto/ask/deny) | `permissions.py` + `harness.py:tool_node` | 危险工具默认 ask，REPL 里 `/allow run_bash` 可改 |
| Hook 总线 | `hooks.py` + `harness.py:tool_node` | pre_tool 可阻断/改写参数，post_tool 适合写日志 |
| 危险命令拦截 | `hooks.py:block_dangerous_bash` | 内置 hook 示例，拦 `rm -rf /` 等模式 |
| 审计日志 | `hooks.py:audit_logger` | 每个会话写到 `.sessions/<id>.jsonl` |
| Agent 自管理 Todo | `tools.py:todo_write` + `state.AgentState.todos` | LLM 写入待办，状态副作用合并到 state，REPL `/todos` 查看 |
| 上下文压缩 | `compression.py` | 超过 30 条消息时把"较老的一半"摘要成 SystemMessage，避开 tool_call 边界 |
| 迭代 / 错误预算 | `harness.py:route_after_agent` | iteration ≥ 25 或 error_count ≥ 5 时强制停机 |
| Checkpointing | `harness.py` 的 `MemorySaver` | 同一 thread_id 多轮对话连续，`/reset` 开新会话 |
| 子 Agent 派发 | `subagent.py:spawn_subagent` | 主 Agent 可派一个只读子 Agent 去探查，主上下文只看结论 |
| 流式输出 | `app.py:main` | `app.stream(stream_mode="values")` |

## 怎么跑

```bash
# 1. 在 langchain_learning 项目根目录，确认 .env 已经填好
source .venv/bin/activate

# 2. 进入 REPL
python 08_agent_harness/app.py
```

斜杠命令：

```
/help          帮助
/todos         看 Agent 的待办清单
/policy        看权限策略
/allow <tool>  把某工具改 auto
/deny  <tool>  把某工具改 deny
/reset         开新 session
/quit          退出
```

## 试试这些 prompt

第一次跑可以试试由浅到深：

1. **简单读写**："在 workspace 下创建 hello.py，里面写一个打印 'hi' 的 main 函数，并执行它"
2. **多步规划**："实现一个 fibonacci 模块（fib.py），包含递归和迭代两种实现，再写一个 test_fib.py 测试它们结果一致，最后用 python -m unittest 跑通"
3. **派子 Agent**："这个 workspace 里都有什么 .py 文件，分别是干嘛的？"——观察主 Agent 如何调用 spawn_subagent 而不是亲自 grep
4. **触发权限提示**：默认 `run_bash` 是 ask，所以会被打断要批准

## 设计取舍

- **没用 `create_react_agent`**：那个 prebuilt 把 hooks、权限、压缩这些都封死了。这里我们手写 `StateGraph` 才能在 `tool_node` 里插入权限和 hook
- **压缩用的是消息条数而不是 token**：示例里更直观；想严谨可以换成 `tiktoken` 计 token
- **子 Agent 是同步的**：简单清晰；想并行用 `asyncio.gather` 或 LangGraph 的 `Send`
- **MemorySaver 是内存版**：重启就丢。生产换成 `SqliteSaver` / `PostgresSaver` 一行代码的事

## 跟 LangChain 自带 Agent 的对照

| 你想要的 | LangChain 直接给 | 这个 harness |
| --- | --- | --- |
| 工具调用循环 | `create_react_agent` | `StateGraph` 手写 |
| 工具执行 | `ToolNode` | 自己的 `tool_node`，多了权限+hook |
| 多轮记忆 | `RunnableWithMessageHistory` | `MemorySaver` checkpointer |
| 人在回路 | LangGraph 的 `interrupt` | `permissions.ask` |
| 上下文太长 | 没现成 | `compression.maybe_compress` |
| 子 Agent | 没现成 | `spawn_subagent` |

读完这套就能理解：**Claude Code、Cursor、Cline 这类 Agent 产品 90% 的复杂度都在 harness，不在 LLM 调用本身。**
