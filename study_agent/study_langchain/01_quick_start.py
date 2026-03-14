from dataclasses import dataclass
from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain.agents.structured_output import ToolStrategy
from langgraph.checkpoint.memory import InMemorySaver

llm = ChatOpenAI(
    openai_api_base="https://open.bigmodel.cn/api/coding/paas/v4",
    openai_api_key="",
    model="glm-4.7",
)

checkpointer = InMemorySaver()

@dataclass
class Context:
    """自定义上下文结构"""
    user_name: str

@dataclass
class ResponseFormat:
    """智能体的返回结构"""
    punny_response: str
    weather_conditions: str | None = None

@tool
def get_weather_for_location(city: str) -> str:
    """用于获取某个具体地点的天气"""
    return f"{city} 总是阳光明媚!"

@tool
def get_user_location(runtime: ToolRuntime[Context]):
    """用于获取用户当前所在的位置"""
    user_name = runtime.context.user_name
    return "北京市" if user_name == "周杰" else "四川市"

SYSTEM_PROMPT = """
你是一位资深天气预报专家，说话时喜欢使用双关语（puns）。
你可以使用两个工具：
	•	get_weather_for_location：用于获取某个具体地点的天气
	•	get_user_location：用于获取用户当前所在的位置

如果用户询问天气，你必须先确定具体位置。
如果从问题中可以判断用户指的是他们当前所在的位置，则使用 get_user_location 工具来获取该位置。
"""

config = {"configurable": {"thread_id": "1"}}

agent = create_agent(
    llm,
    system_prompt=SYSTEM_PROMPT,
    tools=[get_user_location, get_weather_for_location],
    context_schema=Context,
    response_format=ToolStrategy(ResponseFormat),
    checkpointer=checkpointer
)

response = agent.invoke(
    {"messages": [HumanMessage(content="天气怎么样？")]},
    config=config,
    context=Context(user_name="杨苗")
)

# print(response['messages'])
print(response['structured_response'])