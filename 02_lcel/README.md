# 02 · LCEL（LangChain Expression Language）

用 `|` 把 prompt、模型、parser、函数串成一条 Runnable，统一拿到 `invoke / stream / batch / ainvoke` 四个入口。

| 文件 | 学到什么 |
| --- | --- |
| [01_pipe_chain.py](01_pipe_chain.py) | `prompt \| llm \| parser` 三件套，以及 `.batch` 批量并发 |
| [02_runnable_parallel.py](02_runnable_parallel.py) | `RunnableParallel`：多分支并行返回 dict |
| [03_runnable_passthrough.py](03_runnable_passthrough.py) | `RunnablePassthrough.assign` 给 dict 追加字段（RAG 的核心模式） |
| [04_runnable_lambda.py](04_runnable_lambda.py) | `RunnableLambda` 把普通函数塞进链路 |
| [05_runnable_branch.py](05_runnable_branch.py) | `RunnableBranch` 条件路由，类似 if/elif/else |

> 看完这章再去看 04 章 RAG 会非常顺，因为 RAG 本质就是 LCEL 的标准应用。
