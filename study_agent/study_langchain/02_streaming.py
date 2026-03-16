from langchain.agents import create_agent
from langchain.tools import tool
from langgraph.config import get_stream_writer  
from llm_config import get_default_llm, get_deepseek_llm, get_zhipu_llm

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

for chunk in agent.stream(
    {"messages": [{"role": "user", "content": "北京天气怎么样?"}]},
    stream_mode=["updates", "messages", "custom"],
    version="v2",
):
    # 按照Agent进度输出：
    if chunk["type"] == "updates":
        for step, data in chunk["data"].items():
            print(f"step: {step}")
            print(f"content: {data['messages'][-1].content_blocks}")
    
    # 按照LLM token输出：
    if chunk["type"] == "messages":
        token, metadata = chunk["data"]
        print(f"node: {metadata['langgraph_node']}")
        print(f"content: {token.content_blocks}")

    # 按照自定义更新输出：
    if chunk["type"] == "custom":
        print(chunk["data"])