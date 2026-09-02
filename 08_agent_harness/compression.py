"""
上下文压缩：当历史消息过长时，把"较老的一半"摘要成一条 SystemMessage。

策略：
- 触发阈值用消息条数（简单直观；想严谨可以换 tiktoken 计 token）
- 始终保留：第一条 SystemMessage（人设）、最近 N 条消息（保持工具调用上下文连贯）
- 中间的消息送给小一档的 LLM 摘要

注意：不要把还没 tool_response 的 AI tool_call 切成"已摘要"——会让 OpenAI
报错"tool_call_id 找不到对应 assistant message"。这里的策略是：先找到一个
"安全切点"（既不是 ToolMessage、上一条也不是带 tool_calls 的 AIMessage），
再做切割。
"""
from __future__ import annotations  # 延迟注解

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage  # 消息类型

import sys  # 修改 import 路径
from pathlib import Path  # 路径解析
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 加入项目根目录以 import _common
from _common import get_llm  # noqa: E402  # 获取 LLM 实例的公共工厂


def _is_safe_cut(prev: BaseMessage | None, cur: BaseMessage) -> bool:  # 定义函数
    """判断在 cur 处切割是否不会破坏 tool_call / ToolMessage 配对。"""
    if isinstance(cur, ToolMessage):  # 不能在 ToolMessage 上切（它必须紧跟 AIMessage tool_calls）
        return False  # 返回结果
    if isinstance(prev, AIMessage) and getattr(prev, "tool_calls", None):  # 上一条是待响应的 tool_call
        return False  # 返回结果
    return True  # 其余位置可安全切割


def maybe_compress(messages: list[BaseMessage], threshold: int = 30, keep_recent: int = 10) -> list[BaseMessage]:  # 定义函数
    """超过 threshold 条就压缩，否则原样返回。"""
    if len(messages) <= threshold:  # 未超阈值
        return messages  # 不压缩

    # 第 0 条若是 SystemMessage 永远保留
    head: list[BaseMessage] = []  # 头部保留区（人设 system prompt）
    body_start = 0  # 可压缩区起始下标
    if messages and isinstance(messages[0], SystemMessage):  # 首条是 system
        head = [messages[0]]  # 保留第一条
        body_start = 1  # 从第二条开始才是 body

    # 找一个安全切点：从倒数第 keep_recent 个开始往前找
    cut = max(body_start, len(messages) - keep_recent)  # 初始切点：保留最近 keep_recent 条
    while cut > body_start:  # 向前扫描直到 body_start
        prev = messages[cut - 1] if cut > 0 else None  # 切点前的消息
        if _is_safe_cut(prev, messages[cut]):  # 当前切点安全
            break  # 停止搜索
        cut -= 1  # 切点前移一位再试

    to_summarize = messages[body_start:cut]  # 中间待摘要段
    tail = messages[cut:]  # 尾部原样保留
    if not to_summarize:  # 没有可摘要内容（切点贴到 body_start）
        return messages  # 放弃压缩

    # 用 temperature=0 的 LLM 做摘要，避免胡编
    llm = get_llm(temperature=0.0)  # 低温摘要模型
    transcript = "\n\n".join(  # 把待摘要消息拼成纯文本
        f"[{type(m).__name__}] {getattr(m, 'content', '') or ''}" for m in to_summarize  # for 循环
    )  # 闭合括号/元组/字典
    prompt = (  # 摘要指令
        "你是一个会话压缩助手。把下面的多轮 Agent 对话压缩成简洁的中文摘要，"  # 字符串/template 参数
        "包含：用户目标、Agent 已采取的关键步骤与工具调用、目前已知事实、未完成的事项。"  # 字符串/template 参数
        "不要丢失文件路径、命令、错误信息这些具体细节。\n\n"  # 字符串/template 参数
        f"---\n{transcript}\n---"  # 字符串/template 参数
    )  # 闭合括号/元组/字典
    summary = llm.invoke(prompt).content  # 调用 LLM 生成摘要文本

    summary_msg = SystemMessage(  # 用 SystemMessage 承载摘要
        content=f"[历史摘要 — 压缩了 {len(to_summarize)} 条消息]\n{summary}"  # 执行本行逻辑
    )  # 闭合括号/元组/字典
    return head + [summary_msg] + tail  # 组装：保留 head + 摘要 + 最近 tail
