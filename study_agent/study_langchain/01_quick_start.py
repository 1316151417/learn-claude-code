from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

llm = ChatOpenAI(
    openai_api_base="https://open.bigmodel.cn/api/coding/paas/v4",
    openai_api_key="TODO",
    model="glm-4.7",
)

@tool
def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"{city} 总是阳光明媚!"

agent = create_agent(
    llm,
    tools=[get_weather],
    system_prompt="你是一个有用的助手，在需要的时候使用工具。",
)

# 输入必须是消息列表，不是 dict
result = agent.invoke(
    {"messages": [HumanMessage(content="北京天气怎么样？")]}
)
print(result["messages"][-1].content)