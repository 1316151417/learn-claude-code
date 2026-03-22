import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient  
from langchain.agents import create_agent
from common.llm_config import get_default_llm, get_deepseek_llm, get_zhipu_llm
from common.trace_handler import LLMTraceHandler

async def main():
    client = MultiServerMCPClient(
        {
            "math": {
                "transport": "stdio",  # Local subprocess communication
                "command": "python",
                # Absolute path to your math_server.py file
                "args": ["/Users/zhoujie/IdeaProjects/learn-claude-code/study_agent/study_langchain/04_mcp_server_stdio_math.py"],
            },
            "weather": {
                "transport": "http",  # HTTP-based remote server
                # Ensure you start your weather server on port 8000
                "url": "http://localhost:8000/mcp",
            }
        }
    )

    tools = await client.get_tools()
    
    config = {
        "configurable": {"thread_id": "1"},
        "callbacks": [LLMTraceHandler(show_prompt=True, show_tools=True)]
    }
    agent = create_agent(
        model=get_default_llm(),
        tools=tools
    )
    math_response = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "what's (3 + 5) x 12?"}]},
        config=config
    )
    weather_response = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "what is the weather in nyc?"}]},
        config=config
    )
    print(math_response)
    print(weather_response)

if __name__ == "__main__":
    asyncio.run(main())