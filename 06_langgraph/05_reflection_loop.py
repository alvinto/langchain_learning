"""
06-5 自我纠错循环（Producer / Critic）
学到：用 LangGraph 条件边实现「生成 → 评审 → 不通过则回环重写」。
- generate 节点：Producer Agent 根据任务（及上轮反馈）写草稿
- review 节点：Critic Agent 结构化评审，输出 approved + feedback
- 条件边：通过 → END；不通过且未超次数 → 回到 generate

图结构：
    START → generate → review ──通过──→ END
                         ↑      │
                         └──未通过且未超轮次──┘
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from typing import Literal, TypedDict

from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from _common import banner, get_llm

logger = logging.getLogger(__name__)


# ---------- State：图内共享字段，节点只返回需要更新的部分 ----------

class ReflectionState(TypedDict):
    topic: str              # 写作主题
    requirements: str       # 评审对照的硬性要求（Critic 依此打分）
    draft: str              # Producer 当前草稿
    feedback: str           # Critic 上轮给出的修改意见（回环时喂给 Producer）
    approved: bool          # 是否已通过评审
    revision: int           # 已生成几轮（用于防止无限循环）
    max_revisions: int      # 最多允许几轮 generate


# ---------- Critic 结构化输出：避免从自由文本里解析 PASS/FAIL ----------

class ReviewResult(BaseModel):
    approved: bool = Field(description="草稿是否满足全部要求")
    feedback: str = Field(
        description="通过时可为空；不通过时给出具体、可执行的修改建议",
    )


# Producer 温度稍高，便于多样化改写；Critic 温度 0，评审要稳定
producer_llm = get_llm(temperature=0.7)
critic_llm = get_llm(temperature=0).with_structured_output(ReviewResult)

PRODUCER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "你是文案 Producer。根据任务要求写一版完整草稿，直接输出正文，不要解释过程。",
    ),
    (
        "human",
        # feedback_block 首轮为空提示，重试时带上 Critic 意见
        "任务：{topic}\n\n要求：{requirements}\n\n"
        "{feedback_block}",
    ),
])

CRITIC_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "你是严格评审 Critic。对照「要求」检查草稿，缺一项即判不通过。"
        "feedback 要具体，指出缺什么、怎么改。",
    ),
    (
        "human",
        "任务：{topic}\n\n要求：{requirements}\n\n草稿：\n{draft}",
    ),
])


def generate(state: ReflectionState) -> dict:
    """Producer 节点：写/重写草稿。"""
    revision = state.get("revision", 0) + 1
    feedback = state.get("feedback", "").strip()
    logger.info("── generate 第 %d 轮 ── topic=%r", revision, state["topic"])
    if feedback:
        logger.info("带上轮评审意见重写（%d 字）", len(feedback))
        logger.debug("feedback: %s", feedback)
    # 第二轮起把 Critic 意见注入 prompt，实现「按反馈修订」
    feedback_block = (
        f"上一轮评审意见（请逐条修正）：\n{feedback}"
        if feedback
        else "（首轮生成，无评审意见）"
    )
    draft = producer_llm.invoke(
        PRODUCER_PROMPT.format_messages(
            topic=state["topic"],
            requirements=state["requirements"],
            feedback_block=feedback_block,
        )
    ).content
    logger.info("草稿已生成（%d 字）", len(draft or ""))
    logger.debug("draft:\n%s", draft)
    # 每次生成后先标记未通过，等 review 节点更新 approved
    return {"draft": draft, "revision": revision, "approved": False}


def review(state: ReflectionState) -> dict:
    """Critic 节点：对照 requirements 评审 draft，输出结构化结论。"""
    logger.info("── review 评审第 %d 轮草稿 ──", state.get("revision", 0))
    result: ReviewResult = critic_llm.invoke(
        CRITIC_PROMPT.format_messages(
            topic=state["topic"],
            requirements=state["requirements"],
            draft=state["draft"],
        )
    )
    logger.info(
        "评审结果: approved=%s, feedback=%r",
        result.approved,
        (result.feedback[:120] + "…") if len(result.feedback) > 120 else result.feedback,
    )
    return {
        "approved": result.approved,
        "feedback": result.feedback.strip(),
    }


def route_after_review(state: ReflectionState) -> Literal["generate", "__end__"]:
    """条件边路由：通过或超轮次 → 结束；否则回到 generate 重写。"""
    if state.get("approved"):
        logger.info("路由 → END（评审通过）")
        return END
    # 达到上限仍不通过：带着最后一版 draft 结束，避免死循环
    if state.get("revision", 0) >= state.get("max_revisions", 2):
        logger.warning(
            "路由 → END（已达 max_revisions=%d，仍未通过）",
            state.get("max_revisions", 2),
        )
        return END
    logger.info("路由 → generate（未通过，继续修订）")
    return "generate"


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    banner("06-5 Reflection Loop · Producer / Critic")

    graph = (
        StateGraph(ReflectionState)
        .add_node("generate", generate)
        .add_node("review", review)
        .add_edge(START, "generate")
        .add_edge("generate", "review")
        # review 之后按 route_after_review 的返回值走 generate 或 END
        .add_conditional_edges("review", route_after_review, ["generate", END])
        .compile()
    )

    topic = "LangGraph 自我纠错循环"
    # 故意设多条硬性要求，方便观察 Critic 打回 → Producer 修订的过程
    requirements = (
        "1) 标题一行；2) 正文 80~150 字；3) 恰好 3 条 bullet 说明适用场景；"
        "4) 结尾一句行动号召；5) 禁止出现「待补充」「TBD」等占位符。"
    )

    logger.info("开始 invoke · topic=%r · max_revisions=3", topic)
    out = graph.invoke({
        "topic": topic,
        "requirements": requirements,
        "draft": "",
        "feedback": "",
        "approved": False,
        "revision": 0,
        "max_revisions": 2,
    })
    logger.info(
        "invoke 结束 · revision=%d · approved=%s",
        out["revision"],
        out["approved"],
    )

    print(f"修订轮次: {out['revision']}")
    print(f"评审通过: {out['approved']}")
    if not out["approved"]:
        print(f"未通过原因: {out['feedback']}")
    print("\n===== 最终草稿 =====\n")
    print(out["draft"])


if __name__ == "__main__":
    # DEBUG 可看完整 draft / feedback：LOGLEVEL=DEBUG python 05_reflection_loop.py
    import os
    if os.getenv("LOGLEVEL", "").upper() == "DEBUG":
        logging.getLogger(__name__).setLevel(logging.DEBUG)
    main()
