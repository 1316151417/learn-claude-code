import os
from dotenv import load_dotenv
from dataclasses import dataclass
from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.structured_output import ToolStrategy

from langchain_core.callbacks import BaseCallbackHandler
import json

class LLMTraceHandler(BaseCallbackHandler):
    def on_llm_start(self, serialized, prompts, **kwargs):
        print("==========llm start==========")
        for p in prompts:
            for line in p.split("\n"):
                print(line)
    def on_llm_end(self, response, **kwargs):
        print("==========llm end==========")
        gen = response.generations[0][0]
        msg = gen.message
        # LLM文本
        if msg.content:
            print(f"LLM  → {msg.content}")
        # Tool调用
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            for t in tool_calls:
                name = t.get("name")
                args = t.get("args")
                print(f"    LLM  → {name}({args})")
    def on_tool_start(self, serialized, input_str, **kwargs):
        print("==========tool exc==========")
        name = serialized.get("name", "tool")
        print(f"Tool → {name}({input_str})")
    def on_tool_end(self, output, **kwargs):
        print(f"    Tool → {output}")

trace_handler = LLMTraceHandler()

load_dotenv()
api_base = os.getenv("ZHIPU_BASE_URL")
api_key = os.getenv("ZHIPU_API_KEY")

llm = ChatOpenAI(
    openai_api_base=api_base,
    openai_api_key=api_key,
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
def get_user_city(runtime: ToolRuntime[Context]):
    """获取用户所在城市"""
    user_name = runtime.context.user_name
    city = "北京" if user_name == "周杰" else "四川"
    return city

@tool
def get_weather_for_city(city: str) -> str:
    """获取城市的天气"""
    return f"{city} 总是阳光明媚!"

SYSTEM_PROMPT = """
角色：你是一位资深天气预报专家，说话时喜欢使用双关语（puns）。
工具：
1. get_user_city 获取用户所在城市
2. get_weather_for_city 获取城市天气情况 
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
    response_format=ToolStrategy(ResponseFormat),
    checkpointer=checkpointer
)

response = agent.invoke(
    {"messages": [HumanMessage(content="天气怎么样？")]},
    config=config,
    context=Context(user_name="杨苗")
)