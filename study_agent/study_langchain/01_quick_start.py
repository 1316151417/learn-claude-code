from langchain.agents import create_agent
from langchain_core.tools import tool, ToolRuntime
from dataclasses import dataclass
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

llm = ChatOpenAI(
    openai_api_base="https://open.bigmodel.cn/api/coding/paas/v4",
    openai_api_key="",
    model="glm-4.7",
)

@dataclass
class Context:
    """Custom runtime context schema."""
    user_id: str

@dataclass
class ResponseFormat:
    """Response schema for the agent."""
    punny_response: str
    weather_conditions: str | None = None

@tool
def get_weather(city: str) -> str:
    """用于获取某个具体地点的天气"""
    return f"{city} 总是阳光明媚!"

@tool
def get_user_location(runtime: ToolRuntime[Context]):
    """用于获取用户当前所在的位置"""
    user_name = runtime.context.user_name
    return "北京" if user_name == "周杰" else "四川"

agent = create_agent(
    llm,
    tools=[get_user_location, get_weather],
    system_prompt="""
你是一位资深天气预报专家，说话时喜欢使用双关语（puns）。
你可以使用两个工具：
	•	get_weather_for_location：用于获取某个具体地点的天气
	•	get_user_location：用于获取用户当前所在的位置

如果用户询问天气，你必须先确定具体位置。
如果从问题中可以判断用户指的是他们当前所在的位置，则使用 get_user_location 工具来获取该位置。
    """,
)

# 输入必须是消息列表，不是 dict
result = agent.invoke(
    {"messages": [HumanMessage(content="天气怎么样？")]},
    context=Context(user_name="杨苗")
)
print(result["structured_response"])