from dataclasses import dataclass
from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
from langchain_core.messages import HumanMessage
from langchain.agents.structured_output import ToolStrategy
from langgraph.checkpoint.memory import InMemorySaver

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
    return f"用户在 {city}"

@tool
def get_weather_for_city(city: str) -> str:
    """获取城市的天气"""
    return f"{city} 总是阳光明媚!"

SYSTEM_PROMPT = """
角色：你是一位资深天气预报专家，说话时喜欢使用双关语（puns）。
工具：
1. get_user_city 获取用户所在城市
2. get_weather_for_city 获取城市的天气
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

def print_agent_trace(messages):
    for msg in messages:
        cls = msg.__class__.__name__
        content = getattr(msg, "content", None) or ""
        print(f"--- {cls} ---")
        # 内容
        print(f"content: {content.strip()!r}")

        # 如果是 AIMessage，看看 tool_calls
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            for call in tool_calls:
                name = call.get("name")
                args = call.get("args")
                print(f"tool_call -> name: {name}, args: {args}")

        # 如果是 ToolMessage，把 tool结果也显示
        if cls == "ToolMessage":
            name = getattr(msg, "name", None)
            tool_res = getattr(msg, "content", "")
            print(f"tool_result -> tool: {name}, result: {tool_res.strip()!r}")
        print()

print_agent_trace(response['messages'])
print(response['structured_response'])