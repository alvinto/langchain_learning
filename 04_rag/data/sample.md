# LangChain 简介

LangChain 是一个用于开发由大语言模型驱动的应用程序的框架。
它的核心理念是把 prompt、模型、工具、记忆、检索等抽象成统一的 Runnable 接口，再用 `|` 拼接。

## 核心组件

- **Models**：对各种 LLM / Chat / Embedding 模型的统一封装。
- **Prompts**：模板化的提示词，支持变量替换和角色化。
- **LCEL (LangChain Expression Language)**：用 `|` 把组件串成链。
- **Memory**：保存多轮会话历史，可按 session 隔离。
- **Retrievers**：从向量库或外部源检索相关上下文。
- **Tools / Agents**：让模型调用外部工具，自主决策。

## 与 LangGraph 的关系

LangGraph 是基于 LangChain 构建的图状态编排框架，适合写有循环、条件分支、人在回路的复杂 Agent。
单链场景用 LCEL 就够了；多步、复杂控制流推荐 LangGraph。

## 推荐学习路径

1. 先掌握 LCEL 三件套：prompt | llm | parser
2. 学 RunnableWithMessageHistory 实现多轮
3. 学 RAG 把私有数据接入
4. 学工具调用 / Agent
5. 用 LangGraph 编排复杂流程
