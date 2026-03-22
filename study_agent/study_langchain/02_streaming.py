from langchain.agents import create_agent
from langchain.tools import tool
from langgraph.config import get_stream_writer
from common.llm_config import get_default_llm
from common.stream_visualizer import visualize_stream


@tool
def get_weather_for_city(city: str) -> str:
    """获取城市的天气"""
    writer = get_stream_writer()
    writer("查询中...")
    writer(f"查询结果: {city} 总是阳光明媚!")
    return f"{city} 总是阳光明媚!"

llm = get_default_llm()

agent = create_agent(
    llm,
    system_prompt="你是天气预报专家",
    tools=[get_weather_for_city]
)

# 使用可视化输出
visualize_stream(
    agent,
    input_data={"messages": [{"role": "user", "content": "北京天气怎么样?"}]},
    # stream_mode="updates"
    stream_mode="messages"
    # stream_mode="custom"
)
