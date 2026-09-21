
"""
create agent with memory
使用checkpointer参数
LangChain 的智能体将短期记忆视为其状态的一部分来加以管理。
通过将这些信息存储在图的结构中，代理能够在保持不同对话线程之间独立性的同时，获取某次对话的完整上下文信息。
状态会通过检查点机制被保存在数据库或内存中，这样线程就可以在任何时候重新开始执行。
当智能体被调用或某个步骤（比如工具调用）完成后，短期记忆会得到更新。而在每个步骤开始时，都会读取当前的状态。
"""
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from _common import get_llm


def get_user_info() -> str:
    """Look up information about the current user."""
    return "No user profile on file."


agent = create_agent(
    model=get_llm(),
    tools=[get_user_info],
    checkpointer=InMemorySaver(),
)

thread_config = {"configurable": {"thread_id": "1"}}
response = agent.invoke(
    {"messages": [{"role": "user", "content": "Hi! My name is Bob."}]},
    thread_config,
)["messages"][-1].content

print(response)  # "Hi Bob! Nice to see you here. How are you doing?"

response = agent.invoke(
    {"messages": [{"role": "user", "content": "What's my name?"}]},
    thread_config,
)["messages"][-1].content

print(response)  # "You are Bob!"
