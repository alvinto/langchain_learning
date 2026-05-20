# 01 · LLM 基础

学会用 LangChain 调用模型——所有后面章节的地基。

| 文件 | 学到什么 |
| --- | --- |
| [01_hello_llm.py](01_hello_llm.py) | `get_llm()` 拿到模型，`.invoke()` 单轮问答 |
| [02_chat_messages.py](02_chat_messages.py) | `SystemMessage / HumanMessage / AIMessage` 三种角色，多轮就是消息列表 |
| [03_prompt_template.py](03_prompt_template.py) | `PromptTemplate` / `ChatPromptTemplate` / `MessagesPlaceholder` |
| [04_output_parser.py](04_output_parser.py) | 字符串 / JSON / Pydantic 三种解析器 |
| [05_streaming.py](05_streaming.py) | `.stream()` 边生成边打印 |

```bash
python 01_basics/01_hello_llm.py
```
