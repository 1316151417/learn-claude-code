from dataclasses import dataclass
from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.structured_output import ToolStrategy

from trace_handler import LLMTraceHandler
from llm_config import get_default_llm

trace_handler = LLMTraceHandler()

llm = get_default_llm()

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
def get_user_city(runtime: ToolRuntime[Context]):
    """获取用户所在城市"""
    user_name = runtime.context.user_name
    city = "北京市" if user_name == "周杰" else "四川市"
    return city

@tool
def get_weather_for_city(city: str) -> str:
    """获取城市的天气"""
    return f"{city} 总是阳光明媚!"

SYSTEM_PROMPT = """
角色：你是一位资深天气预报专家，说话时喜欢使用双关语（puns）。

工具使用流程：
1. 先调用 get_user_city() 获取用户城市，返回 {"city": "城市名"}
2. 从结果中提取 city 值，调用 get_weather_for_city(city=提取的城市)

示例对话：
用户：天气怎么样？
1. get_user_city → {"city": "四川市"}
2. get_weather_for_city(city="四川市") → "四川市 总是阳光明媚!"

始终严格按顺序调用工具，并正确传递参数。
"""

config = {
    "configurable": {"thread_id": "1"},
    "callbacks": [trace_handler]
}

agent = create_agent(
    llm,
    system_prompt=SYSTEM_PROMPT,
    tools=[get_user_city, get_weather_for_city],
    context_schema=Context,
    # response_format=ToolStrategy(ResponseFormat),
    checkpointer=checkpointer
)

response = agent.invoke(
    {"messages": [HumanMessage(content="天气怎么样？")]},
    config=config,
    context=Context(user_name="杨苗")
)