"""
04-7 多轮 RAG（Common patterns）

多轮 RAG 的核心坑点：
1. **历史消息占 token**，和检索到的 context 一起塞进 prompt，容易挤爆窗口、压缩「资料」区。
2. **追问带指代**（「它」「第一个」），若直接用当前句做向量检索，召回往往偏离意图。
3. **记忆不会自动清理**，session 里消息只增不减，存储与每次请求的 token 持续上涨。

解决方案（关键区分：**检索阶段是否带上历史**）：
- **方案 A（简单、最常用）**：检索 **只用当前用户问题**；`chat_history` 只出现在 **回答用 prompt** 里。
- **方案 B（增强）**：用历史 + 当前问题 **改写成 standalone query**，再用改写句去检索，提升召回。
- **方案 B′（assign）**：用 `RunnablePassthrough.assign` 分步写入 `search_query`、`context`，
  与官方 `create_retrieval_chain` 的 assign 结构一致（见 `build_scheme_b_assign_chain`）。

本文件用同一知识库、同一轮对话对比：裸检索 vs A vs B vs B′；并演示对 history 做 trim。

---------------------------------------------------------------------------
与官方写法对照（LangChain Classic / LCEL，包名 `langchain_classic.chains`）
文档：https://python.langchain.com/docs/use_cases/question_answering/chat_history
---------------------------------------------------------------------------

【方案 A · 检索只用当前问，历史只进回答 prompt】

  官方三件套：
    from langchain_classic.chains import create_retrieval_chain
    from langchain_classic.chains.combine_documents import create_stuff_documents_chain

    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", "...\\n{context}"),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])
    combine = create_stuff_documents_chain(llm, qa_prompt)
    rag_a = create_retrieval_chain(retriever, combine)
    # create_retrieval_chain 对 BaseRetriever 固定做：(lambda x: x["input"]) | retriever
    # → 检索键是 input，不会把 chat_history 送进向量库
    rag_a.invoke({"input": question, "chat_history": messages})

  本文件 `build_scheme_a_chain` 等价关系：
    itemgetter("question") | retriever     ≈  官方 x["input"] | retriever
    answer_prompt + MessagesPlaceholder    ≈  create_stuff_documents_chain 里的 qa_prompt
    入参 question / chat_history           ≈  官方 input / chat_history
    （本 demo 返回 str；官方返回 dict，含 context、answer 等键）

【方案 B · 历史参与改写 query，再检索】

  官方：
    from langchain_classic.chains import create_history_aware_retriever, create_retrieval_chain

    contextualize_q_prompt = ChatPromptTemplate.from_messages([
        ("system", "… formulate a standalone question …"),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])
    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )
    # 内部 RunnableBranch：
    #   无 chat_history → input 直接 | retriever
    #   有 chat_history → contextualize_q_prompt | llm | StrOutputParser() | retriever
    rag_b = create_retrieval_chain(history_aware_retriever, combine)
    rag_b.invoke({"input": question, "chat_history": messages})

  本文件 `build_scheme_b_chain` / `REPHRASE_PROMPT` 等价关系：
    REPHRASE_PROMPT + condense_to_search_query  ≈  create_history_aware_retriever 的「有历史」分支
    enrich_with_condensed_retrieval            ≈  history_aware_retriever 输出 Document 列表后再 format
    回答侧 answer_prompt 与 A 相同              ≈  同一个 create_stuff_documents_chain 思路

【方案 B′ · RunnablePassthrough.assign 改写 + 检索】

  官方 create_retrieval_chain 源码形态：
    RunnablePassthrough.assign(context=retrieval_docs).assign(answer=combine_docs_chain)

  本文件把「改写 query」拆成第一步 assign，「检索拼 context」第二步 assign：
    RunnablePassthrough.assign(search_query=RunnableBranch(..., condense, 原问))
    | RunnablePassthrough.assign(context=itemgetter("search_query") | retriever | format_docs)
    | answer_prompt | llm | parser

  与 `build_scheme_b_chain`（RunnableLambda 一次做完）语义相同，assign 版更易插桩、与 Classic 链对齐。

【Session · 谁负责攒历史】

  官方常用 RunnableWithMessageHistory 包最外层（见 03_memory/02_runnable_with_history.py）：
    from langchain_core.runnables.history import RunnableWithMessageHistory

    store = RunnableWithMessageHistory(
        rag_b,
        get_session_history,
        input_messages_key="input",           # 映射到 chain 的 input
        history_messages_key="chat_history",
    )
    store.invoke({"input": q}, config={"configurable": {"session_id": "u1"}})

  本文件 `InMemoryChatMessageHistory` + 手动 add_user/add_ai  ≈  同上 store，只是未包 Runnable 层，
  便于看清每轮传入 chain 的 chat_history 长什么样。

【坑点 3 · 历史过长】

  官方文档建议在写入/读出 history 时 trim 或摘要，无单独 magic API：
    trim_messages(..., strategy="last")     → 本文件 trim_chat_history
    SummarizationMiddleware / 03_memory/07  →  Agent 或自管 session 时的摘要方案

  注意：trim 通常作用在「送进 LLM 的 chat_history」；方案 A/B 的检索仍应优先用当前 input
  （B 的改写链只吃 input + chat_history 生成 query，不要把整库文档塞进 retriever）。
"""
from __future__ import annotations

import sys
from operator import itemgetter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import trim_messages
from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableBranch, RunnableLambda, RunnablePassthrough
from langchain_text_splitters import RecursiveCharacterTextSplitter

from _common import banner, get_embeddings, get_llm


def build_retriever():
    docs = TextLoader(
        str(Path(__file__).parent / "data" / "sample.md"),
        encoding="utf-8",
    ).load()
    chunks = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=30).split_documents(
        docs
    )
    return FAISS.from_documents(chunks, get_embeddings()).as_retriever(search_kwargs={"k": 2})


def format_docs(docs) -> str:
    return "\n\n".join(d.page_content for d in docs)


def preview_docs(label: str, query: str, retriever) -> None:
    docs = retriever.invoke(query)
    print(f"\n--- 检索 query: {label!r} → {query!r} ---")
    for i, d in enumerate(docs, 1):
        snippet = d.page_content.replace("\n", " ")[:100]
        print(f"  [{i}] {snippet}...")


# 方案 B · 查询改写（官方：contextualize_q_prompt + create_history_aware_retriever）
# 变量名必须用 input + chat_history，与 hub/langchain-ai/chat-langchain-rephrase 及 Classic 链一致。
REPHRASE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是检索查询改写助手。根据对话历史和用户的追问，"
            "生成一条**单独成立**的检索问句（保留实体名，消解「它/这个/前者」等指代）。"
            "只输出问句本身，不要解释。",
        ),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ]
)

condense_to_search_query = REPHRASE_PROMPT | get_llm(temperature=0) | StrOutputParser()


def _qa_answer_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是严谨助手。仅根据「资料」回答；资料不足就说「资料中没有提到」。\n\n资料:\n{context}",
            ),
            MessagesPlaceholder("chat_history"),
            ("human", "{question}"),
        ]
    )


def _search_query_runnable():
    """无历史 → 原问；有历史 → condense（与 create_history_aware_retriever 分支一致）。

    RunnableBranch 约定：前面是 (condition, runnable) 对，**最后一项是 default 分支**
    （不能写成 (lambda _: True, chain) 元组，否则会 TypeError）。
    """
    return RunnableBranch(
        (
            lambda x: not x.get("chat_history", False),
            itemgetter("question"),
        ),
        {
            "input": itemgetter("question"),
            "chat_history": itemgetter("chat_history"),
        }
        | condense_to_search_query,
    )


def build_retrieval_prep_assign(retriever):
    """assign 中间链：输入 dict 上增加 search_query、context，原键保留（Passthrough）。"""
    return (
        RunnablePassthrough.assign(
            search_query=_search_query_runnable(),
        )
        | RunnablePassthrough.assign(
            context=itemgetter("search_query") | retriever | format_docs,
        )
    )


def build_scheme_a_chain(retriever):
    """方案 A：retriever 只吃当前 question；history 仅用于生成答案。

    官方一行版：create_retrieval_chain(retriever, create_stuff_documents_chain(llm, qa_prompt))
    其中 retriever 只接收 invoke 字典里的 input（本文件字段名为 question）。
    """
    # 官方 create_retrieval_chain 等价于 assign(context=retrieval_docs) + assign(answer=combine)
    # 这里手写 dict LCEL：context 分支 ≈ (lambda x: x["input"]) | retriever | format_docs
    return (
        {
            "context": itemgetter("question") | retriever | format_docs,
            "question": itemgetter("question"),
            "chat_history": itemgetter("chat_history"),
        }
        | _qa_answer_prompt()
        | get_llm()
        | StrOutputParser()
    )


def build_scheme_b_chain(retriever):
    """方案 B：先 condense 再 retriever；history 参与检索阶段的 query 改写。

    官方一行版：
      history_aware_retriever = create_history_aware_retriever(llm, retriever, rephrase_prompt)
      rag_b = create_retrieval_chain(history_aware_retriever, combine)
    """
    def enrich_with_condensed_retrieval(payload: dict) -> dict:
        question = payload["question"]
        history = payload["chat_history"]
        # 官方 create_history_aware_retriever：无 history 时 retriever.invoke(input)；
        # 有 history 时 rephrase_prompt | llm | StrOutputParser() | retriever
        if history:
            search_query = condense_to_search_query.invoke(
                {"input": question, "chat_history": history}
            ).strip()
        else:
            search_query = question
        context = format_docs(retriever.invoke(search_query))
        return {
            "context": context,
            "question": question,
            "chat_history": history,
        }

    return (
        RunnableLambda(enrich_with_condensed_retrieval)
        | _qa_answer_prompt()
        | get_llm()
        | StrOutputParser()
    )


def build_scheme_b_assign_chain(retriever):
    """方案 B′：RunnablePassthrough.assign 改写 search_query 再 assign context 后回答。

    等价于 create_retrieval_chain(history_aware_retriever, combine) 的 LCEL 拆解写法；
    第一步 assign 对应 history-aware 的 query，第二步 assign 对应 retriever → context。
    """
    return (
        build_retrieval_prep_assign(retriever)
        | _qa_answer_prompt()
        | get_llm()
        | StrOutputParser()
    )


def trim_chat_history(messages: list, max_messages: int = 6) -> list:
    """坑点 3：对送进 LLM 的历史做裁剪（不删 session 存储，只减本次 prompt 体积）。

    生产里可放在 get_session_history() 或 RunnableWithMessageHistory 回调里，
    在返回 messages 给 chain 之前调用（与 03_memory/05_trim_messages 同一 API）。
    """
    return trim_messages(
        messages,
        max_tokens=max_messages,
        token_counter=len,
        strategy="last",
        include_system=False,
        start_on="human",
    )


def demo_memory_pressure(history_store: InMemoryChatMessageHistory) -> None:
    approx = count_tokens_approximately(history_store.messages)
    print(
        f"\n>> 坑点 3 · session 已累积 {len(history_store.messages)} 条消息，"
        f"近似 {approx} tokens（会随对话增长）"
    )
    trimmed = trim_chat_history(history_store.messages, max_messages=4)
    print(f"   送入 LLM 前 trim 为 {len(trimmed)} 条（检索仍只用当前问句）")


def main() -> None:
    banner("04-7 Multi-turn RAG (A vs B vs B′ assign)")
    retriever = build_retriever()
    chain_a = build_scheme_a_chain(retriever)
    chain_b = build_scheme_b_chain(retriever)
    chain_b_assign = build_scheme_b_assign_chain(retriever)
    prep_assign = build_retrieval_prep_assign(retriever)

    # 官方会用 RunnableWithMessageHistory 自动维护 chat_history；这里手动维护便于对照字段。
    session = InMemoryChatMessageHistory()
    cfg_base = {"question": "", "chat_history": []}

    # 第 1 轮：完整问题，三种检索 query 一致
    q1 = "LangChain 的核心组件有哪些？"
    print(f"\n======== 第 1 轮 ========\n用户: {q1}")
    preview_docs("裸检索", q1, retriever)

    session.add_user_message(q1)
    ans1 = chain_a.invoke({**cfg_base, "question": q1, "chat_history": session.messages})
    session.add_ai_message(ans1)
    print(f"\n助手(A): {ans1[:200]}...")

    # 第 2 轮：指代追问 — 坑点 2
    q2 = "它和 LangGraph 是什么关系？"
    print(f"\n======== 第 2 轮（指代追问）========\n用户: {q2}")

    print("\n>> 坑点 2 · 若检索直接用当前句（不含历史实体）：")
    preview_docs("裸检索（易偏）", q2, retriever)

    standalone = condense_to_search_query.invoke(
        {"input": q2, "chat_history": trim_chat_history(session.messages)}
    )
    print(f"\n>> 方案 B · 改写后再检索：{standalone!r}")
    preview_docs("B 改写后", standalone, retriever)

    demo_memory_pressure(session)
    history_for_llm = trim_chat_history(session.messages)

    payload = {"question": q2, "chat_history": history_for_llm}
    ans_a = chain_a.invoke(payload)
    ans_b = chain_b.invoke(payload)

    prepared = prep_assign.invoke(payload)
    print(f"\n>> 方案 B′ assign · 中间态 search_query: {prepared['search_query']!r}")
    ans_b_assign = chain_b_assign.invoke(payload)

    print("\n>> 方案 A 回答（检索仅用当前问句，历史只辅助理解）：")
    print(ans_a)
    print("\n>> 方案 B 回答（RunnableLambda 改写 + 检索）：")
    print(ans_b)
    print("\n>> 方案 B′ 回答（RunnablePassthrough.assign 改写 + 检索）：")
    print(ans_b_assign)

    session.add_user_message(q2)
    session.add_ai_message(ans_b_assign)


if __name__ == "__main__":
    main()
