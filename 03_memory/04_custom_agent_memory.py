"""
03-4 自定义智能体记忆
学到：自定义 AgentState，添加 checkpointer。
"""
from langchain.agents import create_agent, AgentState
from langgraph.checkpoint.memory import InMemorySaver

from _common import get_llm


class CustomAgentState(AgentState):
    user_id: str
    preferences: dict

def get_user_info() -> str:
    """Look up information about the current user."""
    return "No user profile on file."

agent = create_agent(
    get_llm(),
    tools=[get_user_info],
    state_schema=CustomAgentState,
    checkpointer=InMemorySaver(),
)

# Custom state can be passed in invoke
result = agent.invoke(
    {
        "messages": [{"role": "user", "content": "Hello"}],
        "user_id": "user_123",
        "preferences": {"theme": "dark"}
    },
    {"configurable": {"thread_id": "1"}})

print(result)